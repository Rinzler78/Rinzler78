"""Integration tests guarding the real data/ files against their contracts.

Migration safety net: any edit that breaks a schema, a foreign key, or the
hours→score pipeline fails here.
"""

import json
from datetime import date
from pathlib import Path

from scripts.data_loader import check_referential_integrity, load_collection
from scripts.hours_calculator import compute_tech_hours
from scripts.score_engine import compute_skill

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SCHEMAS = ROOT / "schemas"


def _schema(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def test_real_techs_conform_to_tech_schema():
    techs = load_collection(DATA / "techs.json", schema=_schema("tech.schema.json"))
    assert len(techs) > 0


def test_real_experiences_conform_to_experience_schema():
    exps = load_collection(
        DATA / "experiences.json", schema=_schema("experience.schema.json")
    )
    assert len(exps) > 0


def test_real_projects_conform_to_project_schema():
    projs = load_collection(
        DATA / "projects.json", schema=_schema("project.schema.json")
    )
    assert len(projs) > 0


def test_projects_only_reference_known_techs():
    tech_ids = {t["id"] for t in load_collection(DATA / "techs.json")}
    for proj in load_collection(DATA / "projects.json"):
        for tech_id in proj.get("tech_weights", {}):
            assert tech_id in tech_ids, (
                f"Project {proj['id']!r} weights unknown tech {tech_id!r}"
            )


def test_real_timeline_conforms_to_timeline_schema():
    events = load_collection(
        DATA / "timeline.json", schema=_schema("timeline.schema.json")
    )
    assert len(events) > 0


def test_real_content_collections_conform_to_schemas():
    for data_file, schema_file in [
        ("services.json", "service.schema.json"),
        ("modes.json", "mode.schema.json"),
        ("methodology.json", "methodology.schema.json"),
    ]:
        collection = load_collection(DATA / data_file, schema=_schema(schema_file))
        assert len(collection) > 0


def test_real_data_referential_integrity_holds():
    bag = {
        "domains": load_collection(DATA / "domains.json"),
        "techs": load_collection(DATA / "techs.json"),
        "projects": load_collection(DATA / "projects.json"),
        "timeline": load_collection(DATA / "timeline.json"),
    }
    check_referential_integrity(bag)


def test_experiences_only_reference_known_techs():
    tech_ids = {t["id"] for t in load_collection(DATA / "techs.json")}
    for exp in load_collection(DATA / "experiences.json"):
        for tech_id in exp["tech_weights"]:
            assert tech_id in tech_ids, (
                f"Experience {exp['id']!r} references unknown tech {tech_id!r}"
            )


def test_full_pipeline_produces_valid_skills():
    techs = load_collection(DATA / "techs.json")
    experiences = load_collection(DATA / "experiences.json")
    projects = load_collection(DATA / "projects.json")
    today = date(2026, 1, 1)

    tech_hours = compute_tech_hours(experiences, projects, today)

    for tech in techs:
        th = tech_hours.get(tech["id"])
        if th is None:
            continue  # tech defined but not yet wired to any period
        skill = compute_skill(tech, th, today)
        assert 0 <= skill.score_max <= 99
        assert 0 <= skill.score_current <= 99
        assert skill.score_current <= skill.score_max or skill.override_applied
        assert skill.tech_id == tech["id"]


def test_validate_data_cli_passes_on_real_data():
    import scripts.validate_data as vd

    assert vd.main() == 0


def test_ai_driven_development_anchored_2022_and_at_least_advanced():
    # All projects since 2022 are AI-assisted: AI-Driven Development must derive
    # `since == 2022` and rate at least `advanced` (>= 70). Guards the data tag.
    techs = load_collection(DATA / "techs.json")
    experiences = load_collection(DATA / "experiences.json")
    projects = load_collection(DATA / "projects.json")
    today = date(2026, 5, 31)
    tech_hours = compute_tech_hours(experiences, projects, today)

    th = tech_hours["ai-driven-development"]
    assert th.since == 2022, f"expected AI since 2022, got {th.since}"

    tech = next(t for t in techs if t["id"] == "ai-driven-development")
    skill = compute_skill(tech, th, today)
    assert skill.score_current >= 70, skill.score_current
    assert skill.level_current.value in ("advanced", "expert")


def test_every_featured_tech_has_hours():
    techs = load_collection(DATA / "techs.json")
    experiences = load_collection(DATA / "experiences.json")
    projects = load_collection(DATA / "projects.json")
    tech_hours = compute_tech_hours(experiences, projects, date(2026, 1, 1))

    for tech in techs:
        if tech.get("featured"):
            assert tech["id"] in tech_hours, (
                f"Featured tech {tech['id']!r} has no exposure hours"
            )
