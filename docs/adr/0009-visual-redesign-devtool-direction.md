# ADR-009 — Visual redesign: a dense, chart-led showcase

- **Status**: Accepted
- **Date**: 2026-06-03, rewritten 2026-09-23
- **Amends**: [ADR-003](0003-data-schema-collections-and-derived-views.md) (display posture), [ADR-007](0007-display-type-outlined-to-paths.md) (display typeface), [ADR-008](0008-in-repo-multipage.md) (what the front page carries)
- **Related to**: [ADR-001](0001-data-driven-svg-generation.md), [ADR-006](0006-hours-based-expertise-model.md)

## Context

The first generated profile shipped an editorial, light-first identity: paper/ink
palette, a warm coral accent, a high-contrast serif outlined to paths for the hero
(ADR-007), and — following ADR-008 — a **lean front page** delegating the substance
to four detail pages.

The owner reviewed it against the live profile it was to replace and judged it
**weaker**: *"less information and less visual"*. Measured, the gap is not subtle:

| | Live page | Generated front page |
| --- | --- | --- |
| Sections | **13** | **1** ("Explorer", a list of four links) |

This repo's output is a **commercial showcase**. Its judge is a prospect who gives it
thirty seconds and never clicks. Against that judge, "lean" is not restraint, it is
absence — the detail pages may as well not exist.

The first draft of this ADR made the problem worse. Reasoning from internal design
goals — palette coherence, "no third-party widgets", "one device per intention" — it
decided to *remove* the animated tagline, the activity block, the contribution graph
and the badge row. Each removal was locally defensible; the sequence was wrong,
because arguments from internal consistency are always available and always point the
same way. A removal is only an improvement when something stronger takes the place.

## Decision

A **dense, chart-led showcase**. Four levers, all of them, together:

| Lever | What it means here |
| --- | --- |
| Visual density | The first screen is full and alive — not a hero above a link list |
| Signature data-viz | The 20-year domain timeline and the career arc: things no other profile has |
| Execution refinement | Typography, depth, gradients — premium-product finish |
| Engineering proof | The repo itself on display: pipeline, tests, CI, ADRs |

1. **The front page carries the substance.** Reverses ADR-008's lean front. Detail
   pages go *deeper*; they no longer *replace*. Target: at least as many sections as
   the page being replaced.

2. **Standard chart forms, one per question.** A 100 % stacked area for "what was he
   doing then", a donut for "how is the whole split", ranked bars for "what is
   strongest". Standard forms read without instruction; an invented device asks for an
   effort a showcase visitor will not make. Never the same device twice — that
   monotony is what triggered the redesign in the first place.

3. **Every chart is doubled by text.** A reader who only reads prose must still get
   the point. This is not decoration: GitHub serves README SVGs inside an `<img>`, so
   **no JavaScript runs** — there is no hover, no tooltip, no second render. Direct
   labels, a `<title>` and a value-listing `aria-label` are the only reading aids
   available, and they are also the relief the light-mode contrast warning requires.

4. **Posture: dark-first.** The dark palette becomes primary (served by the `<img>`
   fallback at the root); light becomes the `prefers-color-scheme: light` override.
   Reverses the light-first flip that followed ADR-003. The `<picture>` mechanism is
   unchanged — only the default swaps. SVG backgrounds match the GitHub canvas
   (`#0d1117` / `#ffffff`) so the views sit in the page rather than on it.

5. **Accent: indigo for the interface, a validated palette for data.** Indigo leads
   the UI (hero rule, meters, links); coral is kept as the **arc origin** and for geek
   microcopy. Series colors are a separate concern and come from a
   CVD-validated categorical palette: an indigo/coral-led set measures ΔE 1.5 between
   coral and aqua under protanopia — two series a colorblind reader cannot separate.
   Brand identity never overrides that.

6. **Self-generated visuals only.** Third-party widgets are replaced by in-house
   equivalents, never simply deleted. The rule is directional: a widget goes when
   something stronger stands in its place. Two of the three in use were returning 503
   and 402 when this was written, which is the uptime argument making itself.

7. **Typography: outlined display, system-safe body.** The hero name and arc stay
   **outlined to paths** — ADR-007's mechanism is *kept*, its typeface replaced.
   Fraunces gives way to **Inter Display** (OFL-1.1). Dropping the outlining would have
   been pointless: GitHub loads no web font in an `<img>`, so an un-outlined "Inter"
   renders as whatever sans the visitor's OS supplies. Body text stays system-safe.

8. **Geek as subordinated texture.** Terminal prompts, `boot_log`, monospace labels and
   the C# profile-as-code stay — the last moves to the front page, collapsed, above the
   footer. Always subordinate to legibility.

## Considered options

- **Keep the lean front and make the detail pages excellent** — respects ADR-008.
  Rejected: it optimizes for the reader who clicks, and the judge does not click.
- **Restore the third-party widgets** — cheapest way back to density. Rejected: two
  were down at the time of writing, and their styling cannot be made coherent.
- **A single signature visualization, richly executed** — one strong idea instead of
  many. Rejected: it answers one question, and the page has to answer several.
- **Invented visual devices over standard chart forms** — more distinctive. Rejected:
  distinctiveness bought with a reading cost, paid by a visitor who will not pay it.
- **Brand-colored data series** — palette unity. Rejected on measurement, not taste:
  the CVD validator fails the set.

## Consequences

**Positive**
- The front page answers a prospect's questions without a click.
- Standard forms plus doubled text make it legible to non-technical and technical
  readers alike, and to a screen reader.
- Self-generated visuals remove third-party uptime and styling risk.
- Charts and scores derive from the same exposure hours, so they cannot disagree.

**Negative**
- A dense page is long. Order matters more than it did, and a weak section is now
  visible rather than hidden behind a link.
- Full re-theme: new palette, every template re-skinned, both READMEs and all pages
  regenerated.
- Reverses parts of three accepted ADRs (003 posture, 007 typeface, 008 front-page
  scope). The Fraunces TTF is replaced, not the outlining step.
- Charts must be correct at write time, with no interaction layer to compensate — so
  their geometry carries build-time guards (see `tests/test_charts.py`).

## Open items

- Final section order on the front page.
- Exact indigo steps for both modes, WCAG AA verified against the GitHub canvas.
- Whether the domain heatmap survives alongside the stacked area, or the area replaces
  it (both read the same `domain_years` series).

## Success criteria

- The front page carries at least as many sections as the page it replaces (13).
- No section repeats another section's visual device.
- Every chart is readable without JavaScript and is doubled by a text conclusion.
- The categorical palette passes the CVD validator in both modes.
- Zero third-party rendering widgets remain; generation stays deterministic.
