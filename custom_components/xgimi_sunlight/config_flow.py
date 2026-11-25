"""Config and options flow for the XGIMI Sunlight integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import selector

from .const import (
    CONF_DEFAULT_LAMP_MODE,
    CONF_HOLD_RESPONSE_PORT,
    CONF_HOST,
    CONF_LIGHT_SHAPE,
    CONF_NAME,
    DEFAULT_LAMP_MODE,
    DEFAULT_LIGHT_SHAPE,
    DEFAULT_NAME,
    DOMAIN,
    LAMP_LABEL_TO_MODE,
    LAMP_MODE_LABEL,
    LAMP_MODES,
    LIGHT_SHAPE_SINGLE,
    LIGHT_SHAPE_SPLIT,
    LIGHT_SHAPES,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)

SHAPE_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[
            selector.SelectOptionDict(
                value=LIGHT_SHAPE_SPLIT,
                label="Split: one switch per lamp mode (Custom / Rhythm / Daylight / Movie)",
            ),
            selector.SelectOptionDict(
                value=LIGHT_SHAPE_SINGLE,
                label="Single: one lamp that switches mode through effects",
            ),
        ],
        mode=selector.SelectSelectorMode.DROPDOWN,
    )
)

MODE_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[LAMP_MODE_LABEL[mode] for mode in LAMP_MODES],
        mode=selector.SelectSelectorMode.DROPDOWN,
    )
)


class XgimiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ask for the device address."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Collect the host and optional name."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = (user_input.get(CONF_HOST) or "").strip()
            name = (user_input.get(CONF_NAME) or "").strip() or DEFAULT_NAME

            if not host:
                errors[CONF_HOST] = "invalid_host"
            else:
                await self.async_set_unique_id(host)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=name,
                    data={CONF_HOST: host, CONF_NAME: name},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Change the address of an existing entry."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            host = (user_input.get(CONF_HOST) or "").strip()
            name = (user_input.get(CONF_NAME) or "").strip() or DEFAULT_NAME

            if not host:
                errors[CONF_HOST] = "invalid_host"
            elif any(
                other.unique_id == host and other.entry_id != entry.entry_id
                for other in self._async_current_entries()
            ):
                errors[CONF_HOST] = "already_configured"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    unique_id=host,
                    title=name,
                    data={CONF_HOST: host, CONF_NAME: name},
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
            description_placeholders={"name": entry.title},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return XgimiOptionsFlow()


class XgimiOptionsFlow(OptionsFlow):
    """Entity layout, default mode and response-port preference."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Render and validate the options form."""
        errors: dict[str, str] = {}

        if user_input is not None:
            cleaned: dict[str, Any] = dict(user_input)

            label = cleaned.get(
                CONF_DEFAULT_LAMP_MODE, LAMP_MODE_LABEL[DEFAULT_LAMP_MODE]
            )
            cleaned[CONF_DEFAULT_LAMP_MODE] = LAMP_LABEL_TO_MODE.get(
                label, DEFAULT_LAMP_MODE
            )

            if not errors:
                return self.async_create_entry(title="", data=cleaned)

        shape = self.config_entry.options.get(CONF_LIGHT_SHAPE, DEFAULT_LIGHT_SHAPE)
        if shape not in LIGHT_SHAPES:
            shape = DEFAULT_LIGHT_SHAPE

        default_mode = self.config_entry.options.get(
            CONF_DEFAULT_LAMP_MODE, DEFAULT_LAMP_MODE
        )
        if default_mode not in LAMP_MODES:
            default_mode = DEFAULT_LAMP_MODE

        hold_port = bool(self.config_entry.options.get(CONF_HOLD_RESPONSE_PORT, True))

        schema = vol.Schema(
            {
                vol.Required(CONF_LIGHT_SHAPE, default=shape): SHAPE_SELECTOR,
                vol.Required(
                    CONF_DEFAULT_LAMP_MODE,
                    default=LAMP_MODE_LABEL[default_mode],
                ): MODE_SELECTOR,
                vol.Required(CONF_HOLD_RESPONSE_PORT, default=hold_port): cv.boolean,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
            description_placeholders={"host": self.config_entry.data[CONF_HOST]},
        )
