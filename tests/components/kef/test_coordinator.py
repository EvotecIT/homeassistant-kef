"""Coordinator tests for KEF."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kef.const import (
    CONF_BACKEND,
    CONF_DEVICE_ID,
    CONF_OFFLINE_RETRY_INTERVAL,
    CONF_SCAN_INTERVAL,
    CONF_TCP_PORT,
    DEFAULT_OFFLINE_RETRY_INTERVAL_SECONDS,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DOMAIN,
)
from custom_components.kef.coordinator import KefCoordinator
from custom_components.kef.exceptions import KefAuthenticationRequiredError, KefError
from custom_components.kef.models import KefBackend
from tests.conftest import TEST_HOST, TEST_PORT, TEST_SNAPSHOT


async def test_legacy_address_change_preserves_entity_identity(hass) -> None:
    """A new legacy IP must not create a second set of Home Assistant entities."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.0.2.12",
            CONF_BACKEND: KefBackend.LEGACY.value,
            CONF_DEVICE_ID: "kef-legacy-192.0.2.11",
        },
        title="KEF",
    )
    coordinator = KefCoordinator(hass, entry)
    snapshot = replace(
        TEST_SNAPSHOT,
        device=replace(
            TEST_SNAPSHOT.device,
            backend=KefBackend.LEGACY,
            host="192.0.2.12",
            unique_id="kef-legacy-192.0.2.12",
        ),
    )
    coordinator.client = SimpleNamespace(async_refresh=AsyncMock(return_value=snapshot))

    result = await coordinator._async_update_data()

    assert result.device.unique_id == "kef-legacy-192.0.2.11"
    assert result.device.host == "192.0.2.12"


@pytest.mark.asyncio
async def test_event_listener_requests_refresh_on_events(hass) -> None:
    """Modern event-queue updates should trigger a coordinator refresh."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": TEST_HOST,
            "port": TEST_PORT,
            CONF_TCP_PORT: 50001,
            CONF_BACKEND: "modern",
        },
        title="KEF",
    )
    coordinator = KefCoordinator(hass, entry)
    coordinator.async_request_refresh = AsyncMock()

    class _FakeModernClient:
        backend = KefBackend.MODERN

        def __init__(self) -> None:
            self.async_poll_events = AsyncMock(
                side_effect=[
                    [
                        {
                            "path": "player:volume",
                            "itemValue": {"type": "i32_", "i32_": 79},
                        }
                    ],
                    asyncio.CancelledError(),
                ]
            )
            self.async_reset_event_queue = AsyncMock()

    coordinator.client = _FakeModernClient()

    with pytest.raises(asyncio.CancelledError):
        await coordinator._async_event_listener_loop()

    coordinator.async_request_refresh.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_event_listener_falls_back_after_device_error(monkeypatch, hass) -> None:
    """Event queue failures should reset local state and retain polling fallback."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": TEST_HOST,
            "port": TEST_PORT,
            CONF_TCP_PORT: 50001,
            CONF_BACKEND: "modern",
        },
        title="KEF",
    )
    coordinator = KefCoordinator(hass, entry)

    class _FakeModernClient:
        backend = KefBackend.MODERN
        async_poll_events = AsyncMock(side_effect=KefError("offline"))
        async_reset_event_queue = AsyncMock()

    coordinator.client = _FakeModernClient()

    async def cancel_after_fallback(delay: float) -> None:
        assert delay == 5
        raise asyncio.CancelledError

    with monkeypatch.context() as patch_context:
        patch_context.setattr(
            "custom_components.kef.coordinator.asyncio.sleep",
            cancel_after_fallback,
        )
        with pytest.raises(asyncio.CancelledError):
            await coordinator._async_event_listener_loop()

    coordinator.client.async_reset_event_queue.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_stop_event_listener_cancels_and_clears_queue(hass) -> None:
    """Unloading should cancel the listener and clear its local queue state."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": TEST_HOST,
            "port": TEST_PORT,
            CONF_TCP_PORT: 50001,
            CONF_BACKEND: "modern",
        },
        title="KEF",
    )
    coordinator = KefCoordinator(hass, entry)

    class _FakeModernClient:
        backend = KefBackend.MODERN
        async_reset_event_queue = AsyncMock()

    coordinator.client = _FakeModernClient()
    listener_task = asyncio.create_task(asyncio.Event().wait())
    coordinator._event_listener_task = listener_task

    await coordinator.async_stop_event_listener()

    assert listener_task.cancelled()
    assert coordinator._event_listener_task is None
    coordinator.client.async_reset_event_queue.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_update_data_raises_config_entry_auth_failed(hass) -> None:
    """Authentication failures should trigger Home Assistant reauth."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": TEST_HOST,
            "port": TEST_PORT,
            CONF_TCP_PORT: 50001,
            CONF_BACKEND: "modern",
        },
        title="KEF",
    )
    coordinator = KefCoordinator(hass, entry)
    coordinator.client = AsyncMock()
    coordinator.client.async_refresh.side_effect = KefAuthenticationRequiredError(
        "password required"
    )

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_apply_local_change_publishes_updated_snapshot(hass) -> None:
    """A local change should replace the snapshot and notify listeners."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": TEST_HOST,
            "port": TEST_PORT,
            CONF_TCP_PORT: 50001,
            CONF_BACKEND: "modern",
        },
        title="KEF",
    )
    coordinator = KefCoordinator(hass, entry)
    coordinator.data = replace(TEST_SNAPSHOT, volume_raw=40, volume_level=0.40)
    updates: list[int | None] = []
    coordinator.async_add_listener(lambda: updates.append(coordinator.data.volume_raw))

    coordinator.async_apply_local_change(volume_raw=44, volume_level=0.44)

    assert coordinator.data.volume_raw == 44
    assert coordinator.data.volume_level == 0.44
    assert updates == [44]


@pytest.mark.asyncio
async def test_apply_local_change_is_a_no_op_before_first_refresh(hass) -> None:
    """No snapshot yet means nothing to patch."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": TEST_HOST,
            "port": TEST_PORT,
            CONF_TCP_PORT: 50001,
            CONF_BACKEND: "modern",
        },
        title="KEF",
    )
    coordinator = KefCoordinator(hass, entry)

    coordinator.async_apply_local_change(volume_raw=44)

    assert coordinator.data is None


def _coordinator(hass) -> KefCoordinator:
    """Build a coordinator against a throwaway config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": TEST_HOST,
            "port": TEST_PORT,
            CONF_TCP_PORT: 50001,
            CONF_BACKEND: "modern",
        },
        title="KEF",
    )
    return KefCoordinator(hass, entry)


@pytest.mark.asyncio
async def test_local_change_survives_a_read_that_started_before_it(hass) -> None:
    """An in-flight read is stale for a field written during it; keep the write."""
    coordinator = _coordinator(hass)
    coordinator.data = replace(TEST_SNAPSHOT, volume_raw=40, volume_level=0.40)
    reading = asyncio.Event()
    finish = asyncio.Event()

    async def _slow_refresh():
        reading.set()
        await finish.wait()
        # captured before the write below
        return replace(TEST_SNAPSHOT, volume_raw=40, volume_level=0.40)

    coordinator.client = SimpleNamespace(async_refresh=_slow_refresh)
    task = asyncio.create_task(coordinator._async_update_data())
    await reading.wait()
    coordinator.async_apply_local_change(volume_raw=44, volume_level=0.44)
    finish.set()

    snapshot = await task
    assert snapshot.volume_raw == 44
    assert snapshot.volume_level == 0.44


@pytest.mark.asyncio
async def test_local_change_survives_one_stale_post_write_read(hass) -> None:
    """An immediate stale refresh should not undo an acknowledged write."""
    coordinator = _coordinator(hass)
    coordinator.data = replace(TEST_SNAPSHOT, volume_raw=40, volume_level=0.40)
    coordinator.async_apply_local_change(volume_raw=44, volume_level=0.44)
    snapshots = iter(
        [
            replace(TEST_SNAPSHOT, volume_raw=40, volume_level=0.40),
            replace(TEST_SNAPSHOT, volume_raw=60, volume_level=0.60),
        ]
    )

    async def _refresh():
        return next(snapshots)

    coordinator.client = SimpleNamespace(async_refresh=_refresh)

    snapshot = await coordinator._async_update_data()
    assert snapshot.volume_raw == 44
    assert coordinator._local_changes == {"volume_raw": 44, "volume_level": 0.44}

    snapshot = await coordinator._async_update_data()
    assert snapshot.volume_raw == 60
    assert coordinator._local_changes == {}


@pytest.mark.asyncio
async def test_matching_post_write_read_settles_local_change(hass) -> None:
    """A device response matching the write should settle without a grace wait."""
    coordinator = _coordinator(hass)
    coordinator.data = replace(TEST_SNAPSHOT, volume_raw=40, volume_level=0.40)
    coordinator.async_apply_local_change(volume_raw=44, volume_level=0.44)

    async def _refresh():
        return replace(TEST_SNAPSHOT, volume_raw=44, volume_level=0.44)

    coordinator.client = SimpleNamespace(async_refresh=_refresh)

    snapshot = await coordinator._async_update_data()
    assert snapshot.volume_raw == 44
    assert coordinator._local_changes == {}


@pytest.mark.asyncio
async def test_nested_eq_change_survives_immediate_stale_refresh(hass) -> None:
    """The post-write grace cycle should also preserve nested EQ snapshots."""
    coordinator = _coordinator(hass)
    coordinator.data = TEST_SNAPSHOT
    assert TEST_SNAPSHOT.eq_profile is not None
    updated_profile = replace(
        TEST_SNAPSHOT.eq_profile,
        subwoofer_preset="kc62",
        subwoofer_gain=-1,
    )
    coordinator.async_apply_local_change(eq_profile=updated_profile)

    async def _refresh():
        return TEST_SNAPSHOT

    coordinator.client = SimpleNamespace(async_refresh=_refresh)

    snapshot = await coordinator._async_update_data()
    assert snapshot.eq_profile == updated_profile
    assert snapshot.eq_profile.subwoofer_preset == "kc62"
    assert coordinator._local_changes == {"eq_profile": updated_profile}


@pytest.mark.asyncio
async def test_successful_refresh_records_when_device_data_was_fetched(
    monkeypatch, hass
) -> None:
    """Media position timestamps should represent the successful device refresh."""
    coordinator = _coordinator(hass)
    coordinator.client = SimpleNamespace(
        async_refresh=AsyncMock(return_value=TEST_SNAPSHOT)
    )
    refreshed_at = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(
        "custom_components.kef.coordinator.dt_util.utcnow",
        lambda: refreshed_at,
    )

    await coordinator._async_update_data()

    assert coordinator.last_device_update_at == refreshed_at


async def test_client_creation_failure_is_an_update_failure(monkeypatch, hass) -> None:
    """An unreachable speaker at startup must not log an unexpected traceback."""
    coordinator = _coordinator(hass)
    monkeypatch.setattr(
        "custom_components.kef.coordinator.async_create_client",
        AsyncMock(side_effect=KefError("Cannot connect")),
    )

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    assert coordinator.client is None


async def test_brief_failures_keep_last_snapshot_then_go_offline(hass) -> None:
    """Two failed polls keep the last state; the third marks the speaker offline."""
    coordinator = _coordinator(hass)
    coordinator.data = TEST_SNAPSHOT
    coordinator.client = SimpleNamespace(
        async_refresh=AsyncMock(side_effect=KefError("timeout"))
    )

    assert await coordinator._async_update_data() is TEST_SNAPSHOT
    assert await coordinator._async_update_data() is TEST_SNAPSHOT
    assert not coordinator.is_offline
    assert coordinator.update_interval == timedelta(
        seconds=DEFAULT_SCAN_INTERVAL_SECONDS
    )

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    assert coordinator.is_offline
    assert coordinator.update_interval == timedelta(
        seconds=DEFAULT_OFFLINE_RETRY_INTERVAL_SECONDS
    )


async def test_offline_retry_interval_follows_the_option(hass) -> None:
    """The slower offline retry uses the configured interval."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": TEST_HOST, "port": TEST_PORT, CONF_BACKEND: "modern"},
        options={CONF_SCAN_INTERVAL: 15, CONF_OFFLINE_RETRY_INTERVAL: 300},
        title="KEF",
    )
    coordinator = KefCoordinator(hass, entry)
    coordinator.data = TEST_SNAPSHOT
    coordinator.client = SimpleNamespace(
        async_refresh=AsyncMock(side_effect=KefError("timeout"))
    )

    for _ in range(2):
        await coordinator._async_update_data()
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    assert coordinator.update_interval == timedelta(seconds=300)


async def test_recovery_restores_the_normal_polling_interval(hass) -> None:
    """A successful poll after going offline returns to normal polling."""
    coordinator = _coordinator(hass)
    coordinator.data = TEST_SNAPSHOT
    coordinator.client = SimpleNamespace(
        async_refresh=AsyncMock(
            side_effect=[KefError("a"), KefError("b"), KefError("c"), TEST_SNAPSHOT]
        )
    )
    for _ in range(2):
        await coordinator._async_update_data()
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    await coordinator._async_update_data()

    assert not coordinator.is_offline
    assert coordinator.update_interval == timedelta(
        seconds=DEFAULT_SCAN_INTERVAL_SECONDS
    )


async def test_failure_count_resets_after_a_successful_poll(hass) -> None:
    """Only consecutive failures count towards going offline."""
    coordinator = _coordinator(hass)
    coordinator.data = TEST_SNAPSHOT
    coordinator.client = SimpleNamespace(
        async_refresh=AsyncMock(
            side_effect=[KefError("a"), KefError("b"), TEST_SNAPSHOT, KefError("c")]
        )
    )

    for _ in range(4):
        await coordinator._async_update_data()

    assert not coordinator.is_offline


async def test_auth_failure_is_never_tolerated(hass) -> None:
    """A password problem must reach reauth even while a snapshot exists."""
    coordinator = _coordinator(hass)
    coordinator.data = TEST_SNAPSHOT
    coordinator.client = SimpleNamespace(
        async_refresh=AsyncMock(
            side_effect=KefAuthenticationRequiredError("password required")
        )
    )

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_event_listener_waits_while_offline(monkeypatch, hass) -> None:
    """An offline speaker's event queue waits for polling instead of retrying."""
    coordinator = _coordinator(hass)
    coordinator._online.clear()
    reset_done = asyncio.Event()

    class _FakeModernClient:
        backend = KefBackend.MODERN
        async_poll_events = AsyncMock(
            side_effect=[KefError("offline"), asyncio.CancelledError]
        )
        async_reset_event_queue = AsyncMock(side_effect=reset_done.set)

    coordinator.client = _FakeModernClient()
    real_sleep = asyncio.sleep
    retry_delays: list[float] = []

    async def no_retry_sleep(delay: float, *args, **kwargs) -> None:
        if delay:
            retry_delays.append(delay)
        await real_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", no_retry_sleep)
    task = asyncio.create_task(coordinator._async_event_listener_loop())
    await reset_done.wait()
    await real_sleep(0)

    assert not task.done()
    assert coordinator.client.async_poll_events.await_count == 1

    coordinator._handle_refresh_success()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert coordinator.client.async_poll_events.await_count == 2
    assert retry_delays == []


async def test_device_seen_refreshes_an_offline_speaker(hass) -> None:
    """A discovery announcement retries an offline speaker right away."""
    coordinator = _coordinator(hass)
    coordinator.config_entry.add_to_hass(hass)
    coordinator.async_request_refresh = AsyncMock()
    coordinator._online.clear()

    coordinator.async_device_seen()
    await hass.async_block_till_done()

    coordinator.async_request_refresh.assert_awaited_once_with()


async def test_device_seen_ignores_an_online_speaker(hass) -> None:
    """Routine announcements from a reachable speaker do not add polls."""
    coordinator = _coordinator(hass)
    coordinator.config_entry.add_to_hass(hass)
    coordinator.async_request_refresh = AsyncMock()

    coordinator.async_device_seen()
    await hass.async_block_till_done()

    coordinator.async_request_refresh.assert_not_awaited()
