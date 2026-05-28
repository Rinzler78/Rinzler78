"""Integration tests guarding the real data/ files against their contracts.

These are the migration safety net: any future edit that breaks a schema
or introduces a dangling foreign key fails here.
"""

import json
from datetime import date
from pathlib import Path

from scripts.data_loader import check_referential_integrity, load_collection
from scripts.score_engine import compute_skill

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SCHEMAS = ROOT / "schemas"


def _schema(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def test_real_techs_conform_to_tech_schema():
    techs = load_collection(DATA / "techs.json", schema=_schema("tech.schema.json"))
    assert len(techs) > 0


def test_real_data_referential_integrity_holds():
    bag = {
        "domains": load_collection(DATA / "domains.json"),
        "techs": load_collection(DATA / "techs.json"),
        "projects": load_collection(DATA / "projects.json"),
        "timeline": load_collection(DATA / "timeline.json"),
    }
    check_referential_integrity(bag)


def test_every_real_tech_computes_a_skill():
    techs = load_collection(DATA / "techs.json")
    projects = load_collection(DATA / "projects.json")
    today = date(2026, 1, 1)

    for tech in techs:
        skill = compute_skill(tech, projects, today)
        assert 0 <= skill.score <= 99
        assert skill.tech_id == tech["id"]
