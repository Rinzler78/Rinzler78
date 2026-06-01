"""Hero banner guards: outlined display type + encoded signature arc (ADR-007)."""

from pathlib import Path

import defusedxml.ElementTree as ET

import scripts.generate as gen

ROOT = Path(__file__).resolve().parent.parent


def _header(variant: str = "") -> str:
    gen.main()
    base = ROOT / "assets" / "svg"
    path = base / variant / "header.svg" if variant else base / "header.svg"
    return path.read_text(encoding="utf-8")


def test_hero_outlines_display_text_to_paths():
    svg = _header()
    ET.fromstring(svg)  # well-formed
    assert '<path d="M' in svg  # glyphs are vector paths, not web-font text


def test_hero_shows_the_signature_arc_with_years_and_signatures():
    svg = _header()
    for year in ("2006", "2011", "2020", "2023"):
        assert year in svg
    assert "NFC" in svg  # mobile signature word (Ingenico)
    assert "url(#arc-h)" in svg  # ribbon gradient encodes the arc


def test_hero_aria_label_covers_outlined_text():
    # ADR-007: outlined glyphs are not text — accessibility rests on aria-label.
    svg = _header()
    assert 'aria-label="Boris Leclere —' in svg
    assert "embedded 2006" in svg
    assert "ai 2023" in svg


def test_hero_carries_subtitle_and_scale():
    svg = _header()
    assert "des startups en construction" in svg  # who-for subtitle
    assert "20 ans de code" in svg  # experience scale line


def test_hero_is_light_first_with_dark_mirror():
    assert 'fill="#faf7f2"' in _header()  # root = light primary
    assert 'fill="#0d1117"' in _header("dark")  # dark mirror
