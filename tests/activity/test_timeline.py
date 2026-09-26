"""Guards for the continuous activity timeline (ADR-013 section 1)."""

from __future__ import annotations

import copy
import json
import pathlib
import runpy
import sys
from datetime import date

import pytest

from scripts.activity import timeline as tl

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "timeline.sample.json"


@pytest.fixture
def raw() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _period(**overrides) -> tl.Period:
    base = {
        "start": "2010-01",
        "end": "2010-12",
        "context": "employment",
        "label": "Org",
        "sources": (tl.Source("org", 1.0),),
    }
    base.update(overrides)
    return tl.Period(**base)


# --- Loading and validation ----------------------------------------------


def test_load_sample_is_valid_and_ordered():
    timeline = tl.load_timeline(FIXTURE)
    assert timeline.as_of == "2011-06"
    assert [p.context for p in timeline.periods] == [
        "none",
        "study",
        "client_mission",
        "employment",
        "parallel_employment",
        "independent_rnd",
    ]
    assert timeline.periods[-1].note == "Synthetic sample, not real data."
    assert timeline.exceptions == ("Synthetic exception note.",)


def test_one_month_period_counts_one_month():
    timeline = tl.load_timeline(FIXTURE)
    mission = timeline.periods[2]
    assert mission.start == mission.end
    assert mission.months == 1
    assert tl.month_range(mission.start, mission.end) == ["2008-07"]


def test_months_cover_the_whole_span_without_loss():
    timeline = tl.load_timeline(FIXTURE)
    total = sum(p.months for p in timeline.periods)
    assert total == len(tl.month_range(tl.TIMELINE_START, timeline.as_of))


def test_month_range_crosses_years():
    assert tl.month_range("2009-11", "2010-02") == [
        "2009-11",
        "2009-12",
        "2010-01",
        "2010-02",
    ]


def test_gap_is_rejected(raw):
    raw["periods"][3]["start"] = "2008-09"
    with pytest.raises(ValueError, match="gap"):
        tl.parse_timeline(raw)


def test_overlap_is_rejected(raw):
    raw["periods"][3]["start"] = "2008-07"
    with pytest.raises(ValueError, match="overlap"):
        tl.parse_timeline(raw)


def test_must_start_at_timeline_start(raw):
    raw["periods"][0]["start"] = "2005-10"
    with pytest.raises(ValueError, match="2005-09"):
        tl.parse_timeline(raw)


def test_must_end_at_as_of(raw):
    raw["as_of"] = "2011-07"
    with pytest.raises(ValueError, match="as_of"):
        tl.parse_timeline(raw)


def test_start_after_end_is_rejected(raw):
    raw["periods"][2]["end"] = "2008-06"
    with pytest.raises(ValueError, match="after"):
        tl.parse_timeline(raw)


@pytest.mark.parametrize("bad", ["2008-13", "2008-00", "2008-7", "08-07", 200807])
def test_malformed_month_is_rejected(raw, bad):
    raw["periods"][2]["start"] = bad
    with pytest.raises(ValueError, match="YYYY-MM"):
        tl.parse_timeline(raw)


def test_unknown_context_is_rejected(raw):
    raw["periods"][3]["context"] = "vacation"
    with pytest.raises(ValueError, match="context"):
        tl.parse_timeline(raw)


def test_shares_must_sum_to_one(raw):
    raw["periods"][4]["sources"][1]["share"] = 0.2
    with pytest.raises(ValueError, match="sum"):
        tl.parse_timeline(raw)


def test_share_must_be_positive(raw):
    raw["periods"][4]["sources"] = [
        {"id": "org-c", "share": 1.0},
        {"id": "org-d", "share": 0.0},
    ]
    with pytest.raises(ValueError, match="positive"):
        tl.parse_timeline(raw)


@pytest.mark.parametrize("share", ["1", True, None])
def test_share_must_be_a_number(raw, share):
    raw["periods"][3]["sources"][0]["share"] = share
    with pytest.raises(ValueError, match="number"):
        tl.parse_timeline(raw)


def test_duplicate_source_is_rejected(raw):
    raw["periods"][4]["sources"][1]["id"] = "org-c"
    with pytest.raises(ValueError, match="duplicate"):
        tl.parse_timeline(raw)


@pytest.mark.parametrize("source_id", ["", 3, None])
def test_source_id_must_be_a_non_empty_string(raw, source_id):
    raw["periods"][3]["sources"][0]["id"] = source_id
    with pytest.raises(ValueError, match="id"):
        tl.parse_timeline(raw)


def test_none_context_takes_no_source(raw):
    raw["periods"][0]["sources"] = [{"id": "x", "share": 1.0}]
    with pytest.raises(ValueError, match="none"):
        tl.parse_timeline(raw)


def test_other_contexts_need_a_source(raw):
    raw["periods"][3]["sources"] = []
    with pytest.raises(ValueError, match="source"):
        tl.parse_timeline(raw)


@pytest.mark.parametrize("key", ["start", "end", "context", "label", "sources"])
def test_missing_period_key_is_rejected(raw, key):
    del raw["periods"][3][key]
    with pytest.raises(ValueError, match=key):
        tl.parse_timeline(raw)


def test_unknown_period_key_is_rejected(raw):
    raw["periods"][3]["hours"] = 12
    with pytest.raises(ValueError, match="hours"):
        tl.parse_timeline(raw)


def test_unknown_top_level_key_is_rejected(raw):
    raw["extra"] = 1
    with pytest.raises(ValueError, match="extra"):
        tl.parse_timeline(raw)


def test_label_must_be_a_non_empty_string(raw):
    raw["periods"][3]["label"] = ""
    with pytest.raises(ValueError, match="label"):
        tl.parse_timeline(raw)


def test_note_must_be_a_string(raw):
    raw["periods"][3]["note"] = 3
    with pytest.raises(ValueError, match="note"):
        tl.parse_timeline(raw)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: r.pop("periods"),
        lambda r: r.update(periods=[]),
        lambda r: r.update(periods={}),
        lambda r: r.update(exceptions="x"),
        lambda r: r.update(exceptions=[3]),
        lambda r: r["periods"].__setitem__(0, "x"),
        lambda r: r["periods"][3].update(sources="org-b"),
        lambda r: r["periods"][3].update(sources=["org-b"]),
    ],
)
def test_structural_errors_are_rejected(raw, mutate):
    mutate(raw)
    with pytest.raises(ValueError):
        tl.parse_timeline(raw)


def test_top_level_must_be_an_object():
    with pytest.raises(ValueError, match="object"):
        tl.parse_timeline([])


def test_exceptions_are_optional(raw):
    del raw["exceptions"]
    assert tl.parse_timeline(raw).exceptions == ()


def test_invalid_json_file_raises_value_error(tmp_path):
    bad = tmp_path / "t.json"
    bad.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError):
        tl.load_timeline(bad)


def test_parse_does_not_mutate_input(raw):
    before = copy.deepcopy(raw)
    tl.parse_timeline(raw)
    assert raw == before


# --- Budgets (ADR-013 section 1 table) -----------------------------------


def test_day_grid_is_eleven_hours():
    assert tl.AVAILABLE_HOURS_PER_DAY == 11


@pytest.mark.parametrize(
    ("context", "pro", "personal"),
    [
        ("employment", 8, 3),
        ("client_mission", 8, 3),
        ("parallel_employment", 10, 1),
        ("independent_rnd", 0, 11),
        ("study", 0, 0),
        ("none", 0, 0),
    ],
)
def test_daily_budgets(context, pro, personal):
    budget = tl.budget_for(context)
    assert budget.pro_per_weekday == pro
    assert budget.personal_per_commit_day == personal
    assert budget.pro_per_weekday + budget.personal_per_commit_day <= 11


def test_study_budget_is_twelve_hours_a_week_thirty_weeks_a_year():
    budget = tl.budget_for("study")
    academic_months = len(tl.ACADEMIC_MONTHS)
    assert academic_months == 10
    assert budget.study_per_academic_month * academic_months == 12 * 30


def test_unknown_context_budget_raises():
    with pytest.raises(ValueError, match="context"):
        tl.budget_for("vacation")


# --- Calendar ------------------------------------------------------------


@pytest.mark.parametrize(
    ("month", "weekdays"),
    [("2024-02", 21), ("2008-07", 23), ("2010-03", 23), ("2026-09", 22)],
)
def test_weekdays_in_month(month, weekdays):
    assert tl.weekdays_in_month(month) == weekdays


# --- Professional hours --------------------------------------------------


def test_pro_hours_employment_counts_weekdays():
    assert tl.pro_hours(_period(), "2010-03") == {"org": 23 * 8}


def test_pro_hours_one_month_period():
    period = _period(start="2008-07", end="2008-07", context="client_mission")
    assert tl.pro_hours(period, "2008-07") == {"org": 23 * 8}


def test_pro_hours_parallel_split_by_share():
    period = _period(
        context="parallel_employment",
        sources=(tl.Source("org-c", 0.7), tl.Source("org-d", 0.3)),
    )
    hours = tl.pro_hours(period, "2010-03")
    assert hours == pytest.approx({"org-c": 23 * 10 * 0.7, "org-d": 23 * 10 * 0.3})
    assert sum(hours.values()) == pytest.approx(230)


def test_pro_hours_independent_rnd_is_zero():
    period = _period(context="independent_rnd")
    assert tl.pro_hours(period, "2010-03") == {"org": 0.0}


def test_pro_hours_none_is_empty():
    period = _period(context="none", sources=())
    assert tl.pro_hours(period, "2010-03") == {}


def test_pro_hours_study_academic_month():
    period = _period(context="study")
    assert tl.pro_hours(period, "2010-03") == {"org": 36.0}


@pytest.mark.parametrize("month", ["2010-07", "2010-08"])
def test_pro_hours_study_summer_is_zero(month):
    period = _period(context="study")
    assert tl.pro_hours(period, month) == {"org": 0.0}


def test_pro_hours_month_outside_period_raises():
    with pytest.raises(ValueError, match="outside"):
        tl.pro_hours(_period(), "2011-01")


def test_period_pro_total():
    period = _period(start="2010-03", end="2010-03")
    assert tl.period_pro_total(period) == 23 * 8


# --- Personal hours ------------------------------------------------------


def test_personal_hours_counts_commit_days_only():
    days = {date(2021, 3, 1), date(2021, 3, 2)}
    assert tl.personal_hours(tl.budget_for("independent_rnd"), days) == 22


def test_personal_hours_weekend_counts_the_same():
    saturday, monday = date(2021, 3, 6), date(2021, 3, 8)
    budget = tl.budget_for("employment")
    assert tl.personal_hours(budget, {saturday}) == tl.personal_hours(budget, {monday})


def test_personal_hours_no_commit_no_hours():
    assert tl.personal_hours(tl.budget_for("independent_rnd"), set()) == 0


# --- CLI -----------------------------------------------------------------


def test_cli_check_prints_months_and_pro_hours(capsys):
    assert tl.main(["--check", str(FIXTURE)]) == 0
    out = capsys.readouterr().out
    assert "2008-07" in out and "client_mission" in out
    assert "months=1" in out
    assert "pro_hours=184" in out
    assert "total" in out


def test_cli_check_reports_invalid_file(tmp_path, raw, capsys):
    raw["periods"][3]["start"] = "2008-09"
    bad = tmp_path / "t.json"
    bad.write_text(json.dumps(raw), encoding="utf-8")
    assert tl.main(["--check", str(bad)]) == 1
    assert "gap" in capsys.readouterr().err


def test_cli_defaults_to_private_dir(tmp_path, monkeypatch, capsys):
    (tmp_path / "timeline.json").write_text(
        FIXTURE.read_text(encoding="utf-8"), encoding="utf-8"
    )
    monkeypatch.setenv("PROFILE_PRIVATE_DIR", str(tmp_path))
    assert tl.main(["--check"]) == 0
    assert "independent_rnd" in capsys.readouterr().out


def test_cli_without_file_or_env_fails(monkeypatch, capsys):
    monkeypatch.delenv("PROFILE_PRIVATE_DIR", raising=False)
    assert tl.main(["--check"]) == 2
    assert "PROFILE_PRIVATE_DIR" in capsys.readouterr().err


def test_module_entry_point(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["timeline", "--check", str(FIXTURE)])
    monkeypatch.delitem(sys.modules, "scripts.activity.timeline", raising=False)
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("scripts.activity.timeline", run_name="__main__")
    assert exc.value.code == 0
