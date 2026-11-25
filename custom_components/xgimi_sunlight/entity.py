"""Shared entity plumbing for the XGIMI Sunlight integration."""

from __future__ import annotations

import logging

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, MANUFACTURER, MODEL
from .protocol import Command, SendResult, XgimiError
from .runtime import XgimiRuntime

_LOGGER = logging.getLogger(__name__)


class XgimiEntity(Entity):
    """Base class wiring an entity to the runtime and its state feedback."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, runtime: XgimiRuntime, unique_suffix: str) -> None:
        """Bind the entity to its runtime."""
        self._runtime = runtime
        self._attr_unique_id = f"{runtime.entry_id}_{unique_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, runtime.entry_id)},
            name=runtime.name,
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to device state pushes and local state changes."""
        self._runtime.client.register_state_callback(self._handle_state_update)
        self._runtime.add_listener(self._handle_state_update)

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from device state pushes."""
        self._runtime.client.remove_state_callback(self._handle_state_update)
        self._runtime.remove_listener(self._handle_state_update)

    @callback
    def _handle_state_update(self) -> None:
        """Write state after the device reported a change."""
        self.async_write_ha_state()

    async def _async_send(self, command: Command, *, hold: bool = False) -> SendResult:
        """Send a command and translate a rejection into a HA error."""
        try:
            result = await self._runtime.async_send(command, hold=hold)
        except XgimiError as err:
            raise HomeAssistantError(
                f"Failed to send a command to {self._runtime.host}: {err}"
            ) from err

        if result.accepted is False:
            raise HomeAssistantError(
                f"{self._runtime.host} rejected the command: {result.message}"
            )

        if result.accepted is None and result.degraded:
            _LOGGER.debug(
                "Command replies disabled for %s; assuming the command worked",
                self._runtime.host,
            )
        return result
