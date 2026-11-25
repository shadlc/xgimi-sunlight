# XGIMI Sunlight for Home Assistant

<div align="center">

[![hassfest](https://github.com/shadlc/xgimi-sunlight/actions/workflows/validate.yml/badge.svg)](https://github.com/shadlc/xgimi-sunlight/actions/workflows/validate.yml)
[![GitHub Release](https://img.shields.io/github/v/release/shadlc/xgimi-sunlight)](https://github.com/shadlc/xgimi-sunlight/releases)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.10%2B-blue.svg)](https://www.home-assistant.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=shadlc&repository=xgimi-sunlight&category=integration)

<img width="320" alt="XGIMI Sunlight dashboard" src="https://github.com/user-attachments/assets/13ec01b3-bd0a-47d8-9a71-f63e2c59641d">

<sub>Example dashboard</sub>

**English** · [简体中文](README.zh-Hans.md)

</div>

A local-push integration for the XGIMI Sunlight ceiling lamp and projector. Commands travel
over the length-prefixed TCP stream on port 13145, with UDP 16750 as a fallback, and state
comes back on the same TCP stream as `50023` frames. **No cloud dependency, no vendor account
and no external packages** — all traffic stays on the local network.

---

## Features

- **Four lamp modes** — custom, rhythm, daylight and movie, each as its own entity, plus a master switch
- **Brightness and colour temperature** in custom mode, 10 steps each, 2700–6500 K
- **Projector power** with real state read from the device state table
- **All 15 remote keys**, as a `remote` entity or as click / long-press buttons
- **System volume** as a slider, 0–99
- **Installed apps** — the list is read from the device, apps launch by name or package
- **Media playback** through the DLNA renderer: images, video and audio, no vendor app required
- **On-demand screen capture** saved to `www` and shown on the dashboard
- **Self-correcting state** — lamp values are re-read every 30 s, so a change the device never pushed cannot leave an entity stale
- **Two UI layouts** — one switch per lamp mode, or a single lamp with an effect picker

## Requirements

| Requirement | Detail |
| --- | --- |
| Home Assistant | 2024.10 or newer (validated on 2026.11) |
| Network | Home Assistant and the device on the same subnet; the protocol is local and unauthenticated |
| UDP 16751 | Must be free on the Home Assistant host — the device sends its replies there |

## Installation

### HACS (recommended)

1. HACS → top-right menu → **Custom repositories**
2. Add `https://github.com/shadlc/xgimi-sunlight` with category **Integration**
3. Search for “XGIMI Sunlight” in HACS and download it
4. Restart Home Assistant

### Manual

Copy `custom_components/xgimi_sunlight` into `<config>/custom_components/` and restart Home
Assistant.

## Configuration

### Add the device

1. **Settings → Devices & services → Add integration** and search for **XGIMI Sunlight**
2. Enter the device address (for example `192.168.1.50`; a DHCP reservation is recommended)
   and a name
3. The integration opens a state channel to TCP 13145 and reconnects automatically

If the address changes, run **Reconfigure** on the entry — deleting and re-adding is not needed.

### Options

**Settings → Devices & services → XGIMI Sunlight → Configure**:

| Option | Default | Description |
| --- | --- | --- |
| Lamp entity layout | One switch per mode | Or one lamp whose modes are effects |
| Default lamp mode | Custom | Mode used by the single-lamp layout when no effect is given |
| Reserve UDP 16751 | On | Turning it off loses command replies and rejection detection |

## Entities

Each device creates 34 entities.

### Lights

| Entity | Description |
| --- | --- |
| `light.*_custom_lamp` | Custom mode, with brightness (1–10 steps) and colour temperature (2700–6500 K) |
| `light.*_rhythm_lamp` | Rhythm mode, on/off |
| `light.*_daylight_lamp` | Daylight mode, on/off |
| `light.*_movie_lamp` | Movie mode, on/off |
| `switch.*_lamp` | Master switch; turning it on restores the last mode |

The four modes are mutually exclusive — the device holds one `ceilingLampMode` value. Only the
custom lamp exposes brightness and colour temperature; the three presets are on/off because the
device drives them with its own profile. Writing brightness or colour temperature switches the
device to custom mode.

### Projector

| Entity | Description |
| --- | --- |
| `switch.*_projector` | Power. `on` while `POWER_SLEEP_SYSTEM_UI` is `1`; power-on sends the `power` key once when the flag says standby, power-off sends the standby frame |
| `remote.*_remote` | The 15 remote keys through `remote.send_command`, with `num_repeats`, `delay_secs` and `hold_secs` |

### Controls

| Entity | Description |
| --- | --- |
| `number.*_volume` | System volume, 0–99 (the firmware reads back 0 for 100) |
| `select.*_remote_key` | Key used by the click and long-press buttons |
| `select.*_app` | App launched by the open-app button; the list is read from the device |
| `text.*_command` | Holds a phrase; `button.*_send_command` hands it to the voice assistant |
| `text.*_media` | Holds a URL or path; `button.*_play_media` plays it |

### Buttons

| Entity | Description |
| --- | --- |
| `button.*_press` / `button.*_hold` | Click or long-press the key selected above |
| `button.*_power_menu` | Open the power menu |
| `button.*_screenshot` | Press the remote screenshot key |
| `button.*_screen_off` | Turn the light engine off |
| `button.*_mute` | Mute the projector |
| `button.*_auto_focus` / `button.*_manual_focus` | Focus control |
| `button.*_settings` / `button.*_home` / `button.*_back` / `button.*_menu` | Navigation |
| `button.*_send_command` / `button.*_play_media` / `button.*_stop_media` | Run the text boxes and stop playback |
| `button.*_open_app` | Launch the selected app |
| `button.*_reboot` / `button.*_clean_memory` / `button.*_check_for_updates` | Maintenance |
| `button.*_listen_to_music` / `button.*_exit_music_mode` | Music mode |

All 21 buttons are enabled by default.

### Camera

| Entity | Description |
| --- | --- |
| `camera.*_screen` | The last capture; a new frame is taken only when `xgimi_sunlight.screenshot` is called |

## Services

| Service | Description |
| --- | --- |
| `xgimi_sunlight.send_command` | Hands text to the device voice assistant, for features without a frame |
| `xgimi_sunlight.press_key` | Clicks or long-presses a remote key by name |
| `xgimi_sunlight.play_media` | Plays an image, a video or an audio file through the DLNA renderer |
| `xgimi_sunlight.stop_media` | Ends the renderer session |
| `xgimi_sunlight.screenshot` | Captures the screen and saves the JPEG under `www` |
| `xgimi_sunlight.open_app` | Launches an installed app, by `package` or by `app` name |

```yaml
action: xgimi_sunlight.press_key
data:
  key: power
  hold_secs: 1
```

`play_media` takes either a URL the device can download or a file on the Home Assistant host:

```yaml
action: xgimi_sunlight.play_media
data:
  path: /config/www/photo.jpg   # absolute
  # path: www/photo.jpg        # same file
  # path: media/holiday.mp4    # from the media folder
```

Local files are published under a random token on the Home Assistant HTTP server, so the device
needs no credentials. Custom integrations have no file-upload dialog, so the file must already
be on the host — through Samba, SSH or a file-editor add-on. Called with no source, `play_media`
replays the last successful item.

## Media playback

The device renders the file through its DLNA renderer, discovered over SSDP, so the port is not
fixed. Images and MP4 video were verified on hardware; other formats are passed through with the
matching DLNA class.

Playback continues until the remote is used or `xgimi_sunlight.stop_media` is called. Stopping
ends the session and the projector returns to its own idle display — the ambient photo wall — not
to the previously active app. Display only: the lamp state is not touched.

`play_media` requires the renderer to be running. It is not while the device is asleep or while a
foreground app such as the music player holds the screen; the service reports this explicitly
instead of failing silently.

## Screen capture

```yaml
action: xgimi_sunlight.screenshot
response_variable: shot
```

The service writes the frame to `www/xgimi_screen.jpg` and returns its path and `/local/` URL.
Captures are **on demand**: each capture flashes the projection and leaves a JPEG under
`/storage/emulated/0/Pictures/Screenshots/` on the device, so nothing captures automatically.

One capture runs at a time — the device handles a single request, so a concurrent call is
rejected with `A screen capture is already running` rather than queued. A capture takes
0.6–1.2 s on the device; the transfer itself is 50–100 ms.

## Dashboard

`dashboards/xgimi_dashboard.yaml` is a ready-made English example and
`dashboards/xgimi_dashboard.zh-Hans.yaml` the Chinese one. Copy either into the configuration
directory and register it:

```yaml
lovelace:
  dashboards:
    xgimi-lamp:
      mode: yaml
      title: XGIMI Sunlight
      icon: mdi:lamp
      show_in_sidebar: true
      filename: xgimi_dashboard.yaml
```

The dashboard assumes the entity prefix `xgimi_sunlight`; adjust the IDs when the device name
differs.

## State and behaviour

| Topic | Detail |
| --- | --- |
| Source of truth | `50023` frames on TCP 13145; the device pushes on change and ignores polls |
| Initial values | One `50040` query per lamp parameter on every (re)connect |
| Self-correction | The four lamp parameters are re-read every 30 s, because the device does not push every change |
| Preset modes | Daylight, rhythm and movie report the profile's own percentage values; they are exposed as attributes only |
| Power changes | Not pushed; the 30 s re-read keeps the switch honest |
| Degraded mode | If UDP 16751 cannot be bound, commands still work but rejections are not observable; a repair issue is raised |
| Asleep device | Only ICMP answers; TCP 13145, UDP 16750 and the renderer are all closed |

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| Entities unavailable | The device is asleep. Power it on with the remote or the vendor app |
| Commands ignored, state still updating | A foreground app closed UDP 16750; commands already prefer TCP, so this only affects the fallback path |
| `play_media` reports the renderer is not running | The device is asleep or an app holds the screen. Wake it or leave the app |
| Lamp entity lags reality | Wait up to 30 s for the next re-read; if it persists, check the log for `50040` replies |
| Capture is slow or flashes | Both are device behaviour: a capture re-initialises the panel and cannot be silent |
| `A screen capture is already running` | One capture at a time is a device limit; retry after the current one finishes |
| Port 16751 already in use | Another instance or program holds the port. Turn off **Reserve UDP 16751** to degrade gracefully |

## Automation examples

```yaml
# Warm the lamp at sunset, custom mode
action: light.turn_on
target:
  entity_id: light.xgimi_sunlight_custom_lamp
data:
  brightness: 200
  color_temp_kelvin: 3000
```

```yaml
# Long-press home to open the task switcher
action: xgimi_sunlight.press_key
data:
  key: home
  hold_secs: 1
```

## Protocol

Reverse-engineering notes and message formats: [`docs/PROTOCOL.md`](docs/PROTOCOL.md) — the
request shapes, the TCP frame (`FF FF E0 4A` + big-endian length + JSON), the structured light
API (`50040`/`50041`), state keys, the screenshot reply and the port scan.

## Development

```powershell
python -m pip install ruff==0.17.6
python -m ruff check custom_components
python -m ruff format --check custom_components
```

## Contributing

Issues and pull requests are welcome. Keep changes to one concern per pull request, run the two
ruff commands above, and verify behaviour on a real device — the protocol notes in
[`docs/PROTOCOL.md`](docs/PROTOCOL.md) record what has actually been measured.

## License

[MIT license](LICENSE)

> Unofficial integration. Not affiliated with or endorsed by XGIMI.

## Related projects

- [Lzk119/XGMI_HA](https://github.com/Lzk119/XGMI_HA) — another Home Assistant integration for the same lamp model; lamp and projector switches through the structured light API.
- [manymuch/Xgimi-4-Home-Assistant](https://github.com/manymuch/Xgimi-4-Home-Assistant) — general XGIMI projector integration built on text commands instead of key codes.
