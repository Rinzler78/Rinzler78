"""Domain membership has to survive being read as a timeline.

Every per-domain view answers "when was he doing this". A tech filed under the
wrong domain does not just mislabel a chip, it keeps a whole row of the journey
heatmap lit: general-purpose operating systems are used on every engagement, so
filing them under `embedded` shows embedded work running to the present day —
while the profile itself states that professional embedded work stopped.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# Operating systems used as a workstation or a server. Not embedded targets:
# Windows CE is, these are not.
GENERAL_PURPOSE_OS = {"linux-ubuntu", "windows"}


def _techs() -> list[dict]:
    return json.loads((DATA / "techs.json").read_text(encoding="utf-8"))


def _domain_ids() -> set[str]:
    return {
        d["id"] for d in json.loads((DATA / "domains.json").read_text(encoding="utf-8"))
    }


def test_general_purpose_operating_systems_are_infrastructure():
    by_id = {t["id"]: t for t in _techs()}
    for tech_id in GENERAL_PURPOSE_OS:
        assert by_id[tech_id]["domain"] == "devops", (
            f"{tech_id} is a workstation/server OS: filing it under "
            f"{by_id[tech_id]['domain']!r} keeps that domain lit for every "
            "engagement that merely runs on it."
        )


def test_embedded_holds_only_embedded_targets():
    embedded = {t["id"] for t in _techs() if t["domain"] == "embedded"}
    assert embedded.isdisjoint(GENERAL_PURPOSE_OS)
    assert "windows-ce" in embedded  # a real embedded target stays


def test_every_tech_points_at_a_declared_domain():
    declared = _domain_ids()
    for tech in _techs():
        assert tech["domain"] in declared, (
            f"{tech['id']} → unknown domain {tech['domain']!r}"
        )


def test_context_documents_every_declared_domain():
    context = (ROOT / "CONTEXT.md").read_text(encoding="utf-8")
    for domain_id in _domain_ids():
        assert f"`{domain_id}`" in context, (
            f"CONTEXT.md does not mention the {domain_id} domain"
        )
