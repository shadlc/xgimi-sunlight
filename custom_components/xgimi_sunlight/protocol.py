"""Wire protocol for the XGIMI Sunlight."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import struct
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

from .const import (
    ACTION_CONTROL,
    ACTION_CONTROL_ERROR,
    ACTION_CONTROL_OK,
    ACTION_KEY_EVENT,
    ACTION_LIGHT_PARAM,
    ACTION_LIGHT_QUERY,
    ACTION_STATE_PUSH,
    ACTION_VOLUME,
    APP_MODE,
    APP_TYPE_LIST,
    COMMAND_TIMEOUT,
    CONTROL_PORT,
    DEFAULT_DELAY_TIME,
    DEFAULT_MSGID,
    DEFAULT_TIME,
    DEFAULT_TYPE,
    KEY_EVENT_CLICK,
    KEY_EVENT_HOLD,
    KEY_EVENT_TYPE,
    MAX_STATE_FRAME,
    RESPONSE_PORT,
    SCREENSHOT_MODE,
    SCREENSHOT_TYPE,
    STATE_CONNECT_TIMEOUT,
    STATE_FRAME_MAGIC,
    STATE_PORT,
    STATE_QUERY_MSGID,
    STATE_RETRY_MAX,
    STATE_RETRY_MIN,
    TEXT_MODE,
)

_LOGGER = logging.getLogger(__name__)

STATE_PUSH_DEBOUNCE: Final = 0.15


@dataclass(frozen=True, slots=True)
class KeyCommand:
    """A remote key event."""

    code: int


@dataclass(frozen=True, slots=True)
class InvokeCommand:
    """A one-shot action such as ``power_off``."""

    action: int


@dataclass(frozen=True, slots=True)
class TextCommand:
    """A natural-language command for the device voice assistant."""

    data: str = ""
    mode: int = TEXT_MODE
    type: int = DEFAULT_TYPE
    delay_time: int = DEFAULT_DELAY_TIME
    time: int = DEFAULT_TIME


@dataclass(frozen=True, slots=True)
class ControlCommand:
    """A raw control frame with an explicit mode and type."""

    mode: int
    type: int = DEFAULT_TYPE
    data: str | None = None


@dataclass(frozen=True, slots=True)
class LightParamCommand:
    """A structured lamp write."""

    param: str
    value: str


@dataclass(frozen=True, slots=True)
class VolumeCommand:
    """An absolute volume write."""

    value: int


def volume(value: int) -> VolumeCommand:
    """Build an absolute volume write."""
    return VolumeCommand(value=int(value))


Command = (
    KeyCommand
    | InvokeCommand
    | TextCommand
    | ControlCommand
    | LightParamCommand
    | VolumeCommand
)


def light_param(param: str, value: str | int) -> LightParamCommand:
    """Build a structured lamp write."""
    return LightParamCommand(param=param, value=str(value))


def build_light_query(param: str, *, msgid: str = DEFAULT_MSGID) -> dict[str, Any]:
    """Build the frame that reads one lamp value."""
    return {
        "action": ACTION_LIGHT_QUERY,
        "commonCmd": {"type": param},
        "msgid": msgid,
    }


def build_screenshot_request(*, msgid: str = DEFAULT_MSGID) -> dict[str, Any]:
    """Build the frame that asks the device for a screen capture."""
    return {
        "action": ACTION_CONTROL,
        "controlCmd": {"mode": SCREENSHOT_MODE, "type": SCREENSHOT_TYPE},
        "msgid": msgid,
    }


def parse_screenshot_path(message: dict[str, Any] | None, host: str) -> str | None:
    """Return the image URL from a screenshot reply, with ``%s`` resolved."""
    if not isinstance(message, dict):
        return None
    path = message.get("imagePath")
    if not isinstance(path, str) or not path:
        return None
    return path.replace("%s", host)


def parse_light_query(response: dict[str, Any] | None) -> dict[str, str]:
    """Extract ``{key: value}`` from a lamp query reply."""
    if not isinstance(response, dict):
        return {}
    detail = response.get("featureDetailInfo")
    if not isinstance(detail, dict):
        return {}
    values: dict[str, str] = {}
    apply_state_entries(values, [detail])
    return values


def build_app_list_request(*, msgid: str = DEFAULT_MSGID) -> dict[str, Any]:
    """Build the frame that asks the device where its app list lives."""
    return {
        "action": ACTION_CONTROL,
        "controlCmd": {"mode": APP_MODE, "type": APP_TYPE_LIST},
        "msgid": msgid,
    }


def parse_app_list_path(message: dict[str, Any] | None, host: str) -> str | None:
    """Return the app list URL from an app list reply, with ``%s`` resolved."""
    if not isinstance(message, dict):
        return None
    path = message.get("imagePath")
    if not isinstance(path, str) or not path:
        return None
    return path.replace("%s", host)


class XgimiError(Exception):
    """Base error for the XGIMI protocol layer."""


class XgimiConnectionError(XgimiError):
    """The local UDP channel could not be created."""


class XgimiCommandRejected(XgimiError):
    """The device rejected the command."""

    def __init__(self, message: str) -> None:
        """Store the device supplied reason."""
        super().__init__(message)
        self.message = message


@dataclass(frozen=True, slots=True)
class SendResult:
    """Normalised outcome of a command."""

    accepted: bool | None
    message: str | None = None
    response: dict[str, Any] | None = None
    degraded: bool = False


def build_payload_dict(
    msgid: str, command: Command, *, hold: bool = False
) -> dict[str, Any]:
    """Return the JSON body for a command."""
    match command:
        case KeyCommand(code=code):
            event = KEY_EVENT_HOLD if hold else KEY_EVENT_CLICK
            return {
                "action": ACTION_KEY_EVENT,
                "commonCmd": {
                    "action": event,
                    "code": str(code),
                    "type": KEY_EVENT_TYPE,
                },
            }
        case InvokeCommand(action=action_id):
            return {"action": action_id}
        case TextCommand():
            return {
                "action": ACTION_CONTROL,
                "controlCmd": {
                    "data": command.data,
                    "delayTime": command.delay_time,
                    "mode": command.mode,
                    "time": command.time,
                    "type": command.type,
                },
                "msgid": msgid,
            }
        case ControlCommand():
            control: dict[str, Any] = {"mode": command.mode, "type": command.type}
            if command.data is not None:
                control["data"] = command.data
                control["delayTime"] = DEFAULT_DELAY_TIME
                control["time"] = DEFAULT_TIME
            return {"action": ACTION_CONTROL, "controlCmd": control, "msgid": msgid}
        case LightParamCommand(param=param, value=value):
            return {
                "action": ACTION_LIGHT_PARAM,
                "commonCmd": {"type": param, "value": value},
                "msgid": msgid,
            }
        case VolumeCommand(value=level):
            return {
                "action": ACTION_VOLUME,
                "commonCmd": {"volume": str(level)},
                "msgid": msgid,
            }
        case _:  # pragma: no cover - exhaustive
            raise XgimiError(f"unsupported command {command!r}")


def encode_command(msgid: str, command: Command, *, hold: bool = False) -> bytes:
    """Serialise a command into the device wire format."""
    return json.dumps(
        build_payload_dict(msgid, command, hold=hold), ensure_ascii=False
    ).encode("utf-8")


def reply_actions(command: Command) -> tuple[int, ...]:
    """Return the actions the device answers a command with."""
    match command:
        case KeyCommand():
            return (ACTION_KEY_EVENT,)
        case InvokeCommand(action=action_id):
            return (action_id,)
        case LightParamCommand():
            return (ACTION_LIGHT_PARAM,)
        case VolumeCommand():
            return (ACTION_VOLUME,)
        case TextCommand() | ControlCommand():
            return (ACTION_CONTROL_OK, ACTION_CONTROL_ERROR)
        case _:  # pragma: no cover - exhaustive
            return ()


def interpret_response(response: dict[str, Any] | None) -> SendResult:
    """Normalise a device response into a :class:`SendResult`."""
    if response is None:
        return SendResult(accepted=None)

    action = response.get("action")

    if action == ACTION_CONTROL_OK:
        return SendResult(accepted=True, response=response)

    if action == ACTION_CONTROL_ERROR:
        extra = response.get("extraInfo") or {}
        message = extra.get("message") or "unknown error"
        return SendResult(accepted=False, message=message, response=response)

    status = response.get("status") or {}
    state = status.get("state")
    if state is not None:
        accepted = state == 1
        return SendResult(
            accepted=accepted,
            message=None if accepted else f"device status {state}",
            response=response,
        )

    return SendResult(accepted=None, response=response)


class _XgimiDatagramProtocol(asyncio.DatagramProtocol):
    """Forward every datagram to the owning client."""

    def __init__(self, client: XgimiUdpClient) -> None:
        self._client = client

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self._client._handle_datagram(data, addr)

    def error_received(self, exc: Exception) -> None:
        _LOGGER.debug("UDP error (device may be offline): %s", exc)


class XgimiUdpClient:
    """UDP client for a single device."""

    def __init__(
        self,
        host: str,
        *,
        control_port: int = CONTROL_PORT,
        response_port: int = RESPONSE_PORT,
        msgid: str = DEFAULT_MSGID,
        prefer_response_port: bool = True,
    ) -> None:
        """Initialise the client (no I/O happens here)."""
        self.host = host
        self.control_port = control_port
        self.response_port = response_port
        self.msgid = msgid
        self.prefer_response_port = prefer_response_port

        self._transport: asyncio.DatagramTransport | None = None
        self._local_port: int | None = None
        self._lock = asyncio.Lock()

        self._pending_msgid: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._pending_action: dict[int, asyncio.Future[dict[str, Any]]] = {}

        self.last_response: dict[str, Any] | None = None
        self.state: dict[str, str] = {}
        self._last_announced: dict[str, str] = {}
        self._state_callbacks: list[Callable[[], None]] = []
        self._flush_handle: asyncio.TimerHandle | None = None

    @property
    def local_port(self) -> int | None:
        """Return the bound local port."""
        return self._local_port

    @property
    def connected(self) -> bool:
        """Return whether the local UDP channel is ready."""
        return self._transport is not None

    @property
    def can_receive(self) -> bool:
        """Return whether replies and state pushes can be received."""
        return self._local_port == self.response_port

    async def async_start(self) -> None:
        """Open the UDP channel (idempotent)."""
        if self._transport is not None:
            return

        loop = asyncio.get_running_loop()
        last_error: Exception | None = None

        candidates = (self.response_port, 0) if self.prefer_response_port else (0,)

        for port in candidates:
            try:
                transport, _ = await loop.create_datagram_endpoint(
                    lambda: _XgimiDatagramProtocol(self),
                    local_addr=("0.0.0.0", port),
                )
            except OSError as err:
                last_error = err
                _LOGGER.debug("Could not bind UDP port %s: %s", port, err)
                continue

            self._transport = transport  # type: ignore[assignment]
            self._local_port = port or transport.get_extra_info("sockname")[1]
            if port:
                _LOGGER.debug(
                    "UDP ready on local %s -> %s:%s (replies enabled)",
                    self._local_port,
                    self.host,
                    self.control_port,
                )
            else:
                _LOGGER.warning(
                    "UDP port %s is unavailable; command replies are disabled and "
                    "commands cannot be confirmed",
                    self.response_port,
                )
            return

        raise XgimiConnectionError(
            f"unable to open a UDP channel for {self.host}"
        ) from last_error

    async def async_stop(self) -> None:
        """Close the channel and drop any pending waiters."""
        if self._flush_handle is not None:
            self._flush_handle.cancel()
            self._flush_handle = None
        if self._transport is not None:
            self._transport.close()
            self._transport = None
        for future in (*self._pending_msgid.values(), *self._pending_action.values()):
            if not future.done():
                future.cancel()
        self._pending_msgid.clear()
        self._pending_action.clear()
        self._local_port = None

    def build_payload(self, command: Command, *, hold: bool = False) -> bytes:
        """Serialise a command into the device wire format."""
        return encode_command(self.msgid, command, hold=hold)

    def build_payload_dict(
        self, command: Command, *, hold: bool = False
    ) -> dict[str, Any]:
        """Return the command as a JSON-ready mapping."""
        return build_payload_dict(self.msgid, command, hold=hold)

    async def async_send(
        self,
        command: Command,
        *,
        hold: bool = False,
        wait_response: bool = False,
        timeout: float = COMMAND_TIMEOUT,
    ) -> SendResult:
        """Send a command, optionally waiting for and normalising the reply."""
        async with self._lock:
            await self.async_start()
            assert self._transport is not None

            payload = self.build_payload(command, hold=hold)
            future = self._register_waiter(command, wait_response)

            try:
                self._transport.sendto(payload, (self.host, self.control_port))
            except OSError as err:
                self._discard_waiter(command)
                raise XgimiError(
                    f"failed to send {payload!r} to {self.host}: {err}"
                ) from err

            _LOGGER.debug("Sent to %s:%s: %s", self.host, self.control_port, payload)

            if future is None:
                return SendResult(accepted=None, degraded=not self.can_receive)

            try:
                response = await asyncio.wait_for(future, timeout)
            except TimeoutError:
                _LOGGER.debug("No reply for %s within %.1fs", payload, timeout)
                return SendResult(accepted=None, degraded=not self.can_receive)
            finally:
                self._discard_waiter(command)

            result = interpret_response(response)
            return SendResult(
                accepted=result.accepted,
                message=result.message,
                response=result.response,
                degraded=not self.can_receive,
            )

    def _register_waiter(
        self, command: Command, wait_response: bool
    ) -> asyncio.Future[dict[str, Any]] | None:
        """Create the future a reply will resolve, if one is wanted."""
        if not wait_response or not self.can_receive:
            return None

        future: asyncio.Future[dict[str, Any]] = (
            asyncio.get_running_loop().create_future()
        )
        if isinstance(command, TextCommand | ControlCommand):
            self._pending_msgid[self.msgid] = future
        elif isinstance(command, LightParamCommand):
            self._pending_action[ACTION_LIGHT_PARAM] = future
        elif isinstance(command, VolumeCommand):
            self._pending_action[ACTION_VOLUME] = future
        elif isinstance(command, KeyCommand | InvokeCommand):
            key = (
                ACTION_KEY_EVENT if isinstance(command, KeyCommand) else command.action
            )
            self._pending_action[key] = future
        return future

    def _discard_waiter(self, command: Command) -> None:
        """Remove a waiter regardless of outcome."""
        if isinstance(command, TextCommand | ControlCommand):
            self._pending_msgid.pop(self.msgid, None)
        elif isinstance(command, LightParamCommand):
            self._pending_action.pop(ACTION_LIGHT_PARAM, None)
        elif isinstance(command, VolumeCommand):
            self._pending_action.pop(ACTION_VOLUME, None)
        elif isinstance(command, KeyCommand):
            self._pending_action.pop(ACTION_KEY_EVENT, None)
        elif isinstance(command, InvokeCommand):
            self._pending_action.pop(command.action, None)

    async def async_query_light(
        self,
        param: str,
        *,
        timeout: float = COMMAND_TIMEOUT,
    ) -> dict[str, str] | None:
        """Read one lamp value."""
        if not self.can_receive:
            return None

        async with self._lock:
            await self.async_start()
            assert self._transport is not None

            payload = build_light_query(param, msgid=self.msgid)
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            future: asyncio.Future[dict[str, Any]] = (
                asyncio.get_running_loop().create_future()
            )
            self._pending_action[ACTION_LIGHT_QUERY] = future
            try:
                self._transport.sendto(body, (self.host, self.control_port))
                _LOGGER.debug("Query %s -> %s:%s", param, self.host, self.control_port)
                response = await asyncio.wait_for(future, timeout)
            except TimeoutError:
                _LOGGER.debug("No reply for lamp query type=%s", param)
                return None
            except OSError as err:
                _LOGGER.debug("Lamp query failed: %s", err)
                return None
            finally:
                self._pending_action.pop(ACTION_LIGHT_QUERY, None)

            values = parse_light_query(response)
            return values or None

    def _handle_datagram(self, data: bytes, addr: tuple[str, int]) -> None:
        """Decode a datagram and route it."""
        try:
            message = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            _LOGGER.debug("Non-JSON datagram from %s: %r", addr, data)
            return

        if not isinstance(message, dict):
            _LOGGER.debug("Unexpected datagram from %s: %r", addr, message)
            return

        self.last_response = message
        action = message.get("action")

        if action == ACTION_STATE_PUSH:
            self._handle_state_push(message)
            return

        if action == ACTION_CONTROL_OK:
            self._resolve(
                self._pending_msgid.get(str(message.get("msgid", ""))), message
            )
            return

        if action == ACTION_CONTROL_ERROR:
            self._resolve(
                self._pending_msgid.get(str(message.get("msgid", ""))), message
            )
            return

        if isinstance(action, int):
            self._resolve(self._pending_action.get(action), message)
            return

        _LOGGER.debug("Ignoring datagram with unknown action: %s", message)

    @staticmethod
    def _resolve(
        future: asyncio.Future[dict[str, Any]] | None, message: dict[str, Any]
    ) -> None:
        """Complete a waiter if it is still pending."""
        if future is not None and not future.done():
            future.set_result(message)

    def _handle_state_push(self, message: dict[str, Any]) -> None:
        """Store pushed state, ignoring the device's retransmissions."""
        _LOGGER.debug("State push: %s", message)
        info = message.get("deviceStateInfo") or {}
        changed = apply_state_entries(self.state, info.get("state"))
        if not changed:
            return

        fresh = {
            key: value
            for key, value in changed.items()
            if self._last_announced.get(key) != value
        }
        if not fresh:
            return

        self._last_announced.update(fresh)
        _LOGGER.debug("State changed: %s", fresh)
        self._schedule_state_callback()

    def _schedule_state_callback(self) -> None:
        """Coalesce bursts of state pushes into one callback."""
        if self._flush_handle is not None:
            self._flush_handle.cancel()
        loop = asyncio.get_running_loop()
        self._flush_handle = loop.call_later(
            STATE_PUSH_DEBOUNCE, self._fire_state_callbacks
        )

    def _fire_state_callbacks(self) -> None:
        """Invoke registered state listeners."""
        self._flush_handle = None
        for callback in list(self._state_callbacks):
            try:
                callback()
            except Exception:
                _LOGGER.exception("Error in state listener")

    def register_state_callback(self, callback: Callable[[], None]) -> None:
        """Register a listener called when pushed state changes."""
        if callback not in self._state_callbacks:
            self._state_callbacks.append(callback)

    def remove_state_callback(self, callback: Callable[[], None]) -> None:
        """Remove a previously registered listener."""
        if callback in self._state_callbacks:
            self._state_callbacks.remove(callback)


def encode_state_frame(payload: dict[str, Any]) -> bytes:
    """Wrap ``payload`` in the device's TCP frame header."""
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return STATE_FRAME_MAGIC + struct.pack(">i", len(raw)) + raw


def build_state_query(msgid: str = STATE_QUERY_MSGID) -> dict[str, Any]:
    """Return the status query that also subscribes the TCP connection."""
    return {"action": ACTION_STATE_PUSH, "msgid": msgid}


def decode_state_frames(buffer: bytes) -> tuple[list[dict[str, Any]], bytes]:
    """Split every complete frame out of ``buffer``."""
    messages: list[dict[str, Any]] = []

    while True:
        index = buffer.find(STATE_FRAME_MAGIC)
        if index < 0:
            keep = len(STATE_FRAME_MAGIC) - 1
            return messages, buffer[-keep:] if len(buffer) > keep else buffer
        if index:
            buffer = buffer[index:]

        header_end = len(STATE_FRAME_MAGIC) + 4
        if len(buffer) < header_end:
            return messages, buffer

        (length,) = struct.unpack(">i", buffer[len(STATE_FRAME_MAGIC) : header_end])
        if not 0 < length <= MAX_STATE_FRAME:
            _LOGGER.debug("Dropping TCP frame with invalid length %s", length)
            buffer = buffer[len(STATE_FRAME_MAGIC) :]
            continue

        frame_end = header_end + length
        if len(buffer) < frame_end:
            return messages, buffer

        raw = buffer[header_end:frame_end]
        buffer = buffer[frame_end:]

        try:
            message = json.loads(raw.decode("utf-8").strip())
        except (UnicodeDecodeError, json.JSONDecodeError):
            _LOGGER.debug("Dropping malformed TCP frame: %r", raw[:120])
            continue
        if isinstance(message, dict):
            messages.append(message)

    return messages, buffer


def apply_state_entries(target: dict[str, str], entries: Any) -> dict[str, str]:
    """Fold a state array into ``target``."""
    changed: dict[str, str] = {}
    if not isinstance(entries, list):
        return changed

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        key = entry.get("key")
        if not isinstance(key, str):
            continue
        value = entry.get("value")
        if value is None:
            value = entry.get("curChildItem")
        if value is None:
            continue
        value = str(value)
        if target.get(key) != value:
            changed[key] = value
        target[key] = value

    return changed


class XgimiStateChannel:
    """Persistent connection that delivers device state."""

    def __init__(
        self,
        host: str,
        *,
        port: int = STATE_PORT,
        connect_timeout: float = STATE_CONNECT_TIMEOUT,
        retry_min: float = STATE_RETRY_MIN,
        retry_max: float = STATE_RETRY_MAX,
    ) -> None:
        """Initialise the channel (no I/O happens here)."""
        self.host = host
        self.port = port
        self.connect_timeout = connect_timeout
        self.retry_min = retry_min
        self.retry_max = retry_max

        self.state: dict[str, str] = {}
        self.last_message: dict[str, Any] | None = None

        self._task: asyncio.Task[None] | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._buffer = b""
        self._connected = False
        self._ever_connected = False
        self._closing = False
        self._callbacks: list[Callable[[], None]] = []
        self._connect_callbacks: list[Callable[[], None]] = []
        self._last_announced: dict[str, str] = {}
        self._flush_handle: asyncio.TimerHandle | None = None
        self._waiters: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._collect_action: int | None = None
        self._collected: list[dict[str, Any]] = []

    @property
    def connected(self) -> bool:
        """Return whether the TCP state channel is currently open."""
        return self._connected

    @property
    def ever_connected(self) -> bool:
        """Return whether the channel has been up at least once."""
        return self._ever_connected

    async def async_start(self) -> None:
        """Start the background connector (idempotent)."""
        if self._task is not None:
            return
        self._closing = False
        self._task = asyncio.create_task(self._run(), name=f"xgimi-state-{self.host}")

    async def async_stop(self) -> None:
        """Cancel the connector and close the socket."""
        self._closing = True
        if self._flush_handle is not None:
            self._flush_handle.cancel()
            self._flush_handle = None

        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task

        self._close_writer()
        self._connected = False

    def _close_writer(self) -> None:
        """Close the stream without blocking."""
        writer, self._writer = self._writer, None
        if writer is not None:
            with contextlib.suppress(RuntimeError, OSError):
                writer.close()

    async def _run(self) -> None:
        """Connect, subscribe, read frames, reconnect forever."""
        delay = self.retry_min
        while not self._closing:
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port),
                    self.connect_timeout,
                )
            except (OSError, TimeoutError) as err:
                _LOGGER.debug("State channel to %s unavailable: %s", self.host, err)
                await asyncio.sleep(delay)
                delay = min(delay * 2, self.retry_max)
                continue

            self._writer = writer
            self._connected = True
            self._ever_connected = True
            self._buffer = b""
            delay = self.retry_min
            _LOGGER.debug("State channel connected to %s:%s", self.host, self.port)
            self._schedule_callback()
            self._fire_connect()

            try:
                writer.write(encode_state_frame(build_state_query()))
                await writer.drain()
                while not self._closing:
                    chunk = await reader.read(65536)
                    if not chunk:
                        _LOGGER.debug("State channel closed by %s", self.host)
                        break
                    self._buffer += chunk
                    messages, self._buffer = decode_state_frames(self._buffer)
                    for message in messages:
                        self._handle_message(message)
            except (OSError, TimeoutError) as err:
                _LOGGER.debug("State channel error: %s", err)
            except asyncio.CancelledError:
                self._close_writer()
                self._connected = False
                raise
            finally:
                self._close_writer()
                if self._connected:
                    self._connected = False
                    self._schedule_callback()

            if self._closing:
                return
            await asyncio.sleep(delay)

    async def async_refresh(self) -> bool:
        """Re-send the state query on the live connection."""
        writer = self._writer
        if writer is None or not self._connected:
            return False
        try:
            writer.write(encode_state_frame(build_state_query()))
            await writer.drain()
        except (OSError, TimeoutError) as err:
            _LOGGER.debug("State query to %s failed: %s", self.host, err)
            return False
        return True

    async def async_request(
        self,
        payload: dict[str, Any],
        action: int | tuple[int, ...],
        *,
        timeout: float,
    ) -> dict[str, Any] | None:
        """Send one frame and wait for the reply whose ``action`` matches."""
        writer = self._writer
        if writer is None or not self._connected:
            return None

        actions = (action,) if isinstance(action, int) else action
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        previous = {item: self._waiters.get(item) for item in actions}
        for item in actions:
            self._waiters[item] = future
        try:
            writer.write(encode_state_frame(payload))
            await writer.drain()
            return await asyncio.wait_for(future, timeout)
        except TimeoutError:
            _LOGGER.debug("No reply for action %s from %s", actions, self.host)
            return None
        except (OSError, RuntimeError) as err:
            _LOGGER.debug("Request %s to %s failed: %s", actions, self.host, err)
            return None
        finally:
            for item in actions:
                if self._waiters.get(item) is not future:
                    continue
                if previous[item] is None:
                    self._waiters.pop(item, None)
                else:
                    self._waiters[item] = previous[item]

    async def async_collect(
        self,
        payloads: list[dict[str, Any]],
        action: int,
        *,
        timeout: float,
    ) -> list[dict[str, Any]]:
        """Send frames at once and return every reply with `action`."""
        writer = self._writer
        if writer is None or not self._connected:
            return []

        self._collect_action = action
        self._collected = []
        try:
            for payload in payloads:
                writer.write(encode_state_frame(payload))
            await writer.drain()
            await asyncio.sleep(timeout)
            return list(self._collected)
        except OSError:
            return list(self._collected)
        finally:
            self._collect_action = None
            self._collected = []

    def _handle_message(self, message: dict[str, Any]) -> None:
        """Apply one decoded frame."""
        self.last_message = message
        action = message.get("action")
        if action == self._collect_action:
            self._collected.append(message)
            return

        waiter = self._waiters.get(action) if isinstance(action, int) else None
        if waiter is not None and not waiter.done():
            waiter.set_result(message)
            return

        if action == ACTION_LIGHT_QUERY:
            changed_values = apply_state_entries(
                self.state, [message.get("featureDetailInfo") or {}]
            )
            if changed_values:
                self._schedule_callback()
            return

        if action != ACTION_STATE_PUSH:
            _LOGGER.debug("State channel ignored frame: %s", message)
            return

        info = message.get("deviceStateInfo") or {}
        changed = apply_state_entries(self.state, info.get("state"))
        if not changed:
            return

        fresh = {
            key: value
            for key, value in changed.items()
            if self._last_announced.get(key) != value
        }
        if not fresh:
            return

        self._last_announced.update(fresh)
        _LOGGER.debug("State channel change: %s", fresh)
        self._schedule_callback()

    def register_callback(self, callback: Callable[[], None]) -> None:
        """Register a listener called when state or connectivity changes."""
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[], None]) -> None:
        """Remove a previously registered listener."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def _schedule_callback(self) -> None:
        """Coalesce bursts of frames into a single listener call."""
        if self._flush_handle is not None:
            self._flush_handle.cancel()
        loop = asyncio.get_running_loop()
        self._flush_handle = loop.call_later(STATE_PUSH_DEBOUNCE, self._fire)

    def _fire(self) -> None:
        """Invoke every registered listener."""
        self._flush_handle = None
        for callback in list(self._callbacks):
            try:
                callback()
            except Exception:
                _LOGGER.exception("Error in state channel listener")

    def register_connect_callback(self, callback: Callable[[], None]) -> None:
        """Register a listener called each time the TCP channel connects."""
        if callback not in self._connect_callbacks:
            self._connect_callbacks.append(callback)

    def remove_connect_callback(self, callback: Callable[[], None]) -> None:
        """Remove a previously registered connect listener."""
        if callback in self._connect_callbacks:
            self._connect_callbacks.remove(callback)

    def _fire_connect(self) -> None:
        """Invoke every connect listener."""
        for callback in list(self._connect_callbacks):
            try:
                callback()
            except Exception:
                _LOGGER.exception("Error in state channel connect listener")


def key(name_or_code: str | int) -> KeyCommand:
    """Build a :class:`KeyCommand` from a key name or a raw code."""
    from .const import KEY_CODES

    if isinstance(name_or_code, int):
        return KeyCommand(code=name_or_code)
    try:
        return KeyCommand(code=KEY_CODES[name_or_code])
    except KeyError as err:
        raise XgimiError(f"unknown key {name_or_code!r}") from err


def text(data: str) -> TextCommand:
    """Build a natural-language command for the voice assistant."""
    return TextCommand(data=data)
