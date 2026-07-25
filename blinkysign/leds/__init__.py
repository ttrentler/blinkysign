"""LED hardware access.

Importing this package never touches hardware; the SPI libraries are imported
lazily by the backend factory so the rest of BlinkySign can be imported and
tested on a machine without a strip attached.
"""

from blinkysign.leds.controller import (
    LEDController,
    get_controller,
    reset_controller,
)

__all__ = ["LEDController", "get_controller", "reset_controller"]
