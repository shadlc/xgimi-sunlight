"""XGIMI Sunlight integration for Home Assistant."""

from __future__ import annotations

import logging
from datetime import timedelta
from pathlib import Path
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import (
    ConfigEntryNotReady,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.typing import ConfigType

from . import media, screenshot, views
from .const import (
    APP_MODE,
    APP_TYPE_OPEN,
    ATTR_APP,
    ATTR_COMMAND,
    ATTR_HOLD_SECS,
    ATTR_KEY,
    ATTR_PACKAGE,
    ATTR_PATH,
    ATTR_URL,
    ATTR_WAIT_RESPONSE,
    DOMAIN,
    KEY_CODES,
    RESPONSE_PORT,
    RESYNC_INTERVAL,
    SCREEN_FILE,
    SERVICE_OPEN_APP,
    SERVICE_PLAY_MEDIA,
    SERVICE_PRESS_KEY,
    SERVICE_SCREENSHOT,
    SERVICE_SEND_COMMAND,
    SERVICE_STOP_MEDIA,
)
from .protocol import ControlCommand, XgimiConnectionError, XgimiError, text
from .protocol import key as build_key
from .runtime import (
    XgimiRuntime,
    build_client,
    build_default_lamp_mode,
    build_light_shape,
    build_name,
    build_state_channel,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.LIGHT,
    Platform.SWITCH,
    Platform.REMOTE,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.TEXT,
    Platform.CAMERA,
    Platform.NUMBER,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

ISSUE_PORT_CONFLICT = "response_port_unavailable"

SERVICE_SEND_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_COMMAND): cv.string,
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Optional(ATTR_WAIT_RESPONSE, default=True): cv.boolean,
    }
)

SERVICE_PRESS_KEY_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_KEY): vol.In(sorted(KEY_CODES)),
        vol.Optional(ATTR_HOLD_SECS, default=0): vol.All(
            vol.Coerce(float), vol.Range(min=0, max=10)
        ),
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    }
)

SERVICE_PLAY_MEDIA_SCHEMA = vol.Schema(
    {
        vol.Exclusive(ATTR_URL, "source"): cv.string,
        vol.Exclusive(ATTR_PATH, "source"): cv.string,
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    }
)

SERVICE_STOP_MEDIA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    }
)

SERVICE_SCREENSHOT_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    }
)

SERVICE_OPEN_APP_SCHEMA = vol.Schema(
    {
        vol.Exclusive(ATTR_PACKAGE, "target"): cv.string,
        vol.Exclusive(ATTR_APP, "target"): cv.string,
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    }
)


def _iter_runtimes(hass: HomeAssistant) -> list[XgimiRuntime]:
    """Return every loaded runtime."""
    runtimes: list[XgimiRuntime] = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        runtime = getattr(entry, "runtime_data", None)
        if isinstance(runtime, XgimiRuntime):
            runtimes.append(runtime)
    return runtimes


def _resolve_runtime(hass: HomeAssistant, data: dict[str, Any]) -> XgimiRuntime:
    """Pick the target device from a service call."""
    runtimes = _iter_runtimes(hass)
    if not runtimes:
        raise ServiceValidationError("No XGIMI Sunlight device is configured")

    host = data.get(CONF_HOST)
    if host:
        for runtime in runtimes:
            if runtime.host == host:
                return runtime
        raise ServiceValidationError(f"No configured device uses IP {host}")

    entity_ids = data.get(ATTR_ENTITY_ID)
    if entity_ids:
        registry = er.async_get(hass)
        for entity_id in entity_ids:
            registry_entry = registry.async_get(entity_id)
            if registry_entry is None or registry_entry.config_entry_id is None:
                continue
            for runtime in runtimes:
                if runtime.entry_id == registry_entry.config_entry_id:
                    return runtime

    if len(runtimes) > 1:
        raise ServiceValidationError(
            "Multiple devices are configured; pass host or target to pick one"
        )
    return runtimes[0]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the domain services."""

    async def _async_handle_send_command(
        call: ServiceCall,
    ) -> ServiceResponse | None:
        """Send a free-form natural-language command to the voice assistant."""
        runtime = _resolve_runtime(hass, dict(call.data))
        command: str = call.data[ATTR_COMMAND]
        want_response = (
            bool(call.data.get(ATTR_WAIT_RESPONSE, True)) or call.return_response
        )

        try:
            result = await runtime.client.async_send(
                text(command), wait_response=want_response
            )
        except XgimiError as err:
            raise ServiceValidationError(str(err)) from err

        _LOGGER.info(
            "Sent custom command %r to %s (accepted=%s)",
            runtime.host,
            command,
            result.accepted,
        )

        if not call.return_response:
            return None

        return {
            "host": runtime.host,
            "command": command,
            "accepted": result.accepted,
            "error": result.message,
            "degraded": result.degraded,
            "local_port": runtime.client.local_port,
            "raw": result.response,
        }

    async def _async_handle_press_key(call: ServiceCall) -> None:
        """Send a remote key by name."""
        runtime = _resolve_runtime(hass, dict(call.data))
        key_name: str = call.data[ATTR_KEY]
        hold_secs: float = call.data.get(ATTR_HOLD_SECS, 0)

        try:
            command = build_key(key_name)
            if hold_secs > 0:
                await runtime.client.async_send(command, hold=True)
            else:
                await runtime.client.async_send(command)
        except XgimiError as err:
            raise ServiceValidationError(str(err)) from err

    async def _async_handle_play_media(call: ServiceCall) -> None:
        """Play an image, a video or a track on the device."""
        runtime = _resolve_runtime(hass, dict(call.data))
        data = dict(call.data)

        source = data.get(ATTR_URL)
        if not source:
            raw_path = data.get(ATTR_PATH)
            if raw_path:
                source = str(media.resolve_path(hass, str(raw_path)))
            elif runtime.last_media:
                source = runtime.last_media
            else:
                raise ServiceValidationError(
                    "Pass url or path, or play something first"
                )

        try:
            url = await media.async_play(hass, runtime, source)
        except (ConnectionError, FileNotFoundError, ValueError) as err:
            raise HomeAssistantError(str(err)) from err

        _LOGGER.info("Playing %s on %s", url, runtime.host)
        runtime.set_last_media(source)

    async def _async_handle_open_app(call: ServiceCall) -> None:
        """Launch an app by package name, or by the name shown in the picker."""
        runtime = _resolve_runtime(hass, dict(call.data))
        package = call.data.get(ATTR_PACKAGE)
        if not package:
            name = call.data.get(ATTR_APP)
            if not name:
                raise ServiceValidationError("Pass package or app")
            package = runtime.app_package(str(name))
            if package is None:
                raise ServiceValidationError(f"Unknown app: {name}")

        try:
            await runtime.client.async_send(
                ControlCommand(mode=APP_MODE, type=APP_TYPE_OPEN, data=str(package))
            )
        except XgimiError as err:
            raise ServiceValidationError(str(err)) from err

        _LOGGER.info("Opened %s on %s", package, runtime.host)

    async def _async_handle_stop_media(call: ServiceCall) -> None:
        """Stop the renderer."""
        runtime = _resolve_runtime(hass, dict(call.data))
        try:
            await media.async_stop(hass, runtime)
        except ConnectionError as err:
            raise HomeAssistantError(str(err)) from err

    async def _async_handle_screenshot(call: ServiceCall) -> ServiceResponse:
        """Capture the screen and save it under ``www``."""
        runtime = _resolve_runtime(hass, dict(call.data))
        if runtime.screenshot_lock.locked():
            raise ServiceValidationError("A screen capture is already running")
        image = await screenshot.async_capture_image(hass, runtime, force=True)
        if image is None:
            raise HomeAssistantError(f"{runtime.host} did not return a screenshot")

        path = Path(hass.config.path("www")) / SCREEN_FILE
        _LOGGER.info("Saved a screenshot of %s to %s", runtime.host, path)
        return {"path": str(path), "url": runtime.last_screen_url, "bytes": len(image)}

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_COMMAND,
        _async_handle_send_command,
        schema=SERVICE_SEND_COMMAND_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_PRESS_KEY,
        _async_handle_press_key,
        schema=SERVICE_PRESS_KEY_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_PLAY_MEDIA,
        _async_handle_play_media,
        schema=SERVICE_PLAY_MEDIA_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP_MEDIA,
        _async_handle_stop_media,
        schema=SERVICE_STOP_MEDIA_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SCREENSHOT,
        _async_handle_screenshot,
        schema=SERVICE_SCREENSHOT_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_OPEN_APP,
        _async_handle_open_app,
        schema=SERVICE_OPEN_APP_SCHEMA,
    )

    views.register_view(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up one device."""
    client = build_client(entry)

    try:
        await client.async_start()
    except XgimiConnectionError as err:
        raise ConfigEntryNotReady(
            f"Cannot open the UDP channel to {entry.data[CONF_HOST]}: {err}"
        ) from err

    runtime = XgimiRuntime(
        entry_id=entry.entry_id,
        host=entry.data[CONF_HOST],
        name=build_name(entry),
        client=client,
        light_shape=build_light_shape(entry),
        default_lamp_mode=build_default_lamp_mode(entry),
        state_channel=build_state_channel(entry),
    )
    entry.runtime_data = runtime

    screen_path = Path(hass.config.path("www")) / SCREEN_FILE
    if await hass.async_add_executor_job(screen_path.exists):
        stamp = await hass.async_add_executor_job(
            lambda: int(screen_path.stat().st_mtime)
        )
        runtime.set_last_screen_url(f"/local/{SCREEN_FILE}?v={stamp}")

    assert runtime.state_channel is not None
    runtime.state_channel.register_callback(runtime.notify)
    await runtime.state_channel.async_start()
    entry.async_on_unload(runtime.state_channel.remove_callback)

    def _schedule_light_refresh() -> None:
        """Pull the lamp values after the channel (re)connects."""
        hass.async_create_task(runtime.async_refresh_light_state())

    runtime.state_channel.register_connect_callback(_schedule_light_refresh)
    entry.async_on_unload(
        lambda: runtime.state_channel.remove_connect_callback(_schedule_light_refresh)
    )

    await runtime.async_refresh_light_state()

    async def _resync(_now: Any) -> None:
        """Re-read lamp values, which the device does not always push."""
        await runtime.async_refresh_light_state()

    entry.async_on_unload(
        async_track_time_interval(hass, _resync, timedelta(seconds=RESYNC_INTERVAL))
    )

    if client.can_receive:
        async_delete_issue(hass, DOMAIN, f"{ISSUE_PORT_CONFLICT}_{entry.entry_id}")
    else:
        async_create_issue(
            hass,
            DOMAIN,
            f"{ISSUE_PORT_CONFLICT}_{entry.entry_id}",
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key=ISSUE_PORT_CONFLICT,
            translation_placeholders={
                "host": runtime.host,
                "port": str(RESPONSE_PORT),
            },
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an entry, releasing the UDP response port."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    runtime = getattr(entry, "runtime_data", None)
    if isinstance(runtime, XgimiRuntime):
        if runtime.state_channel is not None:
            await runtime.state_channel.async_stop()
        await runtime.client.async_stop()

    async_delete_issue(hass, DOMAIN, f"{ISSUE_PORT_CONFLICT}_{entry.entry_id}")
    return True


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry after options changed."""
    await hass.config_entries.async_reload(entry.entry_id)
