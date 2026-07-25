"""MQTT bridge, driven through a fake paho client.

The point of these tests is that MQTT and HTTP cannot drift apart again: both
dispatch through SignController, so anything the HTTP API can do is reachable
over MQTT, and every state change publishes the same way regardless of origin.
"""
import json

import pytest

from blinkysign.config import Config, MqttConfig
from blinkysign.leds.controller import LEDController
from blinkysign.mqtt import MqttBridge, build_bridge
from blinkysign.sign import build_sign


class FakeMessage:
    def __init__(self, topic, payload):
        self.topic = topic
        self.payload = payload if isinstance(payload, bytes) else payload.encode()


class FakeClient:
    """Records everything, so tests can assert on the wire behaviour."""

    def __init__(self):
        self.published = []
        self.subscribed = []
        self.will = None
        self.credentials = None
        self.tls = None
        self.connected = None
        self.loop_started = False
        self.on_connect = self.on_disconnect = self.on_message = None

    def will_set(self, topic, payload, qos=0, retain=False):
        self.will = (topic, payload, qos, retain)

    def username_pw_set(self, username, password=None):
        self.credentials = (username, password)

    def tls_set(self, **kwargs):
        self.tls = kwargs

    def connect_async(self, host, port, keepalive):
        self.connected = (host, port, keepalive)

    def loop_start(self):
        self.loop_started = True

    def loop_stop(self):
        self.loop_started = False

    def disconnect(self):
        self.connected = None

    def subscribe(self, topic, qos=0):
        self.subscribed.append(topic)

    def publish(self, topic, payload, qos=0, retain=False):
        self.published.append({"topic": topic, "payload": payload, "retain": retain})

    def messages_on(self, topic):
        return [p for p in self.published if p["topic"] == topic]


@pytest.fixture
def rig():
    controller = LEDController(count=8, mode="mock")
    sign = build_sign(Config(), controller)
    client = FakeClient()
    config = MqttConfig(enabled=True, host="broker.invalid", base_topic="blinkysign")
    bridge = MqttBridge(config, sign, client_factory=lambda: client)
    bridge.start()
    client.on_connect(client, None, {}, 0)
    try:
        yield bridge, client, sign, controller
    finally:
        bridge.stop()
        sign.stop()


def test_connects_asynchronously(rig):
    """A slow or dead broker must never block startup."""
    _, client, _, _ = rig
    assert client.connected == ("broker.invalid", 1883, 60)
    assert client.loop_started


def test_subscribes_to_all_command_topics(rig):
    _, client, _, _ = rig
    assert set(client.subscribed) == {
        "blinkysign/cmd/set",
        "blinkysign/cmd/toggle",
        "blinkysign/cmd/effect",
        "blinkysign/cmd/power",
    }


def test_availability_uses_a_retained_will(rig):
    _, client, _, _ = rig
    assert client.will == ("blinkysign/availability", "offline", 1, True)
    online = client.messages_on("blinkysign/availability")
    assert online and online[0]["payload"] == "online"
    assert online[0]["retain"] is True


def test_toggle_command_changes_state_and_publishes(rig):
    bridge, client, sign, _ = rig
    client.on_message(client, None, FakeMessage("blinkysign/cmd/toggle", "{}"))
    assert sign.snapshot().muted is True

    state = client.messages_on("blinkysign/state")
    assert state, "no state published"
    assert json.loads(state[-1]["payload"])["muted"] is True
    assert state[-1]["retain"] is True


def test_set_command(rig):
    _, client, sign, _ = rig
    client.on_message(client, None, FakeMessage("blinkysign/cmd/set", '{"muted": true}'))
    assert sign.snapshot().muted is True
    client.on_message(client, None, FakeMessage("blinkysign/cmd/set", '{"muted": false}'))
    assert sign.snapshot().muted is False


@pytest.mark.parametrize("payload,expected", [
    ("on", True), ("true", True), ("muted", True),
    ("off", False), ("false", False), ("unmuted", False),
])
def test_set_accepts_bare_payloads(rig, payload, expected):
    _, client, sign, _ = rig
    client.on_message(client, None, FakeMessage("blinkysign/cmd/set", payload))
    assert sign.snapshot().muted is expected


@pytest.mark.parametrize("effect", ["rainbow", "pulse", "theater", "wipe"])
def test_every_effect_is_reachable_over_mqtt(rig, effect):
    """The old client hardcoded rainbow/pulse/off and silently dropped the rest."""
    bridge, client, sign, _ = rig
    client.on_message(client, None, FakeMessage(
        "blinkysign/cmd/effect",
        json.dumps({"effect": effect, "wait": 0.0, "cycles": 1, "duration": 0.05}),
    ))
    assert sign.wait_idle(timeout=10)


def test_effect_off_turns_the_leds_off(rig):
    _, client, sign, controller = rig
    client.on_message(client, None, FakeMessage(
        "blinkysign/cmd/effect", '{"effect": "off"}'))
    assert sign.wait_idle(timeout=5)
    assert sign.snapshot().led_on is False


def test_malformed_json_is_ignored_not_raised(rig):
    _, client, sign, _ = rig
    before = sign.snapshot().revision
    client.on_message(client, None, FakeMessage("blinkysign/cmd/set", b"\xff\xfe not json"))
    assert sign.snapshot().revision == before


def test_unknown_effect_does_not_raise(rig):
    _, client, sign, _ = rig
    client.on_message(client, None, FakeMessage(
        "blinkysign/cmd/effect", '{"effect": "disco"}'))


def test_bad_effect_params_do_not_raise(rig):
    _, client, sign, _ = rig
    client.on_message(client, None, FakeMessage(
        "blinkysign/cmd/effect", '{"effect": "pulse", "cycles": 9999}'))


def test_unknown_topic_is_ignored(rig):
    _, client, sign, _ = rig
    before = sign.snapshot().revision
    client.on_message(client, None, FakeMessage("blinkysign/nonsense", "{}"))
    assert sign.snapshot().revision == before


def test_http_side_changes_also_publish(rig):
    """One listener, so every input publishes identically."""
    _, client, sign, _ = rig
    sign.toggle()  # as an HTTP route or the button would
    assert json.loads(client.messages_on("blinkysign/state")[-1]["payload"])["muted"] is True


def test_stop_publishes_offline_and_detaches(rig):
    bridge, client, sign, _ = rig
    bridge.stop()
    assert client.messages_on("blinkysign/availability")[-1]["payload"] == "offline"

    published_before = len(client.published)
    sign.toggle()
    assert len(client.published) == published_before, "listener still attached"


def test_mutual_tls_is_configured_for_aws_iot():
    """tls=mutual on 8883 is the AWS IoT path, without CloudFormation."""
    controller = LEDController(count=4, mode="mock")
    sign = build_sign(Config(), controller)
    client = FakeClient()
    config = MqttConfig(
        enabled=True, host="xyz.iot.us-east-1.amazonaws.com", port=8883,
        tls="mutual", ca_cert="/c/AmazonRootCA1.pem",
        certfile="/c/cert.pem", keyfile="/c/private.key",
    )
    bridge = MqttBridge(config, sign, client_factory=lambda: client)
    try:
        bridge.start()
        assert client.tls["certfile"] == "/c/cert.pem"
        assert client.tls["keyfile"] == "/c/private.key"
        assert client.connected[1] == 8883
    finally:
        bridge.stop()
        sign.stop()


# -- build_bridge: MQTT must never be able to take down local control ------


def test_disabled_by_default():
    controller = LEDController(count=4, mode="mock")
    sign = build_sign(Config(), controller)
    try:
        assert build_bridge(MqttConfig(), sign) is None
    finally:
        sign.stop()


def test_enabled_without_a_host_is_not_fatal():
    controller = LEDController(count=4, mode="mock")
    sign = build_sign(Config(), controller)
    try:
        assert build_bridge(MqttConfig(enabled=True, host=""), sign) is None
    finally:
        sign.stop()


def test_a_broken_broker_config_is_not_fatal(monkeypatch):
    """One process now, so a bad broker must not stop the HTTP API."""
    controller = LEDController(count=4, mode="mock")
    sign = build_sign(Config(), controller)

    def explode(self):
        raise RuntimeError("no paho for you")

    monkeypatch.setattr(MqttBridge, "_build_client", explode)
    try:
        assert build_bridge(MqttConfig(enabled=True, host="broker.invalid"), sign) is None
        # The sign still works.
        assert sign.toggle().muted is True
    finally:
        sign.stop()
