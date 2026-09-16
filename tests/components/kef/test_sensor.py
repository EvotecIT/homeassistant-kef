"""Sensor-platform tests for KEF."""

from __future__ import annotations

from copy import deepcopy
from unittest.mock import patch

import pytest
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import CONF_HOST
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kef.audio import (
    audio_codec_value,
    audio_virtualizer_value,
    format_channels,
)
from custom_components.kef.const import (
    CONF_BACKEND,
    CONF_ENABLE_DIAGNOSTICS,
    DOMAIN,
    model_supports_feature,
)
from custom_components.kef.coordinator import KefCoordinator
from custom_components.kef.sensor import SENSORS
from tests.conftest import TEST_HOST, TEST_SNAPSHOT

EXPECTED_SENSORS = tuple(
    description
    for description in SENSORS
    if model_supports_feature(
        TEST_SNAPSHOT.device.model, description.model_feature
    )
)


@pytest.mark.parametrize(
    ("channel_count", "expected"),
    [
        (None, None),
        (0, None),
        ("0", None),
        ("0.0", None),
        (2, "2.0"),
        ("2", "2.0"),
        ("2.0", "2.0"),
        (6, "5.1"),
        ("6", "5.1"),
        (8, "5.1.2"),
        ("8", "5.1.2"),
        (7, "7"),
    ],
)
def test_format_channels_accepts_numeric_and_wire_string_values(
    channel_count: int | str | None,
    expected: str | None,
) -> None:
    """Channel formatting should tolerate both observed payload shapes."""
    assert format_channels(channel_count) == expected


@pytest.mark.parametrize(
    (
        "codec",
        "stream_channels",
        "audio_channels",
        "expected_codec",
        "expected_virtualizer",
    ),
    [
        ("Dolby PCM - Direct", 6, 2, "PCM 5.1", "Direct 5.1"),
        ("Dolby PCM - Direct", "0", 2, "PCM", "Direct 2.0"),
        (
            "Dolby Digital Plus - Dolby Surround",
            "2",
            2,
            "Dolby Digital Plus 2.0",
            "Dolby Surround 5.1.2",
        ),
        ("PCM", "2.0", 2, "PCM 2.0", "Direct 2.0"),
        (None, None, None, None, None),
    ],
)
def test_audio_sensor_values_decode_codec_and_channel_contract(
    codec: str | None,
    stream_channels: int | str | None,
    audio_channels: int | None,
    expected_codec: str | None,
    expected_virtualizer: str | None,
) -> None:
    """Codec sensors should decode live values without leaking zero channels."""
    snapshot = deepcopy(TEST_SNAPSHOT)
    assert snapshot.playback is not None
    snapshot.playback.codec = codec
    snapshot.playback.stream_channels = stream_channels
    snapshot.playback.audio_channels = audio_channels

    assert audio_codec_value(snapshot) == expected_codec
    assert audio_virtualizer_value(snapshot) == expected_virtualizer


async def _async_publish_test_snapshot(coordinator: KefCoordinator) -> None:
    """Publish the test snapshot instead of contacting a speaker."""
    coordinator.async_set_updated_data(TEST_SNAPSHOT)


async def test_sensor_platform_registers_distinct_names_and_metadata(hass) -> None:
    """Sensors should keep their descriptions and expose useful presentation data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=TEST_SNAPSHOT.device.device_name,
        unique_id=TEST_SNAPSHOT.device.unique_id,
        data={
            CONF_HOST: TEST_HOST,
            CONF_BACKEND: TEST_SNAPSHOT.device.backend,
        },
        options={CONF_ENABLE_DIAGNOSTICS: True},
    )
    entry.add_to_hass(hass)

    with patch.object(
        KefCoordinator,
        "async_config_entry_first_refresh",
        _async_publish_test_snapshot,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    registry = er.async_get(hass)
    sensor_entries = {
        entity_entry.unique_id: entity_entry
        for entity_entry in er.async_entries_for_config_entry(registry, entry.entry_id)
        if entity_entry.domain == "sensor"
    }

    assert len(sensor_entries) == len(EXPECTED_SENSORS)
    assert len(
        {item.entity_id for item in sensor_entries.values()}
    ) == len(EXPECTED_SENSORS)

    for description in EXPECTED_SENSORS:
        unique_id = f"{TEST_SNAPSHOT.device.unique_id}_{description.key}"
        entity_entry = sensor_entries[unique_id]

        assert entity_entry.original_name == description.name
        assert entity_entry.entity_id.startswith("sensor.lsx_ii_test_")
        assert description.device_class is not None or description.icon is not None
        if description.device_class is SensorDeviceClass.ENUM:
            assert description.value_fn(TEST_SNAPSHOT) in description.options

    signal_state = hass.states.get("sensor.lsx_ii_test_wi_fi_signal_level")
    assert signal_state is not None
    assert signal_state.state == "-49"
    assert signal_state.attributes["device_class"] == "signal_strength"
    assert signal_state.attributes["state_class"] == "measurement"
    assert signal_state.attributes["unit_of_measurement"] == "dBm"

    packet_loss_state = hass.states.get(
        "sensor.lsx_ii_test_speed_test_packet_loss"
    )
    assert packet_loss_state is not None
    assert packet_loss_state.attributes["icon"] == (
        "mdi:package-variant-closed-remove"
    )
    assert packet_loss_state.attributes["state_class"] == "measurement"
    assert packet_loss_state.attributes["unit_of_measurement"] == "%"
