"""MQTT bridge -- remote control through any broker.

This replaces iot_client.py, which spoke to AWS IoT Core through the legacy
AWSIoTPythonSDK and required an AWS account, CloudFormation, API Gateway, IAM
and a certificate flow that did not actually work. Plain MQTT reaches a local
Mosquitto, a free HiveMQ or EMQX tier, or -- with tls=mutual on port 8883 --
AWS IoT Core directly, with no CloudFormation involved.

Two rules hold this together:

  * Callbacks only ever call SignController. They never touch the LED strip.
    The old client ran a two-and-a-half second rainbow_cycle inline on the SDK's
    network thread while a second process drove the same SPI bus.
  * Connection is asynchronous and failure is non-fatal. Local HTTP control must
    keep working when the broker is unreachable or misconfigured, because this
    is now one process rather than two.
"""
from __future__ import annotations

import json
import logging
import ssl
from typing import Optional

from blinkysign.config import MqttConfig
from blinkysign.sign import BadEffectParams, SignController
from blinkysign.worker import UnknownEffect

logger = logging.getLogger(__name__)

ONLINE = "online"
OFFLINE = "offline"


class MqttBridge:
    """Publishes sign state and accepts commands over MQTT."""

    def __init__(self, config: MqttConfig, sign: SignController, client_factory=None):
        self._config = config
        self._sign = sign
        self._client_factory = client_factory
        self._client = None
        self._remove_listener = None

    # -- topics ---------------------------------------------------------

    @property
    def base(self) -> str:
        return self._config.base_topic

    @property
    def state_topic(self) -> str:
        return f"{self.base}/state"

    @property
    def availability_topic(self) -> str:
        return f"{self.base}/availability"

    def command_topic(self, name: str) -> str:
        return f"{self.base}/cmd/{name}"

    # -- lifecycle ------------------------------------------------------

    def start(self) -> None:
        client = self._build_client()
        self._client = client

        client.will_set(self.availability_topic, OFFLINE, qos=1, retain=True)
        if self._config.username:
            client.username_pw_set(self._config.username, self._config.password)
        self._configure_tls(client)

        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message

        # State changes -- from HTTP, the button, or MQTT itself -- all publish
        # through the same listener, so every input produces the same update.
        self._remove_listener = self._sign.add_listener(self._publish_snapshot)

        # connect_async + loop_start never block startup. A broker that is down
        # or misconfigured must not prevent the sign from serving HTTP.
        logger.info(
            "MQTT connecting to %s:%d (topics under %s/)",
            self._config.host, self._config.port, self.base,
        )
        client.connect_async(self._config.host, self._config.port, self._config.keepalive)
        client.loop_start()

    def stop(self) -> None:
        if self._remove_listener is not None:
            self._remove_listener()
            self._remove_listener = None
        if self._client is None:
            return
        try:
            self._client.publish(self.availability_topic, OFFLINE, qos=1, retain=True)
            self._client.disconnect()
            self._client.loop_stop()
        except Exception:
            logger.exception("error while stopping the MQTT client")
        self._client = None

    def _build_client(self):
        if self._client_factory is not None:
            return self._client_factory()

        import paho.mqtt.client as mqtt

        # paho 2.x requires the callback API version; 1.x does not accept it.
        try:
            return mqtt.Client(
                mqtt.CallbackAPIVersion.VERSION1,
                client_id=self._config.client_id,
            )
        except AttributeError:  # pragma: no cover - paho 1.x
            return mqtt.Client(client_id=self._config.client_id)

    def _configure_tls(self, client) -> None:
        mode = (self._config.tls or "none").lower()
        if mode == "none":
            return
        if mode == "server":
            client.tls_set(ca_certs=self._config.ca_cert, cert_reqs=ssl.CERT_REQUIRED)
        elif mode == "mutual":
            # This is the AWS IoT Core path: mutual TLS on 8883 with the device
            # certificate, no API Gateway and no CloudFormation.
            client.tls_set(
                ca_certs=self._config.ca_cert,
                certfile=self._config.certfile,
                keyfile=self._config.keyfile,
                cert_reqs=ssl.CERT_REQUIRED,
            )
        else:
            logger.warning("unknown MQTT tls mode %r; continuing without TLS", mode)

    # -- callbacks ------------------------------------------------------

    def _on_connect(self, client, userdata, flags, rc, *args):
        if rc != 0:
            logger.error("MQTT connection refused (code %s)", rc)
            return
        logger.info("MQTT connected")
        for name in ("set", "toggle", "effect"):
            client.subscribe(self.command_topic(name), qos=1)
        client.publish(self.availability_topic, ONLINE, qos=1, retain=True)
        self._publish_snapshot(self._sign.snapshot())

    def _on_disconnect(self, client, userdata, rc, *args):
        if rc != 0:
            logger.warning("MQTT disconnected unexpectedly (code %s); will retry", rc)
        else:
            logger.info("MQTT disconnected")

    def _on_message(self, client, userdata, message):
        topic = message.topic
        try:
            payload = self._decode(message.payload)
        except ValueError as e:
            logger.warning("ignoring malformed payload on %s: %s", topic, e)
            return

        try:
            if topic == self.command_topic("toggle"):
                self._sign.toggle()
            elif topic == self.command_topic("set"):
                self._handle_set(payload)
            elif topic == self.command_topic("effect"):
                self._handle_effect(payload)
            else:
                logger.debug("ignoring message on unhandled topic %s", topic)
        except Exception:
            # A bad command must never take down the network thread.
            logger.exception("error handling MQTT message on %s", topic)

    @staticmethod
    def _decode(raw) -> dict:
        text = raw.decode("utf-8", errors="replace").strip() if isinstance(raw, bytes) else str(raw).strip()
        if not text:
            return {}
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Tolerate bare payloads like "on" / "true" on cmd/set.
            return {"_raw": text}
        if not isinstance(data, dict):
            return {"_raw": data}
        return data

    def _handle_set(self, payload: dict) -> None:
        if "muted" in payload:
            self._sign.set_muted(bool(payload["muted"]))
            return

        raw = payload.get("_raw")
        if isinstance(raw, bool):
            self._sign.set_muted(raw)
        elif isinstance(raw, str) and raw.lower() in ("on", "true", "muted", "1"):
            self._sign.set_muted(True)
        elif isinstance(raw, str) and raw.lower() in ("off", "false", "unmuted", "0"):
            self._sign.set_muted(False)
        else:
            logger.warning("cmd/set without a usable 'muted' field: %r", payload)

    def _handle_effect(self, payload: dict) -> None:
        name = payload.get("effect") or payload.get("_raw")
        if not isinstance(name, str):
            logger.warning("cmd/effect without an effect name: %r", payload)
            return

        if name == "off":
            self._sign.turn_off()
            return

        params = {k: v for k, v in payload.items() if k not in ("effect", "_raw")}
        try:
            # Dispatching through run_effect is what keeps MQTT and HTTP in
            # step; the old client hardcoded rainbow/pulse/off and silently
            # ignored the theater and wipe effects the HTTP API exposed.
            self._sign.run_effect(name, **params)
        except UnknownEffect:
            logger.warning("unknown effect %r requested over MQTT", name)
        except BadEffectParams as e:
            logger.warning("bad parameters for effect %r: %s", name, e)

    # -- publishing -----------------------------------------------------

    def _publish_snapshot(self, snapshot) -> None:
        if self._client is None:
            return
        try:
            self._client.publish(
                self.state_topic,
                json.dumps(snapshot.to_dict()),
                qos=0,
                retain=True,
            )
        except Exception:
            logger.exception("failed to publish state")


def build_bridge(config: MqttConfig, sign: SignController) -> Optional[MqttBridge]:
    """Return a started bridge, or None when MQTT is disabled or unusable."""
    if not config.enabled:
        logger.info("MQTT disabled")
        return None
    if not config.host:
        logger.error("MQTT is enabled but BLINKYSIGN_MQTT_HOST is not set; skipping")
        return None

    bridge = MqttBridge(config, sign)
    try:
        bridge.start()
    except Exception:
        # Never fatal: local HTTP control has to survive a bad broker config.
        logger.exception("could not start the MQTT bridge; continuing without it")
        return None
    return bridge
