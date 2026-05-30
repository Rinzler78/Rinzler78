# ADR-003 — Data schema: everything as collections, derived views, adaptive display

- **Status**: Accepted
- **Date**: 2026-05-27
- **Related to**: [ADR-001](0001-data-driven-svg-generation.md), [ADR-002](0002-tech-score-derivation.md), [ADR-004](0004-i18n-bilingual-readme.md)

## Context

ADR-001 established the data-driven principle. The expansion of scope (structured services, multi-language, dark/light mode, animations, time-of-day) and the desire to treat the data as a **database** call for a more normalized schema than the initial version.

## Decision

### 1. All `data/` files are collections

Each `data/*.json` file is a **JSON array**; each entry carries a stable snake_case `id`. The original singletons (`profile`, `theme`) become collections with one (or several) entries, which allows multiple profiles or themes to coexist without a redesign.

### 2. Inventory of collections

| File | Usual cardinality | Role |
|---|---|---|
| `data/config.json` | 1 | Points to the active `theme_id` and `profile_id` |
| `data/profile.json` | 1 (extensible) | Identity, contacts, links, location |
| `data/themes.json` | 1+ | Available design systems |
| `data/domains.json` | 6–10 | Expertise taxonomy |
| `data/techs.json` | 50+ | Technical skills (FK → domain) |
| `data/projects.json` | 10–20 | Public projects (FK → domain, M:N → techs) |
| `data/timeline.json` | 10–20 | Chronological events (M:N → techs) |
| `data/services.json` | 4–8 | Sellable offerings |
| `data/modes.json` | 3–5 | Engagement modes |
| `data/methodology.json` | 5–10 | Working principles |
| `data/content.json` | 5–10 | Residual narrative modules |

### 3. Derived views (never stored)

Computed by `scripts/generate.py`, never persisted in `data/`:

| View | Derivation |
|---|---|
| `Skill` | `Tech` + score (ADR-002 formula) + level |
| `Experience` | `TimelineEvent.filter(role != null)`, computed periods |
| `Education` | `TimelineEvent.filter(kind == 'education')` |
| `TechRadar` | `Skills` aggregated by cluster (Core/Advanced/Working/Explored) |
| `CoreExpertise` | `Skills.filter(featured == true)` |
| `FeaturedProjects` | `Projects.filter(highlight == true).group_by(domain)` |
| `StackByDomain` | `Techs.group_by(domain)` |
| `ParcoursStory` | `TimelineEvents.filter(highlight == true).sort(year)` |

Invariant: if a factual value can be computed from existing data, we **derive** it instead of duplicating it.

### 4. Stable IDs and referential integrity

- Each entry has a snake_case `id` set at creation, **never modified**.
- References are by id (`domain_id`, `tech_ids[]`, etc.).
- A pre-commit test verifies that each reference points to an existing entity.

### 5. Adaptive dark/light display

The generator produces two sets of SVGs: `assets/svg/dark/*` and `assets/svg/light/*`. The README uses the HTML `<picture>` tag (acceptable because it is GitHub standard, not inline SVG):

```html
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/svg/dark/hero.svg">
  <img src="assets/svg/light/hero.svg" alt="Hero">
</picture>
```

The base **dark** palette (`AI Architect Dark`):
- background `#0D1117`, surface `#161B22`
- primary `#00E5FF`, secondary `#7C3AED`, accent `#22C55E`
- text `#E6EDF3`, muted `#8B949E`

The **light** palette is derived through controlled inversion (not a simple flip): light background, primary/secondary/accent preserved but adjusted for WCAG AA contrast.

### 6. Profile as Code

A README section displays a **code** representation of the profile (C# inspired by spec V1 §5.2), also generated from `data/` to stay in sync. No duplication between the displayed code and the data sources.

## Consequences

### Positive

- Normalized schema, readable like a database, extensible without a redesign.
- No duplication between data and views.
- Adaptive dark/light display without JS, respecting GitHub conventions.
- Allows multiple themes / profiles via `config.json`.

### Negative

- Migration from the current state: extraction of `Mode`/`Methodology` from `content`, addition of `services`/`config`/`themes`, overhaul of `techs` (removal of `level`, addition of `until`/`featured`/`overrides`), enrichment of `timeline` (`role`/`employer`/`kind`).
- Doubling of the SVGs (dark + light) — negligible storage cost, doubled generation cost but still fast.
- Acceptance of the HTML `<picture>` tag — not strict pure Markdown.
