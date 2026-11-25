"""Text entities that hold what the action buttons send."""

from __future__ import annotations

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import TEXT_MAX_LENGTH
from .entity import XgimiEntity
from .runtime import XgimiRuntime


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add the command and media text boxes."""
    runtime: XgimiRuntime = entry.runtime_data
    async_add_entities([XgimiCommandText(runtime), XgimiMediaText(runtime)])


class XgimiCommandText(XgimiEntity, TextEntity):
    """Holds the command that the send button forwards to the device."""

    _attr_translation_key = "command"
    _attr_icon = "mdi:console-line"
    _attr_native_max = TEXT_MAX_LENGTH
    _attr_mode = TextMode.TEXT

    def __init__(self, runtime: XgimiRuntime) -> None:
        """Create the command box."""
        super().__init__(runtime, "command")

    @property
    def native_value(self) -> str:
        """Return the text waiting to be sent."""
        return self._runtime.last_command

    async def async_set_value(self, value: str) -> None:
        """Remember ``value`` for the send button."""
        self._runtime.set_last_command(value.strip())
        self.async_write_ha_state()


class XgimiMediaText(XgimiEntity, TextEntity):
    """Holds the URL or path that the play button sends to the device."""

    _attr_translation_key = "media"
    _attr_icon = "mdi:play-box-multiple-outline"
    _attr_native_max = TEXT_MAX_LENGTH
    _attr_mode = TextMode.TEXT

    def __init__(self, runtime: XgimiRuntime) -> None:
        """Create the media box."""
        super().__init__(runtime, "media")

    @property
    def native_value(self) -> str:
        """Return the media waiting to be played."""
        return self._runtime.last_media

    async def async_set_value(self, value: str) -> None:
        """Remember ``value`` for the play button."""
        self._runtime.set_last_media(value.strip())
        self.async_write_ha_state()
