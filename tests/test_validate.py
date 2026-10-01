"""SVG rules of the tile grid (ADR-015), enforced on every generated SVG."""

from __future__ import annotations

from pathlib import Path

from scripts.validate import svg_rule_errors, validate_svg_rules

ROOT = Path(__file__).resolve().parent.parent

GOOD = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 590 400" width="590" '
    'height="400"><text font-size="20">ok</text></svg>'
)


def test_a_root_with_width_and_height_and_large_text_passes():
    assert svg_rule_errors(GOOD, tile=True) == []


def test_a_percent_root_width_is_refused():
    svg = GOOD.replace('width="590"', 'width="100%"')
    assert any("100%" in e for e in svg_rule_errors(svg, tile=False))


def test_a_root_without_height_is_refused():
    svg = GOOD.replace(' height="400"', "")
    assert any("height" in e for e in svg_rule_errors(svg, tile=False))


def test_tile_text_under_twenty_units_is_refused():
    svg = GOOD.replace('font-size="20"', 'font-size="19.5"')
    assert any("19.5" in e for e in svg_rule_errors(svg, tile=True))


def test_small_text_outside_a_tile_is_not_a_tile_error():
    svg = GOOD.replace('font-size="20"', 'font-size="11"')
    assert svg_rule_errors(svg, tile=False) == []


def test_nested_icon_svg_sizes_are_not_root_sizes():
    svg = GOOD.replace("<text", '<svg width="100%"></svg><text')
    assert svg_rule_errors(svg, tile=True) == []


def test_the_generated_svgs_follow_the_rules():
    assert validate_svg_rules() == []
