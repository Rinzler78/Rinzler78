"""Integration tests guarding the real data/ files against their contracts.

Migration safety net: any edit that breaks a schema, a foreign key, or the
link between the committed activity aggregates and the catalogue fails here.
"""

import json
from pathlib import Path

import scripts.validate_data as vd
from scripts.data_loader import (
    check_aggregates_integrity,
    check_referential_integrity,
    load_collection,
)

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


def test_validate_data_cli_passes_on_real_data():
    assert vd.main() == 0


AGGREGATES = DATA / "activity" / "aggregates.json"
TECH_MAP = ROOT / "scripts" / "activity" / "tech_map.json"


def _aggregates() -> dict:
    return json.loads(AGGREGATES.read_text(encoding="utf-8"))


def test_real_aggregates_conform_to_their_schema():
    import jsonschema

    jsonschema.validate(_aggregates(), _schema("aggregates.schema.json"))


def test_real_aggregates_only_name_catalogued_techs():
    check_aggregates_integrity(
        _aggregates(),
        load_collection(DATA / "techs.json"),
        load_collection(DATA / "domains.json"),
    )


def test_every_tech_shown_as_a_skill_is_catalogued():
    # ADR-016: every tech at or above the working threshold is on the page.
    catalogue = {t["id"] for t in load_collection(DATA / "techs.json")}
    aggregates = _aggregates()
    threshold = aggregates["levels"]["working"]
    shown = {k for k, v in aggregates["techs"].items() if v["hours"] >= threshold}
    assert shown <= catalogue, sorted(shown - catalogue)


def test_tools_every_commit_implies_never_get_hours():
    # ADR-016: Git stays in the catalogue (icon band) but is never a skill line.
    excluded = json.loads(TECH_MAP.read_text(encoding="utf-8"))["excluded"]
    catalogue = {t["id"] for t in load_collection(DATA / "techs.json")}
    assert "git" in excluded and "git" in catalogue
    assert set(excluded).isdisjoint(_aggregates()["techs"])


def test_validate_data_cli_rejects_an_uncatalogued_aggregate_tech(
    tmp_path, monkeypatch, capsys
):
    aggregates = _aggregates()
    aggregates["techs"]["ghost-tech"] = dict(aggregates["techs"]["python"])
    path = tmp_path / "aggregates.json"
    path.write_text(json.dumps(aggregates), encoding="utf-8")
    monkeypatch.setattr(vd, "AGGREGATES", path)
    assert vd.main() == 1
    assert "ghost-tech" in capsys.readouterr().err


def test_validate_data_cli_rejects_aggregates_off_schema(tmp_path, monkeypatch, capsys):
    aggregates = _aggregates()
    aggregates["version"] = 1
    path = tmp_path / "aggregates.json"
    path.write_text(json.dumps(aggregates), encoding="utf-8")
    monkeypatch.setattr(vd, "AGGREGATES", path)
    assert vd.main() == 1
    assert "aggregates.json" in capsys.readouterr().err
