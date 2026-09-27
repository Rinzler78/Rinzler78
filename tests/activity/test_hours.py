"""Guards for the hours aggregates (ADR-013 sections 3-6).

The fixtures ``fixtures/hours_*.json`` are synthetic: a short timeline with
every context, a handful of commit days, and the repository classes and
experiences that drive allocation. Expected figures are derived by hand in the
comments so a failure says which rule moved.
"""

from __future__ import annotations

import copy
import json
import pathlib
import runpy
import sys

import pytest

from scripts.activity import hours as hr
from scripts.activity import timeline as tl

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
REPO = pathlib.Path(__file__).resolve().parents[2]
REAL_TECH_MAP = REPO / "scripts" / "activity" / "tech_map.json"
CATALOGUE = REPO / "data" / "techs.json"


def _json(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def tech_map() -> hr.TechMap:
    return hr.load_tech_map(REAL_TECH_MAP)


@pytest.fixture
def inputs(tech_map) -> hr.Inputs:
    return hr.Inputs(
        timeline=tl.load_timeline(FIXTURES / "hours_timeline.json"),
        days=hr.parse_evidence(_json("hours_evidence.json")),
        classes=hr.parse_repo_classes(_json("hours_repo_classes.json")),
        tech_map=tech_map,
        experiences=hr.parse_experiences(_json("hours_experiences.json")),
        declared=hr.parse_declared(_json("hours_declared.json"), tech_map),
    )


@pytest.fixture
def doc(inputs) -> dict:
    return hr.aggregate(inputs, catalogue=[])


# --- Tech map ------------------------------------------------------------


def _map(**overrides) -> dict:
    base = {
        "version": 1,
        "excluded": {"git": "tool"},
        "collector": {"csharp": "csharp-dotnet", "dotnet": "csharp-dotnet"},
        "techs": {"csharp-dotnet": {"kind": "language", "domain": "languages"}},
    }
    base.update(overrides)
    return base


def test_real_tech_map_loads_and_excludes_git(tech_map):
    assert "git" in tech_map.excluded
    assert "git" not in tech_map.techs
    assert tech_map.techs["xamarin"].domain == "mobile"
    assert tech_map.techs["windows-ce"].domain == "mobile"
    assert tech_map.techs["objective-c"].domain == "mobile"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"version": 2}, "version"),
        ({"collector": {"csharp": "nope"}}, "unknown catalogue id"),
        ({"techs": {"x": {"kind": "tool", "domain": "d"}}}, "kind"),
        ({"techs": {"x": {"kind": "language"}}}, "domain"),
        ({"excluded": {"csharp-dotnet": "why"}}, "excluded"),
        ({"collector": []}, "collector"),
        ({"excluded": []}, "excluded"),
        ({"techs": []}, "techs"),
    ],
)
def test_tech_map_rejects_defects(overrides, message):
    with pytest.raises(ValueError, match=message):
        hr.parse_tech_map(_map(**overrides))


def test_tech_map_rejects_non_object():
    with pytest.raises(ValueError, match="object"):
        hr.parse_tech_map([])


def test_to_catalogue_merges_and_drops_excluded(tech_map):
    weights = tech_map.to_catalogue({"csharp": 0.5, "dotnet": 0.25, "ble": 0.25})
    assert weights == {"csharp-dotnet": 0.75, "bluetooth": 0.25}


def test_to_catalogue_refuses_unknown_collector_id(tech_map):
    with pytest.raises(ValueError, match="unknown collector tech 'cobol'"):
        tech_map.to_catalogue({"cobol": 1.0})


def test_collector_excluded_id_is_dropped():
    mapping = hr.parse_tech_map(
        _map(collector={"git": None, "csharp": "csharp-dotnet"})
    )
    assert mapping.to_catalogue({"git": 0.5, "csharp": 0.5}) == {"csharp-dotnet": 0.5}


# --- File shares ---------------------------------------------------------


def test_shares_are_file_fractions_and_may_overlap():
    # 4 analyzed files: 3 C#, 2 of them calling BLE, 1 README.
    shares = hr.shares_from(4, {"csharp-dotnet": 3, "bluetooth": 2, "python": 0})
    assert shares == {"csharp-dotnet": 0.75, "bluetooth": 0.5}
    assert hr.shares_from(0, {"python": 1}) == {}
    assert hr.shares_from(1, {"python": 3}) == {"python": 1.0}  # capped


def test_allocate_is_hours_times_share():
    alloc = hr.allocate(10.0, {"csharp-dotnet": 0.75, "bluetooth": 0.5, "x": 0.0})
    assert alloc == {"csharp-dotnet": 7.5, "bluetooth": 5.0}
    assert hr.allocate(10.0, {}) == {}


def test_domain_hours_sum_shares_capped(tech_map):
    shares = {"objective-c": 0.5, "xamarin": 0.7, "python": 0.5}
    dom = hr.domain_hours(4.0, shares, tech_map)
    assert dom["mobile"] == pytest.approx(4.0)  # 1.2 capped at 1
    assert dom["languages"] == pytest.approx(2.0)
    assert hr.domain_hours(4.0, {"python": 0.0}, tech_map) == {}


# --- Levels and display --------------------------------------------------


@pytest.mark.parametrize(
    ("hours", "level"),
    [
        (0, None),
        (49.99, None),
        (50, "working"),
        (499.9, "working"),
        (500, "professional"),
        (1599.9, "professional"),
        (1600, "advanced"),
        (4999, "advanced"),
        (5000, "expert"),
    ],
)
def test_level_convention(hours, level):
    assert hr.level_for(hours) == level


@pytest.mark.parametrize(
    ("hours", "shown"),
    [
        (0, 0),
        (49.9, 40),
        (57.4, 50),
        (499.99, 490),
        (999.9, 990),
        (1599.9, 1500),
        (1650, 1600),
        (4999, 4900),
        (12345, 12000),
    ],
)
def test_display_hours_rounds_down(hours, shown):
    assert hr.display_hours(hours) == shown


def test_display_never_crosses_a_threshold():
    ranks = [None, "working", "professional", "advanced", "expert"]
    for raw in range(0, 7000):
        value = raw + 0.99
        shown = hr.display_hours(value)
        assert shown <= value
        assert hr.level_for(shown) == hr.level_for(value) or shown < 50
        assert ranks.index(hr.level_for(shown)) <= ranks.index(hr.level_for(value))


# --- Experiences (declared tiers) ----------------------------------------


def test_experience_shares_use_active_experiences_and_drop_git(tech_map):
    exps = hr.parse_experiences(_json("hours_experiences.json"))
    shares = hr.experience_shares(["freelance"], "2007-07", exps, tech_map)
    # The only declared language takes 100 %; docker keeps its tier.
    assert shares == {"python": 1.0, "docker": 0.35}


def test_estimated_languages_share_pro_rata(tech_map):
    exps = hr.parse_experiences(_json("hours_experiences.json"))
    shares = hr.experience_shares(["org-d", "school-x"], "2010-01", exps, tech_map)
    assert shares == {"csharp-dotnet": 0.5, "c-cpp": 0.5, "windows-ce": 0.35}
    active = hr.experience_shares(["org-d", "school-x"], "2008-02", exps, tech_map)
    assert active == {"csharp-dotnet": 1.0}


def test_estimated_non_language_tiers_are_capped(tech_map):
    exps = hr.parse_experiences(
        [
            {
                "id": "a",
                "start": "2008-01",
                "end": None,
                "tech_weights": {"nfc": "primary"},
            },
            {
                "id": "b",
                "start": "2008-01",
                "end": None,
                "tech_weights": {"nfc": "primary"},
            },
        ]
    )
    assert hr.experience_shares(["a", "b"], "2008-02", exps, tech_map) == {"nfc": 1.0}


def test_experience_shares_unknown_experience_is_empty(tech_map):
    assert hr.experience_shares(["nobody"], "2008-02", {}, tech_map) == {}


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ({}, "list"),
        ([1], "object"),
        ([{"id": "a", "start": "2008-01", "end": None}], "tech_weights"),
        (
            [
                {
                    "id": "a",
                    "start": "2008-01",
                    "end": None,
                    "tech_weights": {"x": "top"},
                }
            ],
            "tier",
        ),
    ],
)
def test_parse_experiences_rejects_defects(raw, message):
    with pytest.raises(ValueError, match=message):
        hr.parse_experiences(raw)


def test_experiences_for_source_maps_timeline_ids():
    assert hr.experiences_for("good-angel") == ("goodangel-mgl-p1", "goodangel-mgl-p2")
    assert hr.experiences_for("freelance-client") == ("freelance",)
    assert hr.experiences_for("gunnebo") == ("gunnebo",)


# --- Declared periods ------------------------------------------------------


def test_parse_declared_reads_periods_and_overlays(tech_map):
    declared = hr.parse_declared(_json("hours_declared.json"), tech_map)
    assert [p.source for p in declared.periods][:2] == [
        "freelance-client",
        "freelance-client",
    ]
    mission = declared.periods[0]
    assert mission.pro_hours_per_weekday == 7
    assert mission.shares() == {"python": 1.0, "docker": 0.35}
    assert declared.periods[3].within_study_budget is True
    assert [p.start for p in declared.for_month("school-x", "2007-02", "2008-05")] == [
        "2006-09",
        "2007-01",
    ]
    assert len(declared.for_month("freelance-client", "2008-05", "2008-05")) == 1
    assert declared.overlay_shares("2007-09") == {"ai-driven-development": 0.1}
    assert declared.overlay_shares("2008-05") == {}
    assert declared.overlay_shares("2006-01") == {}


def test_declared_tier_on_a_language_adds_to_its_share(tech_map):
    raw = {
        "version": 1,
        "periods": [
            {
                "source": "s",
                "start": "2008-01",
                "end": None,
                "languages": {"python": 1.0},
                "tiers": {"python": "incident", "bash": "secondary"},
            }
        ],
    }
    period = hr.parse_declared(raw, tech_map).periods[0]
    assert period.shares() == {"python": 1.0, "bash": 0.35}


def _declared(**overrides) -> dict:
    period = {
        "source": "s",
        "start": "2008-01",
        "end": "2008-02",
        "languages": {"python": 1.0},
        "tiers": {},
    }
    period.update(overrides)
    return {"version": 1, "periods": [period]}


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ([], "object"),
        ({"version": 2, "periods": []}, "version"),
        ({"version": 1, "periods": {}}, "periods"),
        ({"version": 1, "periods": [1]}, "object"),
        (_declared(source=""), "source"),
        (_declared(start="2008"), "YYYY-MM"),
        (_declared(end="2007-01"), "before"),
        (_declared(languages={"python": 0.5}), "sum to 1"),
        (_declared(languages={"cobol": 1.0}), "unknown tech"),
        (_declared(tiers={"docker": "top"}), "tier"),
        (_declared(tiers={"nope": "primary"}), "unknown tech"),
        (_declared(tiers=[]), "tiers"),
        (_declared(pro_hours_per_weekday=0), "pro_hours_per_weekday"),
        (_declared(pro_hours_per_weekday=12), "pro_hours_per_weekday"),
        ({"version": 1, "periods": [], "overlays": {}}, "overlays"),
        ({"version": 1, "periods": [], "overlays": [1]}, "object"),
        (
            {"version": 1, "periods": [], "overlays": [{"tech": "nope"}]},
            "unknown tech",
        ),
        (
            {
                "version": 1,
                "periods": [],
                "overlays": [
                    {
                        "tech": "docker",
                        "periods": [
                            {"start": "2008-01", "end": "2008-02", "tier": "x"}
                        ],
                        "measured_from": "2009-01",
                    }
                ],
            },
            "tier",
        ),
    ],
)
def test_parse_declared_rejects_defects(raw, message, tech_map):
    with pytest.raises(ValueError, match=message):
        hr.parse_declared(raw, tech_map)


def test_empty_declared_keeps_experience_fallback(inputs):
    inputs.declared = hr.Declared((), ())
    units = hr.build_units(inputs)
    assert {u.fallback for u in units if u.fallback} == {"school-x", "freelance-client"}


# --- Evidence and classes ------------------------------------------------


def test_parse_evidence_reads_days():
    days = hr.parse_evidence(_json("hours_evidence.json"))
    assert len(days) == 8
    assert days["2007-08-11"].public is True
    assert days["2007-08-06"].repos == ("git.org-b/app",)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda d: d.pop("days"), "days"),
        (lambda d: d["days"].update({"2007-13-01": d["days"]["2007-08-06"]}), "date"),
        (lambda d: d["days"]["2007-08-06"].pop("file_counts"), "file_counts"),
        (lambda d: d["days"]["2007-08-06"].update({"files": -1}), "files"),
        (lambda d: d["days"]["2007-08-06"].update({"files": True}), "files"),
        (
            lambda d: d["days"]["2007-08-06"].update({"file_counts": {"ble": 9}}),
            "exceeds",
        ),
        (lambda d: d["days"]["2007-08-06"].update({"repos": "x"}), "repos"),
        (
            lambda d: d["days"]["2007-08-06"].update({"file_counts": {"ble": -1}}),
            "integer",
        ),
        (
            lambda d: d["days"]["2007-08-06"].update({"file_counts": {"ble": 0.5}}),
            "integer",
        ),
        (lambda d: d["days"].update({"2007-8-6": {}}), "YYYY-MM-DD"),
    ],
)
def test_parse_evidence_rejects_defects(mutate, message):
    raw = _json("hours_evidence.json")
    mutate(raw)
    with pytest.raises(ValueError, match=message):
        hr.parse_evidence(raw)


def test_parse_evidence_rejects_non_object():
    with pytest.raises(ValueError, match="object"):
        hr.parse_evidence([])


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ([], "object"),
        ({"r": {"context": "work", "source": "x"}}, "context"),
        ({"r": {"context": "pro", "source": ""}}, "source"),
        ({"r": "pro"}, "object"),
    ],
)
def test_parse_repo_classes_rejects_defects(raw, message):
    with pytest.raises(ValueError, match=message):
        hr.parse_repo_classes(raw)


def test_evidence_day_outside_timeline_is_an_error(inputs):
    inputs.days["2009-01-05"] = inputs.days["2008-05-02"]
    with pytest.raises(ValueError, match="outside the timeline"):
        hr.build_units(inputs)


# --- Allocation over the timeline ----------------------------------------


def test_context_totals_are_additive(doc):
    # study: 10 academic months x 36 h; pro: client 2007-07 (22 weekdays at
    # the declared 7 h) + org B 2007-08..12 (23+20+23+22+21 weekdays) +
    # parallel 2008-01..03 (23+21+21 weekdays) at 8 h; personal: 3+3+11+11+11.
    assert doc["context_totals"] == {"pro": 1546.0, "personal": 39.0, "study": 360.0}
    month = doc["by_month"]["2007-08"]["context"]
    assert month == {"pro": 184.0, "personal": 3.0, "study": 0.0}


def test_traced_month_uses_that_month_commit_days(doc):
    aug = doc["by_month"]["2007-08"]["techs"]
    # org B, 5 files: 4 C# + 1 project file (both C#/.NET), 2 calling BLE.
    assert aug["csharp-dotnet"] == pytest.approx(184.0)
    assert aug["bluetooth"] == pytest.approx(184 * 2 / 5)
    assert aug["python"] == pytest.approx(3 * 1 / 2)  # personal: 1 of 2 files


def test_untraced_month_uses_the_period_file_counts(doc):
    # 2007-10: 23 weekdays; org B period: 9 files, 7 C#/.NET, 2 BLE, 2 Python.
    oct_ = doc["by_month"]["2007-10"]["techs"]
    assert oct_["csharp-dotnet"] == pytest.approx(184 * 7 / 9, abs=0.01)
    assert oct_["python"] == pytest.approx(184 * 2 / 9, abs=0.01)
    assert oct_["bluetooth"] == pytest.approx(184 * 2 / 9, abs=0.01)


def test_carried_shares_never_predate_a_first_commit(doc):
    # org D commits TypeScript only in 2008-02: January stays unallocated.
    assert "typescript" not in doc["by_month"]["2008-01"]["techs"]
    assert doc["techs"]["typescript"]["first"] == "2008-02"
    assert doc["techs"]["typescript"]["hours"] == pytest.approx(100.8)


def test_parallel_sources_split_by_share(doc):
    jan = doc["by_month"]["2008-01"]
    # org C 0.7 x 184, 3 of 5 files in C; org D's 0.3 is unallocated.
    assert jan["techs"]["c-cpp"] == pytest.approx(128.8 * 0.6)
    assert jan["techs"]["docker"] == pytest.approx(128.8 * 0.2)
    assert jan["context"]["pro"] == pytest.approx(184.0)


def test_declared_periods_replace_experience_tiers(doc):
    # Two declared periods overlap in 2007-07: 22 weekdays x 7 h split 50/50.
    jul = doc["by_month"]["2007-07"]
    assert jul["context"]["pro"] == pytest.approx(154.0)
    # A: languages as-is, docker secondary 0.35, git excluded; B: bash only.
    assert jul["techs"] == {"python": 77.0, "docker": 26.95, "bash": 77.0}
    measured = 128.8 * 0.2 + 2 * 0.7 * 168 * 0.2
    assert doc["techs"]["docker"]["declared_share"] == pytest.approx(
        26.95 / (26.95 + measured), abs=0.001
    )


def test_study_uses_declared_languages_and_tiers(doc):
    sep = doc["by_month"]["2006-09"]
    assert sep["context"] == {"pro": 0.0, "personal": 0.0, "study": 36.0}
    assert sep["techs"] == {"c-cpp": 21.6, "sql": 14.4, "windows-ce": 12.6}
    assert "2007-07" in doc["by_month"]
    assert "2006-07" not in doc["by_month"]  # context none counts nothing


def test_within_study_budget_splits_the_month(doc):
    # 2007-01: school shares on 18 h, cup shares on the other 18 h.
    jan = doc["by_month"]["2007-01"]
    assert jan["context"]["study"] == 36.0
    assert jan["techs"] == {
        "c-cpp": pytest.approx(10.8 + 18.0),
        "sql": pytest.approx(7.2),
        "windows-ce": pytest.approx(6.3),
        "computer-vision": pytest.approx(12.6),
    }


def test_months_without_declaration_fall_back_to_experiences(inputs, doc):
    apr = doc["by_month"]["2007-04"]["techs"]
    assert apr == {"c-cpp": 36.0, "windows-ce": 12.6}
    fallback = [(u.fallback, u.month) for u in hr.build_units(inputs) if u.fallback]
    assert fallback == [
        ("school-x", "2007-04"),
        ("school-x", "2007-05"),
        ("school-x", "2007-06"),
    ]


def test_ai_overlay_on_personal_days_only(doc):
    # Personal days: 3 h x 0.10 twice (incident), 11 h x 0.35 twice
    # (secondary), then measured from 2008-05 (3 of 10 files).
    ai = doc["techs"]["ai-driven-development"]
    assert ai["hours"] == pytest.approx(0.3 + 0.3 + 3.85 + 3.85 + 3.3, abs=0.01)
    assert ai["declared_share"] == pytest.approx(8.3 / 11.6, abs=0.001)
    # Never on professional hours: org B's October has no AI.
    assert "ai-driven-development" not in doc["by_month"]["2007-10"]["techs"]
    assert doc["by_month"]["2007-08"]["techs"]["ai-driven-development"] == 0.3


def test_pro_repo_outside_its_period_counts_as_personal(doc):
    apr = doc["by_month"]["2008-04"]
    # 2008-04-10: org B repo while org B is no source -> own R&D day (11 h);
    # 2008-04-12: unclassified repo, no tech weights -> 11 h, unallocated.
    assert apr["context"]["personal"] == pytest.approx(22.0)
    assert apr["techs"] == {"csharp-dotnet": 11.0, "ai-driven-development": 7.7}


def test_source_without_pro_budget_gets_no_pro_hours(inputs):
    # Own R&D has no professional budget, even when a repository names it.
    inputs.classes["github.com/me/tool"] = hr.RepoClass("pro", "own-rnd")
    units = hr.build_units(inputs)
    assert not [u for u in units if u.month == "2008-05" and u.kind == "pro"]


def test_pro_only_day_adds_no_personal_hours(doc):
    assert doc["by_month"]["2008-01"]["context"]["personal"] == 0.0


def test_mixed_day_counts_both_pro_trace_and_personal(doc):
    sep = doc["by_month"]["2007-09"]
    assert sep["context"] == {"pro": 160.0, "personal": 3.0, "study": 0.0}
    assert sep["techs"]["python"] == pytest.approx(80.0 + 1.5)


def test_git_is_never_counted(doc):
    assert "git" not in doc["techs"]
    for month in doc["by_month"].values():
        assert "git" not in month["techs"]


def test_tech_entries_carry_level_period_and_domain(doc):
    csharp = doc["techs"]["csharp-dotnet"]
    expected = 184 + 80 + (184 + 176 + 168) * 7 / 9 + 1.5 + 11
    assert csharp["hours"] == pytest.approx(expected, abs=0.1)
    assert csharp["level"] == "professional"
    assert csharp["display_hours"] == hr.display_hours(expected)
    assert (csharp["first"], csharp["last"]) == ("2007-08", "2008-04")
    assert csharp["domain"] == "languages"
    assert csharp["kind"] == "language"
    assert csharp["declared_share"] == 0.0


def test_domains_per_month(doc):
    aug = doc["by_month"]["2007-08"]["domains"]
    assert aug["languages"] == pytest.approx(184 + 1.5)
    assert aug["embedded"] == pytest.approx(184 * 2 / 5)


def test_coverage_and_as_of(doc):
    assert doc["coverage"] == {
        "commit_days": 8,
        "public_days": 3,
        "public_share": 0.375,
    }
    assert doc["activity_as_of"] == "2008-05-02"
    assert doc["version"] == 1
    assert doc["levels"] == {
        "working": 50,
        "professional": 500,
        "advanced": 1600,
        "expert": 5000,
    }


def test_output_names_no_repo_and_no_private_source(doc):
    text = json.dumps(doc)
    for secret in ("org-b", "git.org", "github.com", "unknown.host", "freelance"):
        assert secret not in text


def test_notes_state_the_rules(doc):
    notes = " ".join(doc["notes"])
    assert "not additive" in notes
    assert "convention" in notes
    assert "Git" in notes


def test_notes_list_domain_differences_with_catalogue(inputs):
    catalogue = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    doc = hr.aggregate(inputs, catalogue=catalogue)
    joined = " ".join(doc["notes"])
    assert "objective-c: languages -> mobile" in joined
    assert "windows-ce: embedded -> mobile" in joined


def test_public_source_alias():
    assert hr.public_source("freelance-client") == "client-mission"
    assert hr.public_source("gunnebo") == "gunnebo"


# --- Sanity checks -------------------------------------------------------


def test_sanity_checks_pass_on_fixture(inputs, doc):
    assert hr.sanity_checks(doc, hr.build_units(inputs), inputs) == []


def test_sanity_detects_first_use_before_evidence(inputs, doc):
    bad = copy.deepcopy(doc)
    bad["techs"]["typescript"]["first"] = "2007-01"
    issues = hr.sanity_checks(bad, hr.build_units(inputs), inputs)
    assert any("typescript" in i and "before" in i for i in issues)


def test_sanity_detects_first_use_before_release(inputs, doc):
    bad = copy.deepcopy(doc)
    bad["techs"]["github-actions"] = dict(bad["techs"]["docker"])
    issues = hr.sanity_checks(bad, hr.build_units(inputs), inputs)
    assert any("github-actions" in i and "2019-11" in i for i in issues)


def test_sanity_detects_budget_overflow(inputs, doc):
    units = hr.build_units(inputs)
    # Double the allocation only: the budgets still come from ``units``.
    inflated = [
        hr.Unit(u.month, u.kind, u.hours * 2, u.shares, u.declared, u.period)
        for u in units
    ]
    issues = hr.sanity_checks(doc, units, inputs, allocations=hr.allocations(inflated))
    assert any("exceeds" in i for i in issues)


# --- Serialization and CLI ------------------------------------------------


def _private_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    private = tmp_path / "private"
    private.mkdir()
    for src, dst in (
        ("hours_timeline.json", "timeline.json"),
        ("hours_evidence.json", "evidence.json"),
        ("hours_repo_classes.json", "repo-classes.json"),
        ("hours_declared.json", "declared.json"),
    ):
        (private / dst).write_text(
            (FIXTURES / src).read_text(encoding="utf-8"), encoding="utf-8"
        )
    return private


def _cli_args(out: pathlib.Path) -> list[str]:
    return [
        "--out",
        str(out),
        "--experiences",
        str(FIXTURES / "hours_experiences.json"),
    ]


def test_cli_writes_deterministic_aggregates(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PROFILE_PRIVATE_DIR", str(_private_dir(tmp_path)))
    out = tmp_path / "agg.json"
    assert hr.main(_cli_args(out)) == 0
    first = out.read_bytes()
    assert hr.main(_cli_args(out)) == 0
    assert out.read_bytes() == first
    assert first.endswith(b"\n")
    doc = json.loads(first)
    assert doc["context_totals"]["pro"] == 1546.0
    printed = capsys.readouterr().out
    assert "pro=1546" in printed
    assert "experience fallback: school-x 2007-04" in printed
    assert "csharp-dotnet" in printed
    assert "unclassified repositories: 1" in printed
    assert "sanity: OK" in printed


def test_cli_without_private_dir_fails(monkeypatch, capsys, tmp_path):
    monkeypatch.delenv("PROFILE_PRIVATE_DIR", raising=False)
    assert hr.main(["--out", str(tmp_path / "a.json")]) == 2
    assert "PROFILE_PRIVATE_DIR" in capsys.readouterr().err


def test_cli_reports_invalid_input(tmp_path, monkeypatch, capsys):
    private = _private_dir(tmp_path)
    (private / "repo-classes.json").write_text("[]", encoding="utf-8")
    monkeypatch.setenv("PROFILE_PRIVATE_DIR", str(private))
    assert hr.main(_cli_args(tmp_path / "a.json")) == 1
    assert "repo-classes" in capsys.readouterr().err


def test_cli_refuses_to_write_when_sanity_fails(tmp_path, monkeypatch, capsys):
    private = _private_dir(tmp_path)
    evidence = _json("hours_evidence.json")
    evidence["days"]["2008-05-02"]["file_counts"] = {"github-actions": 1}
    (private / "evidence.json").write_text(json.dumps(evidence), encoding="utf-8")
    monkeypatch.setenv("PROFILE_PRIVATE_DIR", str(private))
    out = tmp_path / "a.json"
    assert hr.main(_cli_args(out)) == 1
    assert not out.exists()
    assert "github-actions" in capsys.readouterr().err


def test_module_entry_point(tmp_path, monkeypatch):
    monkeypatch.setenv("PROFILE_PRIVATE_DIR", str(_private_dir(tmp_path)))
    argv = ["hours", *_cli_args(tmp_path / "a.json")]
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.delitem(sys.modules, "scripts.activity.hours", raising=False)
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("scripts.activity.hours", run_name="__main__")
    assert exc.value.code == 0
