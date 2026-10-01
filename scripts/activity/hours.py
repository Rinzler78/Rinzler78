"""Hours aggregates from the activity timeline and commit evidence (ADR-013).

Inputs (private, read from ``$PROFILE_PRIVATE_DIR``, never committed):

- ``timeline.json``: the continuous timeline (``scripts.activity.timeline``);
  without ``as_of``, it runs to the month of the latest evidence day;
- ``evidence.json``: one entry per own-commit day, written by the collector::

      {"days": {"YYYY-MM-DD": {"repos": [...], "commits": n, "public": bool,
                               "files": n, "file_counts": {tech: n}, ...}}}

  ``files`` counts the analyzed files of the day, ``file_counts`` the files
  touching each collector tech;
- ``repo-classes.json``: every repository key of the evidence mapped to
  ``{"context": "pro" | "personal", "source": <timeline source id>}``.

Public inputs: ``scripts/activity/tech_map.json`` (collector tech -> catalogue
id, kind and domain of each catalogue id, excluded ids) and
``data/experiences.json`` (declared tiers, used only where no trace exists).

Rules:

1. **File share** (measured time): a tech receives the hours times the share
   of analyzed files touching it. A C# file calling a BLE API counts for both
   C# and BLE; each file has one language, so languages sum to about 1; no tech
   can exceed the hours it is allocated from.
2. **Professional time** (``timeline.pro_hours``) is split by source. A source's
   month uses the file counts summed over that source's commit days of the
   month. A month without a commit uses the source's counts over the whole
   period, restricted to techs already seen in an own commit by the end of that
   month (a carried share never predates a first commit). Study counts the
   same way.
3. **Declared periods** (``$PROFILE_PRIVATE_DIR/declared.json``, written by
   the author): a source with no trace in the period at all uses the declared
   period covering the month (``end: null`` runs to ``as_of``). ``languages``
   are explicit shares summing to 1; ``tiers`` give primary 0.70, secondary
   0.35, incident 0.10 of the hours to each other tech. Several declared
   periods covering the same month (an overlap between missions, or a
   ``within_study_budget`` project inside the study budget) share its hours
   equally. ``pro_hours_per_weekday`` overrides the context budget for those
   months (hours = weekdays x override x source share); ``timeline.py`` keeps
   its budgets, the override lives here. Hours are flagged ``declared``. Only
   when a month has neither evidence nor a declared period do the tiers of
   ``data/experiences.json`` apply (``experience_shares``, last fallback,
   reported by the CLI).
4. **Overlays** (declared): a tech gets a tier share (full 1.00, primary
   0.70, secondary 0.35, incident 0.10) of the hours of the allocation units
   in scope during listed months, flagged declared, unless the measured share
   is higher; from ``measured_from`` on, evidence only. Scope is ``personal``
   (personal commit days), ``pro`` (professional and study hours) or ``all``;
   a period may carry its own ``scope``, or a ``source`` limiting it to that
   timeline source's professional hours. A scope string may continue with a
   free-text note after its keyword (``"all (personal code and ...)"``);
   ``per period`` means every period states its own scope or source.
5. **Personal time**: each commit day on which at least one repository is
   personal counts the period's personal budget, with the day's file shares.
   A day with only professional repositories adds nothing: the calendar
   already counted it. A professional repository whose source is not a source
   of the day's period counts as personal time (the calendar did not count
   that day). Unclassified repositories are personal.
6. Per-context totals are additive; per-tech and per-domain totals are not.
   A domain gets the sum of its techs' shares, capped at 1.
7. **Levels** by convention (``LEVELS``); displayed hours are rounded down
   (``display_hours``) so a shown figure never crosses a threshold.

Usage: ``python -m scripts.activity.hours --out data/activity/aggregates.json``
"""

from __future__ import annotations

import argparse
import json
import math
import os
import pathlib
import re
import sys
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from datetime import date

from scripts.activity import timeline as tl
from scripts.claims import _ID as CLAIM_ID  # one claim id rule (ADR-014)

REPO = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_TECH_MAP = pathlib.Path(__file__).with_name("tech_map.json")
DEFAULT_EXPERIENCES = REPO / "data" / "experiences.json"
DEFAULT_CATALOGUE = REPO / "data" / "techs.json"
EVIDENCE_NAME = "evidence.json"
CLASSES_NAME = "repo-classes.json"
DECLARED_NAME = "declared.json"
DEFAULT_EVIDENCE_LEVELS = REPO / "data" / "activity" / "evidence_levels.json"
DEFAULT_CLAIMS_LOCK = REPO / "data" / "claims.lock.json"
AGGREGATES_VERSION = 2

KINDS = ("language", "platform", "domain")
TIER_WEIGHTS = {"full": 1.00, "primary": 0.70, "secondary": 0.35, "incident": 0.10}
SCOPES = ("personal", "pro", "all")
_SCOPE_RE = re.compile(r"^(personal|pro|all|per period)\b")
# Highest first; below the last threshold a tech has no level (not shown).
LEVELS = (("expert", 5000), ("advanced", 1600), ("professional", 500), ("working", 50))
CONTEXT_KEYS = ("pro", "personal", "study")

# Timeline source ids whose experiences in data/experiences.json carry another
# id. Any source absent here maps to the experience of the same id.
SOURCE_EXPERIENCES: dict[str, tuple[str, ...]] = {
    "good-angel": ("goodangel-mgl-p1", "goodangel-mgl-p2"),
    "my-good-life": ("goodangel-mgl-p1", "goodangel-mgl-p2"),
    "studies-embedded": ("studies-embedded", "robotics-cup"),
    "independent-rnd": ("freelance",),
    "freelance-client": ("freelance",),
}
# Source ids that must never be published under their private id.
PUBLIC_SOURCE_ALIASES = {"freelance-client": "client-mission"}

# First month a tech was publicly available (general availability or first
# public preview); a first use before it is a data error, never a claim.
RELEASE_MONTHS = {
    "github-actions": "2019-11",
    "xamarin-forms": "2014-05",
    "asp-net-core": "2016-06",
    "ef-core": "2016-06",
    "blazor": "2018-02",
    "maui": "2022-05",
    "claude-api": "2023-03",
}

_DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TOLERANCE = 1e-6

NOTES = (
    "Hours measure coding practice, not working time (ADR-013).",
    "Hours per context (pro, personal, study) are additive; hours per tech and "
    "per domain are not additive: a tech receives the hours times the share "
    "of analyzed files touching it, and one file may touch several techs (a C# "
    "file calling a BLE API counts for both), so no tech exceeds its period's "
    "budget.",
    "A domain's hours sum its techs' file shares, capped at the hours: a file "
    "touching two techs of one domain may count twice below that cap.",
    "display_level is the higher of hours_level and evidence_level when the "
    "evidence level's claim is attested in the claims lock, else hours_level; "
    "level_source says which one applies, claim names the attested "
    "achievement, pending_claim a claim still to attest (ADR-018).",
    "Levels are a convention: working >= 50 h, professional >= 500 h, "
    "advanced >= 1,600 h, expert >= 5,000 h. display_hours is rounded down so "
    "a shown figure never crosses a threshold the raw hours do not.",
    "declared_share is the part of a tech's hours declared by the author, for "
    "periods without any collectable commit trace (before 2014, study, a "
    "client whose commits are not collected) and for tool use that leaves no "
    "trace: declared languages share the hours explicitly; other techs get "
    "primary 0.70, secondary 0.35, incident 0.10 of the hours.",
    "Declared periods covering the same month share its hours equally (an "
    "overlap between two missions; a project inside the study budget takes "
    "half of the study hours of the months it covers).",
    "AI-assisted development before its first measurable trace is declared on "
    "personal commit days only, never on employment hours.",
    "Months of a source without a commit use that source's file counts over "
    "its period, restricted to techs already seen in an own commit by then.",
    "Git is excluded from hours: a tool every commit implies.",
    "Xamarin is measured at project level: every file of a project "
    "referencing Xamarin counts for 'xamarin', and for 'xamarin-forms' too "
    "when the project references Xamarin.Forms.",
    "tdd hours are declared only; coverage.test_only_commits counts own "
    "commits touching test files only, as evidence.",
    "The collector does not distinguish ASP.NET Core from ASP.NET Web API 2, "
    "nor EF Core from Entity Framework 6: they are reported under "
    "'asp-net-core' and 'ef-core'.",
)


# --- Tech map -------------------------------------------------------------


@dataclass(frozen=True)
class TechInfo:
    kind: str
    domain: str


@dataclass(frozen=True)
class TechMap:
    collector: dict[str, str | None]
    excluded: frozenset[str]
    techs: dict[str, TechInfo]

    def to_catalogue(self, weights: Mapping[str, float]) -> dict[str, float]:
        """Collector counts -> catalogue counts, merged, excluded ids dropped."""
        out: dict[str, float] = defaultdict(float)
        for tech, weight in weights.items():
            if tech not in self.collector:
                raise ValueError(f"unknown collector tech {tech!r}: add it to tech_map")
            target = self.collector[tech]
            if target is not None:
                out[target] += weight
        return dict(out)


def parse_tech_map(data: object) -> TechMap:
    """Validate a decoded tech map; any defect raises ValueError."""
    if not isinstance(data, dict):
        raise ValueError("tech_map: top level must be an object")
    if data.get("version") != 1:
        raise ValueError("tech_map: version must be 1")
    excluded, collector, techs = (
        data.get("excluded"),
        data.get("collector"),
        data.get("techs"),
    )
    if not isinstance(excluded, dict):
        raise ValueError("tech_map: excluded must be an object")
    if not isinstance(collector, dict):
        raise ValueError("tech_map: collector must be an object")
    if not isinstance(techs, dict):
        raise ValueError("tech_map: techs must be an object")
    infos: dict[str, TechInfo] = {}
    for tech_id, info in techs.items():
        if not isinstance(info, dict) or info.get("kind") not in KINDS:
            raise ValueError(f"tech_map: {tech_id!r} needs a kind among {KINDS}")
        if not isinstance(info.get("domain"), str) or not info["domain"]:
            raise ValueError(f"tech_map: {tech_id!r} needs a domain")
        infos[tech_id] = TechInfo(info["kind"], info["domain"])
    both = sorted(set(excluded) & set(infos))
    if both:
        raise ValueError(f"tech_map: excluded id(s) also in techs: {', '.join(both)}")
    mapping: dict[str, str | None] = {}
    for tech, target in collector.items():
        if target is None or target in excluded:
            mapping[tech] = None
        elif target in infos:
            mapping[tech] = target
        else:
            raise ValueError(f"tech_map: {tech!r} -> unknown catalogue id {target!r}")
    return TechMap(mapping, frozenset(excluded), infos)


def load_tech_map(path: str | os.PathLike[str]) -> TechMap:
    return parse_tech_map(_read_json(path))


# --- Evidence, classes, experiences ---------------------------------------


@dataclass(frozen=True)
class Day:
    day: str
    repos: tuple[str, ...]
    public: bool
    files: int
    file_counts: dict[str, int]
    test_only_commits: int = 0


@dataclass(frozen=True)
class RepoClass:
    context: str
    source: str


@dataclass(frozen=True)
class Experience:
    id: str
    start: str
    end: str | None
    tiers: dict[str, str]


def _count(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def parse_evidence(data: object) -> dict[str, Day]:
    """Validate the collector output and return its days by ISO date."""
    if not isinstance(data, dict) or not isinstance(data.get("days"), dict):
        raise ValueError("evidence: expected an object with a 'days' object")
    days: dict[str, Day] = {}
    for key, raw in data["days"].items():
        where = f"evidence day {key!r}"
        if not isinstance(key, str) or not _DAY_RE.match(key):
            raise ValueError(f"{where}: expected a YYYY-MM-DD date")
        try:
            date.fromisoformat(key)
        except ValueError as exc:
            raise ValueError(f"{where}: invalid date") from exc
        if not isinstance(raw, dict) or not isinstance(raw.get("file_counts"), dict):
            raise ValueError(f"{where}: file_counts must be an object")
        repos = raw.get("repos")
        if not isinstance(repos, list) or not all(isinstance(r, str) for r in repos):
            raise ValueError(f"{where}: repos must be a list of strings")
        files = raw.get("files")
        if not _count(files):
            raise ValueError(f"{where}: files must be a non-negative integer")
        counts = raw["file_counts"]
        for tech, count in counts.items():
            if not _count(count):
                raise ValueError(f"{where}: file count of {tech!r} must be an integer")
            if count > files:
                raise ValueError(f"{where}: file count of {tech!r} exceeds files")
        test_only = raw.get("test_only_commits", 0)
        if not _count(test_only):
            raise ValueError(f"{where}: test_only_commits must be an integer")
        days[key] = Day(
            key, tuple(repos), bool(raw.get("public")), files, counts, test_only
        )
    return days


def parse_repo_classes(data: object) -> dict[str, RepoClass]:
    if not isinstance(data, dict):
        raise ValueError("repo-classes: top level must be an object")
    classes: dict[str, RepoClass] = {}
    for key, raw in data.items():
        if not isinstance(raw, dict):
            raise ValueError(f"repo-classes: {key!r} must be an object")
        context, source = raw.get("context"), raw.get("source")
        if context not in ("pro", "personal"):
            raise ValueError(f"repo-classes: {key!r} context must be pro|personal")
        if not isinstance(source, str) or not source:
            raise ValueError(f"repo-classes: {key!r} needs a source")
        classes[key] = RepoClass(context, source)
    return classes


def parse_experiences(data: object) -> dict[str, Experience]:
    if not isinstance(data, list):
        raise ValueError("experiences: top level must be a list")
    out: dict[str, Experience] = {}
    for raw in data:
        if not isinstance(raw, dict):
            raise ValueError("experiences: each entry must be an object")
        tiers = raw.get("tech_weights")
        if not isinstance(tiers, dict):
            raise ValueError(f"experiences: {raw.get('id')!r} needs tech_weights")
        for tech, tier in tiers.items():
            if tier not in TIER_WEIGHTS:
                raise ValueError(f"experiences: unknown tier {tier!r} for {tech!r}")
        out[raw["id"]] = Experience(raw["id"], raw["start"], raw.get("end"), tiers)
    return out


def experiences_for(source_id: str) -> tuple[str, ...]:
    """Experience ids of ``data/experiences.json`` behind a timeline source."""
    return SOURCE_EXPERIENCES.get(source_id, (source_id,))


def public_source(source_id: str) -> str:
    """The id a source may be published under."""
    return PUBLIC_SOURCE_ALIASES.get(source_id, source_id)


def experience_shares(
    experience_ids: Iterable[str],
    month: str,
    experiences: Mapping[str, Experience],
    tech_map: TechMap,
) -> dict[str, float]:
    """Declared tiers of the experiences active in ``month``, as file shares.

    A tier is the assumed share of the hours (``TIER_WEIGHTS``); declared
    languages share 100 % pro rata of their tiers, since each file has one
    language. Tiers of several active experiences add up, capped at 1. When
    none of the mapped experiences covers the month, all of them count.
    Excluded ids (git) are dropped.
    """
    mapped = [experiences[e] for e in experience_ids if e in experiences]
    index = tl._index(month)
    active = [
        e
        for e in mapped
        if tl._index(e.start) <= index and (e.end is None or index <= tl._index(e.end))
    ]
    tiers: dict[str, float] = defaultdict(float)
    for exp in active or mapped:
        for tech, tier in exp.tiers.items():
            if tech not in tech_map.excluded:
                tiers[tech] += TIER_WEIGHTS[tier]
    languages = math.fsum(
        w for t, w in tiers.items() if tech_map.techs[t].kind == "language"
    )
    return {
        tech: weight / languages
        if tech_map.techs[tech].kind == "language"
        else min(weight, 1.0)
        for tech, weight in tiers.items()
    }


# --- Declared periods --------------------------------------------------------


@dataclass(frozen=True)
class DeclaredPeriod:
    source: str
    start: str
    end: str | None
    languages: dict[str, float]
    tiers: dict[str, str]
    pro_hours_per_weekday: float | None = None
    within_study_budget: bool = False

    def covers(self, month: str) -> bool:
        index = tl._index(month)
        return tl._index(self.start) <= index and (
            self.end is None or index <= tl._index(self.end)
        )

    def shares(self) -> dict[str, float]:
        """Declared languages as-is, plus each tier's share (at most 1)."""
        out = dict(self.languages)
        for tech, tier in self.tiers.items():
            out[tech] = min(out.get(tech, 0.0) + TIER_WEIGHTS[tier], 1.0)
        return out


@dataclass(frozen=True)
class OverlayPeriod:
    start: str
    end: str | None
    tier: str
    scope: str  # personal | pro | all
    source: str | None = None  # pro hours of this timeline source only

    def applies(self, unit: Unit) -> bool:
        index = tl._index(unit.month)
        if index < tl._index(self.start) or (
            self.end is not None and index > tl._index(self.end)
        ):
            return False
        if self.source is not None and unit.source != self.source:
            return False
        if self.scope == "personal":
            return unit.kind == "personal"
        if self.scope == "pro":
            return unit.kind != "personal"
        return True


@dataclass(frozen=True)
class Overlay:
    tech: str
    periods: tuple[OverlayPeriod, ...]
    measured_from: str | None = None

    def share_for(self, unit: Unit) -> float:
        """The declared share this overlay gives ``unit`` (0 when none)."""
        if self.measured_from is not None and unit.month >= self.measured_from:
            return 0.0
        return max(
            (TIER_WEIGHTS[p.tier] for p in self.periods if p.applies(unit)),
            default=0.0,
        )


@dataclass(frozen=True)
class Declared:
    periods: tuple[DeclaredPeriod, ...]
    overlays: tuple[Overlay, ...]
    evidence_levels: dict[str, str] = field(default_factory=dict)

    def for_month(self, source: str, month: str, as_of: str) -> list[DeclaredPeriod]:
        del as_of  # an open end runs to the timeline's end, which bounds months
        return [p for p in self.periods if p.source == source and p.covers(month)]

    def apply_overlays(self, unit: Unit) -> Unit:
        """``unit`` with each overlay's share where it beats the measured one."""
        shares, declared = dict(unit.shares), set(unit.declared)
        for overlay in self.overlays:
            share = overlay.share_for(unit)
            if share > shares.get(overlay.tech, 0.0):
                shares[overlay.tech] = min(share, 1.0)
                declared.add(overlay.tech)
        if declared == set(unit.declared):
            return unit
        return replace(unit, shares=shares, declared=frozenset(declared))


def _month(value: object, where: str) -> str:
    try:
        tl.parse_month(value)
    except ValueError as exc:
        raise ValueError(f"{where}: {exc} (expected YYYY-MM)") from exc
    return str(value)


def _known(tech: str, tech_map: TechMap, where: str) -> str:
    if tech not in tech_map.techs and tech not in tech_map.excluded:
        raise ValueError(f"{where}: unknown tech {tech!r}: add it to tech_map")
    return tech


def _tier(tier: object, where: str) -> str:
    if tier not in TIER_WEIGHTS:
        raise ValueError(f"{where}: unknown tier {tier!r}")
    return str(tier)


def _parse_declared_period(raw: object, tech_map: TechMap) -> DeclaredPeriod:
    if not isinstance(raw, dict):
        raise ValueError("declared: each period must be an object")
    source = raw.get("source")
    if not isinstance(source, str) or not source:
        raise ValueError("declared: a period needs a source")
    where = f"declared {source} {raw.get('start')}"
    start = _month(raw.get("start"), where)
    end = raw.get("end")
    if end is not None and tl._index(_month(end, where)) < tl._index(start):
        raise ValueError(f"{where}: end is before start")
    languages, tiers = raw.get("languages", {}), raw.get("tiers", {})
    if not isinstance(languages, dict) or not isinstance(tiers, dict):
        raise ValueError(f"{where}: languages and tiers must be objects")
    for tech in [*languages, *tiers]:
        _known(tech, tech_map, where)
    if languages and abs(math.fsum(languages.values()) - 1.0) > _TOLERANCE:
        raise ValueError(f"{where}: language shares must sum to 1")
    for tier in tiers.values():
        _tier(tier, where)
    override = raw.get("pro_hours_per_weekday")
    if override is not None and not (
        isinstance(override, int | float) and 0 < override <= tl.AVAILABLE_HOURS_PER_DAY
    ):
        raise ValueError(f"{where}: pro_hours_per_weekday must be in (0, 11]")
    excluded = tech_map.excluded
    return DeclaredPeriod(
        source=source,
        start=start,
        end=end,
        languages={t: float(v) for t, v in languages.items() if t not in excluded},
        tiers={t: v for t, v in tiers.items() if t not in excluded},
        pro_hours_per_weekday=override,
        within_study_budget=bool(raw.get("within_study_budget", False)),
    )


def _scope(value: object, where: str) -> str:
    match = _SCOPE_RE.match(value) if isinstance(value, str) else None
    if match is None:
        raise ValueError(
            f"{where}: scope must start with personal, pro, all or 'per period'"
        )
    return match.group(1)


def _parse_overlay(raw: object, tech_map: TechMap) -> Overlay:
    if not isinstance(raw, dict):
        raise ValueError("declared: each overlay must be an object")
    tech = _known(str(raw.get("tech")), tech_map, "declared overlay")
    where = f"declared overlay {tech}"
    default = raw.get("scope")
    periods = []
    for p in raw.get("periods", []):
        start = _month(p.get("start"), where)
        end = None if p.get("end") is None else _month(p.get("end"), where)
        tier = _tier(p.get("tier"), where)
        source = p.get("source")
        if "scope" in p:
            scope = _scope(p["scope"], where)
        elif source is not None:
            scope = "pro"
        else:
            scope = _scope(default, where)
        if scope == "per period":
            raise ValueError(f"{where}: a period needs its own scope or source")
        if source is not None and scope != "pro":
            raise ValueError(f"{where}: a source limits pro hours only")
        periods.append(OverlayPeriod(start, end, tier, scope, source))
    measured = raw.get("measured_from")
    return Overlay(
        tech, tuple(periods), None if measured is None else _month(measured, where)
    )


def parse_declared(data: object, tech_map: TechMap) -> Declared:
    """Validate the author's declared periods and overlays."""
    if not isinstance(data, dict):
        raise ValueError("declared: top level must be an object")
    if data.get("version") != 1:
        raise ValueError("declared: version must be 1")
    periods, overlays = data.get("periods"), data.get("overlays", [])
    if not isinstance(periods, list):
        raise ValueError("declared: periods must be a list")
    if not isinstance(overlays, list):
        raise ValueError("declared: overlays must be a list")
    raw_levels = data.get("evidence_levels", {})
    if not isinstance(raw_levels, dict):
        raise ValueError("declared: evidence_levels must be an object")
    evidence: dict[str, str] = {}
    for tech, entry in raw_levels.items():
        if not isinstance(entry, dict) or level_rank(entry.get("level")) == 0:
            raise ValueError(f"declared: evidence_levels.{tech} needs a known level")
        evidence[_known(tech, tech_map, "declared evidence_levels")] = entry["level"]
    return Declared(
        tuple(_parse_declared_period(p, tech_map) for p in periods),
        tuple(_parse_overlay(o, tech_map) for o in overlays),
        evidence,
    )


# --- File shares ---------------------------------------------------------------


def shares_from(files: int, counts: Mapping[str, float]) -> dict[str, float]:
    """Share of the analyzed files touching each tech (at most 1)."""
    if files <= 0:
        return {}
    return {t: min(c / files, 1.0) for t, c in counts.items() if c > 0}


def allocate(hours: float, shares: Mapping[str, float]) -> dict[str, float]:
    """Hours per tech: the hours times the tech's file share."""
    return {t: hours * s for t, s in shares.items() if s > 0}


def domain_hours(
    hours: float, shares: Mapping[str, float], tech_map: TechMap
) -> dict[str, float]:
    """Hours per domain: its techs' shares summed, capped at the hours."""
    per_domain: dict[str, float] = defaultdict(float)
    for tech, share in shares.items():
        if share > 0:
            per_domain[tech_map.techs[tech].domain] += share
    return {d: hours * min(share, 1.0) for d, share in per_domain.items()}


# --- Levels ------------------------------------------------------------------


def level_rank(level: object) -> int:
    """0 for no level, then working < professional < advanced < expert."""
    names = [name for name, _ in reversed(LEVELS)]
    return names.index(level) + 1 if level in names else 0


@dataclass(frozen=True)
class EvidenceLevel:
    """A level granted by an attested achievement (ADR-018)."""

    level: str
    claim: str


def parse_evidence_levels(data: object, tech_map: TechMap) -> dict[str, EvidenceLevel]:
    """Validate ``data/activity/evidence_levels.json``: level and claim id only."""
    if not isinstance(data, dict):
        raise ValueError("evidence_levels: top level must be an object")
    if data.get("version") != 1:
        raise ValueError("evidence_levels: version must be 1")
    levels = data.get("levels")
    if not isinstance(levels, dict):
        raise ValueError("evidence_levels: levels must be an object")
    out: dict[str, EvidenceLevel] = {}
    for tech, entry in levels.items():
        where = f"evidence_levels.{tech}"
        _known(tech, tech_map, where)
        if not isinstance(entry, dict) or set(entry) != {"level", "claim"}:
            raise ValueError(f"{where}: keys must be exactly level and claim")
        if level_rank(entry["level"]) == 0:
            raise ValueError(f"{where}: unknown level {entry['level']!r}")
        claim = entry["claim"]
        if not isinstance(claim, str) or not CLAIM_ID.fullmatch(claim):
            raise ValueError(f"{where}: claim must be a kebab-case id")
        out[tech] = EvidenceLevel(entry["level"], claim)
    return out


def evidence_mismatches(
    levels: Mapping[str, EvidenceLevel], declared: Declared
) -> list[str]:
    """Committed evidence levels that differ from the author's declaration."""
    issues = []
    for tech in sorted(set(levels) | set(declared.evidence_levels)):
        committed = levels[tech].level if tech in levels else "none"
        stated = declared.evidence_levels.get(tech, "none")
        if committed != stated:
            issues.append(
                f"evidence level of {tech}: committed {committed}, declared {stated}"
            )
    return issues


def level_for(hours: float) -> str | None:
    for name, threshold in LEVELS:
        if hours >= threshold:
            return name
    return None


def display_hours(hours: float) -> int:
    """Round down: to 10 below 1,000, to 100 below 10,000, then to 1,000."""
    step = 10 if hours < 1000 else 100 if hours < 10000 else 1000
    return int(hours // step * step)


# --- Allocation units --------------------------------------------------------


@dataclass(frozen=True)
class Unit:
    """Hours of one month and one context kind, with their tech file shares."""

    month: str
    kind: str  # "pro" | "personal" | "study"
    hours: float
    shares: dict[str, float]
    declared: frozenset[str]  # techs whose share was declared, not measured
    period: int
    fallback: str | None = None  # source id when experiences.json tiers apply
    source: str | None = None  # timeline source of professional/study hours


@dataclass
class Inputs:
    timeline: tl.Timeline
    days: dict[str, Day]
    classes: dict[str, RepoClass]
    tech_map: TechMap
    experiences: dict[str, Experience]
    declared: Declared = field(default_factory=lambda: Declared((), ()))
    catalogue_counts: dict[str, dict[str, float]] = field(default_factory=dict)

    def counts_of(self, day: str) -> dict[str, float]:
        """File counts of ``day`` per catalogue id."""
        if day not in self.catalogue_counts:
            self.catalogue_counts[day] = self.tech_map.to_catalogue(
                self.days[day].file_counts
            )
        return self.catalogue_counts[day]

    def shares_of(self, days: Iterable[str]) -> dict[str, float]:
        """File shares over several days: counts and files summed first."""
        days = list(days)
        files = sum(self.days[d].files for d in days)
        return shares_from(files, _sum(self.counts_of(d) for d in days))


def _period_index(timeline: tl.Timeline, month: str) -> int:
    index = tl._index(month)
    for i, period in enumerate(timeline.periods):
        if tl._index(period.start) <= index <= tl._index(period.end):
            return i
    raise ValueError(f"evidence day in {month} is outside the timeline")


def _sum(dicts: Iterable[Mapping[str, float]]) -> dict[str, float]:
    out: dict[str, float] = defaultdict(float)
    for weights in dicts:
        for tech, weight in weights.items():
            out[tech] += weight
    return dict(out)


def first_seen(inputs: Inputs) -> dict[str, str]:
    """First month each catalogue tech touches a file in an own commit."""
    seen: dict[str, str] = {}
    for day in sorted(inputs.days):
        for tech, count in inputs.counts_of(day).items():
            if count > 0:
                seen.setdefault(tech, day[:7])
    return seen


def build_units(inputs: Inputs) -> list[Unit]:
    """Every allocation unit of the timeline: pro/study by month and source,
    personal by commit day."""
    timeline, classes = inputs.timeline, inputs.classes
    # Commit days of each (period, source) and personal commit days by period.
    source_days: dict[tuple[int, str], list[str]] = defaultdict(list)
    personal_days: list[tuple[int, str]] = []
    for day in sorted(inputs.days):
        index = _period_index(timeline, day[:7])
        period_sources = {s.id for s in timeline.periods[index].sources}
        personal = False
        for repo in inputs.days[day].repos:
            cls = classes.get(repo)
            if cls and cls.context == "pro" and cls.source in period_sources:
                source_days[(index, cls.source)].append(day)
            else:
                personal = True
        if personal:
            personal_days.append((index, day))

    seen = first_seen(inputs)
    units: list[Unit] = []
    for index, period in enumerate(timeline.periods):
        kind = "study" if period.context == "study" else "pro"
        for source in period.sources:
            traced = [
                d for d in source_days[(index, source.id)] if inputs.days[d].files
            ]
            whole = inputs.shares_of(traced)
            for month in tl.month_range(period.start, period.end):
                hours = tl.pro_hours(period, month)[source.id]
                if not traced:
                    units.extend(
                        _untraced_units(inputs, month, kind, hours, source, index)
                    )
                    continue
                if hours <= 0:
                    continue
                in_month = [d for d in traced if d[:7] == month]
                if in_month:
                    shares = inputs.shares_of(in_month)
                else:
                    shares = {t: v for t, v in whole.items() if seen[t] <= month}
                units.append(
                    Unit(
                        month, kind, hours, shares, frozenset(), index, None, source.id
                    )
                )

    for index, day in personal_days:
        budget = tl.budget_for(timeline.periods[index].context)
        hours = tl.personal_hours(budget, [date.fromisoformat(day)])
        if hours > 0:
            shares = inputs.shares_of([day])
            units.append(Unit(day[:7], "personal", hours, shares, frozenset(), index))
    return [inputs.declared.apply_overlays(unit) for unit in units]


def _untraced_units(
    inputs: Inputs, month: str, kind: str, hours: float, source: tl.Source, index: int
) -> list[Unit]:
    """Units of a source month without any trace: declared, else experiences."""
    declared = inputs.declared.for_month(source.id, month, inputs.timeline.as_of)
    units = []
    for period in declared:
        if period.pro_hours_per_weekday is not None:
            share = tl.weekdays_in_month(month) * period.pro_hours_per_weekday
            part = share * source.share / len(declared)
        else:
            part = hours / len(declared)
        if part > 0:
            shares = period.shares()
            units.append(
                Unit(
                    month, kind, part, shares, frozenset(shares), index, None, source.id
                )
            )
    if declared or hours <= 0:
        return units
    shares = experience_shares(
        experiences_for(source.id), month, inputs.experiences, inputs.tech_map
    )
    return [
        Unit(month, kind, hours, shares, frozenset(shares), index, source.id, source.id)
    ]


def allocations(units: list[Unit]) -> list[dict[str, float]]:
    return [allocate(u.hours, u.shares) for u in units]


# --- Aggregation -------------------------------------------------------------


def _r(value: float, digits: int = 2) -> float:
    rounded = round(value, digits)
    return 0.0 if rounded == 0 else rounded


def domain_differences(tech_map: TechMap, catalogue: list[dict]) -> list[str]:
    """Catalogue ids whose domain here differs from data/techs.json."""
    diffs = []
    for tech in sorted(catalogue, key=lambda t: t["id"]):
        info = tech_map.techs.get(tech["id"])
        if info and info.domain != tech.get("domain"):
            diffs.append(f"{tech['id']}: {tech.get('domain')} -> {info.domain}")
    return diffs


def _levels(
    hours_level: str | None, evidence: EvidenceLevel | None, attested: set[str]
) -> dict:
    """Hours level, evidence level, and the level shown (ADR-018).

    An evidence level lifts the shown level only when its claim is attested
    (present in the claims lock); otherwise it grants nothing and its claim is
    reported as ``pending_claim``.
    """
    evidence_level = evidence.level if evidence else None
    higher = level_rank(evidence_level) > level_rank(hours_level)
    lifted = higher and evidence.claim in attested
    return {
        "hours_level": hours_level,
        "evidence_level": evidence_level,
        "display_level": evidence_level if lifted else hours_level,
        "level_source": "evidence" if lifted else "hours",
        "claim": evidence.claim if lifted else None,
        "pending_claim": evidence.claim if higher and not lifted else None,
    }


def aggregate(
    inputs: Inputs,
    catalogue: list[dict],
    evidence_levels: Mapping[str, EvidenceLevel] | None = None,
    attested: set[str] | None = None,
) -> dict:
    """The committed aggregates document (deterministic, no private names)."""
    tech_map = inputs.tech_map
    units = build_units(inputs)
    allocs = allocations(units)

    context: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    month_techs: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    month_domains: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    tech_hours: dict[str, list[float]] = defaultdict(list)
    tech_declared: dict[str, list[float]] = defaultdict(list)
    tech_months: dict[str, list[str]] = defaultdict(list)
    for unit, alloc in zip(units, allocs, strict=True):
        context[unit.month][unit.kind].append(unit.hours)
        for tech, hours in alloc.items():
            month_techs[unit.month][tech].append(hours)
            tech_hours[tech].append(hours)
            tech_months[tech].append(unit.month)
            if tech in unit.declared:
                tech_declared[tech].append(hours)
        for domain, hours in domain_hours(unit.hours, unit.shares, tech_map).items():
            month_domains[unit.month][domain].append(hours)

    by_month = {}
    for month in sorted(context):
        by_month[month] = {
            "context": {k: _r(math.fsum(context[month][k])) for k in CONTEXT_KEYS},
            "techs": {t: _r(math.fsum(v)) for t, v in month_techs[month].items()},
            "domains": {d: _r(math.fsum(v)) for d, v in month_domains[month].items()},
        }

    techs = {}
    for tech, parts in tech_hours.items():
        total = math.fsum(parts)
        info = tech_map.techs[tech]
        techs[tech] = {
            "hours": _r(total, 1),
            "display_hours": display_hours(total),
            **_levels(
                level_for(total), (evidence_levels or {}).get(tech), attested or set()
            ),
            "first": min(tech_months[tech]),
            "last": max(tech_months[tech]),
            "declared_share": _r(math.fsum(tech_declared[tech]) / total, 3),
            "kind": info.kind,
            "domain": info.domain,
        }

    days = inputs.days
    public = sum(1 for d in days.values() if d.public)
    diffs = domain_differences(tech_map, catalogue)
    notes = list(NOTES)
    if diffs:
        notes.append("Domains that differ from data/techs.json: " + "; ".join(diffs))
    return {
        # Version 2 (ADR-018): per-tech "level" became hours_level,
        # evidence_level, display_level, level_source, claim, pending_claim.
        "version": AGGREGATES_VERSION,
        "activity_as_of": max(days) if days else inputs.timeline.as_of,
        "coverage": {
            "commit_days": len(days),
            "public_days": public,
            "public_share": _r(public / len(days), 4) if days else 0.0,
            "test_only_commits": sum(d.test_only_commits for d in days.values()),
        },
        "context_totals": {
            k: _r(math.fsum(math.fsum(context[m][k]) for m in context))
            for k in CONTEXT_KEYS
        },
        "levels": {name: threshold for name, threshold in LEVELS},
        "by_month": by_month,
        "techs": techs,
        "notes": notes,
    }


# --- Sanity checks -----------------------------------------------------------


def sanity_checks(
    doc: dict,
    units: list[Unit],
    inputs: Inputs,
    allocations: list[dict[str, float]] | None = None,
) -> list[str]:
    """ADR-013 success criteria: first use and period budgets."""
    allocs = allocations or [allocate(u.hours, u.shares) for u in units]
    issues: list[str] = []
    seen = first_seen(inputs)
    earliest_estimate: dict[str, str] = {}
    for unit in units:
        for tech in unit.declared:
            share = unit.shares.get(tech, 0)
            if share > 0 and unit.month < earliest_estimate.get(tech, "9999-99"):
                earliest_estimate[tech] = unit.month
    for tech, entry in sorted(doc["techs"].items()):
        bound = min(seen.get(tech, "9999-99"), earliest_estimate.get(tech, "9999-99"))
        if entry["first"] < bound:
            issues.append(
                f"{tech}: first use {entry['first']} before its first commit or "
                f"declared period ({bound})"
            )
        release = RELEASE_MONTHS.get(tech)
        if release and entry["first"] < release:
            issues.append(
                f"{tech}: first use {entry['first']} before its release {release}"
            )

    budgets: dict[int, float] = defaultdict(float)
    used: dict[tuple[int, str], float] = defaultdict(float)
    for unit, alloc in zip(units, allocs, strict=True):
        budgets[unit.period] += unit.hours
        for tech, hours in alloc.items():
            used[(unit.period, tech)] += hours
    for (period, tech), hours in sorted(used.items()):
        if hours > budgets[period] + _TOLERANCE:
            issues.append(
                f"{tech}: {hours:.1f} h exceeds the budget {budgets[period]:.1f} h "
                f"of period #{period + 1}"
            )
    return issues


# --- CLI -----------------------------------------------------------------------


def _read_json(path: str | os.PathLike[str]) -> object:
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def dumps(doc: dict) -> str:
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _summary(doc: dict, inputs: Inputs, issues: list[str]) -> str:
    totals = doc["context_totals"]
    unallocated = math.fsum(
        u.hours for u in build_units(inputs) if not allocate(u.hours, u.shares)
    )
    repos = {r for d in inputs.days.values() for r in d.repos}
    unclassified = sum(1 for r in repos if r not in inputs.classes)
    lines = [
        "context hours: "
        + "  ".join(f"{k}={totals[k]:.0f}" for k in CONTEXT_KEYS)
        + f"  (unallocated to any tech: {unallocated:.0f})",
        f"coverage: {doc['coverage']}  activity_as_of={doc['activity_as_of']}",
        f"unclassified repositories: {unclassified}",
        f"{'tech':<24}{'hours':>9}{'shown':>8}  {'level':<13}"
        f"{'first':<9}{'last':<9}declared",
    ]
    ranked = sorted(doc["techs"].items(), key=lambda kv: (-kv[1]["hours"], kv[0]))
    for tech, entry in ranked[:25]:
        lines.append(
            f"{tech:<24}{entry['hours']:>9.0f}{entry['display_hours']:>8}  "
            f"{entry['display_level'] or '-':<13}{entry['first']:<9}{entry['last']:<9}"
            f"{entry['declared_share']:.0%}"
        )
    for unit in build_units(inputs):
        if unit.fallback:
            lines.append(
                f"experience fallback: {unit.fallback} {unit.month} {unit.hours:.1f} h"
            )
    lines.append("sanity: OK" if not issues else f"sanity: {len(issues)} issue(s)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.activity.hours",
        description="Aggregate coding hours per month, tech and domain.",
    )
    parser.add_argument("--out", required=True, help="aggregates file to write")
    parser.add_argument("--tech-map", default=str(DEFAULT_TECH_MAP))
    parser.add_argument("--experiences", default=str(DEFAULT_EXPERIENCES))
    parser.add_argument("--catalogue", default=str(DEFAULT_CATALOGUE))
    parser.add_argument("--evidence-levels", default=str(DEFAULT_EVIDENCE_LEVELS))
    parser.add_argument("--claims-lock", default=str(DEFAULT_CLAIMS_LOCK))
    args = parser.parse_args(argv)

    directory = os.environ.get(tl.PRIVATE_DIR_ENV)
    if not directory:
        print(f"error: {tl.PRIVATE_DIR_ENV} is not set", file=sys.stderr)
        return 2
    private = pathlib.Path(directory)
    try:
        days = parse_evidence(_read_json(private / EVIDENCE_NAME))
        # A timeline without as_of runs to the month of the latest evidence
        # day: the collection, not the clock, dates the aggregates.
        latest = max(days)[:7] if days else None
        inputs = Inputs(
            timeline=tl.load_timeline(private / tl.PRIVATE_TIMELINE_NAME, latest),
            days=days,
            classes=parse_repo_classes(_read_json(private / CLASSES_NAME)),
            tech_map=load_tech_map(args.tech_map),
            experiences=parse_experiences(_read_json(args.experiences)),
        )
        inputs.declared = parse_declared(
            _read_json(private / DECLARED_NAME), inputs.tech_map
        )
        catalogue = _read_json(args.catalogue)
        levels = parse_evidence_levels(
            _read_json(args.evidence_levels), inputs.tech_map
        )
        locked = set(_read_json(args.claims_lock).get("claims", {}))
        doc = aggregate(
            inputs, catalogue=catalogue, evidence_levels=levels, attested=locked
        )
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    issues = sanity_checks(doc, build_units(inputs), inputs)
    issues += evidence_mismatches(levels, inputs.declared)
    print(_summary(doc, inputs, issues))
    pending = sorted({e["pending_claim"] for e in doc["techs"].values()} - {None})
    if pending:
        print(f"claims not yet in the lock: {', '.join(pending)}")
    unmeasured = sorted(set(levels) - set(doc["techs"]))
    if unmeasured:
        print(f"evidence levels without hours: {', '.join(unmeasured)}")
    if issues:
        for issue in issues:
            print(f"sanity: {issue}", file=sys.stderr)
        return 1
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(dumps(doc), encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
