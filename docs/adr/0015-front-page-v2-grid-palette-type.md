# ADR-015 — Front page v2: pyramid order, tile grid, palette and type

- **Status**: Accepted
- **Date**: 2026-09-26
- **Amends**: [ADR-007](0007-display-type-outlined-to-paths.md) (what is outlined),
  [ADR-008](0008-in-repo-multipage.md) (what the front page carries),
  [ADR-009](0009-visual-redesign-devtool-direction.md) (accent color)
- **Related to**: [ADR-013](0013-activity-timeline-evidence-hours.md), [ADR-014](0014-claims-evidence-registry.md)

## Context

The front page merged on `develop` on 2026-09-25 was audited as rendered by GitHub
(846 px column, dark theme):

- **Proportions.** Every image carried `width="100%"`, and several SVGs declared a root
  `width="100%"` with no height. Their viewBoxes ranged from 190 to 1,200 units, so each
  was scaled by a different factor: a 190-unit donut rendered 846 × 846 px, a 260-unit
  timeline ×3.3, and the eight contact chips — 34 units tall — up to 846 × 537 px, one
  per line. Section titles and prose were set in `<sub>`, beside those oversized charts.
- **Content.** Less information than the previous profile on `master` (no full tool
  list, no live activity), six sections with a title and no sentence, French and English
  mixed on the French page, a hard-coded year, a footer repeating the contacts above it.
- **History chart.** Each year normalized to 100 % hid volume; four of six domains were
  labelled, with their last-year share; labels were escaped twice (`AI &amp;amp; LLM`);
  the first axis tick was clipped.

A throwaway prototype (branch `prototype/bento-grid`) answered the proportions question
on GitHub itself: tiles sharing one unit grid render at one scale (0.705 on every tile),
and **fixed pixel widths wrap**. Measured on GitHub with the column narrowed to 360 px:
two 415 px tiles side by side on desktop stacked on their own, each rendered at 360 px.
Percent widths never wrap, and push SVG text toward 5 px on a phone.

## Decision

### 1. One pyramid page, detail pages linked

The front page reads from simplest to most detailed, so its order shows how the work is
reasoned:

1. identity band — name, role, availability, three or four verifiable key figures,
   contact;
2. **How I can help** — the offer;
3. its proofs — projects with real metrics (ADR-014);
4. skills by domain — hours, level, period, last use (ADR-013);
5. the timeline — every professional activity or mission as a **very short brief**, its
   detail further down or on a linked page;
6. the method — how hours are measured, the level convention, the coverage;
7. links to the detail pages, which keep version-level tables and long descriptions.

The two parallel employments of 2014–2020 appear as two lines on the same span, each
with its product. There is no portrait: GitHub already shows the avatar beside the
profile README.

### 2. Hybrid composition

Visuals are SVG panels — the identity band, charts, the timeline, the activity calendar,
key figures. **All text is native Markdown** — headings, prose, lists, the offer — so it
reflows on a phone, translates, and can be selected. Every visual is doubled by a
sentence of text.

### 3. The tile grid

- Tiles are drawn on one unit grid (full width 1,200 units, half width 590) and embedded
  with a **fixed pixel width** (`width="415"` for a half tile), never a percentage.
  Side by side on desktop, stacked on a narrow screen.
- Every SVG root declares **both `width` and `height`**; a root `width="100%"` without a
  height is forbidden.
- Minimum text size **20 units** (≈ 12 px when a half tile stacks at 360 px).
- The gap between two side-by-side tiles is drawn inside each tile, since the spacing
  between inline images is a text space.

### 4. Palette

The accent moves from indigo to **acid green**: `#a3e635` on a near-black background in
the dark theme, deep green `#3f6212` in the light theme, where the bright tone would fail
contrast on white. Both themes stay served through `<picture>` as ADR-009 set up.

### 5. Type

Outlined to paths in Inter Display (ADR-007's mechanism): the **name, tile titles and
large figures**. Labels and detail values stay in system-safe fonts. Accessibility rests
on `aria-label` / `<title>`, as ADR-007 requires.

### 6. Visuals

- **Activity**: a calendar of every own commit day since 2014, all sources, colored by
  context; plus an in-house streak and last-year graph, labelled as what GitHub sees.
- **History**: real hours per year stacked by context (no double counting), with a band
  per domain showing presence; plus the per-domain share, labelled as relative weight
  because hours overlap across domains (ADR-013 §4).
- The easter egg is generated from the aggregates; the footer is a signature with the
  data's `as_of` date and a link to the method, without repeating contacts.

## Considered options

- **Poster: every text inside composed SVG** — closest to printed-CV references on
  desktop, unreadable and frozen on a phone. Rejected.
- **Percent-width tiles** (the first prototype) — perfect desktop alignment, no
  stacking. Rejected.
- **Keep the indigo accent** — the author chose a new color family.
- **Outline all SVG text** — rejected by ADR-007 for weight and frozen text; the scope
  here stays the hierarchy-bearing text only.

## Consequences

**Positive**
- One scale for every tile; a readable single column on phones without CSS.
- The front page carries the complete picture again, with depth one click away.

**Negative**
- Fixed widths leave a margin on wide columns; the grid is designed for GitHub's
  846 px column.
- More outlined glyphs make the SVGs heavier; bounded to titles and figures.

## Success criteria

- No generated SVG root declares `width="100%"`; every root has a width and a height.
- No SVG text under 20 units.
- On GitHub at a 360 px column, every half tile stacks and no text renders under 12 px.
- Every section has at least one sentence of native text.
