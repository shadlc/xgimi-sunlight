"""Remote platform exposing the 15 verified key codes."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from typing import Any

from homeassistant.components.remote import RemoteEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_DELAY_SECS,
    ATTR_HOLD_SECS,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    DEFAULT_NUM_REPEATS,
    KEY_CODES,
)
from .entity import XgimiEntity
from .protocol import KeyCommand, XgimiError
from .runtime import XgimiRuntime

_LOGGER = logging.getLogger(__name__)

SUPPORTED_KEYS: list[str] = sorted(KEY_CODES)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add the remote entity."""
    runtime: XgimiRuntime = entry.runtime_data
    async_add_entities([XgimiRemote(runtime)])


class XgimiRemote(XgimiEntity, RemoteEntity):
    """A remote control for the projector keys."""

    _attr_translation_key = "remote"
    _attr_icon = "mdi:remote"

    def __init__(self, runtime: XgimiRuntime) -> None:
        """Create the remote entity."""
        super().__init__(runtime, "remote")

    @property
    def is_on(self) -> bool:
        """Return the shared projector state."""
        return self._runtime.projector_power

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the accepted command names."""
        return {"supported_commands": SUPPORTED_KEYS}

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send one or more keys, honouring hold/repeat semantics."""
        hold_secs = float(kwargs.get(ATTR_HOLD_SECS) or 0)
        repeats = int(kwargs.get(ATTR_NUM_REPEATS) or DEFAULT_NUM_REPEATS)
        delay_secs = kwargs.get(ATTR_DELAY_SECS)
        delay_secs = DEFAULT_DELAY_SECS if delay_secs is None else float(delay_secs)

        for name in command:
            if name not in KEY_CODES:
                raise HomeAssistantError(
                    f"Unknown key {name!r}; available keys: {', '.join(SUPPORTED_KEYS)}"
                )
            key_command = KeyCommand(code=KEY_CODES[name])
            for index in range(max(1, repeats)):
                if hold_secs > 0:
                    await self._async_send(key_command, hold=True)
                else:
                    await self._async_send(key_command)
                if index + 1 < repeats:
                    await asyncio.sleep(delay_secs)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the projector on (same path as the projector switch)."""
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
        """Send the explicit power-off frame."""
        try:
            await self._runtime.async_power_off()
        except XgimiError as err:
            raise HomeAssistantError(
                f"Failed to power off the projector: {err}"
            ) from err
