# ADR-011 — Committed reference date for reproducible generation

- **Status**: Accepted (committed data extended by [ADR-013](0013-activity-timeline-evidence-hours.md))
- **Date**: 2026-09-23
- **Amends**: [ADR-006](0006-hours-based-expertise-model.md) (when the hours are measured from)
- **Related to**: [ADR-001](0001-data-driven-svg-generation.md), [ADR-005](0005-quality-gates-ci-branch-protection.md)

## Context

ADR-006 derives every tech's score and level from **exposure hours**, and hours
accrue for as long as a source still employs the tech. `HoursCalculator` therefore
measures each ongoing experience (`end: null`) against a `today` argument, and
`generate.py` passed `date.today()`.

The consequence was not noticed when it was written: **the output is a function of
the system clock**. Regenerating the same revision a few months later moves hours,
which moves scores, which moves levels and the order of rows sorted by score.
Observed on 2026-09-23 against artifacts committed on 2026-06-01: six files changed
with no data edit — two rows swapped in the language table, and Cosmos SDK crossed a
level threshold from `explored` to `working`.

Three things break as a result:

1. **CI**: `ci.yml` ends with `git diff --exit-code` to prove the committed artifacts
   match the data. It fails on its own once enough time passes, and its comment
   claimed generation "only depends on the current year — stable within a calendar
   year", which was wrong: the dependency is monthly.
2. **The pre-commit `generate-profile` hook** rewrites generated files on a commit
   that touched nothing related, so an unrelated change cannot be committed cleanly.
   This blocked a push on 2026-09-23.
3. **ADR-009's success criterion** "generation still deterministic, 2-runs-identical"
   cannot hold across a month boundary.

## Decision

The reference date is **data, committed with the revision it describes**.

1. `data/config.json` holds `as_of` (`YYYY-MM-DD`), validated by
   `schemas/config.schema.json` and enforced by `validate_data.py`. The file is the
   singleton generation config CONTEXT.md already described (it did not exist yet).
2. `scripts.generate.reference_date()` reads it, and `main()` passes that date to the
   whole derivation. `date.today()` no longer appears in the generation path.
3. `scripts/bump_as_of.py` moves it to today. The weekly `update-profile.yml` run
   calls it before regenerating — that workflow is the one place the date advances.
4. `as_of` is pinned to **2026-06-01**, the date the currently committed artifacts
   were generated, so adopting this ADR produces no artifact diff.

## Considered options

- **Keep the clock and regenerate in CI before diffing** — hides the drift rather than
  removing it, and still makes two runs of one revision differ. Rejected.
- **Freeze `until` on every ongoing source** — would falsify the data to serve the
  render. Rejected: the data describes the track record, not the build.
- **Round the reference to the year** — what the CI comment already assumed. Narrows
  the window to a yearly break instead of closing it, and still breaks each January.
  Rejected.

## Consequences

**Positive**
- The same revision regenerates byte-identically, whenever it is built. `git diff
  --exit-code` in CI becomes a real invariant instead of a time bomb.
- A commit that touches unrelated files no longer drags a regeneration diff with it.
- The profile still ages, but on a deliberate weekly commit that is reviewable as a
  diff of its own.

**Negative**
- One more field to keep honest: an `as_of` left stale makes the profile quietly
  under-report ongoing experience. The weekly workflow is the mitigation, and a stale
  date is visible in the data rather than hidden in the build.
- Tests that assert on scores are now pinned to a date, so a bumped `as_of` can
  legitimately change expected values.

## Success criteria

- Generation run with a system clock five years ahead produces identical output
  (`tests/test_reference_date.py::test_generation_ignores_the_system_clock`).
- `data/config.json` is schema-valid and `reference_date()` reflects it.
- `make check` passes on a checkout of any age.
