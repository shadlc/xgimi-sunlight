"""Unauthenticated HTTP view that hands one local file to the device."""

from __future__ import annotations

import mimetypes
import secrets
import socket
from pathlib import Path

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DLNA_PORT, DOMAIN

MEDIA_PATH = f"/api/{DOMAIN}/media/{{token}}"
_TOKENS = f"{DOMAIN}_media_tokens"
_MAX_TOKENS = 32


class XgimiMediaView(HomeAssistantView):
    """Serve one file per random token so the renderer can fetch it."""

    url = f"/api/{DOMAIN}/media/{{token}}"
    name = f"api:{DOMAIN}:media"
    requires_auth = False

    async def get(self, request: web.Request, token: str) -> web.StreamResponse:
        """Return the file registered under ``token``."""
        files: dict[str, Path] = request.app["hass"].data.get(_TOKENS, {})
        path = files.get(token)
        if path is None or not path.is_file():
            return web.Response(status=404)
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return web.FileResponse(path, headers={"Content-Type": content_type})


def register_view(hass: HomeAssistant) -> None:
    """Register the media view once per Home Assistant instance."""
    if hass.data.get(f"{DOMAIN}_media_view"):
        return
    hass.http.register_view(XgimiMediaView())
    hass.data[f"{DOMAIN}_media_view"] = True


def register_file(hass: HomeAssistant, path: Path) -> str:
    """Publish ``path`` under a new random token and return the URL path."""
    token = secrets.token_urlsafe(18)
    files: dict[str, Path] = hass.data.setdefault(_TOKENS, {})
    files[token] = path
    while len(files) > _MAX_TOKENS:
        files.pop(next(iter(files)))
    return MEDIA_PATH.format(token=token)


def _local_address(host: str) -> str:
    """Return the local address used to reach ``host``."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.connect((host, DLNA_PORT))
        return sock.getsockname()[0]


async def async_base_url(hass: HomeAssistant, host: str) -> str:
    """Return the URL prefix the device can use to fetch files from us."""
    address = await hass.async_add_executor_job(_local_address, host)
    return f"http://{address}:{hass.http.server_port}"
