"""Per-domain, per-year exposure — the series a journey view plots.

Aggregating tech hours up to their domain is where the timeline becomes
readable: six rows instead of thirty-four. Two rules earn their own tests.

`languages` is **excluded**: C#, Python and C are used inside every other
domain, so the row is lit every single year and only flattens the scale of the
rows that carry information.

The shares are what gets drawn, never the raw totals. Tier fractions are
cumulative rather than normalized (ADR-006) — one project counts its hours in
full under each domain it touches — so summing across domains produces a number
that double-counts and must never be shown as "hours worked".
"""

from __future__ import annotations

from datetime import date

from scripts.view_builder import build_domain_year_hours

TODAY = date(2026, 9, 1)

TECHS = [
    {"id": "csharp", "domain": "languages"},
    {"id": "docker", "domain": "devops"},
    {"id": "ble", "domain": "embedded"},
]
EXPERIENCES = [
    {
        "start": "2015-01",
        "end": "2016-12",
        "tech_weights": {"ble": "primary", "csharp": "primary"},
    },
    {
        "start": "2020-01",
        "end": None,
        "tech_weights": {"docker": "primary", "csharp": "primary"},
    },
]


def test_hours_are_grouped_by_domain():
    series = build_domain_year_hours(TECHS, EXPERIENCES, [], TODAY)
    assert set(series) == {"embedded", "devops"}
    assert set(series["embedded"]) == {2015, 2016}


def test_languages_is_excluded_as_a_cross_cutting_domain():
    series = build_domain_year_hours(TECHS, EXPERIENCES, [], TODAY)
    assert "languages" not in series


def test_an_unknown_tech_reference_is_ignored_not_guessed():
    experiences = [
        {"start": "2015-01", "end": "2015-12", "tech_weights": {"ghost": "primary"}}
    ]
    assert build_domain_year_hours(TECHS, experiences, [], TODAY) == {}


def test_a_domain_spans_the_union_of_its_techs_years():
    techs = [{"id": "docker", "domain": "devops"}, {"id": "k8s", "domain": "devops"}]
    experiences = [
        {"start": "2018-01", "end": "2018-12", "tech_weights": {"docker": "primary"}},
        {"start": "2022-01", "end": "2022-12", "tech_weights": {"k8s": "primary"}},
    ]
    series = build_domain_year_hours(techs, experiences, [], TODAY)
    assert set(series["devops"]) == {2018, 2022}


def test_concurrent_tiers_are_additive_within_a_domain():
    techs = [{"id": "a", "domain": "devops"}, {"id": "b", "domain": "devops"}]
    one = [{"start": "2020-01", "end": "2020-12", "tech_weights": {"a": "primary"}}]
    two = [
        {
            "start": "2020-01",
            "end": "2020-12",
            "tech_weights": {"a": "primary", "b": "primary"},
        }
    ]
    single = build_domain_year_hours(techs, one, [], TODAY)["devops"][2020]
    double = build_domain_year_hours(techs, two, [], TODAY)["devops"][2020]
    assert double == 2 * single
