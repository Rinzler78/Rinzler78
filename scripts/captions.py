"""Figures for the prose that doubles each chart, computed, never typed.

A chart conclusion in ``data/content.json`` is a wording with placeholders
(``{eras}``, ``{split}``, ``{levels}``); its French source and its English
translation keep the same placeholders. The values are computed here, at
generation time, from the same series the charts draw and from the level
convention committed in the aggregates (ADR-013), and formatted with the
connecting words and number format of the page's language
(``content.caption_words``).
A figure typed into the prose would be wrong the day the aggregates move.

Public surface:
- ``dominant_eras(domain_years)`` — runs of consecutive years led by one domain;
- ``domain_shares(domain_years)`` — lifetime shares that make a whole;
- ``format_eras`` / ``format_split`` / ``format_levels`` — per-language prose;
- ``caption_words(data, lang)`` — connecting words and number format;
- ``caption_values(data, lang)`` — the placeholder values of one page;
- ``render_conclusions(data, lang)`` — fills every chart conclusion in place.
"""

from __future__ import annotations

# Shortest run of years that reads as an era rather than as noise: a domain
# leading a single year between two others is a blip, not a period.
ERA_MIN_YEARS = 3

# Largest domains named by the split conclusion.
SPLIT_NAMED = 4

_LEVEL_ORDER = ("working", "professional", "advanced", "expert")


def _join(items: list[str], words: dict[str, str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + words["and"] + items[-1]


def _percent(value: float, words: dict[str, str]) -> str:
    text = f"{value:.1f}".replace(".", words["decimal"])
    return words["percent"].format(value=text)


def _thousands(value: int, words: dict[str, str]) -> str:
    return f"{value:,}".replace(",", words["thousands"])


def dominant_eras(
    domain_years: dict[str, dict[int, float]], min_years: int = ERA_MIN_YEARS
) -> list[tuple[str, int, int]]:
    """``(domain, first, last)`` runs of at least ``min_years`` led by a domain.

    A run covers consecutive years only: a year without hours ends it. A
    year's leader is the domain with the most hours; a tie goes to the
    first domain id in alphabetical order, so the result never depends on
    dictionary order.
    """
    years = sorted({y for row in domain_years.values() for y in row})
    leaders = []
    for year in years:
        ranked = sorted(
            ((-row.get(year, 0.0), domain) for domain, row in domain_years.items()),
        )
        leaders.append((year, ranked[0][1]))

    eras: list[tuple[str, int, int]] = []
    start = 0
    for i in range(1, len(leaders) + 1):
        if (
            i == len(leaders)
            or leaders[i][1] != leaders[start][1]
            or leaders[i][0] != leaders[i - 1][0] + 1  # a gap year ends a run
        ):
            first, domain = leaders[start]
            last = leaders[i - 1][0]
            if last - first + 1 >= min_years:
                eras.append((domain, first, last))
            start = i
    return eras


def domain_shares(domain_years: dict[str, dict[int, float]]) -> list[tuple[str, float]]:
    """Lifetime share per domain, one decimal, largest first, summing to 100.

    Rounding each share independently rarely lands on 100; the remainder goes
    to the smallest share, where it is least visible.
    """
    totals = {k: sum(v.values()) for k, v in domain_years.items()}
    grand = sum(totals.values())
    if not grand:
        return []
    shares = sorted(
        ((k, round(v / grand * 100, 1)) for k, v in totals.items()),
        key=lambda kv: (-kv[1], kv[0]),
    )
    drift = round(100.0 - sum(pct for _, pct in shares), 1)
    shares[-1] = (shares[-1][0], round(shares[-1][1] + drift, 1))
    return shares


def format_eras(
    eras: list[tuple[str, int, int]],
    labels: dict[str, str],
    as_of_year: int,
    words: dict[str, str],
) -> str:
    parts = []
    for domain, first, last in eras:
        label = labels.get(domain, domain)
        if last >= as_of_year:
            parts.append(words["since"].format(label=label, start=first))
        else:
            parts.append(words["range"].format(label=label, start=first, end=last))
    return _join(parts, words)


def format_split(
    shares: list[tuple[str, float]],
    labels: dict[str, str],
    words: dict[str, str],
    named: int = SPLIT_NAMED,
) -> str:
    shown = shares[:named]
    if not shown:
        return ""
    (top, top_pct), rest = shown[0], shown[1:]
    head = words["split_head"].format(
        label=labels.get(top, top), pct=_percent(top_pct, words)
    )
    if not rest:
        return head
    tail = [f"{labels.get(k, k)} {_percent(pct, words)}" for k, pct in rest]
    return head + words["split_then"] + _join(tail, words)


def format_levels(levels: dict[str, int], words: dict[str, str]) -> str:
    ordered = [lvl for lvl in _LEVEL_ORDER if lvl in levels]
    return _join(
        [
            words["level"].format(level=lvl, hours=_thousands(levels[lvl], words))
            for lvl in ordered
        ],
        words,
    )


def caption_words(data: dict, lang: str) -> dict[str, str]:
    """The connecting words and number format of ``lang``, from the content.

    Display copy lives in ``data/content.json`` (``caption_words``), one block
    per language, so this module carries no prose of its own.
    """
    words = data["content"]["caption_words"]
    if lang not in words:
        raise ValueError(f"no caption words for language {lang!r}")
    return words[lang]


def caption_values(data: dict, lang: str) -> dict[str, str]:
    """The placeholder values for one page, from its enriched data bag."""
    words = caption_words(data, lang)
    labels = {d["id"]: d["label"] for d in data["domains"]}
    series = data["domain_years"]
    return {
        "eras": format_eras(dominant_eras(series), labels, data["as_of_year"], words),
        "split": format_split(domain_shares(series), labels, words),
        "levels": format_levels(data["aggregates"]["levels"], words),
    }


def render_conclusions(data: dict, lang: str) -> None:
    """Fill the placeholders of every chart conclusion, in place.

    An unknown placeholder raises ``KeyError``: a wording that asks for a
    figure nobody computes must fail the build, not ship with braces.
    """
    values = caption_values(data, lang)
    for block in data["content"]["charts"].values():
        if block.get("conclusion"):
            block["conclusion"] = block["conclusion"].format_map(values)
