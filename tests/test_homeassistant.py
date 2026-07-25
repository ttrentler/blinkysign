"""Home Assistant MQTT discovery.

These assert the payloads match what the MQTT integration documents, since a
malformed discovery config fails silently -- the entity simply never appears,
with nothing logged on our side.
"""
import json

import pytest

from blinkysign import __version__
from blinkysign.config import Config, MqttConfig
from blinkysign.homeassistant import NO_EFFECT, discovery_messages, slugify
from blinkysign.leds.controller import LEDController
from blinkysign.mqtt import MqttBridge
from blinkysign.sign import build_sign

from tests.test_mqtt import FakeClient, FakeMessage


EFFECTS = ["rainbow", "pulse", "theater", "wipe"]


@pytest.fixture
def messages():
    return dict(discovery_messages(
        base_topic="blinkysign",
        node_id="blinkysign",
        friendly_name="BlinkySign",
        effects=EFFECTS,
    ))


# -- topic structure ------------------------------------------------------


def test_topics_follow_the_documented_format(messages):
    """<discovery_prefix>/<component>/<node_id>/<object_id>/config"""
    assert set(messages) == {
        "homeassistant/switch/blinkysign/muted/config",
        "homeassistant/light/blinkysign/leds/config",
    }


def test_prefix_is_configurable():
    topics = dict(discovery_messages(
        base_topic="blinkysign", node_id="blinkysign", friendly_name="BlinkySign",
        effects=EFFECTS, discovery_prefix="ha",
    ))
    assert all(t.startswith("ha/") for t in topics)


@pytest.mark.parametrize("raw,expected", [
    ("BlinkySign", "blinkysign"),
    ("Ted's Sign", "ted_s_sign"),
    ("office/sign", "office_sign"),
    ("  ", "blinkysign"),
    ("!!!", "blinkysign"),
])
def test_slugify(raw, expected):
    assert slugify(raw) == expected


# -- payload contract -----------------------------------------------------


@pytest.mark.parametrize("key", ["muted", "leds"])
def test_every_entity_has_the_required_keys(messages, key):
    payload = [p for t, p in messages.items() if t.endswith(f"/{key}/config")][0]
    for required in ("name", "unique_id", "state_topic", "command_topic",
                     "availability_topic", "device", "origin"):
        assert required in payload, f"{key} is missing {required}"


def test_unique_ids_are_distinct(messages):
    ids = [p["unique_id"] for p in messages.values()]
    assert len(ids) == len(set(ids))


def test_entities_share_one_device(messages):
    devices = [p["device"] for p in messages.values()]
    assert devices[0] == devices[1]
    assert devices[0]["identifiers"] == ["blinkysign"]
    assert devices[0]["sw_version"] == __version__


def test_availability_matches_what_the_bridge_publishes(messages):
    """The bridge's LWT publishes exactly these strings."""
    for payload in messages.values():
        assert payload["availability_topic"] == "blinkysign/availability"
        assert payload["payload_available"] == "online"
        assert payload["payload_not_available"] == "offline"


def test_payloads_are_json_serialisable(messages):
    for payload in messages.values():
        json.loads(json.dumps(payload))


# -- the switch -----------------------------------------------------------


def test_switch_reads_muted_and_commands_cmd_set(messages):
    switch = messages["homeassistant/switch/blinkysign/muted/config"]
    assert switch["value_template"] == "{{ 'ON' if value_json.muted else 'OFF' }}"
    assert switch["command_topic"] == "blinkysign/cmd/set"
    assert switch["state_topic"] == "blinkysign/state"


# -- the light ------------------------------------------------------------


def test_light_reads_led_on_and_commands_cmd_power(messages):
    light = messages["homeassistant/light/blinkysign/leds/config"]
    assert light["state_value_template"] == "{{ 'ON' if value_json.led_on else 'OFF' }}"
    assert light["command_topic"] == "blinkysign/cmd/power"


def test_light_advertises_every_effect_plus_none(messages):
    light = messages["homeassistant/light/blinkysign/leds/config"]
    assert light["effect_list"] == [NO_EFFECT] + EFFECTS
    assert light["effect_command_topic"] == "blinkysign/cmd/effect"
    assert light["effect_state_topic"] == "blinkysign/state"


# -- end to end through the bridge ----------------------------------------


@pytest.fixture
def rig():
    controller = LEDController(count=8, mode="mock")
    sign = build_sign(Config(), controller)
    client = FakeClient()
    config = MqttConfig(enabled=True, host="broker.invalid",
                        base_topic="blinkysign", client_id="blinkysign")
    bridge = MqttBridge(config, sign, client_factory=lambda: client)
    bridge.start()
    client.on_connect(client, None, {}, 0)
    try:
        yield bridge, client, sign, controller
    finally:
        bridge.stop()
        sign.stop()


def test_discovery_is_published_retained_on_connect(rig):
    _, client, _, _ = rig
    configs = [p for p in client.published if p["topic"].startswith("homeassistant/")]
    assert len(configs) == 2
    assert all(p["retain"] for p in configs), (
        "discovery must be retained or HA only sees it if it starts second"
    )


def test_discovery_precedes_the_first_state_publish(rig):
    _, client, _, _ = rig
    topics = [p["topic"] for p in client.published]
    first_state = topics.index("blinkysign/state")
    assert all(
        topics.index(t) < first_state
        for t in topics if t.startswith("homeassistant/")
    )


def test_discovery_advertises_the_effects_the_sign_really_has(rig):
    _, client, sign, _ = rig
    light = [json.loads(p["payload"]) for p in client.published
             if "/light/" in p["topic"]][0]
    assert light["effect_list"] == [NO_EFFECT] + sign.effects


def test_discovery_can_be_disabled():
    controller = LEDController(count=4, mode="mock")
    sign = build_sign(Config(), controller)
    client = FakeClient()
    config = MqttConfig(enabled=True, host="broker.invalid", ha_discovery=False)
    bridge = MqttBridge(config, sign, client_factory=lambda: client)
    try:
        bridge.start()
        client.on_connect(client, None, {}, 0)
        assert not [p for p in client.published if p["topic"].startswith("homeassistant/")]
    finally:
        bridge.stop()
        sign.stop()


def test_shutdown_does_not_delete_the_entities(rig):
    """An empty payload removes an entity -- a restart must not do that."""
    bridge, client, _, _ = rig
    bridge.stop()
    cleared = [p for p in client.published
               if p["topic"].startswith("homeassistant/") and p["payload"] == ""]
    assert not cleared


# -- the commands Home Assistant actually sends ---------------------------


def test_ha_switch_payloads_drive_the_mute_state(rig):
    """HA publishes the literal ON/OFF, not JSON."""
    _, client, sign, _ = rig
    client.on_message(client, None, FakeMessage("blinkysign/cmd/set", "ON"))
    assert sign.snapshot().muted is True
    client.on_message(client, None, FakeMessage("blinkysign/cmd/set", "OFF"))
    assert sign.snapshot().muted is False


def test_ha_light_power_payloads(rig):
    _, client, sign, _ = rig
    client.on_message(client, None, FakeMessage("blinkysign/cmd/power", "OFF"))
    assert sign.wait_idle(timeout=5)
    assert sign.snapshot().led_on is False

    client.on_message(client, None, FakeMessage("blinkysign/cmd/power", "ON"))
    assert sign.wait_idle(timeout=5)
    assert sign.snapshot().led_on is True


def test_power_on_restores_the_current_mute_colour(rig):
    """"On" must not invent a colour -- it repaints the real state."""
    _, client, sign, controller = rig
    sign.set_muted(True)
    client.on_message(client, None, FakeMessage("blinkysign/cmd/power", "OFF"))
    assert sign.wait_idle(timeout=5)
    client.on_message(client, None, FakeMessage("blinkysign/cmd/power", "ON"))
    assert sign.wait_idle(timeout=5)
    assert all(px == (0, 255, 0) for px in controller.strips[0].last_frame)


def test_ha_effect_payload_is_a_bare_name(rig):
    _, client, sign, _ = rig
    client.on_message(client, None, FakeMessage("blinkysign/cmd/effect", "rainbow"))
    assert sign.wait_idle(timeout=10)


@pytest.mark.parametrize("led_on_first", [True, False])
def test_light_turn_on_with_an_effect_does_not_cancel_it(rig, led_on_first):
    """Home Assistant sends TWO messages for light.turn_on(effect=...):

        blinkysign/cmd/effect  pulse
        blinkysign/cmd/power   ON

    The trailing power command must not cancel the effect that arrived a
    moment earlier -- otherwise selecting any effect in Home Assistant appears
    to do nothing at all.
    """
    _, client, sign, _ = rig
    if not led_on_first:
        sign.turn_off()
        assert sign.wait_idle(timeout=5)

    client.on_message(client, None, FakeMessage(
        "blinkysign/cmd/effect",
        json.dumps({"effect": "pulse", "cycles": 10, "duration": 1.0})))
    client.on_message(client, None, FakeMessage("blinkysign/cmd/power", "ON"))

    import time
    time.sleep(0.3)
    assert sign.snapshot().effect == "pulse", "the power command cancelled the effect"


def test_effect_from_an_off_light_settles_on_a_lit_state(rig):
    """Turning the light on *with* an effect should leave it on afterwards.

    Otherwise the effect plays and the strip goes dark again, because the
    resting render it returns to is still "off".
    """
    _, client, sign, controller = rig
    sign.set_muted(True)
    sign.turn_off()
    assert sign.wait_idle(timeout=5)

    client.on_message(client, None, FakeMessage(
        "blinkysign/cmd/effect",
        json.dumps({"effect": "wipe", "color": "blue", "wait": 0.0})))
    client.on_message(client, None, FakeMessage("blinkysign/cmd/power", "ON"))
    assert sign.wait_idle(timeout=10)

    assert sign.snapshot().led_on is True
    assert all(px == (0, 255, 0) for px in controller.strips[0].last_frame), (
        "settled dark instead of returning to the muted colour"
    )


def test_power_on_is_a_no_op_when_already_on(rig):
    _, client, sign, _ = rig
    sign.refresh()  # what service.py does at startup
    assert sign.wait_idle(timeout=5)

    before = sign.snapshot().revision
    client.on_message(client, None, FakeMessage("blinkysign/cmd/power", "ON"))
    assert sign.snapshot().revision == before


def test_selecting_none_cancels_the_running_effect(rig):
    _, client, sign, controller = rig
    sign.set_muted(True)
    client.on_message(client, None, FakeMessage(
        "blinkysign/cmd/effect",
        json.dumps({"effect": "pulse", "cycles": 10, "duration": 1.0})))
    import time
    time.sleep(0.2)

    client.on_message(client, None, FakeMessage("blinkysign/cmd/effect", NO_EFFECT))
    assert sign.wait_idle(timeout=5)
    assert all(px == (0, 255, 0) for px in controller.strips[0].last_frame)


def test_unusable_power_payload_is_ignored(rig):
    _, client, sign, _ = rig
    before = sign.snapshot().revision
    client.on_message(client, None, FakeMessage("blinkysign/cmd/power", "sideways"))
    assert sign.snapshot().revision == before


def test_bridge_subscribes_to_power(rig):
    _, client, _, _ = rig
    assert "blinkysign/cmd/power" in client.subscribed
