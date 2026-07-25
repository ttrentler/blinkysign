"""Physical button, in the same process as the state it changes.

physical_button.py used to run separately and toggle the sign by making an HTTP
request to the local API -- with no timeout, so a button press during a running
effect blocked the GPIO callback thread indefinitely. It also imported RPi.GPIO,
which is absent from the dependencies and does not work on the Pi 5 that the
README recommends.

gpiozero works across every Pi model, selecting lgpio on Bookworm, and it is a
direct call into SignController rather than a network round trip to ourselves.
"""
from __future__ import annotations

import logging
from typing import Optional

from blinkysign.sign import SignController

logger = logging.getLogger(__name__)


class PhysicalButton:
    """Wraps a gpiozero Button wired to SignController.toggle."""

    def __init__(self, pin: int, sign: SignController, bounce_time: float = 0.05,
                 button_factory=None):
        self._pin = pin
        self._sign = sign
        self._bounce_time = bounce_time
        self._button_factory = button_factory
        self._button = None

    def start(self) -> None:
        self._button = self._build_button()
        # gpiozero dispatches this on its own thread; SignController.toggle is
        # the locked path, so that is safe by construction.
        self._button.when_pressed = self._on_press
        logger.info("Physical button active on GPIO %d", self._pin)

    def stop(self) -> None:
        if self._button is None:
            return
        try:
            self._button.close()
        except Exception:
            logger.exception("error closing the button")
        self._button = None

    def _build_button(self):
        if self._button_factory is not None:
            return self._button_factory(self._pin)

        from gpiozero import Button

        return Button(self._pin, pull_up=True, bounce_time=self._bounce_time)

    def _on_press(self, *_args):
        try:
            snapshot = self._sign.toggle()
            logger.info(
                "Button pressed: now %s", "muted" if snapshot.muted else "unmuted"
            )
        except Exception:
            logger.exception("button handler failed")


def build_button(pin: Optional[int], sign: SignController) -> Optional[PhysicalButton]:
    """Return a started button, or None when no pin is configured."""
    if pin is None:
        return None

    button = PhysicalButton(pin, sign)
    try:
        button.start()
    except Exception:
        # A missing gpiozero or an unavailable pin must not stop the sign.
        logger.exception(
            "could not set up the button on GPIO %s; continuing without it", pin
        )
        return None
    return button
