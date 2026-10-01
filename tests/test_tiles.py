"""Tile layout guards: the compact "also" line of a skills tile."""

from __future__ import annotations

from scripts import tiles
from scripts.icons import IconSpec

LOGO = IconSpec("x", "vendored", "#000000", (0, 0, 24, 24), ("M0 0h1",))
INITIALS = IconSpec("y", "initials", initials="Y")


def _row(label, hours="≈ 5 100 h", level="expert", icon=LOGO) -> dict:
    return {"label": label, "hours_text": hours, "level": level, "icon": icon}


def _segments(rows):
    return [seg for line in tiles.also_layout(rows) for seg in line]


def test_every_also_entry_shows_its_level():
    (seg,) = _segments([_row("Windows CE")])
    assert seg.text == "Windows CE 5 100 h · "
    assert seg.level == "expert"
    assert seg.icon is True


def test_entries_flow_and_never_cross_the_right_edge():
    rows = [_row(f"Tech number {i}", level="professional") for i in range(6)]
    for seg in _segments(rows):
        end = seg.x + seg.width
        assert end <= tiles.RIGHT, seg


def test_an_entry_wider_than_the_tile_wraps_onto_two_lines():
    row = _row("Cross-platform architecture", hours="≈ 440 h", level="working")
    lines = tiles.also_layout([row])
    assert len(lines) == 2
    assert lines[0][0].text == "Cross-platform architecture"
    assert lines[1][0].text == "440 h · " and lines[1][0].level == "working"
    for line in lines:
        assert line[0].x + line[0].width <= tiles.RIGHT


def test_initials_entries_carry_no_badge():
    (seg,) = _segments([_row("GPRS", icon=INITIALS)])
    assert seg.icon is False and seg.x == tiles.X0


def test_an_outlined_title_that_cannot_fit_at_the_floor_fails():
    import pytest

    with pytest.raises(tiles.LayoutError, match="too wide"):
        tiles.outline(0, 0, "W" * 60, 34, "#000", max_width=200)


def test_an_outlined_title_shrinks_to_fit_when_it_can():
    _, width = tiles.outline(0, 0, "aioz-node-auto-withdraw", 34, "#000", max_width=400)
    assert width <= 400
