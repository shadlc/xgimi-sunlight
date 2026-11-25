"""Media playback over the device's DLNA renderer."""

from __future__ import annotations

import logging
import socket
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse
from xml.sax.saxutils import escape

from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DLNA_AVTRANSPORT,
    DLNA_CACHE_TTL,
    DLNA_PORT,
    DLNA_TIMEOUT,
    MEDIA_CLASSES,
    MEDIA_EXTENSIONS,
    MEDIA_KIND_IMAGE,
    MEDIA_MIME_TYPES,
    SSDP_PORT,
    SSDP_SEARCH_TARGET,
    SSDP_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

_NS = "{urn:schemas-upnp-org:device-1-0}"
_DESCRIPTION = "http://{host}:{port}/"

_CACHE: dict[str, tuple[float, str]] = {}

_DIDL = (
    '<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/"'
    ' xmlns:dc="http://purl.org/dc/elements/1.1/"'
    ' xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/">'
    '<item id="1" parentID="0" restricted="1"><dc:title>XGIMI Sunlight</dc:title>'
    "<upnp:class>{media_class}</upnp:class>"
    '<res protocolInfo="{protocol}">{url}</res></item></DIDL-Lite>'
)

_ENVELOPE = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"'
    ' s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
    "<s:Body>{body}</s:Body></s:Envelope>"
)


def _suffix(url: str) -> str:
    """Return the lower-case suffix of the path behind ``url``."""
    return Path(url.split("?")[0]).suffix.lower()


def media_kind(source: str) -> str:
    """Return the kind of media ``source`` points at."""
    return MEDIA_EXTENSIONS.get(_suffix(source), MEDIA_KIND_IMAGE)


def _protocol_info(url: str) -> str:
    """Return the DLNA protocol info for the media behind ``url``."""
    mime = MEDIA_MIME_TYPES.get(_suffix(url), "application/octet-stream")
    kind = media_kind(url)
    if kind == MEDIA_KIND_IMAGE and mime in ("image/jpeg", "image/png"):
        preset = "JPEG_LRG" if mime == "image/jpeg" else "PNG_LRG"
        return f"http-get:*:{mime}:DLNA.ORG_PN={preset};DLNA.ORG_OP=01;DLNA.ORG_CI=0"
    return f"http-get:*:{mime}:DLNA.ORG_OP=01;DLNA.ORG_CI=0"


def _escape_metadata(metadata: str) -> str:
    """Escape DIDL-Lite so it can travel inside the SOAP body."""
    return escape(metadata, {'"': "&quot;"})


def _ssdp_location(host: str, timeout: float) -> str | None:
    """Ask ``host`` where its MediaRenderer description lives."""
    request = (
        "M-SEARCH * HTTP/1.1\r\n"
        f"HOST: {host}:{SSDP_PORT}\r\n"
        'MAN: "ssdp:discover"\r\n'
        f"MX: {max(1, int(timeout))}\r\n"
        f"ST: {SSDP_SEARCH_TARGET}\r\n"
        "\r\n"
    ).encode()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        try:
            sock.sendto(request, (host, SSDP_PORT))
        except OSError as err:
            _LOGGER.debug("SSDP search to %s failed: %s", host, err)
            return None
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                payload, _ = sock.recvfrom(8192)
            except OSError:
                break
            for line in payload.decode("utf-8", "replace").splitlines():
                if line.lower().startswith("location:"):
                    return line.split(":", 1)[1].strip()
    return None


async def _async_description_url(hass: HomeAssistant, host: str) -> str:
    """Return the renderer description URL, discovering it when needed."""
    now = time.monotonic()
    cached = _CACHE.get(host)
    if cached and now - cached[0] < DLNA_CACHE_TTL:
        return cached[1]

    location = await hass.async_add_executor_job(_ssdp_location, host, SSDP_TIMEOUT)
    if not location:
        location = _DESCRIPTION.format(host=host, port=DLNA_PORT)
        _LOGGER.debug("SSDP found no renderer on %s, trying %s", host, location)
    _CACHE[host] = (now, location)
    return location


def forget(host: str) -> None:
    """Drop the cached description URL for ``host``."""
    _CACHE.pop(host, None)


async def _async_control_url(hass: HomeAssistant, host: str) -> str:
    """Read the device description and return the AVTransport control URL."""
    session = async_get_clientsession(hass)
    description = await _async_description_url(hass, host)
    try:
        async with session.get(description, timeout=DLNA_TIMEOUT) as response:
            response.raise_for_status()
            payload = await response.text()
    except (TimeoutError, ClientError) as err:
        forget(host)
        raise ConnectionError(f"{description} is unreachable: {err}") from err

    try:
        root = ET.fromstring(payload)
    except ET.ParseError as err:
        forget(host)
        raise ConnectionError(f"{host} returned an invalid description: {err}") from err

    parsed = urlparse(description)
    base = f"{parsed.scheme}://{parsed.netloc}"
    for service in root.iter(f"{_NS}service"):
        service_type = service.findtext(f"{_NS}serviceType") or ""
        if service_type != DLNA_AVTRANSPORT:
            continue
        control = service.findtext(f"{_NS}controlURL") or ""
        if control.startswith("http"):
            return control
        return f"{base}{control}"
    raise ConnectionError(f"{host} does not expose AVTransport")


async def _async_soap(
    hass: HomeAssistant, control_url: str, action: str, body: str
) -> None:
    """Post one SOAP action to the renderer."""
    session = async_get_clientsession(hass)
    try:
        async with session.post(
            control_url,
            data=_ENVELOPE.format(body=body).encode(),
            headers={
                "Content-Type": 'text/xml; charset="utf-8"',
                "SOAPACTION": f'"{DLNA_AVTRANSPORT}#{action}"',
            },
            timeout=DLNA_TIMEOUT,
        ) as response:
            await response.read()
            if response.status >= 400:
                raise ConnectionError(
                    f"{action} failed with HTTP {response.status}: {await response.text()}"
                )
    except (TimeoutError, ClientError) as err:
        raise ConnectionError(f"{action} failed: {err}") from err


async def _async_play_once(hass: HomeAssistant, host: str, url: str, kind: str) -> None:
    """Send SetAVTransportURI and Play to the renderer."""
    control_url = await _async_control_url(hass, host)
    metadata = _DIDL.format(
        media_class=MEDIA_CLASSES.get(kind, MEDIA_CLASSES[MEDIA_KIND_IMAGE]),
        protocol=_protocol_info(url),
        url=escape(url),
    )
    await _async_soap(
        hass,
        control_url,
        "SetAVTransportURI",
        f'<u:SetAVTransportURI xmlns:u="{DLNA_AVTRANSPORT}"><InstanceID>0</InstanceID>'
        f"<CurrentURI>{escape(url)}</CurrentURI>"
        f"<CurrentURIMetaData>{_escape_metadata(metadata)}</CurrentURIMetaData>"
        "</u:SetAVTransportURI>",
    )
    await _async_soap(
        hass,
        control_url,
        "Play",
        f'<u:Play xmlns:u="{DLNA_AVTRANSPORT}"><InstanceID>0</InstanceID><Speed>1</Speed></u:Play>',
    )


async def async_play_media(hass: HomeAssistant, host: str, url: str, kind: str) -> None:
    """Ask the renderer to play ``url`` as ``kind``."""
    try:
        await _async_play_once(hass, host, url, kind)
    except ConnectionError:
        forget(host)
        await _async_play_once(hass, host, url, kind)
    _LOGGER.debug("Asked %s to play %s as %s", host, url, kind)


async def async_stop_media(hass: HomeAssistant, host: str) -> None:
    """Stop whatever the renderer is playing."""

    async def stop() -> None:
        control_url = await _async_control_url(hass, host)
        await _async_soap(
            hass,
            control_url,
            "Stop",
            f'<u:Stop xmlns:u="{DLNA_AVTRANSPORT}"><InstanceID>0</InstanceID></u:Stop>',
        )

    try:
        await stop()
    except ConnectionError:
        forget(host)
        await stop()
