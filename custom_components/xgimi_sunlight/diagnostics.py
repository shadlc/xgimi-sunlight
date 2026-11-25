"""Diagnostics support for the XGIMI Sunlight integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    ACTION_LIGHT_PARAM,
    ACTION_LIGHT_QUERY,
    CONF_HOLD_RESPONSE_PORT,
    CONF_HOST,
    CONTROL_PORT,
    KEY_CODES,
    LIGHT_PARAM_BRIGHTNESS,
    LIGHT_PARAM_COLOR_TEMP,
    LIGHT_PARAM_MODE,
    LIGHT_PARAM_POWER,
    LIGHT_QUERY_ORDER,
    RESPONSE_PORT,
    STATE_PORT,
)
from .runtime import XgimiRuntime


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime: XgimiRuntime | None = getattr(entry, "runtime_data", None)

    diagnostics: dict[str, Any] = {
        "entry": {
            "host": entry.data.get(CONF_HOST),
            "options": dict(entry.options),
            "response_port_preferred": entry.options.get(CONF_HOLD_RESPONSE_PORT, True),
        },
        "protocol": {
            "control_port": CONTROL_PORT,
            "response_port": RESPONSE_PORT,
            "supported_keys": KEY_CODES,
            "light_actions": {
                "write": ACTION_LIGHT_PARAM,
                "read": ACTION_LIGHT_QUERY,
            },
            "light_params": {
                "power": LIGHT_PARAM_POWER,
                "color_temp": LIGHT_PARAM_COLOR_TEMP,
                "brightness": LIGHT_PARAM_BRIGHTNESS,
                "mode": LIGHT_PARAM_MODE,
            },
            "light_query_order": list(LIGHT_QUERY_ORDER),
        },
    }

    if runtime is None:
        diagnostics["runtime"] = "not loaded"
        return diagnostics

    diagnostics["runtime"] = {
        "connected": runtime.client.connected,
        "local_port": runtime.client.local_port,
        "state_feedback": runtime.state_feedback,
        "degraded": not runtime.client.can_receive,
        "lamp_is_on": runtime.lamp_is_on,
        "lamp_mode": runtime.lamp_mode,
        "lamp_brightness": runtime.lamp_brightness,
        "lamp_color_temp": runtime.lamp_color_temp,
        "light_shape": runtime.light_shape,
        "default_lamp_mode": runtime.default_lamp_mode,
        "known_state": dict(runtime.device_state),
        "last_response": runtime.client.last_response,
    }

    channel = runtime.state_channel
    diagnostics["state_channel"] = {
        "port": STATE_PORT,
        "connected": channel.connected if channel is not None else None,
        "online": runtime.online,
        "last_message": channel.last_message if channel is not None else None,
    }
    return diagnostics
