"""Hero banner guards: outlined display type + encoded signature arc (ADR-007)."""

from pathlib import Path

import defusedxml.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent


def _header(variant: str = "") -> str:
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


def test_hero_is_dark_first_with_light_mirror():
    # ADR-009 reverses the posture: the <img> fallback serves dark, and the
    # background matches the GitHub canvas so the banner sits in the page.
    assert 'fill="#0d1117"' in _header()  # root = dark primary
    assert 'fill="#ffffff"' in _header("light")  # light mirror


def test_the_arc_gradient_runs_warm_to_cool():
    # The arc encodes the career direction: coral at `embedded` (2006), indigo
    # at `ai` (2023). Coral survives the indigo re-theme as the arc's origin —
    # it is what makes the gradient readable as a direction rather than
    # decoration (ADR-009).
    svg = _header()
    first = svg.index('stop-color="#f78166"')  # coral origin
    indigo = svg.index('stop-color="#818cf8"')
    assert first < indigo, "the arc no longer starts warm"


def test_the_accent_is_indigo_not_coral():
    # Coral is demoted to the arc origin and geek microcopy; it must no longer
    # be the interface accent, or the re-theme is only half applied.
    svg = _header()
    assert "#818cf8" in svg
