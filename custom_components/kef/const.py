"""Constants for the KEF integration."""

from __future__ import annotations

DOMAIN = "kef"

DEFAULT_PORT = 80
DEFAULT_SCAN_INTERVAL_SECONDS = 10
MIN_SCAN_INTERVAL_SECONDS = 5
MAX_SCAN_INTERVAL_SECONDS = 120

CONF_BACKEND = "backend"
CONF_DEVICE_ID = "device_id"
CONF_ENABLE_DIAGNOSTICS = "enable_diagnostics"
CONF_ENABLE_EQ_SENSORS = "enable_eq_sensors"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_TCP_PORT = "tcp_port"

DEFAULT_ENABLE_DIAGNOSTICS = False
DEFAULT_ENABLE_EQ_SENSORS = True

AIRPLAY_ZEROCONF_TYPE = "_airplay._tcp.local."
DEFAULT_LEGACY_PORT = 50001

API_ROOT = "/api"
GET_DATA_ENDPOINT = "/getData"
GET_ROWS_ENDPOINT = "/getRows"
SET_DATA_ENDPOINT = "/setData"
EVENT_MODIFY_QUEUE_ENDPOINT = "/event/modifyQueue"
EVENT_POLL_QUEUE_ENDPOINT = "/event/pollQueue"

STATE_ON = "powerOn"
STATE_OFF = "standby"

DEFAULT_MODERN_SOURCE_LIST = (
    "wifi",
    "bluetooth",
    "tv",
    "optical",
    "coaxial",
    "analog",
    "usb",
)

MODERN_MODEL_SOURCE_MAP: dict[str, tuple[str, ...]] = {
    "LSX2": ("wifi", "bluetooth", "tv", "optical", "analog", "usb"),
    "LSX2LT": ("wifi", "bluetooth", "tv", "optical", "usb"),
    "LSXII": ("wifi", "bluetooth", "tv", "optical", "analog", "usb"),
    "LS50W2": ("wifi", "bluetooth", "tv", "optical", "coaxial", "analog"),
    "LS50WII": ("wifi", "bluetooth", "tv", "optical", "coaxial", "analog"),
    "LS60": ("wifi", "bluetooth", "tv", "optical", "coaxial", "analog"),
    "XIO": ("wifi", "bluetooth", "tv", "optical"),
}

LEGACY_SOURCE_LIST = (
    "Wifi",
    "Bluetooth",
    "Aux",
    "Opt",
    "Usb",
)

PROBE_PATHS = {
    "device_name": "settings:/deviceName",
    "version": "settings:/version",
    "release_text": "settings:/releasetext",
    "mac": "settings:/system/primaryMacAddress",
    "model_code": "settings:/kef/host/modelName",
    "speaker_status": "settings:/kef/host/speakerStatus",
    "source": "settings:/kef/play/physicalSource",
    "volume": "player:volume",
    "mute": "settings:/mediaPlayer/mute",
    "play_mode": "settings:/mediaPlayer/playMode",
    "player_data": "player:player/data",
    "play_time": "player:player/data/playTime",
    "eq_profile": "kef:eqProfile",
    "network_info": "network:info",
}
