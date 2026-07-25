"""Home Assistant MQTT discovery.

Publishing a retained config document per entity makes the sign appear in Home
Assistant on its own, with no YAML for the user to write. That brings
automations, dashboards and voice control along with it -- "when my calendar
says I am in a meeting, turn the sign on" becomes a thing you click together.

Two entities, under one device:

  switch  "Muted"  -- the semantic on-air state. This is the one you automate.
  light   "LEDs"   -- the strip itself: power, plus the four effects.

They are deliberately separate because they are genuinely different attributes.
Muting changes the colour; turning the light off makes the strip dark whatever
the mute state is.

Topic format, per the MQTT integration docs:

    <discovery_prefix>/<component>/<node_id>/<object_id>/config

Payloads are retained, so Home Assistant finds the sign whenever it starts,
not only when the sign happens to boot first. They are deliberately *not*
cleared on shutdown -- an empty payload deletes the entity, and a restart
should not make the user's dashboard cards and automations disappear. Going
offline is what the availability topic is for.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from blinkysign import __version__

PROJECT_URL = "https://github.com/ttrentler/blinkysign"

# "none" is not an animation; it means "stop the current one and go back to
# showing the mute state". Home Assistant needs a member of effect_list to
# represent not-running-an-effect, and the bridge maps it onto a refresh.
NO_EFFECT = "none"


def slugify(value: str) -> str:
    """Reduce a name to something safe for a topic segment and a unique_id."""
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip().lower()).strip("_")
    return slug or "blinkysign"


def _device_block(node_id: str, friendly_name: str) -> Dict[str, Any]:
    return {
        "identifiers": [node_id],
        "name": friendly_name,
        "manufacturer": "BlinkySign",
        "model": "WS2812B on-air sign",
        "sw_version": __version__,
        "configuration_url": PROJECT_URL,
    }


def _origin_block() -> Dict[str, Any]:
    return {
        "name": "BlinkySign",
        "sw_version": __version__,
        "support_url": PROJECT_URL,
    }


def discovery_messages(
    base_topic: str,
    node_id: str,
    friendly_name: str,
    effects: List[str],
    discovery_prefix: str = "homeassistant",
) -> List[Tuple[str, Dict[str, Any]]]:
    """Build the (topic, payload) pairs to publish, retained."""
    state_topic = f"{base_topic}/state"
    availability_topic = f"{base_topic}/availability"

    availability = {
        "availability_topic": availability_topic,
        "payload_available": "online",
        "payload_not_available": "offline",
    }
    device = _device_block(node_id, friendly_name)
    origin = _origin_block()

    # The switch: muted on/off.
    #
    # Home Assistant sends the literal "ON"/"OFF", which the bridge's cmd/set
    # handler already understands -- it lowercases bare payloads and accepts
    # on/true/muted/1 and off/false/unmuted/0.
    muted = {
        "name": "Muted",
        "unique_id": f"{node_id}_muted",
        "object_id": f"{node_id}_muted",
        "state_topic": state_topic,
        "value_template": "{{ 'ON' if value_json.muted else 'OFF' }}",
        "command_topic": f"{base_topic}/cmd/set",
        "payload_on": "ON",
        "payload_off": "OFF",
        "icon": "mdi:microphone-off",
        "device": device,
        "origin": origin,
    }
    muted.update(availability)

    # The light: the strip's power, plus effects.
    leds = {
        "name": "LEDs",
        "unique_id": f"{node_id}_leds",
        "object_id": f"{node_id}_leds",
        "state_topic": state_topic,
        "state_value_template": "{{ 'ON' if value_json.led_on else 'OFF' }}",
        "command_topic": f"{base_topic}/cmd/power",
        "payload_on": "ON",
        "payload_off": "OFF",
        "effect_command_topic": f"{base_topic}/cmd/effect",
        "effect_state_topic": state_topic,
        # value_json.effect is null whenever nothing is animating.
        "effect_value_template": (
            "{{ value_json.effect if value_json.effect else '" + NO_EFFECT + "' }}"
        ),
        "effect_list": [NO_EFFECT] + list(effects),
        "icon": "mdi:led-strip-variant",
        "device": device,
        "origin": origin,
    }
    leds.update(availability)

    return [
        (f"{discovery_prefix}/switch/{node_id}/muted/config", muted),
        (f"{discovery_prefix}/light/{node_id}/leds/config", leds),
    ]
