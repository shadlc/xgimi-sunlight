"""Projector power switch for the XGIMI Sunlight."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    LIGHT_PARAM_POWER,
    STATE_VALUE_OFF,
    STATE_VALUE_ON,
)
from .entity import XgimiEntity
from .protocol import XgimiError, light_param
from .runtime import XgimiRuntime

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add the projector and lamp switches."""
    runtime: XgimiRuntime = entry.runtime_data
    async_add_entities([XgimiProjectorSwitch(runtime), XgimiLampSwitch(runtime)])


class XgimiLampSwitch(XgimiEntity, SwitchEntity, RestoreEntity):
    """One-click lamp power, independent of the four mode lights."""

    _attr_translation_key = "lamp"
    _attr_icon = "mdi:desk-lamp"

    def __init__(self, runtime: XgimiRuntime) -> None:
        """Create the lamp switch."""
        super().__init__(runtime, "lamp")

    @property
    def is_on(self) -> bool | None:
        """Return the lamp power state reported by the device."""
        return self._runtime.lamp_is_on

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the reported lamp details alongside the switch."""
        return {
            "state_feedback": self._runtime.state_feedback,
            "device_online": self._runtime.online,
            "raw_lamp_mode": self._runtime.lamp_mode,
            "volume": self._runtime.volume,
        }

    async def async_added_to_hass(self) -> None:
        """Restore the last known lamp state after a restart."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._runtime.optimistic_lamp_on = last_state.state == STATE_ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the lamp on, keeping the mode it was last in."""
        if self._runtime.lamp_is_on:
            return
        self._runtime.set_optimistic_lamp(
            is_on=True, mode=self._runtime.lamp_mode or self._runtime.default_lamp_mode
        )
        try:
            await self._async_send(light_param(LIGHT_PARAM_POWER, STATE_VALUE_ON))
        except Exception:
            self._runtime.set_optimistic_lamp(is_on=False)
            raise

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the lamp off."""
        self._runtime.set_optimistic_lamp(is_on=False)
        await self._async_send(light_param(LIGHT_PARAM_POWER, STATE_VALUE_OFF))


class XgimiProjectorSwitch(XgimiEntity, SwitchEntity, RestoreEntity):
    """Projector power."""

    _attr_translation_key = "projector"
    _attr_icon = "mdi:projector"

    def __init__(self, runtime: XgimiRuntime) -> None:
        """Create the projector switch."""
        super().__init__(runtime, "projector")

    @property
    def is_on(self) -> bool:
        """Return the shared projector state."""
        return self._runtime.projector_power

    async def async_added_to_hass(self) -> None:
        """Restore the last known power state after a restart."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._runtime.projector_is_on = last_state.state == STATE_ON

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the online state and the system volume."""
        return {
            "device_online": self._runtime.online,
            "volume": self._runtime.volume,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the projector on with the power key."""
        if self._runtime.projector_power:
            _LOGGER.debug("Projector already reachable; not sending anything")
            return
        try:
            await self._runtime.async_power_on()
        except XgimiError as err:
            raise HomeAssistantError(
                f"Failed to power on the projector: {err}"
            ) from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Put the projector in standby with the explicit power-off frame."""
        try:
            await self._runtime.async_power_off()
        except XgimiError as err:
            raise HomeAssistantError(
                f"Failed to power off the projector: {err}"
            ) from err
