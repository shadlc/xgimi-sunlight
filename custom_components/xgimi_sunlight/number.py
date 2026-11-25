"""Volume number entity for the XGIMI Sunlight."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import VOLUME_MAX, VOLUME_MIN
from .entity import XgimiEntity
from .protocol import XgimiError
from .runtime import XgimiRuntime


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add the projector volume slider."""
    runtime: XgimiRuntime = entry.runtime_data
    async_add_entities([XgimiVolume(runtime)])


class XgimiVolume(XgimiEntity, NumberEntity):
    """Absolute projector volume."""

    _attr_translation_key = "volume"
    _attr_icon = "mdi:volume-high"
    _attr_native_min_value = VOLUME_MIN
    _attr_native_max_value = VOLUME_MAX
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(self, runtime: XgimiRuntime) -> None:
        """Create the volume slider."""
        super().__init__(runtime, "volume")

    @property
    def native_value(self) -> float | None:
        """Return the volume the device reports."""
        return self._runtime.volume

    async def async_set_native_value(self, value: float) -> None:
        """Write the volume and refresh the entity."""
        try:
            await self._runtime.async_set_volume(int(value))
        except XgimiError as err:
            raise HomeAssistantError(str(err)) from err
        self.async_write_ha_state()
