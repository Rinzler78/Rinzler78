# ADR-012 — Quality gates tiered by responsibility

- **Status**: Accepted
- **Date**: 2026-09-23
- **Amends**: [ADR-005](0005-quality-gates-ci-branch-protection.md) (where each gate runs)
- **Related to**: [ADR-011](0011-committed-reference-date.md)

## Context

ADR-005 moved the quality gates to the pre-commit framework and put nearly all of
them on the `pre-commit` stage, with the test suite and the dependency audit on
`pre-push`. Two years of data later, that placement had three measurable problems.

**The loop was too slow to test in.** The suite took ~40 s. Not because there are many
tests — 109 of them — but because each guard that reads a generated artifact opened
with its own `gen.main()`: 36 SVGs, two READMEs, eight pages and a font→path outlining
pass, about two seconds, some twenty-five times over. A red-green-refactor cycle that
costs forty seconds is one nobody runs; the gate then only fires at commit time, which
is precisely when it is most expensive to be wrong.

**`pip-audit` never audited this project.** Declared with `language: python` and
`additional_dependencies: ["pip-audit>=2.7"]`, it ran inside the isolated virtualenv
pre-commit builds for it — an environment containing pip-audit's own dependencies and
`pre-commit-placeholder-package 0.0.0`. It audited that, found a package that is not on
PyPI, and exited 1. It blocked a push on 2026-09-23 while never having looked at a
single dependency of this repository.

**Every push paid for a network call.** A dependency CVE audit is a property of the
dependency set, which changes a few times a year, not of the commit being pushed.

## Decision

Each gate answers one question, and carries only the checks that answer it.

| Stage | Question | Contents | Budget |
| --- | --- | --- | --- |
| `pre-commit` | Is what I just wrote correct? | hygiene, ruff, bandit, gitleaks, cspell, data schema validation, regeneration + artifact validation, **the tests the staged files can affect** | seconds |
| `pre-push` | Is the branch green as a whole? | full suite + 90 % coverage floor | tens of seconds |
| `pre-merge-commit` | Is it safe to integrate? | full suite + coverage, **dependency CVE audit** | slowest, rarest |

Supporting changes:

1. **`tests/conftest.py`** renders the profile once per session, `autouse`. The guards
   read that output. The two tests that genuinely need a second render — the
   determinism guard and the reference-date guard — still call `gen.main()`
   themselves, because there the second run *is* the behavior under test.
2. **`scripts/impacted_tests.py`** maps staged paths to guards: a test file to itself, a
   module to its sibling `test_<stem>.py`, data / schemas / templates / artifacts to the
   generation and real-data guards. Modules whose guard is not named `test_<stem>.py`
   are listed explicitly. **Anything unmapped widens to the full suite** — packaging,
   CI config, `conftest.py`, an unknown module. Skipping a test that a change could
   break turns a green commit into a false statement, so the selector is built to widen
   when unsure, and `tests/test_impacted_tests.py` pins that behavior.
3. **`pip-audit` moves to `language: system`**, running in the dev environment where
   the project is actually installed, and to the `pre-merge-commit` stage. CI keeps
   running it as an explicit step, so no push reaches `master` unaudited.

## Considered options

- **Leave everything on pre-commit** — the status quo. Rejected: it is what made the
  loop unusable, and an unusable gate is the one people route around. The doctrine
  forbids bypassing a hook, which makes it doubly important that no hook be a tax.
- **`pytest-testmon` for impact analysis** — coverage-based selection, more precise than
  a path map. Rejected for now: it carries a state database that goes stale silently,
  and the failure mode of staleness is a skipped test, the one outcome this must never
  produce. The explicit map is auditable and its widening is testable.
- **Drop `pip-audit` locally and rely on CI** — simpler, but pushes the discovery of a
  vulnerable dependency to after integration. Keeping it on the merge gate costs one
  network call per merge.
- **Keep the per-test `gen.main()` calls and just select fewer tests** — treats the
  symptom. Selection would still leave the generation guards at seconds apiece, and the
  full suite at pre-push would stay at forty seconds.

## Consequences

**Positive**
- Full suite: **~40 s → ~7 s**. A typical module edit at `pre-commit`: **~1.4 s**.
- `pip-audit` audits this project's dependencies for the first time.
- The cost of each gate now matches how often it fires.

**Negative**
- `impacted_tests.py` is a second source of truth about which tests cover what, and it
  drifts if a module's guard is renamed. Mitigated by widening on any unmapped path and
  by `tests/test_impacted_tests.py`, but a renamed guard silently widens instead of
  failing loudly.
- A session-scoped fixture means tests share generated state. A test that *writes* to
  the generated artifacts would leak into its neighbors; none does today.
- `pre-merge-commit` does not fire for merges performed on GitHub, so for squash-merged
  pull requests the audit comes from CI rather than from the local hook.

## Success criteria

- `pytest -q` completes in under 10 s on a warm checkout.
- `python scripts/impacted_tests.py <a module>` runs only that module's guards, and
  `pyproject.toml` or `conftest.py` widens to the full suite.
- `pre-commit run --hook-stage pre-merge-commit --all-files` passes, `pip-audit`
  included.
