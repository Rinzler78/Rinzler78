"""Exposure hours split per calendar year.

The totals alone answer "how much"; a per-domain timeline needs "when". Both
candidate forms for the journey view — a heatmap and a stacked area — read the
same per-year series, so it belongs in the pipeline rather than in whichever
template happens to draw it.

The load-bearing property is the one pinned by
``test_per_year_hours_sum_to_the_totals``: the split must be a *partition* of
what ``compute_tech_hours`` already reports. If the two drift apart, a chart
and a score derived from the same data start telling different stories.
"""

from __future__ import annotations

from datetime import date

from scripts.hours_calculator import (
    HOURS_PER_PERSONAL_DAY,
    HOURS_PER_YEAR,
    TIER_FRACTION,
    compute_tech_hours,
    compute_tech_hours_by_year,
)

TODAY = date(2026, 9, 1)


def _exp(start, end, weights):
    return {"start": start, "end": end, "tech_weights": weights}


def _proj(start, end, days, weights):
    return {"start": start, "end": end, "active_days": days, "tech_weights": weights}


def test_a_full_year_experience_lands_entirely_in_that_year():
    by_year = compute_tech_hours_by_year(
        [_exp("2015-01", "2015-12", {"csharp": "primary"})], [], TODAY
    )
    assert set(by_year["csharp"]) == {2015}
    assert by_year["csharp"][2015] == round(
        HOURS_PER_YEAR * (11 / 12) * TIER_FRACTION["primary"]
    )


def test_a_span_is_pro_rated_across_the_years_it_crosses():
    by_year = compute_tech_hours_by_year(
        [_exp("2014-07", "2016-07", {"csharp": "primary"})], [], TODAY
    )
    assert set(by_year["csharp"]) == {2014, 2015, 2016}
    # 2015 is whole; 2014 and 2016 are half-years, so each is about half of it.
    assert by_year["csharp"][2014] < by_year["csharp"][2015]
    assert by_year["csharp"][2016] < by_year["csharp"][2015]


def test_an_ongoing_experience_stops_at_the_reference_date():
    by_year = compute_tech_hours_by_year(
        [_exp("2024-01", None, {"python": "primary"})], [], TODAY
    )
    assert max(by_year["python"]) == TODAY.year
    # The current year is partial: eight months, not twelve.
    assert by_year["python"][2026] < by_year["python"][2025]


def test_project_days_spread_uniformly_over_their_span():
    # `active_days` carries no month, so the spread is an explicit, documented
    # approximation rather than a measurement.
    by_year = compute_tech_hours_by_year(
        [], [_proj("2022-01", "2024-12", 30, {"docker": "primary"})], TODAY
    )
    years = by_year["docker"]
    assert set(years) == {2022, 2023, 2024}
    assert len({round(v) for v in years.values()}) == 1
    total = 30 * HOURS_PER_PERSONAL_DAY * TIER_FRACTION["primary"]
    assert abs(sum(years.values()) - total) <= 3


def test_tiers_scale_the_per_year_split_the_same_way():
    both = compute_tech_hours_by_year(
        [_exp("2015-01", "2015-12", {"a": "primary", "b": "incident"})], [], TODAY
    )
    ratio = TIER_FRACTION["incident"] / TIER_FRACTION["primary"]
    assert abs(both["b"][2015] - both["a"][2015] * ratio) <= 1


def test_per_year_hours_sum_to_the_totals():
    experiences = [
        _exp("2014-07", "2016-07", {"csharp": "primary", "docker": "secondary"}),
        _exp("2024-01", None, {"python": "primary", "csharp": "incident"}),
    ]
    projects = [_proj("2022-01", "2024-12", 30, {"docker": "primary"})]

    totals = compute_tech_hours(experiences, projects, TODAY)
    by_year = compute_tech_hours_by_year(experiences, projects, TODAY)

    assert set(by_year) == set(totals)
    for tech_id, years in by_year.items():
        assert abs(sum(years.values()) - totals[tech_id].hours) <= 2, tech_id


def test_no_year_is_reported_with_zero_hours():
    by_year = compute_tech_hours_by_year(
        [_exp("2015-01", "2015-12", {"csharp": "primary"})], [], TODAY
    )
    assert all(v > 0 for v in by_year["csharp"].values())
