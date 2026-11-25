"""Read the installed app list and launch apps on the device."""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import unquote

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    ACTION_APP_LIST_REPLY,
    APP_TIMEOUT,
)
from .protocol import XgimiError, build_app_list_request, parse_app_list_path
from .runtime import XgimiRuntime

_LOGGER = logging.getLogger(__name__)


async def async_fetch_apps(
    hass: HomeAssistant, runtime: XgimiRuntime
) -> list[dict[str, str]]:
    """Return ``[{"name": ..., "package": ...}]`` for the installed apps."""
    channel = runtime.state_channel
    if channel is None or not channel.connected:
        raise XgimiError(f"{runtime.host} is not connected")

    reply = await channel.async_request(
        build_app_list_request(), ACTION_APP_LIST_REPLY, timeout=APP_TIMEOUT
    )
    url = parse_app_list_path(reply, runtime.host)
    if url is None:
        raise XgimiError(f"{runtime.host} did not return an app list")

    session = async_get_clientsession(hass)
    async with session.get(url, timeout=APP_TIMEOUT) as response:
        raw = await response.read()

    text = unquote(raw.decode("utf-8", "replace"))
    try:
        payload: Any = json.loads(text)
    except ValueError as err:
        raise XgimiError(f"Unreadable app list from {runtime.host}") from err

    entries = payload.get("appList") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return []

    apps: list[dict[str, str]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        package = entry.get("packageName")
        if not isinstance(package, str) or not package:
            continue
        name = entry.get("appName")
        apps.append({"name": str(name or package), "package": package})

    apps.sort(key=lambda app: app["name"].casefold())
    return apps
