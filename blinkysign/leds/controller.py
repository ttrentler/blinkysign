#!/usr/bin/env python3
"""
LED Controller for BlinkySign
Controls WS2812B LED strips connected to Raspberry Pi using SPI interface.

Hardware imports are deferred into the backend factory so this module can be
imported (and tested) on a machine without SPI. Select a backend explicitly
with BLINKYSIGN_BACKEND=auto|spi|mock|null; the default, auto, tries SPI and
falls back to the mock backend with a warning.
"""
import os
import time
import logging
import threading
from collections import deque

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# LED Configuration
LED_COUNT = int(os.getenv('LED_COUNT', 30))  # Number of LED pixels per strip
LED_BRIGHTNESS = float(os.getenv('LED_BRIGHTNESS', 0.5))  # Brightness (0.0 to 1.0)

# Backend selection
BACKEND_MODE = os.getenv('BLINKYSIGN_BACKEND', 'auto').strip().lower()

# Color definitions
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
PURPLE = (128, 0, 128)
CYAN = (0, 255, 255)
WHITE = (255, 255, 255)
OFF = (0, 0, 0)

# Default colors for different states
MUTED_COLOR = GREEN
UNMUTED_COLOR = RED
CONNECTING_COLOR = BLUE
ERROR_COLOR = YELLOW


class MockStrip:
    """In-memory stand-in for a NeoPixel strip.

    Implements the subset of the NeoPixel_SPI interface the controller uses, and
    records every show() so tests can assert on what would have been displayed.
    """

    MAX_FRAMES = 2048

    def __init__(self, count, brightness=1.0):
        self._pixels = [OFF] * count
        self.brightness = brightness
        self.frames = deque(maxlen=self.MAX_FRAMES)
        self.show_count = 0

    def __len__(self):
        return len(self._pixels)

    def __getitem__(self, index):
        return self._pixels[index]

    def __setitem__(self, index, color):
        self._pixels[index] = tuple(color)

    def fill(self, color):
        self._pixels = [tuple(color)] * len(self._pixels)

    def show(self):
        self.show_count += 1
        self.frames.append((self.brightness, list(self._pixels)))

    @property
    def last_frame(self):
        """The pixel buffer as of the most recent show(), or None."""
        return self.frames[-1][1] if self.frames else None


def _create_spi_strip(count, brightness):
    """Build a real SPI-backed NeoPixel strip. Imports hardware libs lazily."""
    import board
    import busio
    import neopixel_spi

    spi = busio.SPI(clock=board.SCK, MOSI=board.MOSI)
    return neopixel_spi.NeoPixel_SPI(
        spi, count, brightness=brightness, auto_write=False
    )


def create_strips(count, brightness, mode=None):
    """Build the strip list for a backend mode.

    Returns (strips, backend_name). backend_name is one of spi, mock, null.
    """
    mode = (mode or BACKEND_MODE or 'auto').strip().lower()

    if mode == 'mock':
        return [MockStrip(count, brightness)], 'mock'

    if mode == 'null':
        return [], 'null'

    try:
        strip = _create_spi_strip(count, brightness)
    except Exception as e:
        if mode == 'spi':
            # Explicitly asked for hardware; don't silently pretend.
            logger.error("SPI backend requested but unavailable: %s", e)
            return [], 'null'
        logger.warning(
            "SPI unavailable (%s) -- falling back to the mock backend. "
            "No LEDs will light up. Set BLINKYSIGN_BACKEND=spi to make this fatal.",
            e,
        )
        return [MockStrip(count, brightness)], 'mock'

    logger.info("SPI NeoPixel strip initialized")
    return [strip], 'spi'


class LEDController:
    """Controller for WS2812B LED strips."""

    def __init__(self, count=None, brightness=None, mode=None):
        self.led_count = LED_COUNT if count is None else count
        self.brightness = LED_BRIGHTNESS if brightness is None else brightness

        self.strips, self.backend_name = create_strips(
            self.led_count, self.brightness, mode
        )
        self.active_strips = len(self.strips)
        logger.info(
            "Initialized %d LED strip(s) on the %s backend",
            self.active_strips,
            self.backend_name,
        )

    @property
    def available(self):
        """True only when real hardware is driving the LEDs."""
        return self.backend_name == 'spi' and bool(self.strips)

    def _max_len(self):
        """Longest strip, so effects stay correct with mixed-length strips."""
        return max((len(s) for s in self.strips), default=0)

    def set_all_strips(self, color):
        """Set all strips to the same color"""
        for strip in self.strips:
            strip.fill(color)
            strip.show()
        logger.info(f"All strips set to color: {color}")

    def set_strip(self, strip_index, color):
        """Set a specific strip to a color"""
        if 0 <= strip_index < len(self.strips):
            self.strips[strip_index].fill(color)
            self.strips[strip_index].show()
            logger.info(f"Strip {strip_index} set to color: {color}")
        else:
            logger.error(f"Invalid strip index: {strip_index}")

    def set_muted(self):
        """Set LEDs to the muted state (MUTED_COLOR, green by default)"""
        self.set_all_strips(MUTED_COLOR)
        logger.info("LEDs set to MUTED state")

    def set_unmuted(self):
        """Set LEDs to the unmuted state (UNMUTED_COLOR, red by default)"""
        self.set_all_strips(UNMUTED_COLOR)
        logger.info("LEDs set to UNMUTED state")

    def set_connecting(self):
        """Set LEDs to connecting state (blue)"""
        self.set_all_strips(CONNECTING_COLOR)
        logger.info("LEDs set to CONNECTING state")

    def set_error(self):
        """Set LEDs to error state (yellow)"""
        self.set_all_strips(ERROR_COLOR)
        logger.info("LEDs set to ERROR state")

    def turn_off(self):
        """Turn off all LEDs"""
        self.set_all_strips(OFF)
        logger.info("All LEDs turned off")

    @staticmethod
    def _wheel(pos):
        """Generate rainbow colors across 0-255 positions"""
        if pos < 85:
            return (pos * 3, 255 - pos * 3, 0)
        elif pos < 170:
            pos -= 85
            return (255 - pos * 3, 0, pos * 3)
        else:
            pos -= 170
            return (0, pos * 3, 255 - pos * 3)

    def rainbow_cycle(self, wait=0.01):
        """Rainbow cycle animation across all strips"""
        for j in range(255):
            for strip in self.strips:
                for i in range(len(strip)):
                    strip[i] = self._wheel((i + j) & 255)
                strip.show()
            time.sleep(wait)

    def theater_chase(self, color, wait=0.05, iterations=10):
        """Movie theater light style chaser animation."""
        for _ in range(iterations):
            for q in range(3):
                for strip in self.strips:
                    for i in range(q, len(strip), 3):
                        strip[i] = color
                    strip.show()

                time.sleep(wait)

                for strip in self.strips:
                    for i in range(q, len(strip), 3):
                        strip[i] = OFF
                    strip.show()

    def color_wipe(self, color, wait=0.05):
        """Fill the dots one after the other with a color."""
        for i in range(self._max_len()):
            for strip in self.strips:
                if i < len(strip):
                    strip[i] = color
                    strip.show()
            time.sleep(wait)

    def pulse(self, color, cycles=3, duration=1.0):
        """Pulse effect on all strips"""
        steps = 50
        try:
            for _ in range(cycles):
                # Fade in
                for i in range(steps):
                    self._render_at_brightness(color, i / steps)
                    time.sleep(duration / (2 * steps))

                # Fade out
                for i in range(steps, 0, -1):
                    self._render_at_brightness(color, i / steps)
                    time.sleep(duration / (2 * steps))
        finally:
            # Always restore, even if interrupted -- otherwise the strip is
            # left stuck at whatever brightness the loop last set.
            for strip in self.strips:
                strip.brightness = self.brightness

    def _render_at_brightness(self, color, brightness):
        for strip in self.strips:
            strip.brightness = brightness
            strip.fill(color)
            strip.show()


# Process-local controller. Built lazily so that importing this module never
# touches hardware -- that was the reason nothing here could be imported or
# tested off a Pi.
_controller = None
_controller_lock = threading.Lock()


def get_controller():
    """Return the process-wide LEDController, building it on first use."""
    global _controller
    if _controller is None:
        with _controller_lock:
            if _controller is None:
                _controller = LEDController()
    return _controller


def reset_controller():
    """Drop the cached controller so the next get_controller() rebuilds it.

    Only useful in tests -- the LED strip is a process-wide singleton in
    production and should not be swapped out under a running worker.
    """
    global _controller
    with _controller_lock:
        _controller = None


def main():
    """Run through colors and effects to verify the strips are working."""
    controller = get_controller()
    if not controller.available:
        logger.warning(
            "Running on the '%s' backend -- this is a dry run, no LEDs will light up.",
            controller.backend_name,
        )
    # Don't make a hardware-free dry run sit through 12 seconds of sleeps.
    hold = 1.0 if controller.available else 0.05

    try:
        logger.info("Testing LED strips...")

        for name, color in (
            ("RED", RED),
            ("GREEN", GREEN),
            ("BLUE", BLUE),
            ("YELLOW", YELLOW),
        ):
            logger.info("Testing %s", name)
            controller.set_all_strips(color)
            time.sleep(hold)

        logger.info("Testing MUTED state")
        controller.set_muted()
        time.sleep(hold)

        logger.info("Testing UNMUTED state")
        controller.set_unmuted()
        time.sleep(hold)

        logger.info("Testing rainbow cycle")
        controller.rainbow_cycle(wait=0.01 if controller.available else 0.0)

        logger.info("Testing theater chase")
        controller.theater_chase(WHITE, wait=0.05 if controller.available else 0.0,
                                 iterations=10 if controller.available else 2)

        logger.info("Testing color wipe")
        controller.color_wipe(CYAN, wait=0.05 if controller.available else 0.0)

        logger.info("Testing pulse effect")
        controller.pulse(BLUE, duration=1.0 if controller.available else 0.05)

        controller.turn_off()
        logger.info("Test complete")
        return 0

    except KeyboardInterrupt:
        controller.turn_off()
        logger.info("Test interrupted")
        return 130
    except Exception as e:
        logger.error(f"Test error: {e}")
        controller.set_error()
        time.sleep(2)
        controller.turn_off()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
