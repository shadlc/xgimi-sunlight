"""Hand a local file or a URL to the device for playback."""

from __future__ import annotations

from pathlib import Path

from homeassistant.core import HomeAssistant

from .const import MEDIA_EXTENSIONS, MEDIA_KIND_IMAGE
from .dlna import async_play_media, async_stop_media
from .runtime import XgimiRuntime
from .views import async_base_url, register_file


def resolve_path(hass: HomeAssistant, text: str) -> Path:
    """Map what the user typed to a file on disk."""
    if text.startswith("media/"):
        return Path(hass.config.path("media", text[len("media/") :]))
    if text.startswith("www/"):
        return Path(hass.config.path("www", text[len("www/") :]))

    path = Path(text).expanduser()
    if path.is_absolute():
        return path

    for folder in ("www", "media"):
        candidate = Path(hass.config.path(folder, text))
        if candidate.is_file():
            return candidate
    return Path(hass.config.path(text))


async def async_play(hass: HomeAssistant, runtime: XgimiRuntime, source: str) -> str:
    """Play ``source`` on the device and return the URL it was given."""
    text = source.strip()
    if not text:
        raise ValueError("No media was given")

    if text.startswith(("http://", "https://")):
        url = text
    else:
        path = resolve_path(hass, text)
        if not path.is_file():
            raise FileNotFoundError(f"{path} is not a file")
        base = await async_base_url(hass, runtime.host)
        url = f"{base}{register_file(hass, path)}"

    suffix = Path(text.split("?")[0]).suffix.lower()
    kind = MEDIA_EXTENSIONS.get(suffix, MEDIA_KIND_IMAGE)
    try:
        await async_play_media(hass, runtime.host, url, kind)
    except ConnectionError as err:
        raise ConnectionError(
            "The projector is not accepting media right now: its DLNA renderer did "
            f"not answer the UPnP search. Check that the projector is on and that "
            f"its cast service is enabled. [{err}]"
        ) from err
    return url


async def async_stop(hass: HomeAssistant, runtime: XgimiRuntime) -> None:
    """Stop playback on the device."""
    await async_stop_media(hass, runtime.host)
