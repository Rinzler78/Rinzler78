from datetime import date

from scripts.view_builder import build_skills


def test_build_skills_enriches_tech_with_derived_fields():
    techs = [{"id": "py", "label": "Python", "domain": "languages", "versions": []}]
    experiences = [
        {"id": "j", "start": "2020-01", "end": None, "tech_weights": {"py": "primary"}}
    ]

    skills = build_skills(techs, experiences, projects=[], today=date(2026, 1, 1))

    skill = skills[0]
    # original fields preserved
    assert skill["id"] == "py"
    assert skill["label"] == "Python"
    assert skill["domain"] == "languages"
    # derived fields attached
    assert skill["hours"] > 0
    assert skill["since"] == 2020
    assert skill["until"] is None  # active period
    assert skill["score_max"] > 0
    assert skill["score_current"] == skill["score_max"]  # active → no decay
    # levels are plain strings for template consumption
    assert isinstance(skill["level_current"], str)
    assert isinstance(skill["level_max"], str)


def test_build_skills_tech_without_hours_is_explored_zero():
    techs = [{"id": "ghost", "label": "Ghost", "domain": "x", "versions": []}]

    skills = build_skills(techs, experiences=[], projects=[], today=date(2026, 1, 1))

    skill = skills[0]
    assert skill["hours"] == 0
    assert skill["since"] is None
    assert skill["until"] is None
    assert skill["score_max"] == 0
    assert skill["level_max"] == "explored"
    assert skill["score_current"] == 0
    assert skill["level_current"] == "explored"


def test_build_skills_preserves_input_order():
    techs = [
        {"id": "a", "domain": "x", "versions": []},
        {"id": "b", "domain": "x", "versions": []},
        {"id": "c", "domain": "x", "versions": []},
    ]

    skills = build_skills(techs, experiences=[], projects=[], today=date(2026, 1, 1))

    assert [s["id"] for s in skills] == ["a", "b", "c"]


def test_build_skills_propagates_override():
    techs = [{"id": "x", "domain": "d", "versions": [], "level_override": "advanced"}]

    skills = build_skills(techs, experiences=[], projects=[], today=date(2026, 1, 1))

    assert skills[0]["level_current"] == "advanced"
    assert skills[0]["override_applied"] is True
