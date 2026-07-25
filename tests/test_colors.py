"""The seven legacy colour names are load-bearing for existing Stream Deck
buttons, so their RGB values are pinned here. This is the regression test that
lets the four duplicated color_map dicts be collapsed into one table safely.
"""
import pytest

from blinkysign.colors import BadColor, NAMED_COLORS, parse_color

LEGACY = {
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "yellow": (255, 255, 0),
    "purple": (128, 0, 128),
    "cyan": (0, 255, 255),
    "white": (255, 255, 255),
}


@pytest.mark.parametrize("name,rgb", sorted(LEGACY.items()))
def test_legacy_names_keep_their_values(name, rgb):
    assert NAMED_COLORS[name] == rgb
    assert parse_color(name) == rgb


def test_name_is_case_and_space_insensitive():
    assert parse_color("  ReD  ") == (255, 0, 0)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("#ff0000", (255, 0, 0)),
        ("#FF0000", (255, 0, 0)),
        ("#f00", (255, 0, 0)),
        ("ff0000", (255, 0, 0)),
        ("255,0,0", (255, 0, 0)),
        ("255, 0, 0", (255, 0, 0)),
    ],
)
def test_hex_and_triple_forms(text, expected):
    assert parse_color(text) == expected


def test_components_are_clamped():
    assert parse_color("999,-5,0") == (255, 0, 0)


def test_tuple_passes_through():
    assert parse_color((1, 2, 3)) == (1, 2, 3)


def test_unknown_falls_back_to_default():
    assert parse_color("chartreuse", default=(0, 0, 255)) == (0, 0, 255)


def test_unknown_without_default_raises():
    with pytest.raises(BadColor):
        parse_color("chartreuse")


def test_bad_hex_raises():
    with pytest.raises(BadColor):
        parse_color("#gggggg")
