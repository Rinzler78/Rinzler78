"""Integration tests guarding the real data/ files against their contracts.

Migration safety net: any edit that breaks a schema, a foreign key, or the
hours→score pipeline fails here.

NOTE: timeline.json is intentionally excluded from the referential-integrity
check below — it still references pre-merge tech ids (langchain, dotnet-maui,
ble, ...) and is scheduled for rework now that experiences.json carries the
dated periods. See task "Rework timeline.json".
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


def test_real_data_referential_integrity_holds():
    bag = {
        "domains": load_collection(DATA / "domains.json"),
        "techs": load_collection(DATA / "techs.json"),
        "projects": load_collection(DATA / "projects.json"),
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
