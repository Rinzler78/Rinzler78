"""The generated chart views, as they ship.

A chart's `aria-label` is the *only* text a screen reader gets from it — the
SVG is served inside an `<img>`, so there is nothing else to read. An
untranslated caption therefore does not merely look sloppy in `README.en.md`,
it makes the chart unreadable for an English screen-reader user. That is what
`test_captions_are_translated_per_language` exists to catch; it already caught
it once, when the captions shipped French-only.
"""

from __future__ import annotations

from pathlib import Path

import defusedxml.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
SVG_DIR = ROOT / "assets" / "svg"
CHARTS = ("journey-share.svg", "domain-split.svg", "top-skills.svg")
VARIANTS = ("", "light", "en", "en/light")


def _read(variant: str, name: str) -> str:
    base = SVG_DIR / variant if variant else SVG_DIR
    return (base / name).read_text(encoding="utf-8")


def test_every_chart_ships_in_every_variant():
    for name in CHARTS:
        for variant in VARIANTS:
            ET.fromstring(_read(variant, name))  # present and well-formed


def test_charts_carry_an_accessible_label_and_title():
    for name in CHARTS:
        root = ET.fromstring(_read("", name))
        assert root.get("role") == "img"
        assert root.get("aria-label")
        assert any(child.tag.endswith("title") for child in root)


def test_captions_are_translated_per_language():
    for name in CHARTS:
        fr = ET.fromstring(_read("", name)).get("aria-label")
        en = ET.fromstring(_read("en", name)).get("aria-label")
        assert fr != en, f"{name}: the English chart kept the French caption"


def test_dark_and_light_use_their_own_series_colors():
    # Dark-first (ADR-009): the root holds the dark variant, light/ the
    # prefers-color-scheme override.
    dark = _read("", "journey-share.svg")
    light = _read("light", "journey-share.svg")
    assert light != dark
    assert "#d95926" in dark  # dark step of the first categorical slot
    assert "#eb6834" in light  # its light step


def test_no_chart_carries_a_script_or_an_event_handler():
    # GitHub strips them anyway; emitting one would mean the chart is relying
    # on behavior that never runs for a visitor.
    for name in CHARTS:
        for variant in VARIANTS:
            svg = _read(variant, name)
            assert "<script" not in svg
            assert "onclick" not in svg.lower()
            assert "onmouseover" not in svg.lower()
