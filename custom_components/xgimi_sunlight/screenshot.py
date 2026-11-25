"""Screen captures fetched from the device."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from aiohttp import ClientError, ClientTimeout
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import ACTION_SCREENSHOT_REPLY, SCREEN_FILE, SCREENSHOT_TIMEOUT
from .protocol import build_screenshot_request, parse_screenshot_path
from .runtime import XgimiRuntime

_LOGGER = logging.getLogger(__name__)


async def async_publish(
    hass: HomeAssistant, runtime: XgimiRuntime, image: bytes
) -> str:
    """Write the capture under ``www`` and return its token-free URL."""
    folder = Path(hass.config.path("www"))
    if not folder.exists():
        await hass.async_add_executor_job(folder.mkdir, 0o755, True, True)
    path = folder / SCREEN_FILE
    await hass.async_add_executor_job(path.write_bytes, image)
    url = f"/local/{SCREEN_FILE}?v={int(time.time())}"
    runtime.set_last_screen_url(url)
    return url


async def async_capture_image(
    hass: HomeAssistant, runtime: XgimiRuntime, *, force: bool = False
) -> bytes | None:
    """Return a capture, reusing the cached image unless ``force`` is set."""
    channel = runtime.state_channel
    if channel is None or not channel.connected:
        _LOGGER.debug("Cannot capture the screen of %s: no state channel", runtime.host)
        return None

    async with runtime.screenshot_lock:
        cached = runtime.screenshot_cache
        if cached is not None and not force:
            return cached[1]

        runtime.set_capturing(True)
        try:
            return await _capture(hass, runtime, cached)
        finally:
            runtime.set_capturing(False)


async def _capture(
    hass: HomeAssistant,
    runtime: XgimiRuntime,
    cached: tuple[float, bytes] | None,
) -> bytes | None:
    """Request one capture and download it, falling back to ``cached``."""
    channel = runtime.state_channel
    if channel is None:
        return cached[1] if cached is not None else None

    reply = await channel.async_request(
        build_screenshot_request(),
        ACTION_SCREENSHOT_REPLY,
        timeout=SCREENSHOT_TIMEOUT,
    )
    url = parse_screenshot_path(reply, runtime.host)
    if url is None:
        _LOGGER.debug(
            "No screenshot path in the reply from %s: %s", runtime.host, reply
        )
        return cached[1] if cached is not None else None

    session = async_get_clientsession(hass)
    try:
        async with session.get(
            url, timeout=ClientTimeout(total=SCREENSHOT_TIMEOUT)
        ) as response:
            response.raise_for_status()
            image = await response.read()
    except (TimeoutError, ClientError) as err:
        _LOGGER.debug("Cannot download the screenshot %s: %s", url, err)
        return cached[1] if cached is not None else None

    runtime.screenshot_cache = (time.monotonic(), image)
    await async_publish(hass, runtime, image)
    return image
