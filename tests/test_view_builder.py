"""View models built from the catalogue and the committed aggregates.

The generator no longer derives anything about a skill: hours, levels and
periods are computed once, on the author's workstation (ADR-013, ADR-018), and
committed as ``data/activity/aggregates.json``. These guards pin how the page
reads them.
"""

from scripts.view_builder import (
    build_domain_year_hours,
    build_profile_as_code,
    build_skills,
)


def _entry(hours, level, first, last, **extra):
    return {
        "hours": hours,
        "display_hours": int(hours // 10 * 10),
        "hours_level": level,
        "evidence_level": None,
        "display_level": level,
        "level_source": "hours",
        "claim": None,
        "pending_claim": None,
        "first": first,
        "last": last,
        "first_year": int(first[:4]),
        "last_year": int(last[:4]),
        "active": int(last[:4]) == 2026,
        "declared_share": 0.0,
        "domain": "languages",
        "kind": "language",
        **extra,
    }


def _aggregates(**techs):
    return {"activity_as_of": "2026-10-01", "techs": techs, "by_month": {}}


def _tech(tech_id, **extra):
    return {"id": tech_id, "label": tech_id.title(), "domain": "languages", **extra}


# --- Profile as code -------------------------------------------------------


def test_profile_as_code_declares_a_class_named_after_the_profile():
    profile = {"name": "Boris Leclere", "role": "Freelance CTO", "status": "available"}

    code = build_profile_as_code(profile, skills=[], services=[])

    assert "class BorisLeclere" in code


def test_profile_as_code_core_skills_are_the_featured_labels_in_skill_order():
    profile = {"name": "Boris", "role": "CTO", "status": "available"}
    skills = [
        {"label": "Python", "featured": True},
        {"label": "C# / .NET", "featured": True},
        {"label": "Git", "featured": False},
    ]

    code = build_profile_as_code(profile, skills, services=[])

    assert "CoreSkills" in code
    assert code.index('"Python"') < code.index('"C# / .NET"')
    assert '"Git"' not in code  # not featured


def test_profile_as_code_services_are_the_visible_titles_by_priority():
    profile = {"name": "Boris", "role": "CTO", "status": "available"}
    services = [
        {"title": "Audit", "visible": True, "priority": 2},
        {"title": "Architecture", "visible": True, "priority": 1},
        {"title": "Hidden", "visible": False, "priority": 3},
    ]

    code = build_profile_as_code(profile, skills=[], services=services)

    assert "Services" in code
    # ordered by priority, hidden excluded
    assert code.index('"Architecture"') < code.index('"Audit"')
    assert '"Hidden"' not in code


def test_profile_as_code_exposes_status_and_compiles_to_balanced_braces():
    profile = {"name": "Boris", "role": "CTO", "status": "available"}

    code = build_profile_as_code(profile, skills=[], services=[])

    assert '"available"' in code
    assert code.count("{") == code.count("}")


# --- Skills ----------------------------------------------------------------


def test_a_skill_carries_its_aggregate_figures_and_keeps_catalogue_fields():
    aggregates = _aggregates(py=_entry(1416.0, "professional", "2018-11", "2026-09"))

    (skill,) = build_skills([_tech("py", featured=True)], aggregates)

    assert skill["label"] == "Py" and skill["featured"] is True
    assert skill["hours"] == 1416.0
    assert skill["display_hours"] == 1410
    assert skill["level"] == "professional"
    assert skill["level_source"] == "hours"
    assert skill["first"] == "2018-11" and skill["last"] == "2026-09"


def test_a_skill_used_in_the_as_of_year_has_no_end_year():
    aggregates = _aggregates(py=_entry(900.0, "professional", "2018-11", "2026-03"))

    (skill,) = build_skills([_tech("py")], aggregates)

    assert (skill["since"], skill["until"]) == (2018, None)


def test_a_skill_last_used_before_the_as_of_year_ends_that_year():
    aggregates = _aggregates(aix=_entry(728.0, "professional", "2012-10", "2013-03"))

    (skill,) = build_skills([_tech("aix")], aggregates)

    assert (skill["since"], skill["until"]) == (2012, 2013)


def test_the_period_comes_from_the_ten_hour_years_not_the_raw_months():
    # NFC: 0.1 h of noise in 2026-09 does not make it active (aggregates v4).
    entry = _entry(1831.2, "advanced", "2011-12", "2026-09")
    entry.update(first_year=2011, last_year=2014, active=False)

    (nfc,) = build_skills([_tech("nfc")], _aggregates(nfc=entry))

    assert (nfc["since"], nfc["until"]) == (2011, 2014)


def test_recency_order_follows_the_period_not_a_noise_month():
    noisy = _entry(1831.2, "advanced", "2011-12", "2026-09")
    noisy.update(last_year=2014, active=False)
    recent = _entry(60.0, "working", "2020-01", "2020-06")
    skills = build_skills(
        [_tech("nfc"), _tech("ts")], _aggregates(nfc=noisy, ts=recent)
    )
    assert [s["id"] for s in skills] == ["ts", "nfc"]


def test_the_displayed_level_is_the_aggregates_display_level():
    entry = _entry(858.0, "professional", "2015-04", "2026-09")
    entry.update(evidence_level="expert", display_level="expert")
    entry.update(level_source="evidence", claim="sdk-design")

    (skill,) = build_skills([_tech("mvvm")], _aggregates(mvvm=entry))

    assert skill["level"] == "expert"
    assert skill["level_source"] == "evidence"
    assert skill["claim"] == "sdk-design"


def test_a_tech_without_aggregates_is_catalogued_but_not_a_skill():
    # Git: a tool every commit implies, in the icon band, never a skill line.
    (git,) = build_skills([_tech("git")], _aggregates())

    assert git["level"] is None
    assert git["hours"] == 0
    assert git["since"] is None and git["until"] is None


def test_a_tech_below_the_working_threshold_is_not_a_skill():
    aggregates = _aggregates(go=_entry(2.7, None, "2022-12", "2026-04"))

    (go,) = build_skills([_tech("go")], aggregates)

    assert go["level"] is None


def test_skills_are_ordered_by_recency_then_hours():
    # ADR-018: never by hours alone; historical techs come after current ones.
    aggregates = _aggregates(
        old=_entry(6000.0, "expert", "2006-09", "2013-06"),
        small=_entry(80.0, "working", "2024-01", "2026-10"),
        big=_entry(900.0, "professional", "2020-01", "2026-10"),
    )
    techs = [_tech("git"), _tech("old"), _tech("small"), _tech("big")]

    order = [s["id"] for s in build_skills(techs, aggregates)]

    assert order == ["big", "small", "old", "git"]


# --- Per-domain, per-year hours (the journey series) ------------------------


def _month(**domains):
    return {"context": {}, "domains": domains, "techs": {}}


def test_domain_hours_are_summed_per_calendar_year():
    aggregates = {
        "by_month": {
            "2015-11": _month(mobile=10.0, embedded=4.0),
            "2015-12": _month(mobile=5.5),
            "2016-01": _month(mobile=1.0),
        }
    }

    series = build_domain_year_hours(aggregates)

    assert series == {"mobile": {2015: 15.5, 2016: 1.0}, "embedded": {2015: 4.0}}


def test_cross_cutting_domains_are_excluded_from_the_journey():
    # Languages and practices run under every other domain: their rows would
    # be lit every year and only flatten the scale of the rows that inform.
    aggregates = {"by_month": {"2020-01": _month(languages=100.0, practices=50.0)}}

    assert build_domain_year_hours(aggregates) == {}


def test_a_year_without_hours_is_not_reported():
    aggregates = {"by_month": {"2020-01": _month(devops=0.0, mobile=3.0)}}

    assert build_domain_year_hours(aggregates) == {"mobile": {2020: 3.0}}
