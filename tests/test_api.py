"""HTTP API.

All nine original routes keep their paths, methods and response keys: existing
Stream Deck buttons and the web button depend on them. Fields are added, never
removed.
"""
import pytest

from blinkysign.config import Config
from blinkysign.leds.controller import LEDController
from blinkysign.server import create_app
from blinkysign.sign import build_sign


@pytest.fixture
def ctx():
    controller = LEDController(count=10, brightness=0.5, mode="mock")
    config = Config()
    sign = build_sign(config, controller)
    app = create_app(config, sign)
    app.config.update(TESTING=True)
    yield app.test_client(), sign, controller, config
    sign.stop()


@pytest.fixture
def client(ctx):
    return ctx[0]


# -- the original route table ---------------------------------------------

LEGACY_ROUTES = [
    ("GET", "/status", 200),
    ("PUT", "/toggle", 200),
    ("PUT", "/set", 400),          # 400 without a body, as before
    ("GET", "/health", 200),
    ("PUT", "/effects/rainbow", 202),
    ("PUT", "/effects/pulse", 202),
    ("PUT", "/effects/theater", 202),
    ("PUT", "/effects/wipe", 202),
    ("PUT", "/off", 200),
]


@pytest.mark.parametrize("method,path,expected", LEGACY_ROUTES)
def test_legacy_routes_still_exist(client, method, path, expected):
    response = client.open(path, method=method)
    assert response.status_code == expected


def test_status_keeps_its_original_keys(client):
    body = client.get("/status").get_json()
    assert "muted" in body and "led_on" in body
    assert isinstance(body["muted"], bool)


def test_toggle_envelope_is_unchanged(client):
    body = client.put("/toggle").get_json()
    assert body["status"] == "success"
    assert "message" in body
    assert body["state"]["muted"] is True
    assert "led_on" in body["state"]


def test_toggle_actually_flips(client):
    assert client.put("/toggle").get_json()["state"]["muted"] is True
    assert client.put("/toggle").get_json()["state"]["muted"] is False


def test_set_requires_muted_field(client):
    assert client.put("/set", json={}).status_code == 400
    assert client.put("/set", json={"nope": 1}).status_code == 400
    assert client.put("/set", data="not json",
                      content_type="application/json").status_code == 400


def test_set_works(client):
    body = client.put("/set", json={"muted": True}).get_json()
    assert body["state"]["muted"] is True


def test_off(client):
    body = client.put("/off").get_json()
    assert body["state"]["led_on"] is False


# -- effects are asynchronous now -----------------------------------------


def test_effects_return_202_and_name_the_effect(client):
    response = client.put("/effects/rainbow")
    assert response.status_code == 202
    body = response.get_json()
    assert body["effect"] == "rainbow"
    assert body["status"] == "accepted"


def test_effect_returns_promptly(client):
    """A ten-second pulse must not hold the request open for ten seconds."""
    import time

    started = time.monotonic()
    response = client.put("/effects/pulse", json={"cycles": 10, "duration": 1.0})
    assert response.status_code == 202
    assert time.monotonic() - started < 0.5


def test_bad_effect_params_are_400(client):
    assert client.put("/effects/pulse", json={"cycles": 999}).status_code == 400


def test_effects_accept_hex_colours(client):
    assert client.put("/effects/wipe", json={"color": "#ff8800"}).status_code == 202


# -- health ---------------------------------------------------------------


def test_health_reports_degraded_without_hardware(client):
    """The mock backend is not real hardware, so this must not claim health.

    A failed strip init used to be completely invisible: the API returned 200
    and "healthy" while nothing was connected.
    """
    body = client.get("/health").get_json()
    assert body["status"] == "degraded"
    assert body["leds"]["available"] is False
    assert body["leds"]["backend"] == "mock"


def test_health_is_200_even_when_degraded(client):
    """Deliberate: probes should not flap over a detached strip."""
    assert client.get("/health").status_code == 200


# -- the panel ------------------------------------------------------------


def test_flask_serves_the_control_panel(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"BlinkySign" in response.data


def test_flask_serves_the_web_button(client):
    assert client.get("/button").status_code == 200


def test_panel_has_no_placeholders_or_third_party_proxy(client):
    """The deploy script used to rewrite this tracked file with a live key."""
    page = client.get("/").data.decode()
    assert "PLACEHOLDER" not in page
    assert "corsproxy.io" not in page


def test_web_button_is_not_pinned_to_localhost(client):
    page = client.get("/button").data.decode()
    assert "http://localhost:5000" not in page


def test_api_config(client):
    body = client.get("/api/config").get_json()
    assert body["default_endpoint"] == ""      # same origin
    assert body["remote_endpoint"] is None
    assert body["requires_api_key"] is False
    assert set(body["effects"]) == {"rainbow", "pulse", "theater", "wipe"}
    assert "red" in body["colors"]


def test_api_config_advertises_a_remote_endpoint_when_set():
    controller = LEDController(count=5, mode="mock")
    config = Config(remote_endpoint="https://example.invalid/prod")
    sign = build_sign(config, controller)
    try:
        client = create_app(config, sign).test_client()
        assert client.get("/api/config").get_json()["remote_endpoint"] == (
            "https://example.invalid/prod"
        )
    finally:
        sign.stop()


# -- auth and CORS --------------------------------------------------------


def test_no_cors_header_by_default(client):
    """It used to be origins:"*" with no auth at all."""
    response = client.get("/status", headers={"Origin": "https://evil.invalid"})
    assert "Access-Control-Allow-Origin" not in response.headers


def test_cors_can_be_opted_into():
    controller = LEDController(count=5, mode="mock")
    config = Config(cors_origins=["https://good.invalid"])
    sign = build_sign(config, controller)
    try:
        client = create_app(config, sign).test_client()
        response = client.get("/status", headers={"Origin": "https://good.invalid"})
        assert response.headers.get("Access-Control-Allow-Origin") == "https://good.invalid"
    finally:
        sign.stop()


class TestTokenAuth:
    @pytest.fixture
    def client(self):
        controller = LEDController(count=5, mode="mock")
        config = Config(api_token="s3cret")
        sign = build_sign(config, controller)
        try:
            yield create_app(config, sign).test_client()
        finally:
            sign.stop()

    def test_mutating_routes_require_the_token(self, client):
        assert client.put("/toggle").status_code == 401
        assert client.put("/off").status_code == 401
        assert client.put("/effects/rainbow").status_code == 401

    def test_health_and_status_are_exempt(self, client):
        assert client.get("/health").status_code == 200
        assert client.get("/status").status_code == 200

    def test_x_api_key_header_works(self, client):
        assert client.put("/toggle", headers={"X-Api-Key": "s3cret"}).status_code == 200

    def test_bearer_token_works(self, client):
        assert client.put(
            "/toggle", headers={"Authorization": "Bearer s3cret"}
        ).status_code == 200

    def test_wrong_token_rejected(self, client):
        assert client.put("/toggle", headers={"X-Api-Key": "nope"}).status_code == 401

    def test_config_advertises_that_a_key_is_needed(self, client):
        assert client.get("/api/config").get_json()["requires_api_key"] is True
