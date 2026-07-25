"""Shared test configuration.

The mock backend is forced before any blinkysign import so that no test can
accidentally reach for SPI -- on a laptop that would merely warn and fall back,
but on a Pi it would drive the real strip during a test run.
"""
import os

os.environ.setdefault("BLINKYSIGN_BACKEND", "mock")
os.environ["BLINKYSIGN_BACKEND"] = "mock"

import pytest  # noqa: E402

from blinkysign.leds import reset_controller  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_controller():
    """Give every test its own LED controller."""
    reset_controller()
    yield
    reset_controller()
