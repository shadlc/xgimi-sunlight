# AGENTS.md

Guidance for AI agents and humans working on this repository. Only non-obvious rules live
here; anything the code already states is deliberately omitted.

## What this is

A Home Assistant custom integration for the **XGIMI Sunlight** ceiling lamp, which also
contains a projector. Commands go over the **length-prefixed TCP stream on 13145** when
it is up and fall back to **UDP 16750**; state arrives on that same stream. No cloud, no
account, no third-party package.

The fact that explains most of the design: **state only arrives over TCP**, never on the
UDP reply channel, and projector power is visible only as `POWER_SLEEP_SYSTEM_UI` in the
queried state table.

## Commands

```powershell
python -m pip install ruff==0.17.6
python -m ruff check custom_components
python -m ruff format --check custom_components
```

## Repository map

```text
custom_components/xgimi_sunlight/   the integration (the only thing that ships)
  protocol.py     sockets, frames, JSON shapes — zero Home Assistant imports
  runtime.py      per-entry state, command orchestration, power sequencing
  entity.py       shared base: device info, dispatch, error mapping
  light.py switch.py remote.py select.py button.py text.py number.py   platforms
  dlna.py views.py  media playback (UPnP, port discovered over SSDP), token file view
  screenshot.py camera.py  screen capture (`30235` + TCP 16741 file server)
  apps.py  installed app list (`20000` mode 7) and app launch
  config_flow.py  setup, options, reconfigure
  const.py        every constant: actions, state keys, ranges, defaults
  diagnostics.py  redacted dump
  brand/          icon.png and dark_icon.png (256x256)
docs/PROTOCOL.md  measured protocol reference (Chinese twin: docs/PROTOCOL.zh-Hans.md)
dashboards/       example Lovelace dashboards (English + Chinese)
```

## Invariants

Break one of these and the device misbehaves in ways that are hard to debug.

* `protocol.py` must import without Home Assistant. It is the only module that knows
  sockets, frame headers and JSON shapes.
* Device values never leak into entities unscaled. Brightness and colour temperature are
  `1..10` on the wire; Home Assistant gets `0..255` and Kelvin. Conversion lives in
  `light.py`, clamping in `runtime.py`.
* Colour temperature is inverted on the wire: device `1` is the **warmest** (~2700 K) and
  `10` the coolest (~6500 K). This was measured, not guessed — do not "fix" the formula.
* Writes are diffed first. Every lamp write restarts the LED driver and is visible as a
  flash, so never send a value the device already reports.
* Only continuous values (brightness, colour temperature) are debounced by
  `LAMP_WRITE_DEBOUNCE`; power and mode are discrete and must be sent immediately.
* The projector power key is a **toggle**. Send it only when the state table reports
  `POWER_SLEEP_SYSTEM_UI == "0"`, otherwise the integration switches the projector off.
* Only the custom lamp entity exposes brightness and colour temperature. The three preset
  modes are on/off; writing brightness there would silently move the lamp to custom mode.
* A long press is **one** `commonCmd.action="1"` frame. A second frame is a second long
  press, which the firmware treats as "open and immediately close".
* `50015` only turns the light engine **off** (`SHUT_SCREEN_SYSTEM_UI` `4` to `3`); sending it again does not bring the picture back. Turning projection back on needs the power key, so `50015` is exposed as a plain action button, never as a switch.
* The renderer port is dynamic: never hardcode it; resolve it with the unicast SSDP
  search in `dlna.py`.
* Images go through the DLNA renderer (UPnP), never through the vendor control
  channel: `70000`, `30200`, `70002` and `42000` all answer but render nothing.
* Commands prefer TCP and never go out twice: a toggle or a key press that lands twice
  fires twice on the device. Fall back to UDP only when the channel is not connected.
* The media view is unauthenticated on purpose and serves one file per random token.
  Never expose a directory or a reusable path through it.

## Changing things

Adding a device action:

1. Add the action id or key code to `const.py`.
2. Add the command shape to `protocol.py`, or reuse `KeyCommand` / `InvokeCommand` /
   `LightParamCommand`.
3. Expose it as an entity or service and sync `strings.json`, `translations/*.json`,
   `icons.json` and `services.yaml`.
4. Check it on a live device, then bump `version` in `manifest.json`.

When a measured protocol fact changes, update **both** `docs/PROTOCOL*.md` files, then the
matching paragraph in both READMEs.

## Language

Source, logs and error messages are English only, including `strings.json` and
`services.yaml`. Chinese belongs in `translations/zh-Hans.json` and the `*.zh-Hans.md`
docs; never add a Chinese literal under `custom_components/`.

Entity names and the UI are translated, but **effect names and select options are protocol
identifiers** (`Custom`, `Rhythm`, `OK`, `Volume +`). Home Assistant cannot translate those
values, so do not try to localise them in code.

## Style

* Comments are rare; docstrings are one line. Explain *why* only where the wire protocol is
  surprising (warm/cool inversion, single-frame long press, diff-before-write).
* Names describe behaviour, not the protocol: `async_power_on`, not `send_key_11`.
* Raise `XgimiError` from `protocol.py` and let `entity.py` map it to a
  `HomeAssistantError`; do not raise HA errors from the transport layer.
* Examples use ASCII identifiers: entity IDs are prefixed `xgimi_sunlight`, never a pinyin
  slug. If a user's device name differs, say so and show the replaceable prefix.

## Definition of done

A change is finished when all of this holds:

* `ruff check` and `ruff format --check` pass
* the change was exercised on the real device and the log stayed clean
* `manifest.json` `version` is bumped
* affected `strings.json`, `translations/*.json`, `icons.json` and both protocol docs are
  in sync

## Boundaries

* No compatibility shims: rename, split or drop things outright instead of keeping aliases,
  legacy options or migration steps. A rename breaks users' automations and dashboards, so
  weigh it instead of shipping both.
* Do not add `requirements` to `manifest.json`. Standard library plus Home Assistant is a
  feature, not a limitation to work around.
* Do not guess protocol behaviour. Measure it on the device, write the measurement into
  `docs/PROTOCOL.md`, then encode it in `protocol.py`.
* Do not commit device IPs, MAC addresses, serial numbers or packet captures. Use
  `192.168.1.50` style placeholders in docs and examples.

## Release

1. Update `manifest.json` `version`.
2. Run the commands above; ruff must pass.
3. Tag `vX.Y.Z`. The `validate` workflow runs hassfest, HACS validation and ruff on every
   push and pull request; `release.yml` attaches a zip on tags.

## Links

* [`README.md`](README.md) / [`README.zh-Hans.md`](README.zh-Hans.md) — install and usage
* [`docs/PROTOCOL.md`](docs/PROTOCOL.md) — frames, actions, state keys, port scan
* [`dashboards/xgimi_dashboard.yaml`](dashboards/xgimi_dashboard.yaml) — example frontend
