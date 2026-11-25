"""Constants for the XGIMI Sunlight integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "xgimi_sunlight"

MANUFACTURER: Final = "XGIMI"
MODEL: Final = "XGIMI Sunlight"
DEFAULT_NAME: Final = "XGIMI Sunlight"

CONTROL_PORT: Final = 16750
RESPONSE_PORT: Final = 16751
COMMAND_TIMEOUT: Final = 3.0
DEFAULT_MSGID: Final = "2"

STATE_PORT: Final = 13145
STATE_FRAME_MAGIC: Final = b"\xff\xff\xe0\x4a"
STATE_QUERY_MSGID: Final = "70002"
STATE_CONNECT_TIMEOUT: Final = 5.0
STATE_RETRY_MIN: Final = 5.0
STATE_RETRY_MAX: Final = 60.0
MAX_STATE_FRAME: Final = 4 * 1024 * 1024

ACTION_CONTROL: Final = 20000
ACTION_CONTROL_OK: Final = 20001
ACTION_CONTROL_ERROR: Final = 20002
ACTION_KEY_EVENT: Final = 50036
ACTION_STATE_PUSH: Final = 50023

KEY_EVENT_CLICK: Final = "3"
KEY_EVENT_HOLD: Final = "1"
KEY_EVENT_TYPE: Final = "inst"

TEXT_MODE: Final = 5
DEFAULT_DELAY_TIME: Final = 0
DEFAULT_TIME: Final = 0
DEFAULT_TYPE: Final = 0

CLEAN_MEMORY_MODE: Final = 9
CLEAN_MEMORY_TYPE: Final = 2

STATE_LAMP_SWITCH: Final = "lightSwitch"
STATE_LAMP_MODE: Final = "ceilingLampMode"
STATE_VOLUME: Final = "VOLUME_SYSTEM_UI"
VOLUME_MIN: Final = 0
VOLUME_MAX: Final = 99
STATE_PROJECTOR_SLEEP: Final = "POWER_SLEEP_SYSTEM_UI"
STATE_PROJECTOR_SLEEP_ON: Final = "1"
STATE_VALUE_ON: Final = "1"
STATE_VALUE_OFF: Final = "0"
RESYNC_INTERVAL: Final = 30.0
LIGHT_QUERY_WINDOW: Final = 2.0

LAMP_MODE_CUSTOM: Final = "0"
LAMP_MODE_RHYTHM: Final = "1"
LAMP_MODE_DAYLIGHT: Final = "6"
LAMP_MODE_MOVIE: Final = "10"

KEY_CODES: Final[dict[str, int]] = {
    "left": 1,
    "right": 2,
    "up": 3,
    "down": 4,
    "ok": 5,
    "back": 6,
    "menu": 7,
    "home": 8,
    "volume_up": 9,
    "volume_down": 10,
    "power": 11,
    "settings": 12,
    "auto_focus": 14,
    "screenshot": 120,
    "power_menu": 131,
}

ACTION_POWER_OFF: Final = 50021
ACTION_REBOOT: Final = 50029
ACTION_CHECK_UPDATE: Final = 50030
ACTION_LISTEN_MUSIC: Final = 50004
ACTION_MANUAL_FOCUS: Final = 50008
ACTION_MUTE: Final = 50012
ACTION_SCREEN_OFF: Final = 50015
ACTION_VOLUME: Final = 50009

ACTION_EXIT_MUSIC: Final = 50013

ACTION_LIGHT_PARAM: Final = 50041
ACTION_LIGHT_QUERY: Final = 50040

LIGHT_PARAM_POWER: Final = "0"
LIGHT_PARAM_COLOR_TEMP: Final = "1"
LIGHT_PARAM_BRIGHTNESS: Final = "2"
LIGHT_PARAM_MODE: Final = "3"

LIGHT_QUERY_ORDER: Final[tuple[str, ...]] = (
    LIGHT_PARAM_POWER,
    LIGHT_PARAM_BRIGHTNESS,
    LIGHT_PARAM_COLOR_TEMP,
    LIGHT_PARAM_MODE,
)

STATE_LAMP_BRIGHTNESS: Final = "lightBrightness"
STATE_LAMP_COLOR_TEMP: Final = "lightColorTemp"

BRIGHTNESS_MIN: Final = 1
BRIGHTNESS_MAX: Final = 10
COLOUR_TEMP_MIN: Final = 1
COLOUR_TEMP_MAX: Final = 10
COLOR_TEMP_MIN_KELVIN: Final = 2700
COLOR_TEMP_MAX_KELVIN: Final = 6500

PROJECTOR_ON_TIMEOUT: Final = 20.0
PROJECTOR_ON_POLL: Final = 0.5
HA_BRIGHTNESS_MAX: Final = 255

CONF_HOST: Final = "host"
CONF_NAME: Final = "name"
CONF_LIGHT_SHAPE: Final = "light_shape"
CONF_DEFAULT_LAMP_MODE: Final = "default_lamp_mode"
CONF_HOLD_RESPONSE_PORT: Final = "hold_response_port"

LIGHT_SHAPE_SPLIT: Final = "split"
LIGHT_SHAPE_SINGLE: Final = "single"
LIGHT_SHAPES: Final[tuple[str, ...]] = (LIGHT_SHAPE_SPLIT, LIGHT_SHAPE_SINGLE)
DEFAULT_LIGHT_SHAPE: Final = LIGHT_SHAPE_SPLIT

LAMP_MODES: Final[tuple[str, ...]] = (
    LAMP_MODE_CUSTOM,
    LAMP_MODE_RHYTHM,
    LAMP_MODE_DAYLIGHT,
    LAMP_MODE_MOVIE,
)
DEFAULT_LAMP_MODE: Final = LAMP_MODE_DAYLIGHT

LAMP_MODE_TO_UNIQUE: Final[dict[str, str]] = {
    LAMP_MODE_CUSTOM: "lamp_custom",
    LAMP_MODE_RHYTHM: "lamp_rhythm",
    LAMP_MODE_DAYLIGHT: "lamp_daylight",
    LAMP_MODE_MOVIE: "lamp_movie",
}

SERVICE_SEND_COMMAND: Final = "send_command"
SERVICE_PRESS_KEY: Final = "press_key"
ATTR_COMMAND: Final = "command"
ATTR_KEY: Final = "key"
ATTR_HOLD_SECS: Final = "hold_secs"
ATTR_NUM_REPEATS: Final = "num_repeats"
ATTR_DELAY_SECS: Final = "delay_secs"
ATTR_WAIT_RESPONSE: Final = "wait_response"

DEFAULT_NUM_REPEATS: Final = 1
DEFAULT_DELAY_SECS: Final = 0.4

LAMP_MODE_LABEL: Final[dict[str, str]] = {
    LAMP_MODE_CUSTOM: "Custom",
    LAMP_MODE_RHYTHM: "Rhythm",
    LAMP_MODE_DAYLIGHT: "Daylight",
    LAMP_MODE_MOVIE: "Movie",
}

LAMP_LABEL_TO_MODE: Final[dict[str, str]] = {
    label: mode for mode, label in LAMP_MODE_LABEL.items()
}

KEY_LABELS: Final[dict[str, str]] = {
    "up": "Up",
    "down": "Down",
    "left": "Left",
    "right": "Right",
    "ok": "OK",
    "back": "Back",
    "home": "Home",
    "menu": "Menu",
    "volume_up": "Volume +",
    "volume_down": "Volume -",
    "power": "Power (toggle)",
    "settings": "Settings",
    "auto_focus": "Auto focus",
    "screenshot": "Screenshot",
    "power_menu": "Power menu",
}

KEY_LABEL_TO_CODE: Final[dict[str, str]] = {
    label: key for key, label in KEY_LABELS.items()
}

DEFAULT_SELECTED_KEY: Final = "ok"

LAMP_WRITE_DEBOUNCE: Final = 0.4

DLNA_PORT: Final = 1414
DLNA_AVTRANSPORT: Final = "urn:schemas-upnp-org:service:AVTransport:1"
DLNA_TIMEOUT: Final = 8.0
DLNA_CACHE_TTL: Final = 900.0

SSDP_PORT: Final = 1900
SSDP_TIMEOUT: Final = 3.0
SSDP_SEARCH_TARGET: Final = "urn:schemas-upnp-org:device:MediaRenderer:1"

SERVICE_PLAY_MEDIA: Final = "play_media"
SERVICE_STOP_MEDIA: Final = "stop_media"
ATTR_URL: Final = "url"
ATTR_PATH: Final = "path"

MEDIA_KIND_IMAGE: Final = "image"
MEDIA_KIND_VIDEO: Final = "video"
MEDIA_KIND_AUDIO: Final = "audio"

MEDIA_EXTENSIONS: Final = {
    ".jpg": MEDIA_KIND_IMAGE,
    ".jpeg": MEDIA_KIND_IMAGE,
    ".png": MEDIA_KIND_IMAGE,
    ".gif": MEDIA_KIND_IMAGE,
    ".webp": MEDIA_KIND_IMAGE,
    ".bmp": MEDIA_KIND_IMAGE,
    ".mp4": MEDIA_KIND_VIDEO,
    ".m4v": MEDIA_KIND_VIDEO,
    ".mkv": MEDIA_KIND_VIDEO,
    ".webm": MEDIA_KIND_VIDEO,
    ".mov": MEDIA_KIND_VIDEO,
    ".avi": MEDIA_KIND_VIDEO,
    ".mp3": MEDIA_KIND_AUDIO,
    ".m4a": MEDIA_KIND_AUDIO,
    ".flac": MEDIA_KIND_AUDIO,
    ".aac": MEDIA_KIND_AUDIO,
    ".wav": MEDIA_KIND_AUDIO,
}

MEDIA_CLASSES: Final = {
    MEDIA_KIND_IMAGE: "object.item.imageItem.photo",
    MEDIA_KIND_VIDEO: "object.item.videoItem",
    MEDIA_KIND_AUDIO: "object.item.audioItem.musicTrack",
}

MEDIA_MIME_TYPES: Final = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".mkv": "video/x-matroska",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
    ".avi": "video/x-msvideo",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".flac": "audio/flac",
    ".aac": "audio/aac",
    ".wav": "audio/wav",
}

TEXT_MAX_LENGTH: Final = 255

SCREENSHOT_MODE: Final = 9
SCREENSHOT_TYPE: Final = 1
ACTION_SCREENSHOT_REPLY: Final = 30235
SCREENSHOT_TIMEOUT: Final = 10.0
SCREEN_FILE: Final = "xgimi_screen.jpg"
SERVICE_SCREENSHOT: Final = "screenshot"

APP_MODE: Final = 7
APP_TYPE_LIST: Final = 3
APP_TYPE_OPEN: Final = 1
ACTION_APP_LIST_REPLY: Final = 30236
APP_TIMEOUT: Final = 10.0
SERVICE_OPEN_APP: Final = "open_app"
ATTR_PACKAGE: Final = "package"
ATTR_APP: Final = "app"
