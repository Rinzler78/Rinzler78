# 0001 — Data-driven architecture: JSON sources + Jinja2 + pre-commit hook

**Status:** Accepted · 2026-05-26

## Context

The README and the ~14 profile SVGs contained the same facts duplicated in several places (tech versions, adoption years, project descriptions, etc.). With each design iteration — changing the palette, the format of a terminal, the layout of a section — every copy had to be kept consistent by hand. The design is expected to evolve several times; the facts, rarely.

The cost of a design overhaul was therefore disproportionate relative to the added value, and divergences between views were likely over time (`Python 3.11+` vs `Python 3.11` in two places, for example).

## Decision

Separate **data** (facts, change rarely) from **presentation** (rendering, iterates often):

- Store the **facts** in `data/*.json` — 7 files corresponding to 7 atomic concepts: `profile`, `domains`, `techs`, `timeline`, `projects`, `theme`, `content`. No duplication between files; links are references by `id`.
- Generate the **SVGs and the README** via Jinja2 templates (`scripts/templates/*.jinja`) that consume the JSON.
- Trigger regeneration automatically via a **git pre-commit hook**. The generated files (`assets/svg/`, `README.md`) are versioned (so that GitHub serves them without a CI step) but the hook guarantees they stay in sync with the data at commit time.

ID convention: **snake_case without version for the root tech** (`csharp`), **nested versions with full id** (`csharp_2_0`, `csharp_12`). Referencing between concepts is **hybrid**: IDs for strong links (timeline → techs, projects → techs), free text for narration only.

## Rejected alternatives

- **Dynamic README in client-side JS**: impossible, GitHub markdown does not execute JavaScript.
- **10 JSON files per view** (one file per SVG): created redundancy between files again (the same techs appear in timeline, id-card, and stacks). Rejected by the user: "that many JSON files doesn't seem right to me".
- **A single monolithic `data.json` file**: painful to edit, frequent git conflicts. Trade-off settled with 7 concept files.
- **f-strings or a Python DOM builder instead of Jinja2**: not expressive enough for nested loops (techs × versions, timeline events × techs-added). Jinja2 is a trivial dependency (`pip install jinja2`) that significantly simplifies the templates.
- **GitHub Actions instead of a pre-commit hook**: adds delay between push and rendering, and requires the output branch to be pushed by a bot. The local pre-commit hook guarantees synchronization at commit time, without a CI round-trip.
- **README not generated, only the SVGs**: leaves the narrative text (intervention modes, easter eggs, prose) coupled to the markdown structure. Generating everything makes `content.json` the single source of editable text.

## Consequences

**Positive**
- A factual value appears in one and only one file.
- Design overhaul = editing the Jinja2 templates + theme.json, without touching the facts.
- Cross-view consistency guaranteed (a single `update` of `dotnet.version` updates id-card, timeline, stack-backend, projects in a single build).
- Reusable for other formats (PDF CV, personal page, JSON-resume) from the same data.

**Negative**
- Costly initial setup: ~1-2 h to extract the data, write `generate.py` and the templates.
- Python + Jinja2 dependency on Boris's machine (and on any other contributor's).
- The pre-commit hook slows down every commit that touches `data/` (by a few seconds).
- The generated files double the number of versioned files. Mitigated by their modest size (< 100 KB total).

## Success criteria

- Fully reproducible regeneration: `python scripts/generate.py` always produces the same output from the same data.
- No divergence between data and the versioned SVGs/README (the hook prevents this case).
- A palette overhaul = a single commit editing `theme.json` (+ the regenerated SVGs/README).
