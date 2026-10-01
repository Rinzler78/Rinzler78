"""Continuous activity timeline and daily hour budgets (ADR-013 section 1).

The author's history is a sequence of periods, month by month from
``TIMELINE_START`` to ``as_of``, with no gap and no overlap. Each period has a
context, which fixes a daily budget inside a fixed day grid, and the sources
(employers, clients, own R&D) that share its professional time.

File format (JSON)::

    {
      "as_of": "YYYY-MM (optional)",
      "periods": [
        {"start": "YYYY-MM", "end": "YYYY-MM" | null, "context": "<context>",
         "label": "...", "sources": [{"id": "...", "share": 1.0}],
         "note": "optional free text"}
      ],
      "exceptions": ["optional free-text notes"]
    }

Both bounds of a period are inclusive: ``start == end`` is a one-month period.
The last period alone may have ``end: null``: the current period, open until
``as_of``. ``as_of`` may be omitted from the file, so the timeline does not
need an edit every month; the caller then supplies it (the hours CLI uses the
month of the latest evidence day, ``--check`` takes ``--as-of`` and defaults to
the current month). A value in the file wins over the caller's.

The real timeline is private (ADR-014) and never lives in this repository.
Its directory is given by the ``PROFILE_PRIVATE_DIR`` environment variable;
the file is ``$PROFILE_PRIVATE_DIR/timeline.json``.

Budgets (``budget_for``):

- the day grid is 08:00-22:00 minus 12:00-13:00 and 18:00-20:00, i.e.
  ``AVAILABLE_HOURS_PER_DAY`` = 11 hours;
- professional hours count by the calendar: every weekday (Monday-Friday) of
  a month counts, at the period's professional budget. No public holiday
  calendar is applied: holidays and leave are not subtracted, a deliberate
  simplification that keeps the count deterministic and country-agnostic;
- personal hours count only on days with at least one own commit, weekends
  included, at the period's personal budget;
- study counts 12 hours of coding a week over 30 weeks a year, i.e. 360
  hours a year spread evenly over the ten academic months (September-June):
  36 hours per academic month, none in July and August. It is credited by
  the calendar, like professional time, since no commit trace exists.

Pure logic: no git, no network; the only I/O is ``load_timeline`` and the CLI.

Usage: ``python -m scripts.activity.timeline --check [file]``
"""

from __future__ import annotations

import argparse
import calendar
import json
import math
import os
import pathlib
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

TIMELINE_START = "2005-09"
PRIVATE_DIR_ENV = "PROFILE_PRIVATE_DIR"
PRIVATE_TIMELINE_NAME = "timeline.json"

DAY_START, DAY_END = 8, 22
BREAKS = ((12, 13), (18, 20))
AVAILABLE_HOURS_PER_DAY = (DAY_END - DAY_START) - sum(b - a for a, b in BREAKS)

STUDY_HOURS_PER_WEEK = 12
STUDY_WEEKS_PER_YEAR = 30
ACADEMIC_MONTHS = frozenset({9, 10, 11, 12, 1, 2, 3, 4, 5, 6})

CONTEXTS = (
    "study",
    "employment",
    "client_mission",
    "parallel_employment",
    "independent_rnd",
    "none",
)

_MONTH_RE = re.compile(r"^(\d{4})-(\d{2})$")
_PERIOD_KEYS = {"start", "end", "context", "label", "sources"}
_PERIOD_OPTIONAL = {"note"}
_TOP_KEYS = {"periods"}
_TOP_OPTIONAL = {"as_of", "exceptions"}
_SHARE_TOLERANCE = 1e-9


@dataclass(frozen=True)
class Budget:
    """Hours a context allows: per weekday, per commit day, per study month."""

    pro_per_weekday: float
    personal_per_commit_day: float
    study_per_academic_month: float = 0.0


_BUDGETS = {
    "employment": Budget(8, 3),
    "client_mission": Budget(8, 3),
    # 50 h/week over five weekdays = 10 working hours a day, 80 % of them
    # coding: 8 hours of practice, split between the two employers by share.
    "parallel_employment": Budget(8, 1),
    "independent_rnd": Budget(0, AVAILABLE_HOURS_PER_DAY),
    "study": Budget(
        0,
        0,
        STUDY_HOURS_PER_WEEK * STUDY_WEEKS_PER_YEAR / len(ACADEMIC_MONTHS),
    ),
    "none": Budget(0, 0),
}


@dataclass(frozen=True)
class Source:
    id: str
    share: float


@dataclass(frozen=True)
class Period:
    start: str
    end: str
    context: str
    label: str
    sources: tuple[Source, ...]
    note: str | None = None

    @property
    def months(self) -> int:
        """Number of calendar months covered, both bounds inclusive."""
        return _index(self.end) - _index(self.start) + 1


@dataclass(frozen=True)
class Timeline:
    as_of: str
    periods: tuple[Period, ...]
    exceptions: tuple[str, ...] = ()


# --- Months --------------------------------------------------------------


def parse_month(value: object) -> tuple[int, int]:
    """Parse ``YYYY-MM`` into ``(year, month)``; raise ValueError otherwise."""
    match = _MONTH_RE.match(value) if isinstance(value, str) else None
    if match is None or not 1 <= int(match.group(2)) <= 12:
        raise ValueError(f"expected a YYYY-MM month, got {value!r}")
    return int(match.group(1)), int(match.group(2))


def _index(month: str) -> int:
    year, mon = parse_month(month)
    return year * 12 + mon - 1


def _from_index(index: int) -> str:
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def month_range(start: str, end: str) -> list[str]:
    """Every month from ``start`` to ``end``, both inclusive."""
    return [_from_index(i) for i in range(_index(start), _index(end) + 1)]


def weekdays_in_month(month: str) -> int:
    """Monday-Friday days in the month; no holiday calendar is applied."""
    year, mon = parse_month(month)
    days = calendar.monthrange(year, mon)[1]
    return sum(1 for day in range(1, days + 1) if date(year, mon, day).weekday() < 5)


# --- Validation ----------------------------------------------------------


def _require_keys(obj: dict, required: set, optional: set, where: str) -> None:
    missing = sorted(required - obj.keys())
    if missing:
        raise ValueError(f"{where}: missing key(s) {', '.join(missing)}")
    unknown = sorted(obj.keys() - required - optional)
    if unknown:
        raise ValueError(f"{where}: unknown key(s) {', '.join(unknown)}")


def _parse_sources(raw: object, context: str, where: str) -> tuple[Source, ...]:
    if not isinstance(raw, list):
        raise ValueError(f"{where}: sources must be a list")
    if context == "none":
        if raw:
            raise ValueError(f"{where}: context 'none' takes no source")
        return ()
    if not raw:
        raise ValueError(f"{where}: context {context!r} needs at least one source")
    sources: list[Source] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError(f"{where}: each source must be an object")
        _require_keys(item, {"id", "share"}, set(), where)
        source_id, share = item["id"], item["share"]
        if not isinstance(source_id, str) or not source_id:
            raise ValueError(f"{where}: source id must be a non-empty string")
        if isinstance(share, bool) or not isinstance(share, int | float):
            raise ValueError(f"{where}: share of {source_id!r} must be a number")
        if share <= 0:
            raise ValueError(f"{where}: share of {source_id!r} must be positive")
        if any(s.id == source_id for s in sources):
            raise ValueError(f"{where}: duplicate source {source_id!r}")
        sources.append(Source(source_id, float(share)))
    total = math.fsum(s.share for s in sources)
    if abs(total - 1.0) > _SHARE_TOLERANCE:
        raise ValueError(f"{where}: shares sum to {total}, expected 1.0")
    return tuple(sources)


def _parse_period(raw: object, position: int, open_end: str | None) -> Period:
    """One period; ``open_end`` replaces ``end: null`` (last period only)."""
    where = f"period #{position}"
    if not isinstance(raw, dict):
        raise ValueError(f"{where}: must be an object")
    _require_keys(raw, _PERIOD_KEYS, _PERIOD_OPTIONAL, where)
    where = f"period #{position} ({raw['start']}..{raw['end']})"
    start, end = raw["start"], raw["end"]
    if end is None:
        if open_end is None:
            raise ValueError(f"{where}: only the last period may have an open end")
        end = open_end
    if _index(start) > _index(end):
        raise ValueError(f"{where}: start is after end")
    context = raw["context"]
    if context not in CONTEXTS:
        raise ValueError(f"{where}: unknown context {context!r}")
    label = raw["label"]
    if not isinstance(label, str) or not label:
        raise ValueError(f"{where}: label must be a non-empty string")
    note = raw.get("note")
    if note is not None and not isinstance(note, str):
        raise ValueError(f"{where}: note must be a string")
    sources = _parse_sources(raw["sources"], context, where)
    return Period(start, end, context, label, sources, note)


def parse_timeline(data: object, as_of: str | None = None) -> Timeline:
    """Validate a decoded timeline document and return it as a ``Timeline``.

    ``as_of`` is the caller's month for a file without one; the file's own
    ``as_of`` wins when both are given. An open last period ends at it.
    """
    if not isinstance(data, dict):
        raise ValueError("timeline: top level must be an object")
    _require_keys(data, _TOP_KEYS, _TOP_OPTIONAL, "timeline")
    as_of = data.get("as_of", as_of)
    if as_of is None:
        raise ValueError("timeline: as_of is neither in the file nor supplied")
    parse_month(as_of)
    raw_periods = data["periods"]
    if not isinstance(raw_periods, list) or not raw_periods:
        raise ValueError("timeline: periods must be a non-empty list")
    exceptions = data.get("exceptions", [])
    if not isinstance(exceptions, list) or not all(
        isinstance(e, str) for e in exceptions
    ):
        raise ValueError("timeline: exceptions must be a list of strings")

    last = len(raw_periods)
    periods = tuple(
        _parse_period(p, i, as_of if i == last else None)
        for i, p in enumerate(raw_periods, 1)
    )
    if periods[0].start != TIMELINE_START:
        raise ValueError(
            f"timeline: must start at {TIMELINE_START}, starts at {periods[0].start}"
        )
    for before, after in zip(periods, periods[1:], strict=False):
        step = _index(after.start) - _index(before.end)
        if step > 1:
            raise ValueError(f"timeline: gap between {before.end} and {after.start}")
        if step < 1:
            raise ValueError(
                f"timeline: overlap between {before.start}..{before.end} "
                f"and {after.start}..{after.end}"
            )
    if periods[-1].end != as_of:
        raise ValueError(
            f"timeline: last period ends at {periods[-1].end}, as_of is {as_of}"
        )
    return Timeline(as_of, periods, tuple(exceptions))


def load_timeline(path: str | os.PathLike[str], as_of: str | None = None) -> Timeline:
    """Read and validate a timeline file; any defect raises ValueError."""
    text = pathlib.Path(path).read_text(encoding="utf-8")
    return parse_timeline(json.loads(text), as_of)


# --- Hours ---------------------------------------------------------------


def budget_for(context: str) -> Budget:
    """The daily budget of a context (ADR-013 section 1 table)."""
    if context not in _BUDGETS:
        raise ValueError(f"unknown context {context!r}")
    return _BUDGETS[context]


def pro_hours(period: Period, month: str) -> dict[str, float]:
    """Professional hours of ``month``, split across the period's sources."""
    if not _index(period.start) <= _index(month) <= _index(period.end):
        raise ValueError(f"{month} is outside the period {period.start}..{period.end}")
    budget = budget_for(period.context)
    if period.context == "study":
        academic = parse_month(month)[1] in ACADEMIC_MONTHS
        total = budget.study_per_academic_month if academic else 0.0
    else:
        total = weekdays_in_month(month) * budget.pro_per_weekday
    return {s.id: total * s.share for s in period.sources}


def period_pro_total(period: Period) -> float:
    """Professional hours over the whole period, all sources together."""
    return math.fsum(
        math.fsum(pro_hours(period, m).values())
        for m in month_range(period.start, period.end)
    )


def personal_hours(budget: Budget, commit_days: Iterable[date]) -> float:
    """Personal hours: the personal budget on each distinct own-commit day.

    The caller passes the commit days that fall inside the period the budget
    belongs to. Weekend days count the same as weekdays.
    """
    return len(set(commit_days)) * budget.personal_per_commit_day


# --- CLI -----------------------------------------------------------------


def _default_path() -> pathlib.Path | None:
    directory = os.environ.get(PRIVATE_DIR_ENV)
    return pathlib.Path(directory) / PRIVATE_TIMELINE_NAME if directory else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.activity.timeline",
        description="Validate an activity timeline and summarize its periods.",
    )
    parser.add_argument(
        "--check",
        nargs="?",
        const="",
        required=True,
        metavar="FILE",
        help=f"timeline file (default: ${PRIVATE_DIR_ENV}/{PRIVATE_TIMELINE_NAME})",
    )
    parser.add_argument(
        "--as-of",
        default=None,
        metavar="YYYY-MM",
        help="month for a file without as_of (default: the current month)",
    )
    args = parser.parse_args(argv)
    as_of = args.as_of or f"{date.today():%Y-%m}"
    path = pathlib.Path(args.check) if args.check else _default_path()
    if path is None:
        print(f"error: no file given and {PRIVATE_DIR_ENV} is not set", file=sys.stderr)
        return 2
    try:
        timeline = load_timeline(path, as_of)
    except (OSError, ValueError) as exc:
        print(f"error: {path}: {exc}", file=sys.stderr)
        return 1

    grand_total = 0.0
    for period in timeline.periods:
        total = period_pro_total(period)
        grand_total += total
        print(
            f"{period.start}..{period.end}  {period.context:<19}  "
            f"months={period.months:<3}  pro_hours={total:.0f}  {period.label}"
        )
    months = sum(p.months for p in timeline.periods)
    print(
        f"total  periods={len(timeline.periods)}  months={months}  "
        f"pro_hours={grand_total:.0f}  as_of={timeline.as_of}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
