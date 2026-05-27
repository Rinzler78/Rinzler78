# ADR-005 — Quality gates, CI GitHub Actions et protection de main

- **Statut** : Accepted
- **Date** : 2026-05-27
- **Lié à** : [ADR-001](0001-data-driven-svg-generation.md), [ADR-003](0003-data-schema-collections-and-derived-views.md), [ADR-004](0004-i18n-bilingual-readme.md)

## Contexte

Le repo doit être gouverné comme un vrai projet logiciel : pre-commit framework standard, tests TDD obligatoires, CI rejouant l'intégralité des contrôles locaux, protection de `main` empêchant les commits directs et les rebases destructifs. La règle CLAUDE.md globale impose 4 catégories de checks (vulnerability scan, package up-to-date, linter, cspell en) couvrant tout le code y compris tests.

## Décision

### 1. Pre-commit framework officiel

Remplace le shell hook custom (`scripts/install-hook.sh` + `.git/hooks/pre-commit`) par `.pre-commit-config.yaml`. Installation via `pre-commit install --hook-type pre-commit --hook-type pre-push`.

Hooks **pre-commit** (rapides) :
- `ruff` (lint + format)
- `bandit` (security scan)
- `detect-secrets` ou `gitleaks` (anti-leak)
- `cspell` configuré `language: en` sur les artefacts EN (templates, schemas, code)
- `jsonschema-validate` sur `data/*.json`
- `referential-integrity-check` (script local : chaque FK pointe sur une entité existante)
- `i18n-translate` (DeepL si champs i18n changés, voir ADR-004)
- `generate-and-diff` (régénère SVG+README, fail si diff)
- `svg-well-formed` (xmllint)

Hooks **pre-push** (lourds) :
- `pytest --cov=scripts --cov-fail-under=90`
- `pip-audit` (CVE deps)
- `link-checker` sur README.md + README.en.md
- `svg-schema-validate` (validation contre XSD SVG si besoin)

### 2. Stratégie TDD

- Framework : `pytest` + `pytest-cov` + `jsonschema` + `responses` (mock DeepL).
- Couverture cible **≥ 90%** bloquante en pre-push et CI.
- Ordre d'écriture des tests : data validation → formule score (ADR-002) → overrides → i18n → vues dérivées → génération → déterminisme → SVG well-formed → DeepL cache.
- Chaque feature commence par un test rouge (règle CLAUDE.md `tdd` skill).

### 3. Packaging

- `pyproject.toml` (PEP 621) : remplace `scripts/requirements.txt`.
  - `[project]` (nom, version, python ≥ 3.11)
  - `[project.optional-dependencies]` : `dev` (ruff, bandit, pre-commit, pip-audit), `test` (pytest, pytest-cov, responses, jsonschema, lxml)
- `Makefile` : `setup`, `validate`, `generate`, `test`, `coverage`, `lint`, `format`, `format-check`, `security`, `audit`, `check`.

### 4. CI GitHub Actions

Trois workflows, permissions minimales par défaut (`contents: read`), élévation isolée.

**`.github/workflows/ci.yml`** (push + PR) :
```yaml
permissions: { contents: read }
jobs:
  precommit:    # pre-commit run --all-files
  test:         # pytest --cov --cov-fail-under=90
  diff-check:   # git diff --exit-code après generate
  linkcheck:    # lychee ou markdown-link-check
```

**`.github/workflows/update-profile.yml`** (cron `0 6 * * 1` + workflow_dispatch) :
```yaml
permissions: { contents: write }   # ISOLÉ
jobs:
  refresh:      # fetch GitHub metrics → data/metrics.json → generate → commit si diff
```

**`.github/workflows/translate-check.yml`** (PR si diff sur `data/`) :
```yaml
permissions: { contents: read }
secrets: [DEEPL_API_KEY]
jobs:
  check:        # cache i18n cohérent avec FR courant, warning si reviewed=false
```

### 5. Protection de `main` (Repository Ruleset)

- Pull Request obligatoire (même solo : force le workflow PR + CI).
- Status checks requis : `ci/precommit`, `ci/test`, `ci/diff-check`.
- Branch up-to-date avant merge.
- Linear history (pas de merge commits, rebase only).
- Conversation resolution requise.
- Force push interdit.
- Suppression de branche interdite.
- Signed commits requis (gratuit puisque la règle CLAUDE.md interdit déjà `--no-gpg-sign`).

### 6. Branching

- `main` protégée, source de vérité.
- Branches features sous forme `feature/<slug>` créées dans `.worktrees/<slug>/` (règle CLAUDE.md).
- Trunk-based (pas de `develop`) — le repo est solo, git flow serait sur-ingénierie.
- Conventional commits : `feat(profile)`, `fix(svg)`, `chore(deps)`, `docs(adr)`, `test(generator)`.

### 7. Anti-attribution IA

Pas de hook spécifique au repo : le hook global Claude `~/.claude/hooks/block-ai-attribution.sh` bloque déjà les commits qui mentionnent Claude/IA/Copilot dans le message. Pas de duplication.

## Conséquences

### Positives

- Aligne avec la règle CLAUDE.md globale.
- Toute défaillance détectée localement avant push (gain de cycle CI).
- Protection de `main` empêche les écrasements accidentels et force la traçabilité PR.
- Permissions GitHub Actions minimales = surface d'attaque réduite.

### Négatives

- PR obligatoire en solo = friction supplémentaire (peut être contournée par auto-merge sur green checks).
- Pre-commit lent au premier run (download des venvs hooks). Cache GitHub Actions amortit en CI.
- Couverture 90% bloquante peut être pénible sur les templates Jinja2 (parser/render rapide à couvrir mais branches conditionnelles dans les templates plus subtiles à atteindre). Stratégie : tester via fixtures de data variées plutôt que d'exporter chaque branche.
