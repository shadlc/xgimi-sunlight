"""One-shot action buttons for the XGIMI Sunlight."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import media
from .const import (
    ACTION_CHECK_UPDATE,
    ACTION_EXIT_MUSIC,
    ACTION_LISTEN_MUSIC,
    ACTION_MANUAL_FOCUS,
    ACTION_MUTE,
    ACTION_REBOOT,
    ACTION_SCREEN_OFF,
    APP_MODE,
    APP_TYPE_OPEN,
    CLEAN_MEMORY_MODE,
    CLEAN_MEMORY_TYPE,
    DOMAIN,
    KEY_CODES,
)
from .entity import XgimiEntity
from .protocol import (
    Command,
    ControlCommand,
    InvokeCommand,
    KeyCommand,
    text,
)
from .runtime import XgimiRuntime

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ButtonSpec:
    """Static description of one action button."""

    key: str
    icon: str
    command: Command | None = None
    special: str | None = None


BUTTON_SPECS: tuple[ButtonSpec, ...] = (
    ButtonSpec(
        "key_press",
        "mdi:gesture-tap",
        special="press",
    ),
    ButtonSpec(
        "key_hold",
        "mdi:gesture-tap-hold",
        special="hold",
    ),
    ButtonSpec(
        "open_app",
        "mdi:apps",
        special="open_app",
    ),
    ButtonSpec(
        "send_command",
        "mdi:send",
        special="send_command",
    ),
    ButtonSpec(
        "play_media",
        "mdi:play",
        special="play_media",
    ),
    ButtonSpec(
        "stop_media",
        "mdi:stop",
        special="stop_media",
    ),
    ButtonSpec(
        "auto_focus", "mdi:camera-iris", KeyCommand(code=KEY_CODES["auto_focus"])
    ),
    ButtonSpec("screenshot", "mdi:camera", KeyCommand(code=KEY_CODES["screenshot"])),
    ButtonSpec("settings", "mdi:cog", KeyCommand(code=KEY_CODES["settings"])),
    ButtonSpec("home", "mdi:home", KeyCommand(code=KEY_CODES["home"])),
    ButtonSpec("menu", "mdi:menu", KeyCommand(code=KEY_CODES["menu"])),
    ButtonSpec("back", "mdi:arrow-u-left-top", KeyCommand(code=KEY_CODES["back"])),
    ButtonSpec(
        "power_menu", "mdi:power-settings", KeyCommand(code=KEY_CODES["power_menu"])
    ),
    ButtonSpec("mute", "mdi:volume-off", InvokeCommand(action=ACTION_MUTE)),
    ButtonSpec(
        "screen_off", "mdi:monitor-off", InvokeCommand(action=ACTION_SCREEN_OFF)
    ),
    ButtonSpec(
        "listen_music",
        "mdi:music",
        InvokeCommand(action=ACTION_LISTEN_MUSIC),
    ),
    ButtonSpec(
        "exit_music",
        "mdi:music-off",
        InvokeCommand(action=ACTION_EXIT_MUSIC),
    ),
    ButtonSpec(
        "manual_focus",
        "mdi:focus-field",
        InvokeCommand(action=ACTION_MANUAL_FOCUS),
    ),
    ButtonSpec(
        "clean_memory",
        "mdi:memory",
        ControlCommand(mode=CLEAN_MEMORY_MODE, type=CLEAN_MEMORY_TYPE),
    ),
    ButtonSpec(
        "reboot",
        "mdi:restart",
        InvokeCommand(action=ACTION_REBOOT),
    ),
    ButtonSpec(
        "check_update",
        "mdi:update",
        InvokeCommand(action=ACTION_CHECK_UPDATE),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the action buttons."""
    runtime: XgimiRuntime = entry.runtime_data
    async_add_entities([XgimiButton(runtime, spec) for spec in BUTTON_SPECS])


class XgimiButton(XgimiEntity, ButtonEntity):
    """A stateless action button."""

    def __init__(self, runtime: XgimiRuntime, spec: ButtonSpec) -> None:
        """Create the button for a spec."""
        super().__init__(runtime, spec.key)
        self._spec = spec
        self._attr_translation_key = spec.key
        self._attr_icon = spec.icon

    async def async_press(self) -> None:
        """Fire the configured command, or the armed key for the picker buttons."""

        if self._spec.special is None:
            assert self._spec.command is not None
            await self._async_send(self._spec.command)
            return

        if self._spec.special == "open_app":
            package = self._runtime.selected_app
            if not package:
                raise ServiceValidationError(
                    "Pick an app from the list first.",
                    translation_domain=DOMAIN,
                    translation_key="no_app",
                    translation_placeholders={},
                )
            await self._async_send(
                ControlCommand(mode=APP_MODE, type=APP_TYPE_OPEN, data=package)
            )
            return

        if self._spec.special == "send_command":
            command_text = self._runtime.last_command
            if not command_text:
                raise ServiceValidationError(
                    "Type something in the command field first.",
                    translation_domain=DOMAIN,
                    translation_key="no_command",
                    translation_placeholders={},
                )
            await self._async_send(text(command_text))
            return

        if self._spec.special == "play_media":
            source = self._runtime.last_media
            if not source:
                raise ServiceValidationError(
                    "Type a URL or a path in the media field first.",
                    translation_domain=DOMAIN,
                    translation_key="no_media",
                    translation_placeholders={},
                )
            try:
                await media.async_play(self.hass, self._runtime, source)
            except (ConnectionError, FileNotFoundError, ValueError) as err:
                raise ServiceValidationError(str(err)) from err
            return

        if self._spec.special == "stop_media":
            await media.async_stop(self.hass, self._runtime)
            return

        key_command = KeyCommand(code=KEY_CODES[self._runtime.selected_key])
        if self._spec.special == "press":
            await self._async_send(key_command)
            return

        await self._async_send(key_command, hold=True)
