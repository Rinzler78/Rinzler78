# ADR-005 — Quality gates, GitHub Actions CI and main protection

- **Status**: Accepted
- **Date**: 2026-05-27
- **Related to**: [ADR-001](0001-data-driven-svg-generation.md), [ADR-003](0003-data-schema-collections-and-derived-views.md), [ADR-004](0004-i18n-bilingual-readme.md)

## Context

The repo must be governed like a real software project: standard pre-commit framework, mandatory TDD tests, CI replaying the entirety of the local checks, protection of `main` preventing direct commits and destructive rebases. The global CLAUDE.md rule mandates 4 categories of checks (vulnerability scan, package up-to-date, linter, cspell en) covering all the code including tests.

## Decision

### 1. Official pre-commit framework

Replaces the custom shell hook (`scripts/install-hook.sh` + `.git/hooks/pre-commit`) with `.pre-commit-config.yaml`. Installation via `pre-commit install --hook-type pre-commit --hook-type pre-push`.

**pre-commit** hooks (fast):
- `ruff` (lint + format)
- `bandit` (security scan)
- `detect-secrets` or `gitleaks` (anti-leak)
- `cspell` configured `language: en` on EN artifacts (templates, schemas, code)
- `jsonschema-validate` on `data/*.json`
- `referential-integrity-check` (local script: each FK points to an existing entity)
- `i18n-translate` (DeepL if i18n fields changed, see ADR-004)
- `generate-and-diff` (regenerates SVG+README, fails if diff)
- `svg-well-formed` (xmllint)

**pre-push** hooks (heavy):
- `pytest --cov=scripts --cov-fail-under=90`
- `pip-audit` (CVE deps)
- `link-checker` on README.md + README.en.md
- `svg-schema-validate` (validation against SVG XSD if needed)

### 2. TDD strategy

- Framework: `pytest` + `pytest-cov` + `jsonschema` + `responses` (mock DeepL).
- Target coverage **≥ 90%** blocking in pre-push and CI.
- Test writing order: data validation → score formula (ADR-002) → overrides → i18n → derived views → generation → determinism → SVG well-formed → DeepL cache.
- Each feature starts with a red test (CLAUDE.md `tdd` skill rule).

### 3. Packaging

- `pyproject.toml` (PEP 621): replaces `scripts/requirements.txt`.
  - `[project]` (name, version, python ≥ 3.11)
  - `[project.optional-dependencies]`: `dev` (ruff, bandit, pre-commit, pip-audit), `test` (pytest, pytest-cov, responses, jsonschema, lxml)
- `Makefile`: `setup`, `validate`, `generate`, `test`, `coverage`, `lint`, `format`, `format-check`, `security`, `audit`, `check`.

### 4. GitHub Actions CI

Three workflows, minimal permissions by default (`contents: read`), isolated elevation.

**`.github/workflows/ci.yml`** (push + PR):
```yaml
permissions: { contents: read }
jobs:
  precommit:    # pre-commit run --all-files
  test:         # pytest --cov --cov-fail-under=90
  diff-check:   # git diff --exit-code after generate
  linkcheck:    # lychee ou markdown-link-check
```

**`.github/workflows/update-profile.yml`** (cron `0 6 * * 1` + workflow_dispatch):
```yaml
permissions: { contents: write }   # ISOLATED
jobs:
  refresh:      # fetch GitHub metrics → data/metrics.json → generate → commit if diff
```

**`.github/workflows/translate-check.yml`** (PR if diff on `data/`):
```yaml
permissions: { contents: read }
secrets: [DEEPL_API_KEY]
jobs:
  check:        # i18n cache consistent with current FR, warning if reviewed=false
```

### 5. Protection of `main` (Repository Ruleset)

- Pull Request mandatory (even solo: forces the PR + CI workflow).
- Required status checks: `ci/precommit`, `ci/test`, `ci/diff-check`.
- Branch up-to-date before merge.
- Linear history (no merge commits, rebase only).
- Conversation resolution required.
- Force push forbidden.
- Branch deletion forbidden.
- Signed commits required (free since the CLAUDE.md rule already forbids `--no-gpg-sign`).

### 6. Branching

- `main` protected, source of truth.
- Feature branches in the form `feature/<slug>` created in `.worktrees/<slug>/` (CLAUDE.md rule).
- Trunk-based (no `develop`) — the repo is solo, git flow would be over-engineering.
- Conventional commits: `feat(profile)`, `fix(svg)`, `chore(deps)`, `docs(adr)`, `test(generator)`.

### 7. AI anti-attribution

No repo-specific hook: the global Claude hook `~/.claude/hooks/block-ai-attribution.sh` already blocks commits that mention Claude/AI/Copilot in the message. No duplication.

## Consequences

### Positive

- Aligns with the global CLAUDE.md rule.
- Any failure detected locally before push (CI cycle gain).
- Protection of `main` prevents accidental overwrites and forces PR traceability.
- Minimal GitHub Actions permissions = reduced attack surface.

### Negative

- Mandatory PR when solo = additional friction (can be worked around with auto-merge on green checks).
- Pre-commit slow on the first run (download of the hooks' venvs). GitHub Actions cache amortizes this in CI.
- Blocking 90% coverage can be painful on the Jinja2 templates (parser/render quick to cover, but conditional branches in the templates more subtle to reach). Strategy: test via varied data fixtures rather than exercising each branch.
