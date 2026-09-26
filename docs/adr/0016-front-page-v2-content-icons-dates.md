# ADR-016 — Front page v2: content sections, tech icons, two reference dates

- **Status**: Accepted
- **Date**: 2026-09-26
- **Amends**: [ADR-011](0011-committed-reference-date.md) (one reference date becomes two),
  [ADR-013](0013-activity-timeline-evidence-hours.md) (tools every commit implies),
  [ADR-015](0015-front-page-v2-grid-palette-type.md) (identity band, sections, visuals)
- **Related to**: [ADR-004](0004-i18n-bilingual-readme.md), [ADR-008](0008-in-repo-multipage.md),
  [ADR-014](0014-claims-evidence-registry.md)

## Context

The v2 prototype (branch `prototype/front-v2`) was rendered on GitHub and its visual
direction accepted: acid-green palette, 415 px tiles, outlined titles and figures, the
activity calendar. The review of its content raised the points this ADR settles:

- A section titled as proof, introduced by a sentence justifying itself, reads as
  defensive. The figures must be shown, not announced.
- Counters were written into the text by hand; a hand-written counter is wrong the day
  after it is written.
- The skills tiles showed 20 of 34 catalogued techs, without icons; Windows CE and
  Windows Mobile sat outside mobile development, and Android was missing.
- The timeline ran from oldest to newest, and repeated descriptions that also belong
  to the achievements.
- Measured on GitHub at a 360 px column, the full-width identity tile renders at scale
  0.3 — about 6 px for 20-unit text — while stacked half tiles stay near 12 px.
- Hours now come from a collection the author runs locally (ADR-013), while external
  counters can be refreshed by CI; a single `as_of` cannot date both.
- Under ADR-013 every counted day is a commit day, so a tool such as Git would score
  all hours: the figure carries no information.

## Decision

### 1. Page order

1. **Identity** as two half tiles — name, role and availability; key figures — side by
   side on desktop, stacked on a phone. Contacts are native links.
2. **How I can help** — the offer, native text.
3. **Achievements** — shipped products, mission deliveries, private projects, studies;
   newest first, each with a context label. Only attested claims (ADR-014).
4. **Open source** — public projects with their counters (section 3).
5. **Skills** — an icon band, then one tile per domain (section 4).
6. **Timeline** — newest first; one line per position: where and when. What was done
   lives in *Achievements* only; each line links to its anchor on the journey page.
7. **Method** and **Activity** — the in-house calendar, then the GitHub contribution
   snake and a streak widget, both in the green palette and labelled as what GitHub
   sees.
8. **Signature** — both reference dates (section 5).

Sections are named by their content. No heading or sentence presents content as proof.

### 2. Detail pages

One page per nature: journey (grouped by company, then client, one anchor per
organization), achievements, projects (open source and private), stack, working with
me. The English version ships in the same change as the French one (ADR-004); new
machine translations start as `reviewed: false`.

### 3. External counters

PyPI downloads and releases, Docker Hub pulls and repository stars are fetched **daily**
by the update workflow and written with their fetch date. Tiles show the fetched values;
live shields.io badges sit beside them. No counter is typed by hand.

### 4. Skills and icons

- Every tech at or above 50 hours appears on the front page: the first five of a domain
  as bars (hours, level, period, last use), the others on one compact line.
- Mobile development gathers Android, Xamarin, Xamarin.Forms (two techs), iOS /
  Objective-C, Windows Mobile and Windows CE.
- **Icon band**, at the head of the skills section: skillicons.dev for the icons it
  serves, in-house icons on the same template (256-unit rounded square, `#242938` dark,
  `#F4F2ED` light) for the others. Measured on 2026-09-26: skillicons.dev returns an
  empty image for Xamarin, Objective-C, Blazor, Anthropic, Claude, Bluetooth and NFC.
- **Icons in the tiles**: brand colors, drawn from vendored Devicon (MIT) and Simple
  Icons (CC0) paths, since an SVG loaded through `<img>` cannot load another image. A
  logo whose brand color fails contrast on the theme background uses its official light
  or dark variant. Techs without a published logo get an initials badge.
- **Tools every commit implies** (Git) get no hours and no tile line; they appear in the
  icon band only.

### 5. Two reference dates

- **Activity date** — the day of the author's last local collection. Hours, levels,
  periods and "active / last used" are computed against it.
- **Counters date** — the day of the last CI fetch.

The footer shows both. No duration is computed against a date later than its data.

## Considered options

- **One `as_of` moved daily** — the current year's hours would stay frozen between
  collections while "active" moved on. Rejected.
- **Achievements folded into the timeline** — one section, but the pyramid order (what
  was done, then where) is lost. Rejected.
- **One detail page per organization** — about fifteen pages, doubled in English.
  Rejected.
- **skillicons.dev only** — omits the author's most distinctive techs. Rejected.
- **Monochrome icons in tiles** — keeps one accent; the author chose brand colors for
  recognition.
- **Git with hours** — trivial (all hours) or arbitrary. Rejected.

## Consequences

**Positive**
- Every figure on the page carries its source and date; none is typed by hand.
- The full catalogue above the display threshold is visible without leaving the page.

**Negative**
- The update workflow commits up to once a day to the default branch.
- Vendored icon paths add weight to the skills tiles and must be refreshed by hand.
- Two external services (skillicons.dev, the streak widget) can be unavailable; the
  page keeps its own calendar and native text either way.

## Success criteria

- No heading or sentence in the generated pages presents content as proof.
- No external counter appears in `data/` or templates except through the fetched
  metrics file.
- Every tech with at least 50 hours in the aggregates appears on the front page, with
  an icon.
- Timeline and achievements are ordered newest first.
- The footer shows two dates, and no "active" label is later than the activity date.
