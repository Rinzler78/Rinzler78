"""Data loader (ADR-003).

Public surface (V1, incremental):
- ``DataLoadError`` exception for any data loading or validation failure.
- ``load_collection(path, schema=None)`` reads a JSON file expected to
  contain a collection (list of dicts), optionally validates against a
  JSON Schema, and returns its parsed content.
- ``check_referential_integrity(bag)`` verifies that every foreign key
  reference in a loaded data bag points to an existing entity.
- ``check_aggregates_integrity(aggregates, techs, domains)`` verifies that the
  committed activity aggregates (ADR-013) only name catalogued techs, filed
  under the same declared domain as in the catalogue.
"""

import json
from pathlib import Path

import jsonschema


class DataLoadError(Exception):
    """Raised when data cannot be loaded or fails validation."""


def load_collection(path: Path, schema: dict | None = None) -> list[dict] | dict:
    path = Path(path)
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise DataLoadError(f"Invalid JSON in {path}: {e}") from e

    if schema is not None:
        try:
            jsonschema.validate(data, schema)
        except jsonschema.ValidationError as e:
            raise DataLoadError(f"Schema violation in {path}: {e.message}") from e

    return data


def check_referential_integrity(bag: dict[str, list[dict]]) -> None:
    """Verify every foreign-key reference in the bag points to an existing id.

    A tech reference may point to a root tech id OR a tech-version id
    (CONTEXT.md). Both are accepted.

    Checks performed:
    - ``tech.domain`` must exist in ``domains``
    - ``project.domain`` must exist in ``domains``
    - ``project.tech_ids[]`` must each exist in ``techs`` or a version id
    - ``timeline[].tech_ids[]`` must each exist in ``techs`` or a version id
    """
    domain_ids = {d["id"] for d in bag.get("domains", [])}
    tech_ids = {t["id"] for t in bag.get("techs", [])}
    version_ids = {v["id"] for t in bag.get("techs", []) for v in t.get("versions", [])}
    tech_refs = tech_ids | version_ids

    for tech in bag.get("techs", []):
        ref = tech.get("domain")
        if ref is not None and ref not in domain_ids:
            raise DataLoadError(
                f"Tech {tech['id']!r} references unknown domain {ref!r}"
            )

    for project in bag.get("projects", []):
        ref = project.get("domain")
        if ref is not None and ref not in domain_ids:
            raise DataLoadError(
                f"Project {project['id']!r} references unknown domain {ref!r}"
            )
        for tid in project.get("tech_ids", []):
            if tid not in tech_refs:
                raise DataLoadError(
                    f"Project {project['id']!r} references unknown tech {tid!r}"
                )

    for event in bag.get("timeline", []):
        for tid in event.get("tech_ids", []):
            if tid not in tech_refs:
                raise DataLoadError(
                    f"Timeline event {event.get('year', '?')!r} "
                    f"references unknown tech {tid!r}"
                )


def check_aggregates_integrity(
    aggregates: dict, techs: list[dict], domains: list[dict]
) -> None:
    """Every tech the aggregates name is catalogued, under the same domain.

    The aggregates are computed on the author's workstation from
    ``scripts/activity/tech_map.json``; the page reads labels and domains from
    ``data/techs.json``. A tech missing from the catalogue would have hours and
    no label, and a domain that differs would put its hours under one domain
    in the charts and its skill line under another.
    """
    catalogue = {t["id"]: t.get("domain") for t in techs}
    domain_ids = {d["id"] for d in domains}

    for tech_id, entry in sorted(aggregates.get("techs", {}).items()):
        if tech_id not in catalogue:
            raise DataLoadError(f"Aggregates reference uncatalogued tech {tech_id!r}")
        domain = entry.get("domain")
        if domain != catalogue[tech_id]:
            raise DataLoadError(
                f"Aggregates file {tech_id!r} under {domain!r}, "
                f"the catalogue under {catalogue[tech_id]!r}"
            )
        if domain not in domain_ids:
            raise DataLoadError(
                f"Aggregates tech {tech_id!r} references unknown domain {domain!r}"
            )

    for month, row in sorted(aggregates.get("by_month", {}).items()):
        for domain in sorted(row.get("domains", {})):
            if domain not in domain_ids:
                raise DataLoadError(
                    f"Aggregates month {month} references unknown domain {domain!r}"
                )
        for tech_id in sorted(row.get("techs", {})):
            if tech_id not in catalogue:
                raise DataLoadError(
                    f"Aggregates month {month} references uncatalogued tech {tech_id!r}"
                )
