"""Legacy controls preserve volume and speaker settings on the binary wire."""

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.kef.kef_client.client import LegacyBinaryClient
from custom_components.kef.kef_client.exceptions import (
    KefResponseError,
    KefUnsupportedDeviceError,
)
from tests.test_legacy_transport import legacy_server

pytestmark = pytest.mark.usefixtures("socket_enabled")


@pytest.mark.parametrize(
    ("volume", "muted", "expected"),
    [(42, True, 170), (170, False, 42), (0, True, 128), (128, False, 0),
     (170, True, 170), (42, False, 42)],
)
async def test_mute_preserves_volume_and_uses_the_mute_bit(volume, muted, expected):
    """Mute toggles the high bit without changing the stored volume."""
    async def handler(reader, writer):
        command = received[-1]
        if command[0] == ord("G"):
            writer.write(bytes([82, command[1], 129, volume, 255]))
        else:
            writer.write(b"R\x11\xff")
        await writer.drain()
        assert await reader.read() == b""

    async with legacy_server(handler, command_length=None) as (
        port, received, disconnected
    ):
        await LegacyBinaryClient("127.0.0.1", port=port).async_set_muted(muted)
        assert received == [b"G%\x80", bytes([83, 37, 129, expected])]


@pytest.mark.parametrize(
    ("current", "action", "expected_codes", "options"),
    [(226, "source", [107], {}), (226, "on", [98], {}),
     (98, "off", [226], {}), (66, "off", [82, 210], {}), (194, "off", [], {}),
     (98, "source", [75], {"standby_time": 20}),
     (98, "source", [91], {"standby_time": 60}),
     (82, "source", [107], {"standby_time": None}),
     (66, "off", [82, 210], {"standby_time": 60}),
     (66, "off", [82, 226], {"standby_time": None}),
     (98, "off", [82, 210], {"standby_time": 20})],
)
async def test_source_and_power_preserve_settings(
    current, action, expected_codes, options,
):
    """Keep R/L and standby bits, including the safe power-off sequence."""
    async def handler(reader, writer):
        command = received[-1]
        if command[0] == ord("G"):
            writer.write(bytes([82, command[1], 129, current, 255]))
        else:
            writer.write(b"R\x11\xff")
        await writer.drain()
        assert await reader.read() == b""

    async with legacy_server(handler, command_length=None) as (
        port, received, disconnected
    ):
        client = LegacyBinaryClient("127.0.0.1", port=port, **options)
        if action == "source":
            await client.async_select_source("Opt")
        elif action == "on":
            await client.async_turn_on()
        else:
            await client.async_turn_off()
        assert received == [b"G0\x80"] + [
            bytes([83, 48, 129, code]) for code in expected_codes
        ]


@pytest.mark.parametrize("action", ["mute", "source"])
async def test_unknown_settings_prevent_control_writes(action):
    """Do not write a guessed volume or source after an unknown state reply."""
    async def handler(reader, writer):
        command = received[-1]
        writer.write(bytes([82, command[1], 129, 255, 255]))
        await writer.drain()
        assert await reader.read() == b""

    async with legacy_server(handler, command_length=None) as (
        port, received, disconnected
    ):
        client = LegacyBinaryClient("127.0.0.1", port=port)
        with pytest.raises(KefResponseError):
            if action == "mute":
                await client.async_set_muted(True)
            else:
                await client.async_select_source("Opt")
        assert received == [b"G%\x80" if action == "mute" else b"G0\x80"]


@pytest.mark.parametrize(
    ("operation", "arguments"),
    [
        ("async_set_standby_mode", ("standby_20mins",)),
        ("async_set_startup_tone_enabled", (True,)),
        ("async_set_auto_switch_hdmi_enabled", (True,)),
        ("async_set_front_led_enabled", (True,)),
        ("async_set_standby_led_enabled", (True,)),
        ("async_set_top_panel_enabled", (True,)),
        ("async_set_top_panel_led_enabled", (True,)),
        ("async_set_top_panel_standby_led_enabled", (True,)),
        ("async_set_wake_source", ("optical",)),
        ("async_set_subwoofer_wake_enabled", (True,)),
        ("async_set_kw1_wake_enabled", (True,)),
        ("async_set_usb_charging_enabled", (True,)),
        ("async_set_startup_volume_enabled", (True,)),
        ("async_set_per_input_startup_volume_enabled", (True,)),
        ("async_set_default_volume_global", (35,)),
        ("async_set_maximum_volume", (80,)),
        ("async_set_volume_step", (3,)),
        ("async_set_volume_limit_enabled", (True,)),
        ("async_set_default_volume_for_source", ("optical", 35)),
        ("async_set_cable_mode", ("wireless",)),
        ("async_set_balance", (0,)),
        ("async_set_bass_extension", ("standard",)),
        ("async_set_treble_amount", (0.5,)),
        ("async_set_subwoofer_gain", (0,)),
        ("async_set_sub_out_low_pass_frequency", (80.0,)),
        ("async_set_subwoofer_enabled", (True,)),
        ("async_set_kw1_enabled", (True,)),
        ("async_set_subwoofer_polarity", ("normal",)),
        ("async_set_audio_polarity", ("normal",)),
        ("async_set_subwoofer_preset", ("manual", "LS50W2")),
        ("async_set_sub_enable_stereo", (True,)),
        ("async_set_sound_profile", ("music",)),
        ("async_set_wall_mounted", (True,)),
        ("async_set_auto_detect_placement", (True,)),
        ("async_set_prefer_virtual_x", (True,)),
        ("async_start_calibration", ()),
        ("async_set_desk_mode_enabled", (True,)),
        ("async_set_desk_mode_db", (-3.0,)),
        ("async_set_wall_mode_enabled", (True,)),
        ("async_set_wall_mode_db", (-3.0,)),
        ("async_set_phase_correction_enabled", (True,)),
        ("async_set_high_pass_mode_enabled", (True,)),
        ("async_set_high_pass_frequency", (80.0,)),
        ("async_set_master_channel", ("left",)),
        ("async_set_fixed_volume_level", (35,)),
        ("async_set_remote_ir_enabled", (True,)),
        ("async_set_remote_ir_code", ("ir_code_set_b",)),
        ("async_set_favourite_button_action", ("next",)),
        ("async_set_eq_button_action", (1, "next")),
        ("async_set_analytics_enabled", (True,)),
        ("async_set_app_analytics_enabled", (True,)),
        ("async_set_streaming_quality", ("256",)),
        ("async_set_ui_language", ("en_GB",)),
        ("async_set_speaker_location", ("GB",)),
        ("async_get_firmware_update_status", ()),
        ("async_check_for_firmware_update", ()),
        ("async_install_firmware_update", ()),
        ("async_upload_firmware_update", ("not-device-firmware.bin",)),
    ],
    ids=lambda value: value if isinstance(value, str) else None,
)
async def test_unsupported_modern_control_never_opens_legacy_transport(
    operation, arguments,
):
    """Every unsupported public control fails before contacting an old speaker."""
    client = LegacyBinaryClient("127.0.0.1")
    with patch("asyncio.open_connection", new_callable=AsyncMock) as connect:
        with pytest.raises(KefUnsupportedDeviceError):
            await getattr(client, operation)(*arguments)
        connect.assert_not_called()


async def test_legacy_optional_queries_remain_unknown_without_tcp():
    """An old speaker has no calibration data or event queue to contact."""
    client = LegacyBinaryClient("127.0.0.1")
    with patch("asyncio.open_connection", new_callable=AsyncMock) as connect:
        assert await client.async_get_calibration_status() is None
        assert await client.async_get_calibration_result() is None
        assert await client.async_poll_events(timeout=1) == []
        assert await client.async_reset_event_queue() is None
        connect.assert_not_called()
