"""Runtime data for a single config entry."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME

from .const import (
    ACTION_LIGHT_QUERY,
    ACTION_POWER_OFF,
    BRIGHTNESS_MAX,
    BRIGHTNESS_MIN,
    COLOUR_TEMP_MAX,
    COLOUR_TEMP_MIN,
    COMMAND_TIMEOUT,
    CONF_DEFAULT_LAMP_MODE,
    CONF_HOLD_RESPONSE_PORT,
    CONF_HOST,
    CONF_LIGHT_SHAPE,
    DEFAULT_LAMP_MODE,
    DEFAULT_LIGHT_SHAPE,
    DEFAULT_NAME,
    DEFAULT_SELECTED_KEY,
    KEY_CODES,
    LAMP_MODES,
    LIGHT_QUERY_ORDER,
    LIGHT_QUERY_WINDOW,
    LIGHT_SHAPES,
    PROJECTOR_ON_POLL,
    PROJECTOR_ON_TIMEOUT,
    STATE_LAMP_BRIGHTNESS,
    STATE_LAMP_COLOR_TEMP,
    STATE_LAMP_MODE,
    STATE_LAMP_SWITCH,
    STATE_PROJECTOR_SLEEP,
    STATE_PROJECTOR_SLEEP_ON,
    STATE_VALUE_ON,
    STATE_VOLUME,
    VOLUME_MAX,
    VOLUME_MIN,
)
from .protocol import (
    Command,
    InvokeCommand,
    KeyCommand,
    SendResult,
    XgimiCommandRejected,
    XgimiConnectionError,
    XgimiStateChannel,
    XgimiUdpClient,
    build_light_query,
    build_payload_dict,
    interpret_response,
    parse_light_query,
    reply_actions,
    volume,
)

_LOGGER = logging.getLogger(__name__)


def build_name(entry: ConfigEntry) -> str:
    """Return the configured device name."""
    return entry.data.get(CONF_NAME) or DEFAULT_NAME


def build_light_shape(entry: ConfigEntry) -> str:
    """Return the validated entity layout."""
    shape = entry.options.get(CONF_LIGHT_SHAPE, DEFAULT_LIGHT_SHAPE)
    return shape if shape in LIGHT_SHAPES else DEFAULT_LIGHT_SHAPE


def build_default_lamp_mode(entry: ConfigEntry) -> str:
    """Return the validated default lamp mode."""
    mode = entry.options.get(CONF_DEFAULT_LAMP_MODE, DEFAULT_LAMP_MODE)
    return mode if mode in LAMP_MODES else DEFAULT_LAMP_MODE


def build_client(entry: ConfigEntry) -> XgimiUdpClient:
    """Create the UDP client for this entry."""
    prefer_response_port = entry.options.get(CONF_HOLD_RESPONSE_PORT, True)
    return XgimiUdpClient(
        entry.data[CONF_HOST],
        prefer_response_port=bool(prefer_response_port),
    )


def build_state_channel(entry: ConfigEntry) -> XgimiStateChannel:
    """Create the TCP state channel for this entry."""
    return XgimiStateChannel(entry.data[CONF_HOST])


@dataclass(slots=True)
class XgimiRuntime:
    """Everything an entity needs from its config entry."""

    entry_id: str
    host: str
    name: str
    client: XgimiUdpClient
    light_shape: str
    default_lamp_mode: str
    state_channel: XgimiStateChannel | None = None
    optimistic_lamp_on: bool = False
    optimistic_lamp_mode: str | None = None
    projector_is_on: bool = False
    selected_key: str = DEFAULT_SELECTED_KEY
    last_command: str = ""
    last_media: str = ""
    last_screen_url: str = ""
    selected_app: str = ""
    apps: list[dict[str, str]] = field(default_factory=list)
    lamp_generation: int = 0
    screenshot_lock: asyncio.Lock = field(
        default_factory=asyncio.Lock, init=False, repr=False
    )
    screenshot_cache: tuple[float, bytes] | None = field(
        default=None, init=False, repr=False
    )
    capturing: bool = field(default=False, init=False, repr=False)
    _listeners: list[Callable[[], None]] = field(default_factory=list)
    _refreshing: bool = field(default=False, init=False, repr=False)

    def set_capturing(self, value: bool) -> None:
        """Record that a capture is running so the UI can show it."""
        if self.capturing == value:
            return
        self.capturing = value
        self.notify()

    def next_lamp_generation(self) -> int:
        """Return a new generation number for a pending lamp write."""
        self.lamp_generation += 1
        return self.lamp_generation

    @property
    def device_state(self) -> dict[str, str]:
        """Return the last state values reported by the device."""
        if self.state_channel is not None:
            return self.state_channel.state
        return self.client.state

    async def async_refresh_light_state(self) -> None:
        """Read the four lamp values from the device."""
        if self._refreshing:
            return
        self._refreshing = True
        try:
            target = self.device_state
            changed = False
            channel = self.state_channel
            frames: list[dict[str, Any]] = []
            if channel is not None and channel.connected:
                frames = await channel.async_collect(
                    [
                        build_light_query(param, msgid=self.client.msgid)
                        for param in LIGHT_QUERY_ORDER
                    ],
                    ACTION_LIGHT_QUERY,
                    timeout=LIGHT_QUERY_WINDOW,
                )
            for frame in frames:
                for key, value in (parse_light_query(frame) or {}).items():
                    if target.get(key) != value:
                        target[key] = value
                        changed = True
            if changed:
                self.notify()
        finally:
            self._refreshing = False

    async def async_send(self, command: Command, *, hold: bool = False) -> SendResult:
        """Send a command over TCP when the channel is up, else over UDP."""
        channel = self.state_channel
        if channel is not None and channel.connected:
            payload = build_payload_dict(self.client.msgid, command, hold=hold)
            reply = await channel.async_request(
                payload, reply_actions(command), timeout=COMMAND_TIMEOUT
            )
            _LOGGER.debug("Sent %s over TCP", payload)
            result = interpret_response(reply)
            return SendResult(
                accepted=result.accepted,
                message=result.message,
                response=result.response,
            )

        return await self.client.async_send(command, hold=hold, wait_response=True)

    async def async_query_light(
        self, param: str, *, timeout: float = COMMAND_TIMEOUT
    ) -> dict[str, str] | None:
        """Read one lamp value over TCP when possible, else over UDP."""
        channel = self.state_channel
        if channel is not None and channel.connected:
            reply = await channel.async_request(
                build_light_query(param, msgid=self.client.msgid),
                ACTION_LIGHT_QUERY,
                timeout=timeout,
            )
            if reply is None:
                return None
            return parse_light_query(reply) or None

        return await self.client.async_query_light(param, timeout=timeout)

    @property
    def online(self) -> bool:
        """Return whether the device's control service is reachable."""
        return bool(self.state_channel is not None and self.state_channel.connected)

    @property
    def state_feedback(self) -> bool:
        """Return whether the device is reporting state to us."""
        return self.online or self.client.can_receive

    @property
    def volume(self) -> int | None:
        """Return the projector volume reported by the device, if known."""
        raw = self.device_state.get(STATE_VOLUME)
        if raw is None:
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    async def async_set_volume(self, level: int) -> None:
        """Set the projector volume."""
        level = max(VOLUME_MIN, min(VOLUME_MAX, level))
        result = await self.async_send(volume(level))
        if result.accepted is False:
            raise XgimiCommandRejected(result.message or "volume was rejected")
        self.device_state[STATE_VOLUME] = str(level)
        self.notify()

    @property
    def lamp_is_on(self) -> bool | None:
        """Return the lamp power state, or None when unknown."""
        raw = self.device_state.get(STATE_LAMP_SWITCH)
        if raw is not None and self.state_feedback:
            return raw == STATE_VALUE_ON
        return self.optimistic_lamp_on

    @property
    def lamp_mode(self) -> str | None:
        """Return the active lamp mode id, or None when unknown."""
        raw = self.device_state.get(STATE_LAMP_MODE)
        if raw is not None and self.state_feedback:
            return raw
        return self.optimistic_lamp_mode

    @property
    def lamp_brightness(self) -> int | None:
        """Return the lamp brightness (1-10), or None when unknown."""
        return self._int_state(STATE_LAMP_BRIGHTNESS, BRIGHTNESS_MIN, BRIGHTNESS_MAX)

    @property
    def lamp_color_temp(self) -> int | None:
        """Return the raw colour temperature (1..10), or None."""
        return self._int_state(STATE_LAMP_COLOR_TEMP, COLOUR_TEMP_MIN, COLOUR_TEMP_MAX)

    def _int_state(self, key: str, low: int, high: int) -> int | None:
        """Read an integer state key, clamped to its valid range."""
        raw = self.device_state.get(key)
        if raw is None or not self.state_feedback:
            return None
        try:
            return max(low, min(high, int(raw)))
        except (TypeError, ValueError):
            return None

    def set_optimistic_lamp(self, *, is_on: bool, mode: str | None = None) -> None:
        """Remember the last requested lamp state (degraded mode only)."""
        self.optimistic_lamp_on = is_on
        if is_on and mode is not None:
            self.optimistic_lamp_mode = mode
        self.notify()

    @property
    def projector_power(self) -> bool:
        """Return the best available projector power state."""
        channel = self.state_channel
        if channel is None or not getattr(channel, "ever_connected", False):
            return self.projector_is_on
        if not self.online:
            return False
        raw = self.device_state.get(STATE_PROJECTOR_SLEEP)
        if raw is None:
            return True
        return raw == STATE_PROJECTOR_SLEEP_ON

    async def async_refresh_device_state(self) -> None:
        """Re-send the state query so the state table is fresh."""
        channel = self.state_channel
        if channel is not None:
            await channel.async_refresh()

    def set_projector(self, is_on: bool) -> None:
        """Record the projector power state and refresh every entity."""
        self.projector_is_on = is_on
        self.notify()

    async def async_wait_projector_on(self, timeout: float) -> bool:
        """Poll the device state table until the projector reports itself on."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while loop.time() < deadline:
            await self.async_refresh_device_state()
            if self.online and self.projector_power:
                return True
            await asyncio.sleep(PROJECTOR_ON_POLL)
        return self.online and self.projector_power

    async def async_power_on(self) -> None:
        """Turn the projector on with the power key."""
        if self.projector_power:
            return

        if not self.online:
            raise XgimiConnectionError(
                f"Cannot power on the projector: the control service at {self.host} is"
                " unreachable"
            )

        result = await self.async_send(KeyCommand(code=KEY_CODES["power"]))
        if result.accepted is False:
            raise XgimiCommandRejected(
                result.message or "the device rejected the power key"
            )
        if await self.async_wait_projector_on(PROJECTOR_ON_TIMEOUT):
            _LOGGER.debug("Projector at %s turned on via the power key", self.host)
            return
        raise XgimiConnectionError(
            f"The power key did not turn the projector on: {self.host} still reports"
            " standby"
        )

    async def async_power_off(self) -> None:
        """Put the projector in standby with the explicit power-off frame."""
        result = await self.async_send(InvokeCommand(action=ACTION_POWER_OFF))
        if result.accepted is False:
            raise XgimiCommandRejected(
                result.message or "the device rejected the standby command"
            )

        loop = asyncio.get_running_loop()
        deadline = loop.time() + PROJECTOR_ON_TIMEOUT
        while loop.time() < deadline:
            await self.async_refresh_device_state()
            if not self.projector_power:
                return
            await asyncio.sleep(PROJECTOR_ON_POLL)
        self.set_projector(False)

    def set_selected_key(self, key: str) -> None:
        """Remember the key chosen in the picker."""
        self.selected_key = key
        self.notify()

    def set_last_command(self, command: str) -> None:
        """Remember the command that was sent last."""
        self.last_command = command
        self.notify()

    def set_last_media(self, source: str) -> None:
        """Remember the media that was sent last."""
        self.last_media = source
        self.notify()

    def set_last_screen_url(self, url: str) -> None:
        """Remember where the last capture can be opened without a token."""
        self.last_screen_url = url
        self.notify()

    def set_apps(self, apps: list[dict[str, str]]) -> None:
        """Remember the app list read from the device."""
        self.apps = apps
        if apps and self.selected_app not in self.app_names:
            self.selected_app = apps[0]["package"]
        self.notify()

    @property
    def app_names(self) -> list[str]:
        """Return the display names of the known apps."""
        return [app["name"] for app in self.apps]

    def app_package(self, name: str) -> str | None:
        """Return the package behind ``name``."""
        for app in self.apps:
            if app["name"] == name:
                return app["package"]
        return None

    def set_selected_app(self, package: str) -> None:
        """Remember the app chosen in the picker."""
        self.selected_app = package
        self.notify()

    def add_listener(self, listener: Callable[[], None]) -> None:
        """Register an entity that wants to be refreshed on state changes."""
        if listener not in self._listeners:
            self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[], None]) -> None:
        """Unregister a previously added entity listener."""
        if listener in self._listeners:
            self._listeners.remove(listener)

    def notify(self) -> None:
        """Ask every registered entity to write its state."""
        for listener in list(self._listeners):
            listener()
