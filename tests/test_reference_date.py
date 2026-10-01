"""The page has one reference date, and it is committed data.

Hours, levels, periods and "now" are measured against the date of the
author's latest local collection: ``activity_as_of`` in
``data/activity/aggregates.json`` (ADR-013, ADR-016 as amended, ADR-018).
Reading the system clock instead would make the same revision regenerate
differently tomorrow, break the ``git diff --exit-code`` CI step on its own,
and make the pre-commit ``generate-profile`` hook rewrite files on an
unrelated commit (ADR-011).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import scripts.generate as gen

ROOT = Path(__file__).resolve().parent.parent
AGGREGATES = ROOT / "data" / "activity" / "aggregates.json"
GENERATION_PATH = (
    ROOT / "scripts" / "generate.py",
    ROOT / "scripts" / "view_builder.py",
    ROOT / "scripts" / "charts.py",
)


def _as_of() -> str:
    return json.loads(AGGREGATES.read_text(encoding="utf-8"))["activity_as_of"]


def test_the_reference_date_is_the_aggregates_activity_date():
    data = gen.enrich(gen.load_data())
    assert data["as_of"] == _as_of()
    assert data["as_of_year"] == int(_as_of()[:4])


def test_no_other_reference_date_is_committed():
    assert not (ROOT / "data" / "config.json").exists()


def test_generation_never_reads_the_clock():
    for path in GENERATION_PATH:
        source = path.read_text(encoding="utf-8")
        assert "today(" not in source, f"{path.name} reads the clock"
        assert "now(" not in source, f"{path.name} reads the clock"


def test_no_template_computes_against_a_literal_year():
    # A year typed into a template is a second reference date that never moves.
    for template in (ROOT / "scripts" / "templates").glob("*.jinja"):
        text = template.read_text(encoding="utf-8")
        assert not re.search(r"\b20\d\d\s*-", text), template.name


def test_an_ongoing_skill_reads_as_now_against_the_activity_date():
    data = gen.enrich(gen.load_data())
    as_of_year = data["as_of_year"]
    period_end = {t: e["last_year"] for t, e in data["aggregates"]["techs"].items()}
    for skill in data["skills"]:
        # The period ends at the last year with 10 h (aggregates v4), never
        # after the raw last month nor after the activity date.
        last_year = period_end[skill["id"]]
        assert last_year <= int(skill["last"][:4]) <= as_of_year, skill["id"]
        assert (skill["until"] is None) == (last_year == as_of_year), skill["id"]
