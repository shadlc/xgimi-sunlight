# XGIMI Sunlight protocol reference

Local control protocol of the XGIMI Sunlight ceiling lamp and projector. Values were measured
on a real device (`deviceStateInfo.apiVersion = 1.0.4`); actions marked unverified in the
tables are app constants only. App class names are cited where they explain a frame.

**English** | [简体中文](PROTOCOL.zh-Hans.md)

> Unofficial interface. XGIMI does not publish this protocol and firmware updates may change
> it.

---

## 1. Transports

Commands travel on TCP 13145 and fall back to UDP 16750. State travels on TCP 13145 only
(section 7).

| Item | Value |
| --- | --- |
| Command transport | UDP 16750, no handshake, no authentication |
| Reply target | `controller:16751`, fixed, independent of the source port |
| State transport | TCP `device:13145`, length-prefixed frames (section 7) |
| Encoding | UTF-8 JSON; non-ASCII text is literal, not `\uXXXX` |
| ICMP | No port-unreachable is sent, so `connect()` cannot probe the device |
| Image display | DLNA MediaRenderer on a dynamic TCP port found over SSDP (section 8) |

### Binding and socket rules

- Bind 16751 to receive replies. Any source port executes the command, but only 16751 receives
  the reply; the integration binds it exclusively.
- Do not `connect()` the UDP socket. Replies originate from random ephemeral ports (58501,
  33961, …) and a connected socket lets the kernel drop them.

---

## 2. Requests

### 2.1 Key events

```json
{"action":50036,"commonCmd":{"action":"3","code":"11","type":"inst"}}
```

| Field | Type | Meaning |
| --- | --- | --- |
| `action` | int | Always `50036` |
| `commonCmd.action` | str | `"3"` click, `"1"` long press (one frame per press, no auto-repeat) |
| `commonCmd.code` | str | Key code (section 5.1) |
| `commonCmd.type` | str | Always `"inst"` |

### 2.2 One-shot actions

```json
{"action":50021}
```

`action` is the action id (section 5.2).

### 2.3 Text / voice assistant

```json
{"action":20000,"controlCmd":{"data":"音量调到 50%","delayTime":0,"mode":5,"time":0,"type":0},"msgid":"2"}
```

| Field | Type | Meaning |
| --- | --- | --- |
| `controlCmd.data` | str | Natural-language instruction; Chinese is accepted |
| `controlCmd.delayTime` | int | `0` |
| `controlCmd.mode` | int | `5`, text channel |
| `controlCmd.time` | int | `0` |
| `controlCmd.type` | int | `0` |
| `msgid` | str | `"2"`, a string |

`data` is parsed by the device voice assistant. It reaches behaviour that is not modelled here
("音量调到 50%") but depends on semantic parsing, so it is unsuitable for power control.

Variant: `clean_memory` uses `mode:9, type:2` with no `data`.

---

## 3. Responses

| `action` | Meaning | Key fields |
| --- | --- | --- |
| `20001` | Text command succeeded | `msgid` echo, `agreement` |
| `20002` | Text command failed | `extraInfo.message` (observed `"未知错误"`) |
| `5xxxx` | Key/action echo | `status.state` (`1` accepted) |
| `50023` | State push or query reply | `deviceStateInfo.state[]` |

### Success

```json
{"action":20001,"endScreenCapTime":0,"msgid":"2","startScreenCapTime":0,"type":0,
 "agreement":{"agreementType":0,"isTcp":true,"msgId":"2","phoneIp":"192.168.1.10","port":13145}}
```

### Key/action echo

```json
{"action":50036,"msgid":"0","status":{"state":1},"type":0,"agreement":{...}}
{"action":50021,"msgid":"0","status":{"state":1},"type":0,"agreement":{...}}
```

### State push

```json
{"action":50023,"deviceStateInfo":{"apiVersion":"1.0.4",
  "state":[{"curChildItem":"6","key":"ceilingLampMode"}]},"msgId":0,
 "agreement":{"agreementType":2,"isTcp":true,"port":13145}}
```

Pushes are delivered on TCP 13145 only; an integration that binds 16751 alone receives no
state.

### State query (subscribe)

`{"action":50023,"msgid":"70002"}` returns the full state table and subscribes the connection:
later changes arrive as individual `50023` frames.

```json
{"action":50023,"deviceStateInfo":{"apiVersion":"1.0.4","state":[
  {"key":"lightSwitch","value":"1"},
  {"curChildItem":"6","key":"ceilingLampMode"}]},
 "msgId":1795279299763,"agreement":{"agreementType":2,"isTcp":true,"port":13145}}
```

Value position differs per key: `lightSwitch` uses `value`, `ceilingLampMode` uses
`curChildItem`.

---

## 4. State keys

Lamp state is complete. The projector exposes system keys only and no power flag of its own
(4.2).

### 4.1 Lamp (`50023` pushes, on change)

| Key | Meaning | Value position | Values |
| --- | --- | --- | --- |
| `lightSwitch` | Lamp power | `value` | `"0"` off, `"1"` on |
| `ceilingLampMode` | Lamp mode | `curChildItem` | `"0"` custom, `"1"` rhythm, `"6"` daylight, `"10"` movie |
| `lightBrightness` | Brightness | `value` | `1`…`10` |
| `lightColorTemp` | Colour temperature | `value` | `1` warmest (≈2700 K) … `10` coolest (≈6500 K) |

### 4.2 System keys (only in the `50023` query reply)

About twelve keys return, including:

| Key | Observed | Meaning |
| --- | --- | --- |
| `VOLUME_SYSTEM_UI` | `"14"` | System volume |
| `SHUT_SCREEN_SYSTEM_UI` | `"4"` / `"3"` | Light engine: `4` picture on, `3` off |
| `POWER_SLEEP_SYSTEM_UI` | `"1"` / `"0"` | Projector power: `1` running, `0` standby (lamp still online) |
| `POWER_OFF_SYSTEM_UI` | `"1"` | Constant `1`, not a power state |
| `TIME_POWER_OFF_SYSTEM_UI` | `"-1"` | Scheduled power off, `-1` unset |
| `SEND_COUNT_DOWN_MINUTE_TIME_SYSTEM_UI` | `"-1"` | Countdown |
| `CONFIG_KEY_SUPPORT_FEATURE_LIST`, `CONFIG_KEY_RESOLUTION_AND_FPS` | — | Casting capabilities |
| `MODE_SCREEN_SAVER`, `VIDEO_HISTORY_LIST_HOME`, `IMMERSED_HEALTHY`, `image` | — | Screensaver, history, immersive scene |

The remaining keys carry long JSON blobs for `com.xgimi.atmosphere` (screensaver) and
`com.xgimi.home.immersed`.

### 4.3 Structured light API

All four lamp parameters share one action, selected by the numeric `commonCmd.type`
(`com.xgimi.zhushou.devices.cp02light.Cp02LightUtil`):

```
write: {"action":50041,"commonCmd":{"type":"<0..3>","value":"<n>"},"msgid":"2"}
read:  {"action":50040,"commonCmd":{"type":"<0..3>"},"msgid":"70002"}
```

| `type` | Parameter | Range | State key |
| --- | --- | --- | --- |
| `"0"` | Power | `"0"` / `"1"` | `lightSwitch` |
| `"1"` | Colour temperature | `1`…`10` | `lightColorTemp` |
| `"2"` | Brightness | `1`…`10` | `lightBrightness` |
| `"3"` | Mode | `"0"`/`"1"`/`"6"`/`"10"` | `ceilingLampMode` |

Read replies, verbatim:

```json
{"action":50040,"featureDetailInfo":{"key":"lightSwitch","value":"1"},"msgid":"0","type":0,"agreement":{...}}
{"action":50040,"featureDetailInfo":{"curChildItem":"6","key":"ceilingLampMode"},"msgid":"0","type":3,"agreement":{...}}
```

Power, brightness and colour temperature are in `value`; mode is in `curChildItem`, matching
the `50023` split.

Behaviour:

- All four parameters read back exactly (`lightBrightness` and `lightColorTemp` verified at
  1/5/10).
- Integers only. `2.5` or `5.5` is ignored with no ACK and no change; `5` or `6` applies
  immediately.
- Writing brightness or colour temperature moves the lamp to mode `0` (custom).
- Without `commonCmd.type` the device returns an empty `20001` and does nothing.
- The integration queries `0→2→1→3` at start-up and after every TCP reconnect, because the
  subscription reply carries no lamp keys.

### 4.4 Delivery

- One frame per change over TCP. Query replies and pushes may repeat a value; de-duplicate.
- Event driven. `50023` appears only on change or on query. A command matching the current
  state returns `20001` and pushes nothing.

---

## 5. Command tables

### 5.1 Keys (`action:50036`)

| Name | Code | Name | Code |
| --- | --- | --- | --- |
| `left` | 1 | `home` | 8 |
| `right` | 2 | `volume_up` | 9 |
| `up` | 3 | `volume_down` | 10 |
| `down` | 4 | `power` (toggle) | 11 |
| `ok` | 5 | `settings` | 12 |
| `back` | 6 | `auto_focus` | 14 |
| `menu` | 7 | `screenshot` | 120 |
| `power_menu` | 131 | | |

### 5.2 One-shot actions

| `action` | Function | Verified |
| --- | --- | --- |
| `50021` | Power off (explicit, `OPEN_DORMANT`) | yes |
| `50040` | Read a lamp parameter (`commonCmd.type`) | yes |
| `50041` | Write a lamp parameter (`commonCmd.type` + `value`) | yes |
| `50004` | Music mode | no |
| `50008` | Manual focus | no |
| `50012` | Mute | no |
| `50015` | Screen off | yes |
| `50029` | Reboot | no |
| `50030` | Check for updates | no |

`action` constants from the app's `VcontrolCmd` field initialisers: `50005` auto karaoke,
`50006` projection mode, `50007` switch HDMI, `50009` volume, `50013` quit karaoke, `50014`
sound mode, `50016` brightness mode, `50017` brightness value, `50018/50019/50020` red/green/
blue brightness, `50025` image mode, `50026` 3D mode, `50027` login, `50028` auto KST, `50031`
zoom UI, `50032/50033/50034` curtain open/pause/close, `50035` history playback, `50042` VIP
info.

---

## 6. Projector power

| State | `POWER_SLEEP_SYSTEM_UI` | `SHUT_SCREEN_SYSTEM_UI` | Network |
| --- | --- | --- | --- |
| Running | `"1"` | `"4"` | UDP 16750 and TCP 13145 open |
| Standby, lamp powered | `"0"` | `"3"` | TCP 13145 open |
| Off | — | — | every port closed, ICMP only |

`POWER_SLEEP_SYSTEM_UI` is the power flag: `"1"` means the projector is running, `"0"` means
standby while the lamp stays powered. `SHUT_SCREEN_SYSTEM_UI` describes the light engine
instead, `"4"` for a picture and `"3"` for a dark engine, and is not a power flag.

A device that is off accepts no command and answers ICMP only, so it must be switched on from
the remote or the app before the network interface responds.

- Power off: `50021`, explicit and idempotent.
- Power on: one `power` key press from standby, `50036` with code `11`. The key toggles, so
  read `POWER_SLEEP_SYSTEM_UI` first and send it only while the value is `"0"`.
- Refresh: the flag is not pushed when power changes. Re-send the `50023` query and read the
  value again.

---

## 7. TCP 13145 (state channel)

Every response carries `agreement: {"isTcp":true,"port":13145}`. Frame format
(`com.xgimi.control.connect.protocol.ProtocolFactory`):

```
FF FF E0 4A | int32 big-endian payload length | UTF-8 JSON (device frames end with \n)
```

Handshake:

1. Connect to `device:13145`.
2. Send `{"action":50023,"msgid":"70002"}` (`msgid` is always `70002`).
3. The connection then receives `50023` pushes.

| Step | Result |
| --- | --- |
| Raw JSON written to TCP | no response; the header is mandatory |
| Framed `50023` query | full state table |
| After a UDP lamp command | matching `50023` push on the open connection |

A connected port only means the control service is up: with the lamp on it stays open during
projector standby. Power state comes from `POWER_SLEEP_SYSTEM_UI`.

The subscription reply carries no lamp state: the `50023` query returns the twelve system keys
even with the lamp on (`lightSwitch` / `ceilingLampMode` absent). Lamp state arrives only as
change pushes, so after a Home Assistant restart the switch entities restore the last known
state from `RestoreEntity` until the device changes something.

### 7.1 Other ports (scanned; none is an entry point)

| Port | Finding |
| --- | --- |
| 53 | working DNS server |
| 1414 / 1182 / 1288 | UPnP/DLNA MediaRenderer (Platinum/1.0.5.13); port varies across restarts |
| 7001 / 7002 / 7100 | AirPlay / RAOP (`AirTunes/220.68`) |
| 8080 | accepts a connection, answers nothing, closes it |
| 10100 | HTTP JSON API requiring a signature: `{"status":-1,"message":"Vertify Failed!"}` |
| 16741 | File server: `200 image/jpeg` for a real path, empty `200` otherwise (section 9) |
| 12584 | sends `b'\x03tt'` on connect, purpose unknown |
| 12583 / 12585 / 15735 / 15737 | no banner |

---

## 8. Media playback (DLNA renderer, dynamic port)

The device is a Platinum UPnP MediaRenderer, so pictures, video and audio are pushed over
standard UPnP without the vendor channel.

The renderer's HTTP port is not fixed; 1414, 1182 and 1288 were observed across restarts.
Discover it every time:

```
unicast UDP M-SEARCH -> <device>:1900
  HOST: <device>:1900, MAN: "ssdp:discover", MX: 2,
  ST: urn:schemas-upnp-org:device:MediaRenderer:1
reply header: LOCATION: http://<device>:<port>/
```

Multicast SSDP is often filtered, but a unicast search to the device address is answered
(`Server: UPnP/1.0 DLNADOC/1.50 Platinum/1.0.5.13`, `USN: uuid:<MAC>-dmr::...`). `GET` the
`LOCATION` URL for the description: `friendlyName` 极米神灯, `UDN uuid:<MAC>-dmr`, `DMR-1.50`,
and the AVTransport control URL `/AVTransport/<UDN-suffix>/control.xml`.

1. `SetAVTransportURI` with `CurrentURI` set to a file the device can reach and
   `CurrentURIMetaData` set to a DIDL-Lite item matching the media:

   | Media | `upnp:class`                       | Example `protocolInfo` |
   |-------|------------------------------------|------------------------|
   | image | `object.item.imageItem.photo`      | `http-get:*:image/jpeg:DLNA.ORG_PN=JPEG_LRG;DLNA.ORG_OP=01;DLNA.ORG_CI=0` |
   | video | `object.item.videoItem`            | `http-get:*:video/mp4:DLNA.ORG_OP=01;DLNA.ORG_CI=0` |
   | audio | `object.item.audioItem.musicTrack` | `http-get:*:audio/mpeg:DLNA.ORG_OP=01;DLNA.ORG_CI=0` |

   ```xml
   <DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/"
              xmlns:dc="http://purl.org/dc/elements/1.1/"
              xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/">
     <item id="1" parentID="0" restricted="1">
       <dc:title>photo</dc:title>
       <upnp:class>object.item.imageItem.photo</upnp:class>
       <res protocolInfo="http-get:*:image/jpeg:DLNA.ORG_PN=JPEG_LRG;DLNA.ORG_OP=01;DLNA.ORG_CI=0">http://192.168.1.10:8123/photo.jpg</res>
     </item>
   </DIDL-Lite>
   ```

2. `Play` with `InstanceID 0` and `Speed 1`.

Measured: every call answers `200`, `GetMediaInfo` reports the URL and clip duration,
`GetTransportInfo` reports `PLAYING`. Stills and an H.264/AAC MP4 render full screen; a capture
taken mid-playback shows the video frame, so no separate window is used. Audio follows the same
contract but was not listened to. The device fetches the file itself, so the URL must be
reachable from the device and must not require authentication; the integration publishes local
files under a random token on the Home Assistant HTTP server for this reason.

`Stop` ends the session and the projector returns to its idle display (ambient photo wall), not
to the previous app. Power and lamp are untouched. A second `SetAVTransportURI` replaces the
current item.

Vendor image actions are dead ends on this firmware: `70000` (photo-wall preview) answers
`status.state: 1` without fetching the image, `30200` (`customPlay` with `mediatype 22`, tag
`WALL_1000`) downloads the file, reports `30234 downloadInfo` and fails with `progress: -1`,
`70002` (open app) accepts only an intent URI built from a cloud-hosted template, and `42000`
(art mode) answers `ardModeInfo` without rendering.

---

## 9. Screenshots (`30235`)

1. On the TCP state channel (section 7), send

   ```json
   {"action":20000,"controlCmd":{"mode":9,"type":1},"msgid":"2"}
   ```

   `mode` 9 with `type` 1 selects the screenshot handler; a plain `20001` follows with
   `startScreenCapTime` and `endScreenCapTime` at zero.

2. The capture arrives as a second frame:

   ```json
   {"action":30235,"endScreenCapTime":1795368315590,"imagePath":"http://%s:16741/storage/emulated/0/Pictures/Screenshots/Screenshot_11-23-01-25-15.jpg","startScreenCapTime":1795368315564,"type":0}
   ```

   `%s` is a literal placeholder for the device address. Each capture adds a new file under
   `/storage/emulated/0/Pictures/Screenshots/`.

3. `GET` that URL. The file server on TCP 16741 answers `200 image/jpeg`; every other path
   answers an empty `200`. The server is read-only: `DELETE` and `PUT` on a capture path return
   the same body and leave the file in place.

### Variants and side effects

Only `type: 1` captures. `type: 0` and `type: 2` answer `20001` alone, and `data` is ignored:
`/data/local/tmp` or `DCIM` still produces `Pictures/Screenshots/Screenshot_<timestamp>.jpg`.
Each capture flashes the projection and leaves a JPEG that cannot be removed through the file
server. No silent or no-save variant exists and there is no shell to clean up (7.1), so capture
on request only.

---

## 10. Device identification

| Method | Criterion |
| --- | --- |
| Protocol probe (most reliable) | text command → `20001`; then `50023` containing `ceilingLampMode` / `lightSwitch` |
| mDNS | `_airplay._tcp` / `_raop._tcp` service names carrying the product name |
| Vendor OUI | `4C:24:CE`, Sichuan AI-Link (Wi-Fi module) |
| TCP 8080 | Android Debug Database page (Android device) |

---

## 11. Installed apps and other modes

The app list and the launch command share `action:20000` with `mode:7`:

| Step | Frame | Reply |
| --- | --- | --- |
| List | `{"action":20000,"controlCmd":{"mode":7,"type":3},"msgid":"2"}` | `30236` whose `imagePath` points at `http://%s:16741/data/user/0/com.xgimi.vcontrol/app_appDatas/list` |
| Open | `{"action":20000,"controlCmd":{"mode":7,"type":1,"data":"<package>"},"msgid":"2"}` | `20001` |

The list is a URL-encoded JSON document on the device file server:

```json
{"appList":[{"appName":"QQ Music","packageName":"com.tencent.qqmusictv",
             "versionCode":"9020008","systemApp":false}]}
```

Uninstall uses `type:2` with the same `data` field (unverified).

Modes beyond the four lamp modes:

| Action | Meaning |
| --- | --- |
| `50004` | Enter music mode (screen off, audio only) |
| `50013` | Leave music mode |
| `50021` | Standby |
| `50025` | Image mode (`selectMode` payload) |
| `50026` | 3D mode |
| `50014` | Sound effect |

---

## 12. Volume and the light engine

`50009` sets the volume; `VOLUME_SYSTEM_UI` reports it back, no read call is needed. The device
pushes the new value in a `50023` frame about 2 s after the write.

| Action | Frame | State key | Values |
| --- | --- | --- | --- |
| `50009` | `{"action":50009,"commonCmd":{"volume":"40"},"msgid":"2"}` | `VOLUME_SYSTEM_UI` | `0`-`99`; `100` reads back as `0`, so the integration stops at `99` |

`50015` turns the light engine off only. With a picture on screen `SHUT_SCREEN_SYSTEM_UI` is
`4`; the empty frame below flips it to `3`.

```json
{"action":50015,"commonCmd":{},"msgid":"2"}
```

Sending it again at `3` does not restore the picture, so it is not a toggle.
`ToolManager.sendTurnOn` and `sendTurnOff` compile to this frame, which is why the app uses it
only for switching the picture off. To restore the picture the integration sends the power key
(`11`), as the projector switch does.
