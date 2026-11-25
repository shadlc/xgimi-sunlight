"""Lamp platform for the XGIMI Sunlight."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, ClassVar

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    BRIGHTNESS_MAX,
    BRIGHTNESS_MIN,
    COLOR_TEMP_MAX_KELVIN,
    COLOR_TEMP_MIN_KELVIN,
    COLOUR_TEMP_MAX,
    COLOUR_TEMP_MIN,
    HA_BRIGHTNESS_MAX,
    LAMP_LABEL_TO_MODE,
    LAMP_MODE_CUSTOM,
    LAMP_MODE_LABEL,
    LAMP_MODE_TO_UNIQUE,
    LAMP_MODES,
    LAMP_WRITE_DEBOUNCE,
    LIGHT_PARAM_BRIGHTNESS,
    LIGHT_PARAM_COLOR_TEMP,
    LIGHT_PARAM_MODE,
    LIGHT_PARAM_POWER,
    LIGHT_SHAPE_SINGLE,
    STATE_VALUE_OFF,
    STATE_VALUE_ON,
)
from .entity import XgimiEntity
from .protocol import light_param
from .runtime import XgimiRuntime

_LOGGER = logging.getLogger(__name__)

EFFECTS: list[str] = [LAMP_MODE_LABEL[mode] for mode in LAMP_MODES]

_KELVIN_SPAN = COLOR_TEMP_MAX_KELVIN - COLOR_TEMP_MIN_KELVIN
_DEVICE_TEMP_SPAN = COLOUR_TEMP_MAX - COLOUR_TEMP_MIN


def _to_device_brightness(brightness: int) -> str:
    """Scale Home Assistant's 0-255 brightness onto the device's 1-10 steps."""
    ratio = brightness / HA_BRIGHTNESS_MAX
    scaled = round(BRIGHTNESS_MIN + ratio * (BRIGHTNESS_MAX - BRIGHTNESS_MIN))
    return str(max(BRIGHTNESS_MIN, min(BRIGHTNESS_MAX, scaled)))


def _to_ha_brightness(value: int) -> int:
    """Scale the device's 1-10 brightness onto Home Assistant's 0-255."""
    ratio = (value - BRIGHTNESS_MIN) / (BRIGHTNESS_MAX - BRIGHTNESS_MIN)
    scaled = round(ratio * HA_BRIGHTNESS_MAX)
    return max(1, min(HA_BRIGHTNESS_MAX, scaled))


def _to_device_color_temp(kelvin: int) -> str:
    """Map a Kelvin value onto the device's 1..10 colour temperature."""
    ratio = (kelvin - COLOR_TEMP_MIN_KELVIN) / _KELVIN_SPAN
    value = round(COLOUR_TEMP_MIN + ratio * _DEVICE_TEMP_SPAN)
    return str(max(COLOUR_TEMP_MIN, min(COLOUR_TEMP_MAX, value)))


def _to_ha_kelvin(value: int) -> int:
    """Map the device's 1..10 colour temperature onto Kelvin."""
    ratio = (value - COLOUR_TEMP_MIN) / _DEVICE_TEMP_SPAN
    kelvin = round(COLOR_TEMP_MIN_KELVIN + ratio * _KELVIN_SPAN)
    return max(COLOR_TEMP_MIN_KELVIN, min(COLOR_TEMP_MAX_KELVIN, kelvin))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the lamp entities for the configured layout."""
    runtime: XgimiRuntime = entry.runtime_data

    if runtime.light_shape == LIGHT_SHAPE_SINGLE:
        async_add_entities([XgimiLampSingle(runtime)])
        return

    async_add_entities([XgimiLampMode(runtime, mode) for mode in LAMP_MODES])


class _XgimiLampBase(XgimiEntity, LightEntity):
    """Shared lamp behaviour: power, mode, brightness and colour temperature."""

    _attr_color_mode = ColorMode.COLOR_TEMP
    _attr_supported_color_modes = {ColorMode.COLOR_TEMP}
    _attr_min_color_temp_kelvin = COLOR_TEMP_MIN_KELVIN
    _attr_max_color_temp_kelvin = COLOR_TEMP_MAX_KELVIN

    @property
    def is_on(self) -> bool:
        """Return the lamp power state reported by the device."""
        return bool(self._runtime.lamp_is_on)

    @property
    def brightness(self) -> int | None:
        """Return the reported brightness, or None when the device is silent."""
        value = self._runtime.lamp_brightness
        return None if value is None else _to_ha_brightness(value)

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the reported colour temperature in Kelvin."""
        value = self._runtime.lamp_color_temp
        return None if value is None else _to_ha_kelvin(value)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose whether the reported state is trustworthy."""
        return {
            "state_feedback": self._runtime.state_feedback,
            "device_online": self._runtime.online,
            "raw_lamp_mode": self._runtime.lamp_mode,
            "raw_brightness": self._runtime.lamp_brightness,
            "raw_color_temp": self._runtime.lamp_color_temp,
        }

    async def _async_apply(
        self,
        *,
        mode: str | None,
        brightness: int | None,
        kelvin: int | None = None,
    ) -> None:
        """Turn the lamp on, sending only the values that actually change."""
        runtime = self._runtime
        changed = False

        immediate: list[str] = []
        if not runtime.lamp_is_on:
            immediate.append(light_param(LIGHT_PARAM_POWER, STATE_VALUE_ON))
        if mode is not None and runtime.lamp_mode != mode:
            immediate.append(light_param(LIGHT_PARAM_MODE, mode))

        if immediate:
            runtime.set_optimistic_lamp(is_on=True, mode=mode)
            try:
                for command in immediate:
                    await self._async_send(command)
            except Exception:
                runtime.set_optimistic_lamp(is_on=False)
                raise
            changed = True

        if brightness is None and kelvin is None:
            return

        generation = runtime.next_lamp_generation()
        await asyncio.sleep(LAMP_WRITE_DEBOUNCE)
        if generation != runtime.lamp_generation:
            return

        commands: list[str] = []
        if brightness is not None:
            wanted = _to_device_brightness(brightness)
            if (
                runtime.lamp_brightness is None
                or str(runtime.lamp_brightness) != wanted
            ):
                commands.append(light_param(LIGHT_PARAM_BRIGHTNESS, wanted))
        if kelvin is not None:
            wanted_temp = _to_device_color_temp(kelvin)
            if (
                runtime.lamp_color_temp is None
                or str(runtime.lamp_color_temp) != wanted_temp
            ):
                commands.append(light_param(LIGHT_PARAM_COLOR_TEMP, wanted_temp))

        if not commands:
            return

        runtime.set_optimistic_lamp(is_on=True, mode=mode)
        try:
            for command in commands:
                await self._async_send(command)
        except Exception:
            if not changed:
                runtime.set_optimistic_lamp(is_on=False)
            raise

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the lamp off."""
        self._runtime.set_optimistic_lamp(is_on=False)
        await self._async_send(light_param(LIGHT_PARAM_POWER, STATE_VALUE_OFF))


class XgimiLampMode(_XgimiLampBase):
    """One lamp entity per mode, used by the ``split`` layout."""

    def __init__(self, runtime: XgimiRuntime, mode: str) -> None:
        """Bind the entity to a single lamp mode."""
        super().__init__(runtime, LAMP_MODE_TO_UNIQUE[mode])
        self._mode = mode
        self._is_custom = mode == LAMP_MODE_CUSTOM
        self._attr_translation_key = LAMP_MODE_TO_UNIQUE[mode]
        if not self._is_custom:
            self._attr_color_mode = ColorMode.ONOFF
            self._attr_supported_color_modes = {ColorMode.ONOFF}

    @property
    def brightness(self) -> int | None:
        """Return the brightness, but only for the custom mode."""
        if not self._is_custom:
            return None
        return super().brightness

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the colour temperature, but only for the custom mode."""
        if not self._is_custom:
            return None
        return super().color_temp_kelvin

    @property
    def is_on(self) -> bool:
        """On only when the lamp is on *and* in this mode."""
        if not self._runtime.lamp_is_on:
            return False
        current = self._runtime.lamp_mode
        return current is None or current == self._mode

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Switch the lamp to this entity's mode."""
        await self._async_apply(
            mode=self._mode,
            brightness=kwargs.get(ATTR_BRIGHTNESS) if self._is_custom else None,
            kelvin=kwargs.get(ATTR_COLOR_TEMP_KELVIN) if self._is_custom else None,
        )


class XgimiLampSingle(_XgimiLampBase):
    """A single lamp entity that switches mode through ``effect``."""

    _attr_name = None
    _attr_effect_list: ClassVar[list[str]] = EFFECTS
    _attr_supported_features = LightEntityFeature.EFFECT

    def __init__(self, runtime: XgimiRuntime) -> None:
        """Create the combined lamp entity."""
        super().__init__(runtime, "lamp")

    @property
    def effect(self) -> str | None:
        """Return the current mode as a human readable label."""
        mode = self._runtime.lamp_mode
        return (
            LAMP_MODE_LABEL.get(mode)
            if mode
            else LAMP_MODE_LABEL[self._runtime.default_lamp_mode]
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on, honouring an optional ``effect`` and ``brightness``."""
        requested = kwargs.get(ATTR_EFFECT)
        if requested is None:
            mode: str | None = self._runtime.default_lamp_mode
        else:
            mode = LAMP_LABEL_TO_MODE.get(requested)
            if mode is None:
                _LOGGER.debug("Unknown lamp effect %r; keeping current mode", requested)
        await self._async_apply(
            mode=mode,
            brightness=kwargs.get(ATTR_BRIGHTNESS),
            kelvin=kwargs.get(ATTR_COLOR_TEMP_KELVIN),
        )
