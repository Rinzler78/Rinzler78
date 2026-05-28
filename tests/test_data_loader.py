import pytest

from scripts.data_loader import (
    DataLoadError,
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
        "modes": [{"id": "pompier"}],
        "methodology": [{"id": "simple-before-clever"}],
    }
    check_referential_integrity(bag)
