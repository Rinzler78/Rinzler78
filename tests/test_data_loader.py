import pytest

from scripts.data_loader import (
    DataLoadError,
    check_aggregates_integrity,
    check_referential_integrity,
    load_collection,
)


def test_load_collection_returns_list_of_dicts(tmp_path):
    path = tmp_path / "domains.json"
    path.write_text('[{"id": "embedded", "label": "Embedded", "order": 1}]')

    result = load_collection(path)

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["id"] == "embedded"
    assert result[0]["label"] == "Embedded"


def test_load_collection_invalid_json_raises_data_load_error(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not valid json")

    with pytest.raises(DataLoadError, match="broken.json"):
        load_collection(path)


_TOY_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "label": {"type": "string"},
        },
        "required": ["id", "label"],
    },
}


def test_load_collection_passes_when_data_matches_schema(tmp_path):
    path = tmp_path / "data.json"
    path.write_text('[{"id": "foo", "label": "Foo"}]')

    result = load_collection(path, schema=_TOY_SCHEMA)

    assert result == [{"id": "foo", "label": "Foo"}]


def test_load_collection_raises_when_data_violates_schema(tmp_path):
    path = tmp_path / "data.json"
    path.write_text('[{"id": "foo"}]')  # missing required "label"

    with pytest.raises(DataLoadError, match="label"):
        load_collection(path, schema=_TOY_SCHEMA)


def test_check_referential_integrity_passes_when_all_fks_valid():
    bag = {
        "domains": [{"id": "backend"}],
        "techs": [{"id": "py", "domain": "backend"}],
        "projects": [
            {"id": "p1", "domain": "backend", "tech_ids": ["py"]},
        ],
        "timeline": [{"year": 2023, "tech_ids": ["py"]}],
    }

    check_referential_integrity(bag)  # should not raise


def test_check_referential_integrity_raises_on_dangling_project_tech_id():
    bag = {
        "domains": [{"id": "backend"}],
        "techs": [{"id": "py", "domain": "backend"}],
        "projects": [
            {"id": "p1", "domain": "backend", "tech_ids": ["py", "ghost"]},
        ],
    }

    with pytest.raises(DataLoadError, match="ghost"):
        check_referential_integrity(bag)


def test_check_referential_integrity_raises_on_dangling_project_domain():
    bag = {
        "domains": [{"id": "backend"}],
        "techs": [],
        "projects": [
            {"id": "p1", "domain": "unknown", "tech_ids": []},
        ],
    }

    with pytest.raises(DataLoadError, match="unknown"):
        check_referential_integrity(bag)


def test_check_referential_integrity_raises_on_dangling_tech_domain():
    bag = {
        "domains": [{"id": "backend"}],
        "techs": [{"id": "py", "domain": "phantom"}],
        "projects": [],
    }

    with pytest.raises(DataLoadError, match="phantom"):
        check_referential_integrity(bag)


def test_check_referential_integrity_raises_on_dangling_timeline_tech():
    bag = {
        "domains": [],
        "techs": [{"id": "py"}],
        "projects": [],
        "timeline": [{"year": 2023, "tech_ids": ["py", "missing"]}],
    }

    with pytest.raises(DataLoadError, match="missing"):
        check_referential_integrity(bag)


def test_check_referential_integrity_accepts_version_id_references():
    # A reference may point to a tech-version id, not only a root tech id.
    # CONTEXT.md: tech_ids may reference a Tech OR a tech-version.
    bag = {
        "domains": [],
        "techs": [{"id": "dotnet", "versions": [{"id": "dotnet_10"}]}],
        "projects": [{"id": "p1", "tech_ids": ["dotnet", "dotnet_10"]}],
        "timeline": [{"year": 2026, "tech_ids": ["dotnet_10"]}],
    }

    check_referential_integrity(bag)  # should not raise


def test_check_referential_integrity_passes_on_empty_bag():
    # No entities at all — nothing to check, should not raise
    check_referential_integrity({})


def test_check_referential_integrity_ignores_collections_without_foreign_keys():
    # Services, modes, methodology have no FKs — checker must not error
    bag = {
        "services": [{"id": "architecture"}],
        "modes": [{"id": "emergency-support"}],
        "methodology": [{"id": "simple-before-clever"}],
    }
    check_referential_integrity(bag)


# --- Aggregates (ADR-013, ADR-018) -----------------------------------------


def _aggregates(**techs: str) -> dict:
    """Aggregates naming each tech id with its domain, and one month of it."""
    return {
        "techs": {tech_id: {"domain": domain} for tech_id, domain in techs.items()},
        "by_month": {"2026-01": {"techs": dict.fromkeys(techs, 1.0)}},
    }


_CATALOGUE = [{"id": "python", "domain": "languages"}]
_DOMAINS = [{"id": "languages"}]


def test_aggregates_integrity_passes_when_every_tech_is_catalogued():
    check_aggregates_integrity(_aggregates(python="languages"), _CATALOGUE, _DOMAINS)


def test_aggregates_referencing_an_uncatalogued_tech_fail():
    with pytest.raises(DataLoadError, match="ghost"):
        check_aggregates_integrity(_aggregates(ghost="languages"), [], _DOMAINS)


def test_aggregates_referencing_an_uncatalogued_tech_in_a_month_fail():
    aggregates = _aggregates(python="languages")
    aggregates["by_month"]["2026-01"]["techs"]["ghost"] = 2.0
    with pytest.raises(DataLoadError, match="ghost"):
        check_aggregates_integrity(aggregates, _CATALOGUE, _DOMAINS)


def test_aggregates_domain_must_match_the_catalogue():
    with pytest.raises(DataLoadError, match="python"):
        check_aggregates_integrity(_aggregates(python="mobile"), _CATALOGUE, _DOMAINS)


def test_aggregates_domain_must_be_declared():
    catalogue = [{"id": "python", "domain": "nowhere"}]
    with pytest.raises(DataLoadError, match="nowhere"):
        check_aggregates_integrity(_aggregates(python="nowhere"), catalogue, _DOMAINS)


def test_aggregates_month_domain_must_be_declared():
    aggregates = _aggregates(python="languages")
    aggregates["by_month"]["2026-01"]["domains"] = {"nowhere": 1.0}
    with pytest.raises(DataLoadError, match="nowhere"):
        check_aggregates_integrity(aggregates, _CATALOGUE, _DOMAINS)


def test_aggregates_activity_date_must_exist_in_the_calendar():
    # The schema pattern admits 2026-02-31; the calendar does not.
    aggregates = _aggregates(python="languages")
    aggregates["activity_as_of"] = "2026-02-31"
    with pytest.raises(DataLoadError, match="2026-02-31"):
        check_aggregates_integrity(aggregates, _CATALOGUE, _DOMAINS)


def test_aggregates_with_a_real_activity_date_pass():
    aggregates = _aggregates(python="languages")
    aggregates["activity_as_of"] = "2024-02-29"
    check_aggregates_integrity(aggregates, _CATALOGUE, _DOMAINS)
