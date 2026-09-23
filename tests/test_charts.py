"""Chart geometry guards.

These charts are served by GitHub inside an `<img>`, which runs no JavaScript:
there is no hover layer, no tooltip and no re-render. Whatever the generator
emits is the whole chart, so the geometry has to be right at write time and the
labels have to be baked in — hence the direct-label assertions below.

The tests check *shape*, not aesthetics: a wedge that swallows the circle, a
bar wider than its track or a band that leaves its box are the failures that
survive a visual skim, because a plausible-looking chart is the dangerous kind.
"""

from __future__ import annotations

import defusedxml.ElementTree as ET

from scripts.charts import bar_rows, donut, stacked_area

COLORS = {
    "embedded": "#d95926",
    "mobile": "#d55181",
    "backend": "#3987e5",
    "devops": "#199e70",
    "blockchain": "#c98500",
    "ai-llm": "#9085e9",
}
SERIES = {
    "embedded": {2006: 400, 2007: 800, 2008: 200},
    "devops": {2007: 200, 2008: 600},
}
INK = {
    "text": "#f0f6fc",
    "muted": "#9aa7b4",
    "dim": "#6e7b8a",
    "surface": "#0d1117",
    "track": "#161d26",
}


def _parse(svg: str):
    return ET.fromstring(svg)


# ------------------------------------------------------------ stacked area
def test_stacked_area_is_well_formed_and_labelled():
    svg = stacked_area(SERIES, COLORS, INK, labels={"embedded": "Embedded"})
    root = _parse(svg)
    assert root.get("role") == "img"
    assert root.get("aria-label")


def test_stacked_area_draws_one_band_per_series():
    svg = stacked_area(SERIES, COLORS, INK)
    fills = {p.get("fill") for p in _parse(svg).iter() if p.tag.endswith("path")}
    assert COLORS["embedded"] in fills
    assert COLORS["devops"] in fills


def test_stacked_area_bands_stay_inside_the_view_box():
    svg = stacked_area(SERIES, COLORS, INK, width=400, height=200)
    _, _, vw, vh = (float(v) for v in _parse(svg).get("viewBox").split())
    for path in (p for p in _parse(svg).iter() if p.tag.endswith("path")):
        coords = path.get("d").replace("M", " ").replace("L", " ").replace("Z", " ")
        for pair in coords.split():
            x, y = (float(v) for v in pair.split(","))
            assert -0.5 <= x <= vw + 0.5
            assert -0.5 <= y <= vh + 0.5


def test_stacked_area_normalizes_each_year_to_a_full_column():
    # Shares, not volumes: a year where one domain doubles must not make the
    # column taller, or the reader sees growth that the data does not claim.
    thin = stacked_area(
        {"a": {2020: 1}, "b": {2020: 1}}, {"a": "#111", "b": "#222"}, INK
    )
    thick = stacked_area(
        {"a": {2020: 100}, "b": {2020: 100}}, {"a": "#111", "b": "#222"}, INK
    )
    assert _parse(thin).get("viewBox") == _parse(thick).get("viewBox")


def test_stacked_area_survives_a_year_with_no_exposure():
    svg = stacked_area({"a": {2020: 5, 2021: 0, 2022: 5}}, {"a": "#111"}, INK)
    assert "nan" not in svg.lower()


# -------------------------------------------------------------------- donut
def test_donut_wedges_close_the_circle():
    shares = [("devops", 50.0), ("backend", 30.0), ("mobile", 20.0)]
    svg = donut(shares, COLORS, INK)
    root = _parse(svg)
    wedges = [p for p in root.iter() if p.tag.endswith("path")]
    assert len(wedges) == 3
    assert all(w.get("d").rstrip().endswith("Z") for w in wedges)


def test_donut_refuses_shares_that_do_not_make_a_whole():
    # A wedge chart whose parts do not sum to the whole is a lie about the
    # denominator, and it is invisible once drawn.
    import pytest

    with pytest.raises(ValueError):
        donut([("a", 50.0), ("b", 30.0)], {"a": "#111", "b": "#222"}, INK)


def test_donut_is_labelled_for_screen_readers():
    svg = donut([("devops", 100.0)], COLORS, INK)
    assert _parse(svg).get("aria-label")


# --------------------------------------------------------------- bar chart
def test_bar_length_is_proportional_to_the_value():
    # Both inside the scale — clamping is a separate concern, tested below.
    svg = bar_rows([("A", 90), ("B", 45)], "#818cf8", INK, width=500)
    shapes = [r for r in _parse(svg).iter() if r.tag.endswith("rect")]
    fills = [r for r in shapes if r.get("fill") == "#818cf8"]
    assert len(fills) == 2
    long_bar, short_bar = (float(r.get("width")) for r in fills)
    assert abs(long_bar - 2 * short_bar) < 1.0


def test_bar_rows_print_every_value_next_to_its_bar():
    # No hover layer exists, so an unlabelled bar is an unreadable one.
    svg = bar_rows([("A", 99), ("B", 42)], "#818cf8", INK)
    assert ">99<" in svg
    assert ">42<" in svg
    assert ">A<" in svg


def test_bar_rows_clamp_out_of_range_values():
    svg = bar_rows([("A", 140)], "#818cf8", INK, width=500, maximum=99)
    fills = [
        r
        for r in _parse(svg).iter()
        if r.tag.endswith("rect") and r.get("fill") == "#818cf8"
    ]
    track = [
        r
        for r in _parse(svg).iter()
        if r.tag.endswith("rect") and r.get("fill") == INK["track"]
    ]
    assert float(fills[0].get("width")) <= float(track[0].get("width")) + 0.01


def test_escape_protects_markup_characters_without_double_escaping():
    from scripts.charts import escape

    assert escape('A & B <c> "d"') == "A &amp; B &lt;c&gt; &quot;d&quot;"


def test_a_label_carrying_markup_still_parses():
    svg = bar_rows([('R&D <lead> "x"', 50)], "#818cf8", INK)
    _parse(svg)  # would raise on malformed XML
