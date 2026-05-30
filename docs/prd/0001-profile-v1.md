# PRD-001 — Profile V1: data-driven, bilingual, adaptive, governed

> Status: ready-for-agent
> Date: 2026-05-27
> Links: [ADR-001](../adr/0001-data-driven-svg-generation.md), [ADR-002](../adr/0002-tech-score-derivation.md), [ADR-003](../adr/0003-data-schema-collections-and-derived-views.md), [ADR-004](../adr/0004-i18n-bilingual-readme.md), [ADR-005](../adr/0005-quality-gates-ci-branch-protection.md)

## Problem Statement

Boris is a freelance CTO/software architect targeting startups, scaleups, and mature companies alike, in France and internationally. His current GitHub profile (`Rinzler78/Rinzler78`) is a data-driven README (ADR-001) but a limited one: single-language FR, a simple data schema (3 Tech tiers without derivation), a single visual mode that does not adapt to the visitor's GitHub theme, no structured services catalog, no tests, a custom shell pre-commit not aligned with standard quality rules, and no branch protection.

Without evolving, the profile:
- cuts off the EN-only market (English-speaking recruiters, international clients who do not switch language);
- does not distinguish "shipped to production" from "hacked together as a prototype", which blurs the seniority signal;
- does not surface the commercial offering (sellable services) to a prospect scanning for 30 seconds;
- clashes visually with the GitHub light/dark mode chosen by the visitor;
- does not prove the working method (tests, CI, governance) that a client CTO would seek to validate.

## Solution

Rebuild the `Rinzler78/Rinzler78` repo as a **GitHub Profile Generator**: a software project in its own right, governed as such, that takes normalized JSON data as input and produces as output two READMEs (FR + EN), SVG assets in two variants (dark + light) served via `<picture>` according to the visitor's preference, and a set of subtle dynamic animations. The pipeline is tested (coverage ≥ 90%), validates the schemas, checks referential integrity, translates via DeepL with a committed cache, and runs under GitHub Actions CI with `main` protected by a ruleset.

The V1 profile demonstrates two things simultaneously: (1) who Boris is and what you can buy from him, (2) how Boris builds software — the repo itself being the proof.

## User Stories

### Profile visitor

1. As an English-speaking recruiter visiting `github.com/Rinzler78`, I immediately see a link to the EN version of the README, so that I can switch without having to understand FR.
2. As a potential French client, I read a clear FR pitch at the top of the profile, so that I grasp Boris's offering in 10 seconds.
3. As a client in GitHub Dark Mode, the embedded SVGs appear in a dark variant consistent with the rest of the page, so that reading is comfortable.
4. As a client in GitHub Light Mode, the embedded SVGs appear in a WCAG AA light variant, so that reading is comfortable.
5. As a prospect scanning in 30 seconds, I see the **sellable services** first (Architecture, Audit, AI-Driven Dev, etc.) before the technical details, so that I know what I can buy.
6. As a prospect, I also see the **intervention modes** (firefighter, long-term support, one-shot audit, mentor) to understand how to engage Boris.
7. As a CTO doing an evaluation, I review the technology mastery levels with a defensible score (derived, not arbitrary), so that I can validate Boris's real expertise.
8. As a CTO doing an evaluation, I clearly distinguish `expert` techs (used in critical production), `advanced` (autonomous in production), `professional` (non-central production use), `working` (shipped prototype), `explored` (watching), so that I can calibrate my expectations.
9. As a curious visitor, I review a visual timeline of the journey that blends first code (2006), degrees, successive positions, and technical milestones, so that I understand Boris's trajectory.
10. As a visitor, I see the featured projects grouped by domain with an explanation of "why this project matters", so that I understand the value of what is in the public repo.
11. As a recruiter, I review the "How I work" section that formalizes the working principles (Simple before clever, Tested before trusted, etc.), so that I can judge the engineering philosophy.
12. As a visitor, I see the "Profile as Code" (a C#-inspired snippet that presents Boris as an object), for the dev wink and the geek signal.
13. As a B2B client, I see at the bottom a pyramidal contact block (the hero summary restated + full detail with email, LinkedIn, Malt, etc.), so that I can get in touch quickly.
14. As a visitor, I perceive the "human tone" through the collapsible `~bashrc` easter eggs (basketball, dad) that add personality without breaking the professional seriousness.

### Boris (system user)

15. As Boris, I enter or modify a fact in `data/*.json` and I commit; the pipeline automatically regenerates all artifacts (SVG, README FR, README EN) in the same commit, so as to avoid any desynchronization between data and rendering.
16. As Boris, I enter only the FR version of the narrative fields; DeepL automatically produces the EN version at pre-commit, so as not to double the editorial effort.
17. As Boris, I can manually override an EN translation (flag `manual: true` in the cache), so as to fix a case where DeepL translated poorly.
18. As Boris, I know which EN translations have not yet been reviewed (flag `reviewed: false`) because the hook displays a warning, so that I know where to focus my attention.
19. As Boris, I can override a tech's score or level (`score_override`, `level_override`) when the formula underrates it (e.g. unlisted private use), so as to keep an honest signal without cheating.
20. As Boris, I have a Makefile with clear targets (`make setup`, `make test`, `make check`), so that I can act without memorizing long commands.
21. As Boris, my commit to `main` does not go through: I must open a PR. This forces traceability and full CI, so as to avoid accidental overwrites.
22. As Boris, my commits are GPG-signed (already my standard practice), and `main` rejects any unsigned commit, so as to prove authenticity.
23. As Boris, I see locally all schema, lint, security, deps audit, and missing-translation errors BEFORE pushing, thanks to pre-commit + pre-push, so as not to depend on CI for feedback.
24. As Boris, the `update-profile.yml` workflow runs every Monday morning, fetches the public GitHub metrics, and commits if there is a diff, so that the profile stays up to date without intervention.
25. As Boris, I add a new tech, project, or service by editing a single `data/*.json` file; the radar, the bars, the README sections, and the EN version update automatically.
26. As Boris, I can change the palette or the theme by editing `data/themes.json` and `data/config.json`, without touching the templates, so as to test variants without risking breaking the rendering.
27. As Boris, the DeepL cost stays at €0 (free tier 500k chars/month) as long as I do not exceed the quota, so as to keep the solution self-funded.
28. As Boris, if DeepL is unavailable or the key is missing, the hook fails clearly (no silent fallback), so that I know the EN translation was not produced.
29. As Boris, I test my data changes via `make test` and `make coverage` (≥ 90%), so as to guarantee that the score formula and the derived views remain consistent.
30. As Boris, I consult the ADRs (`docs/adr/`) to understand why a given decision was made, so as to evolve the system without replaying past debates.
31. As Boris, I can add a new theme (for example `solarized`) by creating an entry in `data/themes.json` and pointing `data/config.json` at it, so as to pivot the design without a rewrite.

### Future maintainer / open contributor

32. As a future maintainer of the repo (or an autonomous agent), I find in `CONTEXT.md` a complete glossary of the data vocabulary, so as to understand the concepts without reading the code.
33. As a maintainer, I find in `docs/adr/` the structuring decisions, dated and motivated, so as to know what to modify or supersede.
34. As a contributor, I clone the repo, I run `make setup`, and everything is installed (deps, pre-commit, pre-push) in one command, so as to get started in under 5 minutes.

## Implementation Decisions

### Modules to build / modify

The pipeline is broken down into deep modules, each encapsulating one responsibility testable in isolation. All have dedicated tests (validation Q16).

- **DataLoader**: loads `data/*.json`, validates each file against its JSON Schema, checks referential integrity (each FK points to an existing entity), resolves the active profile and theme via `data/config.json`. Interface: `load() → typed entities`. Will expose a structured exception per error category (schema, FK, missing required field).
- **ScoreEngine**: implements the ADR-002 formula. Inputs: a `Tech`, the `Projects` collection, the current date. Outputs: `(score: int, level: enum)`. Applies the overrides (`score_override`, `level_override`) while verifying their consistency (the override level must fall within the range of the override score if both are set). Pure function, deterministic, no I/O.
- **ViewBuilder**: builds the derived views from the loaded entities. Will expose separate functions for `build_skills`, `build_experience`, `build_education`, `build_tech_radar`, `build_core_expertise`, `build_featured_projects`, `build_stack_by_domain`, `build_parcours_story`. Each view is an immutable view model.
- **I18nTranslator**: manages the translation cycle. Reads/writes `data/i18n-cache/<entity>/<id>.<field>.en.json`. Computes the SHA-256 hash of the FR, detects retranslation needs, calls the DeepL API via the official client, respects `manual: true` (never retranslated) and `reviewed: false` (warning only). Interface: `translate(entity, id, field, fr) → en`. Mockable in tests.
- **ThemeResolver**: resolves the active theme from `config.json` and `themes.json`. For the active theme, exposes two palettes: `dark` (entered directly) and `light` (derived by controlled inversion with WCAG AA guarantees). Pure, no I/O.
- **TemplateRenderer**: loads the Jinja2 templates (existing ones, extended). Produces the artifacts for the two languages × two variants (FR×dark, FR×light, EN×dark, EN×light for SVG; FR and EN for the READMEs that reference the SVGs). Deterministic: no timestamp, no unstable ordering, no random hash.
- **OutputWriter**: atomically writes the generated files (`README.md`, `README.en.md`, `assets/svg/dark/*`, `assets/svg/light/*`). Exposes a `diff_against_committed() → bool` function used by the generate-and-diff hook.
- **MetricsFetcher** (V2 anticipated in V1): fetches public metrics via the GitHub API (star count, public repo count, last push). Writes `data/metrics.json`. Mockable in tests.
- **Hook scripts** (`scripts/hooks/`): one script per custom hook (`validate_data.py`, `check_referential_integrity.py`, `translate.py`, `generate_and_diff.py`, `validate_svg.py`). Each script is a short wrapper that orchestrates the modules above.

### Data schema (ADR-003)

All `data/*.json` files are arrays. Each entry carries a stable snake_case `id`. Inventory:

| File | Concept |
|---|---|
| `data/config.json` | Active theme/profile pointer |
| `data/profile.json` | Identity (name, role, contacts, location, links) |
| `data/themes.json` | Design systems (palette, fonts, patterns) |
| `data/domains.json` | Expertise taxonomy |
| `data/techs.json` | Skills with `since`/`until`/`versions[]`/`featured`/overrides; `level` removed (derived) |
| `data/projects.json` | Public projects referencing techs and domain |
| `data/timeline.json` | Events enriched with `role`/`employer`/`kind` |
| `data/services.json` | Sellable offerings (i18n title/description) |
| `data/modes.json` | Intervention modes (i18n) — extracted from `content` |
| `data/methodology.json` | Working principles (i18n) — extracted from `content` |
| `data/content.json` | Residual narrative modules (easter eggs, boot_log, footer_eof) |

And `data/i18n-cache/`: mirror structure with the EN translations.

### Score formula (ADR-002)

```
active_years    = (until or today) − since
recency_gap     = max(0, today − (until or today))
n_versions      = len(tech.versions)
n_projects      = count(p ∈ projects where tech.id ∈ p.tech_ids)
n_domains       = count(distinct p.domain for those projects)

base            = min(60, active_years × 3)
versions_pts    = min(15, n_versions × 3)
projects_pts    = min(15, n_projects × 3)
centrality_pts  = min(10, max(0, n_domains − 1) × 5)

raw             = base + versions_pts + projects_pts + centrality_pts
forgetting      = recency_gap × 6
featured_bonus  = 15 if featured else 0

score = clamp(0, 99, raw − forgetting + featured_bonus)
```

Mapping to level:
- `score ≥ 85` → `expert`
- `70–84` → `advanced`
- `55–69` → `professional`
- `35–54` → `working`
- `< 35` → `explored`

### Multi-language (ADR-004)

- README.md (FR, default) + README.en.md (EN), reciprocal link at the top.
- Narrative fields: `{ "fr": "..." }` on entry. EN in the committed cache `data/i18n-cache/...`.
- DeepL Free translation (key `DEEPL_API_KEY` in local `.env` + GitHub Secret).
- The cache carries `{ fr_hash, en, manual: bool, reviewed: bool }`.
- `manual: true` → never retranslated. `reviewed: false` → warning, not blocking.

### Adaptive display (ADR-003)

Two sets of SVGs (`assets/svg/dark/` and `assets/svg/light/`). The README uses:

```html
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/svg/dark/hero.svg">
  <img src="assets/svg/light/hero.svg" alt="Hero">
</picture>
```

Dark palette = `AI Architect Dark` (background `#0D1117`, primary cyan `#00E5FF`, etc.). Light palette derived by controlled WCAG AA inversion.

### README layout — 11 sections

1. Hero SVG (identity + availability + pyramidal contact)
2. FR pitch + Services banner (horizontal cards)
3. Featured projects (table by domain)
4. Tech radar + Core expertise (combined SVG)
5. Experience timeline (derived view)
6. How I work + AI-driven (merged)
7. Profile as Code (C#-inspired snippet, generated)
8. Detailed stack (table by domain, collapsible)
9. Quality standards (horizontal badges + link to docs/quality-gates.md)
10. Beyond code (current ~bashrc easter egg preserved)
11. Pyramidal contact footer

### Dynamic animations

- **Snake**: kept (existing `snake.yml` workflow).
- **Activity graph** (Ashutosh00710): added, dark theme aligned with the palette.
- **Typing banner** (DenverCoder1): added in the hero, cycles the taglines (Freelance CTO / Software Architect / AI-Driven Development).
- **GitHub readme stats card** (anuraghazra): added, **rank/grade disabled** (anti-inflation), custom palette.
- **Time-of-day Vercel endpoint**: deferred to V2.

### Quality gates (ADR-005)

- `pyproject.toml` (PEP 621) replaces `scripts/requirements.txt`. `dev` and `test` sections.
- `Makefile` with `setup`/`validate`/`generate`/`test`/`coverage`/`lint`/`format`/`security`/`audit`/`check` targets.
- `.pre-commit-config.yaml` orchestrating:
  - pre-commit: ruff (lint+format), bandit, detect-secrets, cspell (en), jsonschema, referential-integrity, i18n-translate, generate-and-diff, xmllint.
  - pre-push: pytest (cov ≥ 90), pip-audit, link-checker.
- The legacy `install-hook.sh` shell hook is **removed**, replaced by `pre-commit install --hook-type pre-commit --hook-type pre-push`.

### GitHub Actions CI (ADR-005)

- `ci.yml` (push + PR), `permissions: contents: read`: pre-commit run all + pytest cov + diff-check + linkcheck.
- `update-profile.yml` (cron `0 6 * * 1` + workflow_dispatch), `permissions: contents: write` (isolated): fetch metrics + regenerate + commit if diff.
- `translate-check.yml` (PR if data/ touched), `permissions: contents: read`, secret `DEEPL_API_KEY`: check that the i18n cache is consistent.

### Branch protection — `main` Repository Ruleset

- PR required.
- Required status checks: `ci/precommit`, `ci/test`, `ci/diff-check`.
- Branch up-to-date before merge.
- Linear history.
- Conversation resolution.
- Force push forbidden.
- Branch deletion forbidden.
- Signed commits required.

### Migration from the current state

The implementation is done on the `feature/profile-v1` branch in `.worktrees/profile-v1/` (workflow rule). Order:
1. Bootstrap: `pyproject.toml`, `Makefile`, `.pre-commit-config.yaml`, removal of `install-hook.sh`, first tests.
2. JSON Schemas: one schema per `data/*.json` file (collection with typed items).
3. Migrate `data/techs.json`: remove `level`, add `until`/`featured`/`level_override`/`score_override`.
4. Create `data/services.json`, `data/modes.json`, `data/methodology.json`, `data/config.json`, `data/themes.json` (from `data/theme.json`).
5. Enrich `data/timeline.json`: `role`/`employer`/`kind`.
6. Migrate `data/content.json` (slimmed down after extraction).
7. Implement `ScoreEngine` + tests.
8. Implement `ViewBuilder` + tests.
9. Implement `I18nTranslator` + tests (DeepL mocked).
10. Rework `TemplateRenderer` for dark/light + EN.
11. Produce the dark + light SVGs for the 11 sections.
12. Generate `README.md` + `README.en.md`.
13. Set up CI, the update-profile and translate-check workflows.
14. Configure the `main` ruleset (manually via gh CLI or UI).

## Testing Decisions

### What makes a good test here

Test the **external behavior**, not the internal implementation. Criteria:
- A test must not break when the body of a function is refactored without changing its contract.
- The inputs/outputs are the only stable surfaces. We test `score(tech, projects, today) → (score, level)`, not the private `_compute_base()`.
- Prefer **table tests** (input → expected output) for the pure modules (ScoreEngine, ViewBuilder, ThemeResolver).
- Prefer **golden file tests** (snapshot of an expected README/SVG) for the rendering modules, with an explicit update strategy.
- Mock the external I/O (DeepL, GitHub API, filesystem writes) — never hit the network in tests.

### Modules tested

All (Q16):

- **DataLoader**: tests on valid/invalid JSON, valid/invalid schema, FK pointing to an absent entity, valid FK, absent file, empty file, absent config, config pointing to a nonexistent theme.
- **ScoreEngine**: a table of cases covering each tier (expert / advanced / professional / working / explored), edge cases (years=0, featured=true alone, total forgetting, empty versions, empty projects). Override consistency (level + score both set, only one set, detected inconsistency).
- **ViewBuilder**: each view tested separately with controlled fixtures (Experience filters `role != null`, Education filters `kind == 'education'`, FeaturedProjects filters `highlight == true`, etc.). Tests on stable ordering (deterministic sort), correct groupings by domain.
- **I18nTranslator**: DeepL mocked via `responses` or `respx`. Cases: cache absent → API call + cache write; cache present and identical hash → 0 API call; different hash and `manual: false` → retranslation; `manual: true` → no API call; absent API key → structured exception.
- **ThemeResolver**: a table of cases dark → derived light. Verification of WCAG AA contrast via a lib (for example `wcag-contrast`).
- **TemplateRenderer**: golden file for each section × language × variant. Detection of an unfilled Jinja placeholder (regex `{{.*}}` forbidden in output). Verification that all internal links point to an existing file.
- **OutputWriter**: tests on atomic writing (no partial file on failure), diff vs committed (empty diff case, present diff case).
- **MetricsFetcher**: GitHub API mocked. Cases: API OK → metrics written; API 404 on absent repo; API timeout.

### Integration tests

- **Full pipeline**: from a clean `data/` → `generate()` → produces consistent `README.md` + `README.en.md` + SVG.
- **Determinism**: `generate()` × 2 → empty `diff` on all produced files.
- **Referential round-trip**: modifying an id in techs → the project referencing it must be detected as broken.

### Prior art

No existing tests in the repo. Possible inspiration: standard Python pytest test structure, shared fixtures via `conftest.py`, snapshot tests via `pytest-regressions` or `syrupy`.

### Coverage

≥ 90% blocking in pre-push and CI. Configured in `pyproject.toml` via `[tool.coverage]`. Jinja2 template lines hard to cover: strategy = test via varied data fixtures that exercise each conditional branch of the template.

## Out of Scope

- **Time-of-day Vercel endpoint**: deferred to V2. Separate repo or endpoints/ subfolder to be decided at that point.
- **Alternative themes** (Solarized, etc.): the multi-theme mechanism is ready (`themes.json` collection + `config.json` pointer) but V1 ships only `AI Architect Dark`.
- **Full CLI**: `scripts/generate.py` remains a single entry point. No multi-command CLI à la Click/Typer in V1 (V3 spec).
- **Web portfolio export**: not shipped (V3 spec).
- **Advanced GitHub metrics**: V1 starts with stars + public repos + last push. Wakatime, codetime, language breakdown via API: V2.
- **Bilingual beyond FR/EN**: no ES, DE, etc. The i18n model is extensible but V1 ships 2 languages only.
- **DOM/JS animations**: impossible on a GitHub README (no JS). Any animation goes through SVG SMIL or a dynamic serverless endpoint.
- **Server-side browser language detection**: impossible with a GitHub README. The visitor clicks to switch.
- **Browser E2E tests** (Playwright) on the GitHub rendering: not shipped in V1. Manual visual verification after the initial push.

## Further Notes

### Risks

- **DeepL dependency**: if the service is down or the key is revoked, pre-commit fails. Mitigation: DeepL has a very stable SLA (~99.9%), the key is regenerable. In case of a prolonged outage, it is possible to temporarily override via a script that marks all entries `manual: true` with an EN value identical to the FR (to be used exceptionally).
- **90% coverage on Jinja**: can be painful. Mitigation: varied fixtures that exercise each `{% if %}` branch. If truly infeasible on a portion, exclude line by line with a justified `# pragma: no cover`.
- **Inline `<picture>` HTML**: strictly violates the "Markdown only" rule of the initial V1 spec. Decision: accepted because it is GitHub standard, with no equivalent alternative. Documented in ADR-003.
- **Migration of existing data**: removal of `level` from `techs.json`, addition of fields. Risk of information loss on a bad mapping. Mitigation: post-migration referential tests + visual review of the README before merge.
- **Visual regression of the profile during implementation**: during the `feature/profile-v1` branch, the public profile stays on `main` (current state). The final merge replaces everything at once. Mitigation: local preview via `make generate` before the final push.

### Required environment variables

- `DEEPL_API_KEY`: DeepL Free key (`:fx` suffix). Local: `.env`. CI: GitHub Secret.
- `GITHUB_TOKEN`: provided automatically by GitHub Actions for `update-profile.yml`.

### Conventions

- Conventional commits (`feat(profile):`, `fix(svg):`, `chore(deps):`, `docs(adr):`, `test(generator):`).
- Branches under `.worktrees/<slug>/` (workflow rule).
- Single feature branch for this rebuild: `feature/profile-v1`.
- Trunk-based: no `develop`.

### Estimate

Strict TDD implementation: order of magnitude 2–3 days of focused work. The longest parts will be (a) writing the JSON Schemas and data tests, (b) reworking the Jinja2 templates to produce the dark + light + i18n variants.

### Definition of Done

- `make check` passes locally (validate + generate + lint + format-check + security + audit + coverage 90%).
- CI green on the PR.
- `main` ruleset configured.
- README.md (FR) and README.en.md (EN) render visually OK locally and after merge.
- Snake + Activity graph + Typing banner + subtle Stats card appear and update.
- `pre-commit install` is sufficient for a fork to run immediately (provided a DeepL key is available).
- 5 ADRs (002-005 + the existing 001) up to date and linked to each other.
- CONTEXT.md up to date with all the concepts.
- This PRD closed.
