"""Physical button, driven through a fake gpiozero Button."""
import pytest

from blinkysign.button import PhysicalButton, build_button
from blinkysign.config import Config
from blinkysign.leds.controller import LEDController
from blinkysign.sign import build_sign


class FakeButton:
    def __init__(self, pin):
        self.pin = pin
        self.when_pressed = None
        self.closed = False

    def press(self):
        self.when_pressed()

    def close(self):
        self.closed = True


@pytest.fixture
def rig():
    controller = LEDController(count=6, mode="mock")
    sign = build_sign(Config(), controller)
    fakes = []

    def factory(pin):
        fake = FakeButton(pin)
        fakes.append(fake)
        return fake

    button = PhysicalButton(17, sign, button_factory=factory)
    button.start()
    try:
        yield button, fakes[0], sign, controller
    finally:
        button.stop()
        sign.stop()


def test_press_toggles_the_sign(rig):
    _, fake, sign, _ = rig
    fake.press()
    assert sign.snapshot().muted is True
    fake.press()
    assert sign.snapshot().muted is False


def test_press_drives_the_leds(rig):
    _, fake, sign, controller = rig
    fake.press()
    assert sign.wait_idle(timeout=5)
    assert all(px == (0, 255, 0) for px in controller.strips[0].last_frame)


def test_uses_the_configured_pin(rig):
    _, fake, _, _ = rig
    assert fake.pin == 17


def test_stop_closes_the_button(rig):
    button, fake, _, _ = rig
    button.stop()
    assert fake.closed


def test_a_failing_toggle_does_not_escape_the_callback(rig):
    """A GPIO callback that raises would otherwise kill gpiozero's thread."""
    _, fake, sign, _ = rig

    def boom():
        raise RuntimeError("nope")

    sign.toggle = boom
    fake.press()  # must not raise


def test_no_pin_means_no_button():
    controller = LEDController(count=4, mode="mock")
    sign = build_sign(Config(), controller)
    try:
        assert build_button(None, sign) is None
    finally:
        sign.stop()


def test_missing_gpiozero_is_not_fatal():
    """A laptop, or a Pi without gpiozero, still runs the rest of the sign."""
    controller = LEDController(count=4, mode="mock")
    sign = build_sign(Config(), controller)
    try:
        # gpiozero is not installed in the dev environment, so the real
        # factory import fails -- and that must be survivable.
        assert build_button(17, sign) is None
        assert sign.toggle().muted is True
    finally:
        sign.stop()
