# BlinkySign

An internet-connected on-air sign: a 3D-printed enclosure, a WS2812B LED strip
and a Raspberry Pi that turns the sign a colour when you are muted.

## Install

On the Raspberry Pi:

```bash
curl -fsSL https://raw.githubusercontent.com/ttrentler/blinkysign/master/install.sh | bash
```

That installs the dependencies, enables SPI, creates the virtual environment,
installs a systemd service and starts it. When it finishes, open:

```
http://blinkysign.local:5000
```

The installer prints the IP address too, in case mDNS is not available on your
network. If it tells you a reboot is required, the LEDs will not light up until
you do — enabling SPI needs one.

Re-run the same command to upgrade. It will not overwrite your `.env`.

To remove the service (keeping the code and your settings):

```bash
curl -fsSL https://raw.githubusercontent.com/ttrentler/blinkysign/master/install.sh | bash -s -- --uninstall
```

## Hardware

- Raspberry Pi (any model; the Pi 5 works)
- WS2812B LED strip
- 5V power supply sized for your strip — the GPIO pins cannot power a long one
- 3D-printed enclosure, in [3dprints/](3dprints/)
- Optional: a momentary button
- Optional: an Elgato Stream Deck

The strip connects to 5V, ground, MOSI (data) and SCK (clock). SPI is used
rather than bit-banged GPIO because it works on the Pi 5. There is a good wiring
walkthrough at
[core-electronics](https://core-electronics.com.au/guides/fully-addressable-rgb-raspberry-pi/).

## Configuration

Settings live in `.env` next to the code. See [.env.example](.env.example) for
the full list; the common ones:

| Setting | Default | Meaning |
|---|---|---|
| `BLINKYSIGN_PORT` | `5000` | Web server port |
| `BLINKYSIGN_LED_COUNT` | `30` | LEDs on the strip |
| `BLINKYSIGN_LED_BRIGHTNESS` | `0.5` | 0.0–1.0 |
| `BLINKYSIGN_MUTED_COLOR` | `green` | Name, `#RRGGBB` or `r,g,b` |
| `BLINKYSIGN_UNMUTED_COLOR` | `red` | Name, `#RRGGBB` or `r,g,b` |
| `BLINKYSIGN_BUTTON_PIN` | unset | BCM pin for a physical button |
| `BLINKYSIGN_API_TOKEN` | unset | Require a token on state changes |

After editing: `sudo systemctl restart blinkysign`.

> The default is **green for muted, red for unmuted**. Swap the two colour
> settings if you prefer the opposite convention.

## The web interface

The sign serves its own pages — there is no second web server to run.

- `/` — the full control panel
- `/button` — a single large toggle, good on a phone

## API

```
GET  /status              current state
PUT  /toggle              flip muted
PUT  /set                 {"muted": true}
PUT  /off                 all LEDs off
GET  /health              status, and whether the LEDs are actually working
GET  /api/config          what this sign supports

PUT  /effects/rainbow
PUT  /effects/pulse       {"color": "blue", "cycles": 3, "duration": 1.0}
PUT  /effects/theater     {"color": "white", "iterations": 10}
PUT  /effects/wipe        {"color": "blue"}
```

Colours accept a name (`red`, `green`, `blue`, `yellow`, `purple`, `cyan`,
`white`), `#RRGGBB`, or `r,g,b`.

**Effects return `202 Accepted` and run in the background.** They no longer
block the request, and any later command interrupts a running effect within a
frame — so pressing "muted" during a rainbow takes effect immediately rather
than after the animation finishes.

`/health` returns `degraded` rather than `healthy` when the LED strip is not
actually available (SPI disabled, strip unplugged, hardware libraries missing).
It stays HTTP 200 either way so uptime checks do not flap.

If `BLINKYSIGN_API_TOKEN` is set, every state-changing request needs it, as
either `x-api-key: <token>` or `Authorization: Bearer <token>`. `/status` and
`/health` stay open. With no token set the API is open to your network, which
is the behaviour previous versions had.

## Remote control over MQTT

The sign speaks plain MQTT to any broker — no AWS account required. Set the
broker in `.env` and restart.

```
BLINKYSIGN_MQTT_ENABLED=true
BLINKYSIGN_MQTT_HOST=localhost
```

Topics, under `BLINKYSIGN_MQTT_BASE_TOPIC` (default `blinkysign`):

| Topic | Direction | Payload |
|---|---|---|
| `blinkysign/cmd/toggle` | in | anything |
| `blinkysign/cmd/set` | in | `{"muted": true}`, or `on`/`off` |
| `blinkysign/cmd/effect` | in | `{"effect": "pulse", "color": "red"}`, or a bare effect name |
| `blinkysign/cmd/power` | in | `on`/`off` — the strip, independent of mute state |
| `blinkysign/state` | out | full state, retained |
| `blinkysign/availability` | out | `online`/`offline`, retained |

All four effects work over MQTT, exactly as over HTTP.

Any broker will do: a local Mosquitto, a free HiveMQ or EMQX tier, or AWS IoT
Core directly with `BLINKYSIGN_MQTT_TLS=mutual` on port 8883 and your device
certificate. See [.env.example](.env.example) for each shape.

If you only want to reach the sign from elsewhere on your own machine's
network, a Tailscale or Cloudflare Tunnel install is usually simpler than any
broker.

## Home Assistant

With MQTT enabled, the sign announces itself and appears in Home Assistant on
its own — no YAML. Point both at the same broker and it shows up as a
**BlinkySign** device with two entities:

| Entity | What it does |
|---|---|
| `switch.blinkysign_muted` | The on-air state. This is the one to automate. |
| `light.blinkysign_leds` | The strip: on/off, plus the four effects. |

Turning the switch on mutes the sign; the light turns the strip off entirely
whatever the mute state is. The light's effect list contains the four effects
plus `none`, which stops a running effect and goes back to showing the mute
state.

Discovery messages are retained, so Home Assistant finds the sign whenever it
starts — the sign does not need to boot second. Entities are deliberately not
removed when the sign shuts down; it reports `offline` through the availability
topic instead, so your dashboard cards and automations survive a restart.

To turn it off, or to change the discovery prefix:

```
BLINKYSIGN_HA_DISCOVERY=false
BLINKYSIGN_HA_PREFIX=homeassistant
BLINKYSIGN_HA_DEVICE_NAME=BlinkySign
```

An example automation — follow your calendar, so the sign is on whenever you
are in a meeting:

```yaml
automation:
  - alias: "On air when a meeting starts"
    trigger:
      - platform: state
        entity_id: calendar.work
        to: "on"
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.blinkysign_muted

  - alias: "Off air when the meeting ends"
    trigger:
      - platform: state
        entity_id: calendar.work
        to: "off"
    action:
      - service: switch.turn_off
        target:
          entity_id: switch.blinkysign_muted
```

## Stream Deck

Use the "System: Website" action:

| Button | URL | Method | Body |
|---|---|---|---|
| Toggle | `http://blinkysign.local:5000/toggle` | PUT | |
| Muted | `http://blinkysign.local:5000/set` | PUT | `{"muted": true}` |
| Rainbow | `http://blinkysign.local:5000/effects/rainbow` | PUT | |

Add `x-api-key` as a header if you set a token. Sample pages are in
[streamdeck-buttons/](streamdeck-buttons/).

## Service management

```bash
systemctl status blinkysign
journalctl -u blinkysign -f
sudo systemctl restart blinkysign
```

One service, started at boot. Stopping it turns the LEDs off.

## Testing the strip

```bash
~/blinkysign/.venv/bin/blinkysign-ledtest
```

Cycles through colours and effects. It runs without hardware too, reporting
which backend it used — useful for telling "the code is broken" apart from "the
wiring is broken".

## Development

The package imports and tests without any Raspberry Pi hardware:

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest
```

A mock LED backend records what would have been displayed, so the effects,
worker and API are all testable on a laptop. Force it with
`BLINKYSIGN_BACKEND=mock`.

On a Pi, install `.[pi]` as well to get the hardware libraries. There is no CI,
so please run `pytest` before sending a change — and note that a laptop cannot
exercise the SPI or GPIO paths.

Layout:

```
blinkysign/
  service.py      composition root: one process, one systemd unit
  server.py       HTTP API and the control panel
  sign.py         the only thing HTTP, MQTT and the button call
  state.py        thread-safe state, shared by every input
  worker.py       the single thread that owns the LED strip
  mqtt.py         MQTT bridge
  button.py       physical button
  discovery.py    mDNS
  leds/           the strip, and its SPI / mock backends
```

## Upgrading from an earlier version

Several scripts are gone, because one process now does all of it:

| Removed | Replacement |
|---|---|
| `app.py` | `blinkysign` (the service) |
| `iot_client.py` | built-in MQTT bridge |
| `physical_button.py` | built-in button support, via `BLINKYSIGN_BUTTON_PIN` |
| `button_client.py` | `curl -X PUT http://blinkysign.local:5000/toggle` |
| `setup.sh` | `install.sh` |
| `python -m http.server 8000` | the sign serves its own panel |

Existing `.env` files keep working: `PORT`, `LED_COUNT`, `LED_BRIGHTNESS` and
`BUTTON_PIN` are still read.

The AWS CloudFormation deployment has been retired to
[legacy/aws/](legacy/aws/) — it did not work, and that directory's README
explains exactly why. Use MQTT instead.

## Security

If you have ever run the old `deploy_aws.py`, please read
[SECURITY.md](SECURITY.md): it granted your own AWS account administrative IoT
permissions and never removed them.

## License

MIT — see [LICENSE](LICENSE).
