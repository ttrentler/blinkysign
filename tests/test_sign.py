"""SignController is the single path every input takes.

Its job is to make it structurally impossible to reintroduce either of the two
bugs it replaces: the duplicated update_led_state() that let HTTP and MQTT
disagree, and the MQTT effect handler that only understood three of the four
effects the HTTP API exposed.
"""
import pytest

from blinkysign.colors import BLUE, GREEN, OFF, RED
from blinkysign.config import Config
from blinkysign.leds.controller import LEDController
from blinkysign.sign import BadEffectParams, SignController, build_sign
from blinkysign.worker import EFFECT_NAMES, UnknownEffect


@pytest.fixture
def sign():
    controller = LEDController(count=10, brightness=0.5, mode="mock")
    s = build_sign(Config(), controller)
    s._controller = controller  # for assertions
    yield s
    s.stop()


def frame(sign):
    assert sign.wait_idle(timeout=5)
    return sign._controller.strips[0].last_frame


def test_toggle_paints_the_muted_colour(sign):
    assert sign.toggle().muted is True
    assert all(px == GREEN for px in frame(sign))  # MUTED_COLOR default

    assert sign.toggle().muted is False
    assert all(px == RED for px in frame(sign))  # UNMUTED_COLOR default


def test_colours_are_configurable(sign):
    controller = LEDController(count=10, brightness=0.5, mode="mock")
    config = Config(muted_color=(1, 2, 3), unmuted_color=(4, 5, 6))
    s = build_sign(config, controller)
    try:
        s.set_muted(True)
        assert s.wait_idle(timeout=5)
        assert all(px == (1, 2, 3) for px in controller.strips[0].last_frame)
    finally:
        s.stop()


def test_turn_off(sign):
    sign.set_muted(True)
    snapshot = sign.turn_off()
    assert snapshot.led_on is False
    assert all(px == OFF for px in frame(sign))


def test_every_advertised_effect_is_runnable(sign):
    """MQTT and HTTP both dispatch here, so all four must work for both."""
    assert set(sign.effects) == set(EFFECT_NAMES)
    for name in sign.effects:
        sign.run_effect(name, wait=0.0, cycles=1, duration=0.05, iterations=1)
        assert sign.wait_idle(timeout=10)
    assert sign._worker.is_alive()


def test_unknown_effect_raises(sign):
    with pytest.raises(UnknownEffect):
        sign.run_effect("disco")


def test_run_effect_returns_immediately(sign):
    """Effects are asynchronous now -- hence the 202 the API returns."""
    import time

    started = time.monotonic()
    sign.run_effect("pulse", color="blue", cycles=10, duration=1.0)
    assert time.monotonic() - started < 0.2


@pytest.mark.parametrize(
    "params",
    [
        {"cycles": 0},
        {"cycles": 999},
        {"duration": -1},
        {"wait": 5},
        {"cycles": "lots"},
    ],
)
def test_bad_effect_params_are_rejected(sign, params):
    with pytest.raises(BadEffectParams):
        sign.run_effect("pulse", **params)


def test_unknown_colour_falls_back_rather_than_failing(sign, caplog):
    """Deliberately lenient, matching the original color_map.get(color, BLUE).

    An existing Stream Deck button configured with a typo keeps working; the
    fallback is logged rather than silent. Numeric parameters are strict
    instead, because the old code validated none of them and an unbounded
    cycles= would hold the strip for hours.
    """
    sign.run_effect("pulse", color="chartreuse-ish", cycles=1, duration=0.05)
    assert sign.wait_idle(timeout=5)
    assert any("unrecognised colour" in r.message for r in caplog.records)


def test_effect_colour_accepts_hex(sign):
    sign.run_effect("wipe", color="#0000ff", wait=0.0)
    assert sign.wait_idle(timeout=5)
    # The wipe returns to base afterwards, so assert it ran rather than the
    # final frame: the strip recorded a fully-blue frame at some point.
    frames = [f for _, f in sign._controller.strips[0].frames]
    assert any(all(px == BLUE for px in f) for f in frames)


def test_state_and_leds_never_disagree(sign):
    """The drift bug: state said one thing, the strip showed another."""
    for _ in range(5):
        snapshot = sign.toggle()
        expected = GREEN if snapshot.muted else RED
        assert all(px == expected for px in frame(sign))
