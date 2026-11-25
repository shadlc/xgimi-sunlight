"""Pickers for the remote key and the installed apps."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import apps as apps_module
from .const import KEY_LABEL_TO_CODE, KEY_LABELS
from .entity import XgimiEntity
from .protocol import XgimiError
from .runtime import XgimiRuntime

_LOGGER = logging.getLogger(__name__)

KEY_OPTIONS: list[str] = list(KEY_LABELS.values())


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add the key and app pickers."""
    runtime: XgimiRuntime = entry.runtime_data
    async_add_entities([XgimiKeySelect(runtime), XgimiAppSelect(runtime)])


class XgimiKeySelect(XgimiEntity, SelectEntity):
    """Select which remote key the tap/hold buttons should send."""

    _attr_translation_key = "key_select"
    _attr_icon = "mdi:gesture-tap-button"
    _attr_options = KEY_OPTIONS

    def __init__(self, runtime: XgimiRuntime) -> None:
        """Create the key picker."""
        super().__init__(runtime, "key_select")

    @property
    def current_option(self) -> str:
        """Return the armed key as a human readable label."""
        return KEY_LABELS.get(self._runtime.selected_key, KEY_LABELS["ok"])

    async def async_select_option(self, option: str) -> None:
        """Arm the key behind ``option``."""
        key = KEY_LABEL_TO_CODE.get(option)
        if key is None:
            return
        self._runtime.set_selected_key(key)


class XgimiAppSelect(XgimiEntity, SelectEntity):
    """Select which installed app the open-app button should launch."""

    _attr_translation_key = "app"
    _attr_icon = "mdi:apps"
    _attr_should_poll = True

    def __init__(self, runtime: XgimiRuntime) -> None:
        """Create the app picker."""
        super().__init__(runtime, "app")

    @property
    def options(self) -> list[str]:
        """Return the app names, filled in on the first poll."""
        return self._runtime.app_names

    @property
    def current_option(self) -> str | None:
        """Return the selected app name."""
        for app in self._runtime.apps:
            if app["package"] == self._runtime.selected_app:
                return app["name"]
        return None

    @property
    def available(self) -> bool:
        """Only offer the picker once a list is known."""
        return bool(self._runtime.apps)

    async def async_select_option(self, option: str) -> None:
        """Select ``option`` for the open-app button."""
        package = self._runtime.app_package(option)
        if package is None:
            return
        self._runtime.set_selected_app(package)

    async def async_update(self) -> None:
        """Load the app list once, then keep it."""
        if self._runtime.apps or not self._runtime.online:
            return
        try:
            apps = await apps_module.async_fetch_apps(self.hass, self._runtime)
        except (XgimiError, ConnectionError, TimeoutError) as err:
            _LOGGER.debug(
                "Cannot read the app list from %s: %s", self._runtime.host, err
            )
            return
        self._runtime.set_apps(apps)
