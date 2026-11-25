"""Camera that shows the last capture of the projector screen."""

from __future__ import annotations

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import XgimiEntity
from .runtime import XgimiRuntime


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add the screen camera."""
    runtime: XgimiRuntime = entry.runtime_data
    async_add_entities([XgimiScreenCamera(runtime)])


class XgimiScreenCamera(XgimiEntity, Camera):
    """Serve the last capture; the screenshot service takes a new one."""

    _attr_translation_key = "screen"
    _attr_icon = "mdi:projector-screen"
    _attr_brand = "XGIMI"

    def __init__(self, runtime: XgimiRuntime) -> None:
        """Create the camera."""
        super().__init__(runtime, "screen")
        Camera.__init__(self)

    @property
    def available(self) -> bool:
        """Return whether the device can be asked for a frame."""
        return self._runtime.online or self._runtime.screenshot_cache is not None

    @property
    def state(self) -> str:
        """Report a recording state while the device is being asked for a frame."""
        return "recording" if self._runtime.capturing else "idle"

    @property
    def extra_state_attributes(self) -> dict[str, bool | str]:
        """Expose the capture flag and a link the frontend can open."""
        return {
            "capturing": self._runtime.capturing,
            "has_capture": self._runtime.screenshot_cache is not None,
            "last_screen_url": self._runtime.last_screen_url,
        }

    @property
    def entity_picture(self) -> str | None:
        """Return the proxy URL, stamped so a new capture refreshes the card."""
        picture = super().entity_picture
        cached = self._runtime.screenshot_cache
        if picture is None or cached is None:
            return picture
        separator = "&" if "?" in picture else "?"
        return f"{picture}{separator}v={int(cached[0])}"

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return the last capture without asking the device again."""
        cached = self._runtime.screenshot_cache
        return cached[1] if cached is not None else None
