"""Hours aggregates from the activity timeline and commit evidence (ADR-013).

Inputs (private, read from ``$PROFILE_PRIVATE_DIR``, never committed):

- ``timeline.json``: the continuous timeline (``scripts.activity.timeline``);
- ``evidence.json``: one entry per own-commit day, written by the collector::

      {"days": {"YYYY-MM-DD": {"repos": [...], "commits": n, "public": bool,
                               "techs": {collector_tech: weight}, ...}}}

- ``repo-classes.json``: every repository key of the evidence mapped to
  ``{"context": "pro" | "personal", "source": <timeline source id>}``.

Public inputs: ``scripts/activity/tech_map.json`` (collector tech -> catalogue
id, layer and domain of each catalogue id, excluded ids) and
``data/experiences.json`` (declared tiers, used only where no trace exists).

Rules:

1. **Professional time** (``timeline.pro_hours``) is split by source. A source's
   month is allocated with the tech weights of that source's commit days in the
   month. A month without a commit carries the source's weights over the whole
   period, restricted to techs already seen in an own commit by the end of that
   month (a carried weight never predates a first commit); when nothing is
   left, the hours count for the context but no tech. A source with no trace in
   the period at all is allocated from the declared tiers of its experiences
   (``TIER_WEIGHTS``) and flagged ``estimated``. Study counts the same way.
2. **Personal time**: each commit day on which at least one repository is
   personal counts the period's personal budget, allocated with the day's
   weights. A day with only professional repositories adds nothing: the
   calendar already counted it. A professional repository whose source is not
   a source of the day's period counts as personal time (the calendar did not
   count that day). Unclassified repositories are personal.
3. **Overlap**: catalogue ids are grouped into layers (language, platform,
   domain). Within a layer, the weights are normalized to 1 and share the
   hours; across layers the same hour counts once per layer. No tech can
   exceed its period's budget; per-context totals are additive, per-tech
   totals are not. A domain gets, per allocation, the largest share any one
   layer gives its techs (a lower bound of their union, never a sum).
4. **Levels** by convention (``LEVELS``); displayed hours are rounded down
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
from dataclasses import dataclass, field
from datetime import date

from scripts.activity import timeline as tl

REPO = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_TECH_MAP = pathlib.Path(__file__).with_name("tech_map.json")
DEFAULT_EXPERIENCES = REPO / "data" / "experiences.json"
DEFAULT_CATALOGUE = REPO / "data" / "techs.json"
EVIDENCE_NAME = "evidence.json"
CLASSES_NAME = "repo-classes.json"

LAYERS = ("language", "platform", "domain")
TIER_WEIGHTS = {"primary": 0.70, "secondary": 0.35, "incident": 0.10}
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
    "per domain are not additive: one hour counts once in each layer "
    "(language, platform, domain), so no tech exceeds its period's budget.",
    "A domain's hours are, per allocation, the largest share any one layer "
    "gives its techs: a lower bound, never a sum across layers.",
    "Levels are a convention: working >= 50 h, professional >= 500 h, "
    "advanced >= 1,600 h, expert >= 5,000 h. display_hours is rounded down so "
    "a shown figure never crosses a threshold the raw hours do not.",
    "estimated_share is the part of a tech's hours allocated from declared "
    "tiers, for periods without any commit trace (before 2014, study, a source "
    "without commits).",
    "Months of a source without a commit carry that source's weights over its "
    "period, restricted to techs already seen in an own commit by then.",
    "Git is excluded from hours: a tool every commit implies.",
    "The collector does not distinguish native Xamarin from Xamarin.Forms: "
    "measured Xamarin hours are reported under 'xamarin'.",
    "The collector does not distinguish ASP.NET Core from ASP.NET Web API 2, "
    "nor EF Core from Entity Framework 6: they are reported under "
    "'asp-net-core' and 'ef-core'.",
)


# --- Tech map -------------------------------------------------------------


@dataclass(frozen=True)
class TechInfo:
    layer: str
    domain: str


@dataclass(frozen=True)
class TechMap:
    collector: dict[str, str | None]
    excluded: frozenset[str]
    techs: dict[str, TechInfo]

    def to_catalogue(self, weights: Mapping[str, float]) -> dict[str, float]:
        """Collector weights -> catalogue weights, merged, excluded ids dropped."""
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
        if not isinstance(info, dict) or info.get("layer") not in LAYERS:
            raise ValueError(f"tech_map: {tech_id!r} needs a layer among {LAYERS}")
        if not isinstance(info.get("domain"), str) or not info["domain"]:
            raise ValueError(f"tech_map: {tech_id!r} needs a domain")
        infos[tech_id] = TechInfo(info["layer"], info["domain"])
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
    techs: dict[str, float]


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
        if not isinstance(raw, dict) or not isinstance(raw.get("techs"), dict):
            raise ValueError(f"{where}: techs must be an object")
        repos = raw.get("repos")
        if not isinstance(repos, list) or not all(isinstance(r, str) for r in repos):
            raise ValueError(f"{where}: repos must be a list of strings")
        techs = raw["techs"]
        for tech, weight in techs.items():
            if isinstance(weight, bool) or not isinstance(weight, int | float):
                raise ValueError(f"{where}: weight of {tech!r} must be a number")
            if weight < 0:
                raise ValueError(f"{where}: weight of {tech!r} is negative")
        days[key] = Day(key, tuple(repos), bool(raw.get("public")), dict(techs))
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


def tier_weights(
    experience_ids: Iterable[str],
    month: str,
    experiences: Mapping[str, Experience],
    tech_map: TechMap,
) -> dict[str, float]:
    """Declared tiers of the experiences active in ``month``, as weights.

    When none of the mapped experiences covers the month, all of them count.
    Excluded ids (git) are dropped.
    """
    mapped = [experiences[e] for e in experience_ids if e in experiences]
    index = tl._index(month)
    active = [
        e
        for e in mapped
        if tl._index(e.start) <= index and (e.end is None or index <= tl._index(e.end))
    ]
    weights: dict[str, float] = defaultdict(float)
    for exp in active or mapped:
        for tech, tier in exp.tiers.items():
            if tech not in tech_map.excluded:
                weights[tech] += TIER_WEIGHTS[tier]
    return dict(weights)


# --- Overlap rule ----------------------------------------------------------


def _layer_shares(
    weights: Mapping[str, float], tech_map: TechMap
) -> dict[str, dict[str, float]]:
    layers: dict[str, dict[str, float]] = defaultdict(dict)
    for tech, weight in weights.items():
        if weight > 0:
            layers[tech_map.techs[tech].layer][tech] = weight
    shares: dict[str, dict[str, float]] = {}
    for layer, members in layers.items():
        total = math.fsum(members.values())
        shares[layer] = {t: w / total for t, w in members.items()}
    return shares


def allocate(
    hours: float, weights: Mapping[str, float], tech_map: TechMap
) -> dict[str, float]:
    """Split ``hours`` across techs, once per layer (ADR-013 section 4)."""
    out: dict[str, float] = {}
    for members in _layer_shares(weights, tech_map).values():
        for tech, share in members.items():
            out[tech] = hours * share
    return out


def domain_hours(
    hours: float, weights: Mapping[str, float], tech_map: TechMap
) -> dict[str, float]:
    """Hours per domain: the largest share any one layer gives the domain."""
    best: dict[str, float] = {}
    for members in _layer_shares(weights, tech_map).values():
        per_domain: dict[str, float] = defaultdict(float)
        for tech, share in members.items():
            per_domain[tech_map.techs[tech].domain] += share
        for domain, share in per_domain.items():
            best[domain] = max(best.get(domain, 0.0), share)
    return {d: hours * min(share, 1.0) for d, share in best.items()}


# --- Levels ------------------------------------------------------------------


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
    """Hours of one month and one context kind, with their tech weights."""

    month: str
    kind: str  # "pro" | "personal" | "study"
    hours: float
    weights: dict[str, float]
    estimated: bool
    period: int


@dataclass
class Inputs:
    timeline: tl.Timeline
    days: dict[str, Day]
    classes: dict[str, RepoClass]
    tech_map: TechMap
    experiences: dict[str, Experience]
    catalogue_weights: dict[str, dict[str, float]] = field(default_factory=dict)

    def weights_of(self, day: str) -> dict[str, float]:
        if day not in self.catalogue_weights:
            self.catalogue_weights[day] = self.tech_map.to_catalogue(
                self.days[day].techs
            )
        return self.catalogue_weights[day]


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
    """First month each catalogue tech has a positive weight in an own commit."""
    seen: dict[str, str] = {}
    for day in sorted(inputs.days):
        for tech, weight in inputs.weights_of(day).items():
            if weight > 0:
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
                d for d in source_days[(index, source.id)] if inputs.weights_of(d)
            ]
            whole = _sum(inputs.weights_of(d) for d in traced)
            for month in tl.month_range(period.start, period.end):
                hours = tl.pro_hours(period, month)[source.id]
                if hours <= 0:
                    continue
                if not traced:
                    weights = tier_weights(
                        experiences_for(source.id),
                        month,
                        inputs.experiences,
                        inputs.tech_map,
                    )
                    units.append(Unit(month, kind, hours, weights, True, index))
                    continue
                in_month = [d for d in traced if d[:7] == month]
                if in_month:
                    weights = _sum(inputs.weights_of(d) for d in in_month)
                else:
                    weights = {t: w for t, w in whole.items() if seen[t] <= month}
                units.append(Unit(month, kind, hours, weights, False, index))

    for index, day in personal_days:
        budget = tl.budget_for(timeline.periods[index].context)
        hours = tl.personal_hours(budget, [date.fromisoformat(day)])
        if hours > 0:
            weights = inputs.weights_of(day)
            units.append(Unit(day[:7], "personal", hours, weights, False, index))
    return units


def allocations(units: list[Unit], tech_map: TechMap) -> list[dict[str, float]]:
    return [allocate(u.hours, u.weights, tech_map) for u in units]


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


def aggregate(inputs: Inputs, catalogue: list[dict]) -> dict:
    """The committed aggregates document (deterministic, no private names)."""
    tech_map = inputs.tech_map
    units = build_units(inputs)
    allocs = allocations(units, tech_map)

    context: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    month_techs: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    month_domains: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    tech_hours: dict[str, list[float]] = defaultdict(list)
    tech_estimated: dict[str, list[float]] = defaultdict(list)
    tech_months: dict[str, list[str]] = defaultdict(list)
    for unit, alloc in zip(units, allocs, strict=True):
        context[unit.month][unit.kind].append(unit.hours)
        for tech, hours in alloc.items():
            month_techs[unit.month][tech].append(hours)
            tech_hours[tech].append(hours)
            tech_months[tech].append(unit.month)
            if unit.estimated:
                tech_estimated[tech].append(hours)
        for domain, hours in domain_hours(unit.hours, unit.weights, tech_map).items():
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
            "level": level_for(total),
            "first": min(tech_months[tech]),
            "last": max(tech_months[tech]),
            "estimated_share": _r(math.fsum(tech_estimated[tech]) / total, 3),
            "layer": info.layer,
            "domain": info.domain,
        }

    days = inputs.days
    public = sum(1 for d in days.values() if d.public)
    diffs = domain_differences(tech_map, catalogue)
    notes = list(NOTES)
    if diffs:
        notes.append("Domains that differ from data/techs.json: " + "; ".join(diffs))
    return {
        "version": 1,
        "activity_as_of": max(days) if days else inputs.timeline.as_of,
        "coverage": {
            "commit_days": len(days),
            "public_days": public,
            "public_share": _r(public / len(days), 4) if days else 0.0,
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
    allocs = allocations or [
        allocate(u.hours, u.weights, inputs.tech_map) for u in units
    ]
    issues: list[str] = []
    seen = first_seen(inputs)
    earliest_estimate: dict[str, str] = {}
    for unit in units:
        if unit.estimated:
            for tech, weight in unit.weights.items():
                if weight > 0 and unit.month < earliest_estimate.get(tech, "9999-99"):
                    earliest_estimate[tech] = unit.month
    for tech, entry in sorted(doc["techs"].items()):
        bound = min(seen.get(tech, "9999-99"), earliest_estimate.get(tech, "9999-99"))
        if entry["first"] < bound:
            issues.append(
                f"{tech}: first use {entry['first']} before its first commit or "
                f"estimated period ({bound})"
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
        u.hours
        for u in build_units(inputs)
        if not allocate(u.hours, u.weights, inputs.tech_map)
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
        f"{'first':<9}{'last':<9}estimated",
    ]
    ranked = sorted(doc["techs"].items(), key=lambda kv: (-kv[1]["hours"], kv[0]))
    for tech, entry in ranked[:25]:
        lines.append(
            f"{tech:<24}{entry['hours']:>9.0f}{entry['display_hours']:>8}  "
            f"{entry['level'] or '-':<13}{entry['first']:<9}{entry['last']:<9}"
            f"{entry['estimated_share']:.0%}"
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
    args = parser.parse_args(argv)

    directory = os.environ.get(tl.PRIVATE_DIR_ENV)
    if not directory:
        print(f"error: {tl.PRIVATE_DIR_ENV} is not set", file=sys.stderr)
        return 2
    private = pathlib.Path(directory)
    try:
        inputs = Inputs(
            timeline=tl.load_timeline(private / tl.PRIVATE_TIMELINE_NAME),
            days=parse_evidence(_read_json(private / EVIDENCE_NAME)),
            classes=parse_repo_classes(_read_json(private / CLASSES_NAME)),
            tech_map=load_tech_map(args.tech_map),
            experiences=parse_experiences(_read_json(args.experiences)),
        )
        catalogue = _read_json(args.catalogue)
        doc = aggregate(inputs, catalogue=catalogue)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    issues = sanity_checks(doc, build_units(inputs), inputs)
    print(_summary(doc, inputs, issues))
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
