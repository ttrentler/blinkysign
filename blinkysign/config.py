"""Configuration, read once from the environment.

Legacy names (PORT, LED_COUNT, LED_BRIGHTNESS, BUTTON_PIN) are still honoured
so existing .env files keep working; the BLINKYSIGN_-prefixed names win when
both are set.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional

from blinkysign.colors import GREEN, RED, RGB, parse_color


def _env(*names: str, default: Optional[str] = None) -> Optional[str]:
    """First of `names` that is set in the environment."""
    for name in names:
        value = os.getenv(name)
        if value is not None and value != "":
            return value
    return default


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_int(*names: str, default: int) -> int:
    raw = _env(*names)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(*names: str, default: float) -> float:
    raw = _env(*names)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass
class MqttConfig:
    enabled: bool = False
    host: str = ""
    port: int = 1883
    username: Optional[str] = None
    password: Optional[str] = None
    client_id: str = "blinkysign"
    base_topic: str = "blinkysign"
    tls: str = "none"  # none | server | mutual
    ca_cert: Optional[str] = None
    certfile: Optional[str] = None
    keyfile: Optional[str] = None
    keepalive: int = 60


@dataclass
class Config:
    host: str = "0.0.0.0"
    port: int = 5000

    led_count: int = 30
    led_brightness: float = 0.5
    backend: str = "auto"

    muted_color: RGB = GREEN
    unmuted_color: RGB = RED

    api_token: Optional[str] = None
    cors_origins: List[str] = field(default_factory=list)

    remote_endpoint: Optional[str] = None

    button_pin: Optional[int] = None

    mdns_enabled: bool = True
    mdns_name: str = "blinkysign"

    mqtt: MqttConfig = field(default_factory=MqttConfig)

    @classmethod
    def from_env(cls) -> "Config":
        thing = _env("BLINKYSIGN_NAME", "IOT_THING_NAME", default="blinkysign")

        button_raw = _env("BLINKYSIGN_BUTTON_PIN", "BUTTON_PIN")
        try:
            button_pin = int(button_raw) if button_raw is not None else None
        except ValueError:
            button_pin = None

        cors_raw = _env("BLINKYSIGN_CORS_ORIGINS", default="") or ""
        cors_origins = [o.strip() for o in cors_raw.split(",") if o.strip()]

        mqtt = MqttConfig(
            enabled=_env_bool("BLINKYSIGN_MQTT_ENABLED", False),
            host=_env("BLINKYSIGN_MQTT_HOST", default="") or "",
            port=_env_int("BLINKYSIGN_MQTT_PORT", default=1883),
            username=_env("BLINKYSIGN_MQTT_USERNAME"),
            password=_env("BLINKYSIGN_MQTT_PASSWORD"),
            client_id=_env("BLINKYSIGN_MQTT_CLIENT_ID", default=thing) or thing,
            base_topic=(
                _env("BLINKYSIGN_MQTT_BASE_TOPIC", default=thing) or thing
            ).rstrip("/"),
            tls=(_env("BLINKYSIGN_MQTT_TLS", default="none") or "none").lower(),
            ca_cert=_env("BLINKYSIGN_MQTT_CA_CERT"),
            certfile=_env("BLINKYSIGN_MQTT_CERTFILE"),
            keyfile=_env("BLINKYSIGN_MQTT_KEYFILE"),
            keepalive=_env_int("BLINKYSIGN_MQTT_KEEPALIVE", default=60),
        )

        return cls(
            host=_env("BLINKYSIGN_HOST", default="0.0.0.0") or "0.0.0.0",
            port=_env_int("BLINKYSIGN_PORT", "PORT", default=5000),
            led_count=_env_int("BLINKYSIGN_LED_COUNT", "LED_COUNT", default=30),
            led_brightness=_env_float(
                "BLINKYSIGN_LED_BRIGHTNESS", "LED_BRIGHTNESS", default=0.5
            ),
            backend=(_env("BLINKYSIGN_BACKEND", default="auto") or "auto").lower(),
            muted_color=parse_color(_env("BLINKYSIGN_MUTED_COLOR"), default=GREEN),
            unmuted_color=parse_color(_env("BLINKYSIGN_UNMUTED_COLOR"), default=RED),
            api_token=_env("BLINKYSIGN_API_TOKEN"),
            cors_origins=cors_origins,
            remote_endpoint=_env("BLINKYSIGN_REMOTE_ENDPOINT"),
            button_pin=button_pin,
            mdns_enabled=_env_bool("BLINKYSIGN_MDNS_ENABLED", True),
            mdns_name=_env("BLINKYSIGN_MDNS_NAME", default=thing) or thing,
            mqtt=mqtt,
        )
