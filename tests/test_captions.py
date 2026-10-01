"""Chart conclusions carry no hand-typed figure.

Every number in the prose doubling a chart — years of an era, domain shares,
level thresholds — is computed at generation time from the committed
aggregates and injected into the wording, in French and in English. A figure
typed into the prose would be wrong the day the aggregates move.
"""

from __future__ import annotations

import copy

import pytest

import scripts.generate as gen
from scripts.captions import (
    caption_values,
    caption_words,
    domain_shares,
    dominant_eras,
    format_eras,
    format_levels,
    format_split,
)
from scripts.translate import CACHE, localize_data

LABELS = {"mobile": "Mobile", "embedded": "Embedded", "ai-llm": "AI & LLM"}

# Synthetic connecting words: the real ones are display copy in
# data/content.json; these pin the mechanics, including a decimal comma and a
# space as thousands separator.
WORDS = {
    "and": " + ",
    "range": "{label} {start}..{end}",
    "since": "{label} {start}..",
    "split_head": "{label} {pct}",
    "split_then": "; ",
    "level": "{level}>={hours}",
    "decimal": ",",
    "thousands": " ",
    "percent": "{value} pct",
}


def _years(**rows: dict[int, float]) -> dict[str, dict[int, float]]:
    return dict(rows)


# --- Eras -----------------------------------------------------------------


def test_an_era_is_a_run_of_years_led_by_one_domain():
    series = _years(
        mobile={2006: 9, 2007: 9, 2008: 9, 2009: 1, 2010: 1, 2011: 1},
        embedded={2006: 1, 2007: 1, 2008: 1, 2009: 9, 2010: 9, 2011: 9},
    )
    assert dominant_eras(series) == [("mobile", 2006, 2008), ("embedded", 2009, 2011)]


def test_a_lead_shorter_than_the_minimum_is_not_an_era():
    series = _years(
        mobile={2006: 9, 2007: 9, 2008: 9, 2009: 1},
        embedded={2006: 1, 2007: 1, 2008: 1, 2009: 9},
    )
    assert dominant_eras(series) == [("mobile", 2006, 2008)]


def test_a_gap_year_ends_an_era():
    # 2007 has no hours at all: 2006 and 2008 are not consecutive years.
    series = _years(mobile={2006: 9, 2008: 9, 2009: 9, 2010: 9})
    assert dominant_eras(series, min_years=2) == [("mobile", 2008, 2010)]
    assert dominant_eras(series, min_years=1) == [
        ("mobile", 2006, 2006),
        ("mobile", 2008, 2010),
    ]


def test_a_tie_is_broken_deterministically():
    series = _years(
        mobile={2006: 5, 2007: 5, 2008: 5}, embedded={2006: 5, 2007: 5, 2008: 5}
    )
    assert dominant_eras(series) == [("embedded", 2006, 2008)]


def test_eras_close_or_stay_open_at_the_as_of_year():
    eras = [("mobile", 2006, 2008), ("embedded", 2009, 2013), ("ai-llm", 2022, 2026)]
    assert format_eras(eras, LABELS, 2026, WORDS) == (
        "Mobile 2006..2008, Embedded 2009..2013 + AI & LLM 2022.."
    )


# --- Shares ---------------------------------------------------------------


def test_domain_shares_make_a_whole_largest_first():
    shares = domain_shares(_years(mobile={2020: 3.0}, embedded={2019: 1.0}))
    assert shares == [("mobile", 75.0), ("embedded", 25.0)]
    assert sum(pct for _, pct in shares) == 100.0


def test_the_split_names_the_largest_domains_with_their_share():
    shares = [("mobile", 42.6), ("embedded", 19.2), ("ai-llm", 11.4), ("x", 1.0)]
    assert format_split(shares, LABELS, WORDS, named=3) == (
        "Mobile 42,6 pct; Embedded 19,2 pct + AI & LLM 11,4 pct"
    )


def test_a_single_domain_split_has_no_tail():
    assert format_split([("mobile", 100.0)], LABELS, WORDS) == "Mobile 100,0 pct"
    assert format_split([], LABELS, WORDS) == ""


# --- Levels convention ----------------------------------------------------


def test_levels_read_from_the_convention_in_ascending_order():
    levels = {"expert": 5000, "working": 50, "advanced": 1600, "professional": 500}
    assert format_levels(levels, WORDS) == (
        "working>=50, professional>=500, advanced>=1 600 + expert>=5 000"
    )


def test_an_unknown_language_is_refused():
    with pytest.raises(ValueError, match="de"):
        caption_words(gen.load_data(), "de")


# --- Wiring: the rendered conclusions follow the aggregates ----------------


def _conclusions(raw: dict, lang: str) -> dict[str, str]:
    bag = copy.deepcopy(raw)
    if lang == "en":
        bag = gen._escape_amp(localize_data(bag, CACHE))
    data = gen.enrich(bag, lang)
    return {k: v["conclusion"] for k, v in data["content"]["charts"].items()}


def test_conclusions_carry_no_unresolved_placeholder():
    for lang in ("fr", "en"):
        for key, text in _conclusions(gen.load_data(), lang).items():
            assert "{" not in text and "}" not in text, (lang, key)


def _words(lang: str) -> dict[str, str]:
    return gen.load_data()["content"]["caption_words"][lang]


def test_conclusions_follow_the_level_convention():
    raw = gen.load_data()
    raw["aggregates"]["levels"]["expert"] = 7000
    for lang in ("fr", "en"):
        words = _words(lang)
        hours = f"{7000:,}".replace(",", words["thousands"])
        expected = words["level"].format(level="expert", hours=hours)
        assert expected in _conclusions(raw, lang)["top_skills"], lang


def test_conclusions_follow_the_domain_hours():
    raw = gen.load_data()
    for row in raw["aggregates"]["by_month"].values():
        row["domains"] = {"blockchain": 1.0}
    first_year = int(min(raw["aggregates"]["by_month"])[:4])
    for lang in ("fr", "en"):
        words = _words(lang)
        conclusions = _conclusions(raw, lang)
        pct = words["percent"].format(value="100" + words["decimal"] + "0")
        split = words["split_head"].format(label="Blockchain", pct=pct)
        era = words["since"].format(label="Blockchain", start=first_year)
        assert split in conclusions["domain_split"], lang
        assert era in conclusions["journey_share"], lang


def test_english_conclusions_are_english():
    en = _conclusions(gen.load_data(), "en")
    assert "Each year" in en["journey_share"]
    assert "holds" in en["domain_split"]
    assert "convention" in en["top_skills"]


def test_caption_values_are_computed_per_language():
    data = gen.enrich(gen.load_data(), "en")
    values = caption_values(data, "en")
    assert set(values) == {"eras", "split", "levels"}
    assert values["levels"].startswith("working")
