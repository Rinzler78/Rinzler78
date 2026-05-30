from datetime import date

from scripts.hours_calculator import compute_tech_hours


def test_single_experience_primary_tech_gets_full_tier_fraction():
    # 1 year span × 1880 h/yr × 0.70 (primary) = 1316
    experiences = [
        {
            "id": "job1",
            "start": "2020-01",
            "end": "2021-01",
            "tech_weights": {"csharp-dotnet": "primary"},
        }
    ]

    result = compute_tech_hours(experiences, projects=[], today=date(2026, 1, 1))

    assert result["csharp-dotnet"].hours == 1316


def test_concurrent_techs_each_get_full_fraction_not_split():
    # C# + Xamarin + Bluetooth on the same project are used at the same time:
    # each primary gets the full 0.70 fraction, NOT a normalized third.
    experiences = [
        {
            "id": "app",
            "start": "2020-01",
            "end": "2021-01",
            "tech_weights": {
                "csharp-dotnet": "primary",
                "xamarin-forms": "primary",
                "bluetooth": "primary",
            },
        }
    ]

    result = compute_tech_hours(experiences, projects=[], today=date(2026, 1, 1))

    assert result["csharp-dotnet"].hours == 1316
    assert result["xamarin-forms"].hours == 1316
    assert result["bluetooth"].hours == 1316


def test_tiers_map_to_distinct_fractions():
    experiences = [
        {
            "id": "x",
            "start": "2020-01",
            "end": "2021-01",
            "tech_weights": {
                "a": "primary",
                "b": "secondary",
                "c": "incident",
            },
        }
    ]

    result = compute_tech_hours(experiences, projects=[], today=date(2026, 1, 1))

    assert result["a"].hours == 1316  # 1880 × 0.70
    assert result["b"].hours == 658  # 1880 × 0.35
    assert result["c"].hours == 188  # 1880 × 0.10


def test_hours_aggregate_across_multiple_experiences():
    experiences = [
        {"id": "j1", "start": "2018-01", "end": "2019-01",
         "tech_weights": {"py": "primary"}},
        {"id": "j2", "start": "2020-01", "end": "2021-01",
         "tech_weights": {"py": "primary"}},
    ]

    result = compute_tech_hours(experiences, projects=[], today=date(2026, 1, 1))

    assert result["py"].hours == 2632  # 1316 + 1316


def test_personal_projects_contribute_active_days_times_nine():
    projects = [
        {"id": "p1", "active_days": 100, "tech_weights": {"py": "primary"}}
    ]

    result = compute_tech_hours([], projects=projects, today=date(2026, 1, 1))

    assert result["py"].hours == 630  # 100 × 9 × 0.70


def test_since_until_derived_active_tech_has_no_until():
    experiences = [
        {"id": "old", "start": "2009-06", "end": "2013-12",
         "tech_weights": {"cpp": "primary"}},
        {"id": "now", "start": "2023-04", "end": None,
         "tech_weights": {"py": "primary"}},
    ]

    result = compute_tech_hours(experiences, projects=[], today=date(2026, 1, 1))

    # cpp only used in a closed period → until = last end year
    assert result["cpp"].since == 2009
    assert result["cpp"].until == 2013
    # py used in a current (end=None) period → until stays None
    assert result["py"].since == 2023
    assert result["py"].until is None


def test_since_until_span_multiple_periods_takes_min_max():
    experiences = [
        {"id": "a", "start": "2014-04", "end": "2020-06",
         "tech_weights": {"x": "primary"}},
        {"id": "b", "start": "2011-01", "end": "2012-09",
         "tech_weights": {"x": "secondary"}},
    ]

    result = compute_tech_hours(experiences, projects=[], today=date(2026, 1, 1))

    assert result["x"].since == 2011
    assert result["x"].until == 2020
