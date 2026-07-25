"""Colour names and parsing.

This used to be four byte-identical color_map dicts -- three in app.py and one
in iot_client.py -- all shadowing constants that already existed in the LED
controller. There is now one table, and it is the only one.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

RGB = Tuple[int, int, int]

RED: RGB = (255, 0, 0)
GREEN: RGB = (0, 255, 0)
BLUE: RGB = (0, 0, 255)
YELLOW: RGB = (255, 255, 0)
PURPLE: RGB = (128, 0, 128)
CYAN: RGB = (0, 255, 255)
WHITE: RGB = (255, 255, 255)
OFF: RGB = (0, 0, 0)

# The seven names the HTTP API and control panel have always accepted. These
# values are load-bearing for existing Stream Deck buttons; a regression test
# pins them.
NAMED_COLORS: Dict[str, RGB] = {
    "red": RED,
    "green": GREEN,
    "blue": BLUE,
    "yellow": YELLOW,
    "purple": PURPLE,
    "cyan": CYAN,
    "white": WHITE,
    "off": OFF,
}


class BadColor(ValueError):
    """Raised when a colour string cannot be interpreted."""


def _clamp(value: int) -> int:
    return max(0, min(255, value))


def parse_color(value, default: Optional[RGB] = None) -> RGB:
    """Interpret a colour.

    Accepts a known name ("red"), a hex string ("#RRGGBB" or "RGB"), or a
    comma-separated triple ("255,0,0"). Also accepts an already-parsed
    (r, g, b) sequence so callers can pass either through.

    Raises BadColor when the value is unusable and no default was supplied.
    """
    if value is None:
        if default is not None:
            return default
        raise BadColor("no colour given")

    # Already a triple.
    if isinstance(value, (tuple, list)):
        if len(value) != 3:
            raise BadColor(f"expected 3 components, got {len(value)}")
        try:
            return tuple(_clamp(int(c)) for c in value)  # type: ignore[return-value]
        except (TypeError, ValueError):
            raise BadColor(f"non-numeric colour component in {value!r}")

    if not isinstance(value, str):
        raise BadColor(f"cannot interpret {value!r} as a colour")

    text = value.strip().lower()
    if not text:
        if default is not None:
            return default
        raise BadColor("empty colour")

    if text in NAMED_COLORS:
        return NAMED_COLORS[text]

    if text.startswith("#"):
        return _parse_hex(text[1:])

    if "," in text:
        parts = [p.strip() for p in text.split(",")]
        if len(parts) != 3:
            raise BadColor(f"expected 3 components in {value!r}")
        try:
            return tuple(_clamp(int(p)) for p in parts)  # type: ignore[return-value]
        except ValueError:
            raise BadColor(f"non-numeric colour component in {value!r}")

    # Bare hex, e.g. "ff0000" -- but only if it actually looks like hex, so a
    # typo'd name reports as an unknown name rather than a bad hex string.
    if len(text) in (3, 6) and all(c in "0123456789abcdef" for c in text):
        return _parse_hex(text)

    if default is not None:
        return default
    raise BadColor(f"unknown colour {value!r}")


def _parse_hex(digits: str) -> RGB:
    if len(digits) == 3:
        digits = "".join(c * 2 for c in digits)
    if len(digits) != 6 or any(c not in "0123456789abcdef" for c in digits):
        raise BadColor(f"bad hex colour {digits!r}")
    return (
        int(digits[0:2], 16),
        int(digits[2:4], 16),
        int(digits[4:6], 16),
    )
