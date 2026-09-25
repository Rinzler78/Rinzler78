"""Contact chips: the row that replaces the shields.io badges."""

from __future__ import annotations

import defusedxml.ElementTree as ET

from scripts.charts import chip

INK = {
    "text": "#f0f6fc",
    "muted": "#9aa7b4",
    "dim": "#6e7b8a",
    "surface": "#0d1117",
    "track": "#161d26",
    "border": "#252d38",
    "on_accent": "#ffffff",
}


def test_a_chip_is_well_formed_and_labelled():
    root = ET.fromstring(chip("Email", INK, accent="#818cf8"))
    assert root.get("role") == "img"
    assert root.get("aria-label") == "Email"


def test_the_box_grows_with_the_label():
    def width(svg: str) -> float:
        return float(ET.fromstring(svg).get("viewBox").split()[2])

    short = width(chip("X", INK, accent="#818cf8"))
    long = width(chip("A much longer label", INK, accent="#818cf8"))
    assert long > short


def test_a_value_widens_the_chip_and_reaches_the_label():
    plain = chip("Email", INK, accent="#818cf8")
    with_value = chip("Email", INK, accent="#818cf8", value="a@b.c")
    assert "a@b.c" in with_value
    assert "a@b.c" in ET.fromstring(with_value).get("aria-label")
    box = lambda s: float(ET.fromstring(s).get("viewBox").split()[2])  # noqa: E731
    assert box(with_value) > box(plain)


def test_a_primary_chip_inverts_its_ink():
    # Filled with the accent, so the label must not stay accent-colored.
    primary = chip("Email", INK, accent="#818cf8", primary=True)
    assert 'fill="#818cf8"' in primary
    assert INK["on_accent"] in primary


def test_markup_in_a_label_does_not_break_the_chip():
    ET.fromstring(chip('R&D <x> "y"', INK, accent="#818cf8"))
