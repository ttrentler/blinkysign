"""The LED worker: one thread owns the strip, effects preempt within a frame.

Before this, effects ran synchronously inside the Flask request handler with
time.sleep() in the loop, so pulse(cycles=10) held the strip -- and the HTTP
response -- for roughly ten seconds with no way to interrupt it.
"""
import time

import pytest

from blinkysign.colors import BLUE, GREEN, OFF, RED, WHITE
from blinkysign.leds.controller import LEDController
from blinkysign.worker import EFFECT, SOLID, Command, LedWorker, UnknownEffect


@pytest.fixture
def controller():
    return LEDController(count=12, brightness=0.5, mode="mock")


@pytest.fixture
def worker(controller):
    w = LedWorker(controller)
    w.start()
    yield w
    w.stop()


def strip_of(controller):
    return controller.strips[0]


def test_solid_command_paints_the_strip(controller, worker):
    worker.submit(Command(kind=SOLID, color=GREEN))
    assert worker.wait_idle(timeout=5)
    assert all(px == GREEN for px in strip_of(controller).last_frame)


def test_effect_is_preempted_within_a_frame(controller, worker):
    """The headline fix: a state change interrupts a long animation fast."""
    # 10 cycles at 1s each is ~10 seconds of animation in the old design.
    worker.submit(
        Command(kind=EFFECT, effect="pulse", params={"color": BLUE, "cycles": 10, "duration": 1.0})
    )
    time.sleep(0.2)  # let it get going

    started = time.monotonic()
    worker.submit(Command(kind=SOLID, color=GREEN))
    assert worker.wait_idle(timeout=5)
    elapsed = time.monotonic() - started

    assert elapsed < 0.5, f"preemption took {elapsed:.2f}s; expected roughly one frame"
    assert all(px == GREEN for px in strip_of(controller).last_frame)


def test_cancelled_pulse_restores_brightness(controller, worker):
    worker.submit(
        Command(kind=EFFECT, effect="pulse", params={"color": BLUE, "cycles": 10, "duration": 1.0})
    )
    time.sleep(0.2)
    worker.submit(Command(kind=SOLID, color=RED))
    assert worker.wait_idle(timeout=5)

    assert strip_of(controller).brightness == pytest.approx(0.5), (
        "brightness left at a fade value; the strip would stay dim"
    )


def test_effect_returns_to_the_base_state_when_it_finishes(controller, worker):
    """An effect is transient: the sign goes back to what it was showing."""
    worker.submit(Command(kind=SOLID, color=GREEN))
    assert worker.wait_idle(timeout=5)

    worker.submit(
        Command(kind=EFFECT, effect="wipe", params={"color": BLUE, "wait": 0.0})
    )
    assert worker.wait_idle(timeout=5)

    assert all(px == GREEN for px in strip_of(controller).last_frame), (
        "did not return to the persistent state after the effect"
    )


def test_turn_off_preempts_and_stays_off(controller, worker):
    worker.submit(
        Command(kind=EFFECT, effect="rainbow", params={"wait": 0.01})
    )
    time.sleep(0.1)
    worker.submit(Command(kind=SOLID, color=OFF))
    assert worker.wait_idle(timeout=5)
    assert all(px == OFF for px in strip_of(controller).last_frame)


def test_newer_command_replaces_a_pending_one(controller, worker):
    worker.submit(Command(kind=EFFECT, effect="rainbow", params={"wait": 0.01}))
    worker.submit(Command(kind=SOLID, color=RED))
    worker.submit(Command(kind=SOLID, color=BLUE))
    assert worker.wait_idle(timeout=5)
    assert all(px == BLUE for px in strip_of(controller).last_frame)


def test_unknown_effect_does_not_kill_the_worker(controller, worker):
    worker.submit(Command(kind=EFFECT, effect="disco"))
    time.sleep(0.1)
    worker.submit(Command(kind=SOLID, color=GREEN))
    assert worker.wait_idle(timeout=5)
    assert worker.is_alive()
    assert all(px == GREEN for px in strip_of(controller).last_frame)


def test_effect_change_callback_brackets_the_run(controller):
    seen = []
    w = LedWorker(controller, on_effect_change=seen.append)
    w.start()
    try:
        w.submit(Command(kind=EFFECT, effect="wipe", params={"color": RED, "wait": 0.0}))
        assert w.wait_idle(timeout=5)
    finally:
        w.stop()
    assert seen == ["wipe", None]


@pytest.mark.parametrize("count", [1, 7, 30, 31])
@pytest.mark.parametrize("effect,params", [
    ("rainbow", {"wait": 0.0}),
    ("wipe", {"color": BLUE, "wait": 0.0}),
    ("theater", {"color": WHITE, "wait": 0.0, "iterations": 2}),
    ("pulse", {"color": BLUE, "cycles": 1, "duration": 0.02}),
])
def test_every_effect_survives_every_strip_length(count, effect, params):
    """Direct regression for the LED_COUNT-versus-len(strip) bug.

    theater_chase and color_wipe used to iterate the module-global LED_COUNT,
    so any strip that was not exactly that length raised IndexError or left its
    tail dark.
    """
    controller = LEDController(count=count, brightness=0.5, mode="mock")
    w = LedWorker(controller)
    w.start()
    try:
        w.submit(Command(kind=EFFECT, effect=effect, params=params))
        assert w.wait_idle(timeout=10)
        assert w.is_alive()
        assert len(strip_of(controller).last_frame) == count
    finally:
        w.stop()


def test_stop_is_idempotent_and_joins(controller):
    w = LedWorker(controller)
    w.start()
    w.stop()
    w.stop()
    assert not w.is_alive()
