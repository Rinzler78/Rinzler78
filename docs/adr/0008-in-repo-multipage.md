# ADR-008 — In-repo multipage profile (README as front, detail pages generated)

- **Status**: Accepted
- **Date**: 2026-06-01

## Context

The profile is a single scrollable `README.md`: there is no real "first screen", and quick-to-assimilate identity is buried in the same stream as deep detail (full stack, dated track record, every project). The goal is **progressive disclosure**: a concise front that a visitor grasps in seconds, with all the detail reachable one click away — without leaving GitHub and without standing up external hosting.

A GitHub profile README must stay a single `README.md` on the profile landing. But GitHub renders **any** `.md` file in the repo, so detail can live in sibling markdown pages generated from the same data.

## Decision

**Multipage, in-repo, 100% GitHub, data-driven.**

- `README.md` (+ `README.en.md`) = **concise front**: hero (name + signature arc + "who-for" subtitle + scale line), a quick résumé block, and the **full contact cluster** (the actionable, quick-to-grasp layer), plus links to the detail pages.
- **Detail pages** are generated markdown under `pages/` (e.g. `pages/stack.md`, `pages/journey.md`, `pages/projects.md`, `pages/toolbox.md`), each an aggregated **view** of the same `data/` — same `generate.py`, same templates, same dual-palette `<picture>` mechanism, same i18n (`pages/en/*`).
- A **Page** becomes a first-class generation target alongside SVG views: one entry in the generator's targets, one template, rendered for FR + EN.

## Considered options

- **Single long scrollable README** (`<details>` collapsibles) — one file, but heavy scroll and "everything in one place", the opposite of the requested split.
- **README front + GitHub Pages site for the detail** — richer standalone pages, but adds a static-site build/deploy (infra, Pages workflow); leaves the "all-native-GitHub" simplicity. Rejected to avoid infra.
- **Detail in the repo wiki** — separate surface, not data-driven from the same pipeline, harder to keep in sync.

## Consequences

**Positive**
- Realizes the multipage split **without extra infra**, reusing the existing data→Jinja chain (one page = one more aggregated view).
- Front stays light and conversion-oriented; depth is opt-in.
- Detail pages inherit dual-theme + i18n for free.

**Negative**
- Detail sub-pages render with GitHub's **file-browser chrome** (file tree, path header) — less polished than the profile landing. Accepted as the cost of staying infra-free.
- More generated files to keep in sync (mitigated by the generator + pre-commit guarantee).
- Internal links between generated pages must resolve for both FR and EN (validated by `validate.py`).

## Success criteria

- The front README is graspable without scrolling past the contact cluster; every detail block has moved to a linked page.
- Every generated cross-page link points to an existing file (FR and EN) — enforced by `validate.py`.
- Adding a page = one target + one template, no change to the loading/enrichment core.
