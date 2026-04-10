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
CONF_SCAN_INTERVAL = "scan_interval"
CONF_TCP_PORT = "tcp_port"

DEFAULT_ENABLE_DIAGNOSTICS = False

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

STANDBY_MODE_OPTIONS = {
    "standby_none": "Never",
    "standby_20mins": "20 minutes",
    "standby_30mins": "30 minutes",
    "standby_60mins": "60 minutes",
}

WAKE_SOURCE_OPTIONS = {
    "wakeup_default": "Default",
    "wifi": "Wi-Fi",
    "bluetooth": "Bluetooth",
    "usb": "USB",
    "optical": "Optical",
    "tv": "TV",
}

BASS_EXTENSION_OPTIONS = {
    "less": "Less",
    "standard": "Standard",
    "extra": "Extra",
}

MASTER_CHANNEL_OPTIONS = {
    "left": "Left",
    "right": "Right",
}

DEFAULT_VOLUME_SOURCE_SUFFIX = {
    "wifi": "Wifi",
    "bluetooth": "Bluetooth",
    "optical": "Optical",
    "coaxial": "Coaxial",
    "usb": "USB",
    "analog": "Analogue",
    "tv": "TV",
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
    "cable_mode": "settings:/kef/host/cableMode",
    "master_channel": "settings:/kef/host/masterChannelMode",
    "volume": "player:volume",
    "mute": "settings:/mediaPlayer/mute",
    "play_mode": "settings:/mediaPlayer/playMode",
    "player_data": "player:player/data",
    "play_time": "player:player/data/playTime",
    "eq_profile": "kef:eqProfile",
    "network_info": "network:info",
    "standby_mode": "settings:/kef/host/standbyMode",
    "startup_tone": "settings:/kef/host/startupTone",
    "auto_switch_hdmi": "settings:/kef/host/autoSwitchToHDMI",
    "disable_front_led": "settings:/kef/host/disableFrontLED",
    "disable_front_standby_led": "settings:/kef/host/disableFrontStandbyLED",
    "disable_top_panel": "settings:/kef/host/disableTopPanel",
    "wake_up_source": "settings:/kef/host/wakeUpSource",
    "subwoofer_force_on": "settings:/kef/host/subwooferForceOn",
    "subwoofer_force_on_kw1": "settings:/kef/host/subwooferForceOnKW1",
    "usb_charging": "settings:/kef/host/usbCharging",
    "startup_volume_enabled": "settings:/kef/host/standbyDefaultVol",
    "per_input_startup_volume_enabled": "settings:/kef/host/advancedStandbyDefaultVol",
    "default_volume_global": "settings:/kef/host/defaultVolumeGlobal",
    "maximum_volume": "settings:/kef/host/maximumVolume",
    "volume_step": "settings:/kef/host/volumeStep",
    "volume_limit": "settings:/kef/host/volumeLimit",
    "fixed_volume_level": "settings:/kef/host/remote/userFixedVolume",
}
