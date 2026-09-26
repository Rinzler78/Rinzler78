# ADR-007 — Display type outlined to vector paths

- **Status**: Accepted (typeface amended by [ADR-009](0009-visual-redesign-devtool-direction.md); outlined scope extended by [ADR-015](0015-front-page-v2-grid-palette-type.md))
- **Date**: 2026-06-01

> **Amended 2026-09-23 ([ADR-009](0009-visual-redesign-devtool-direction.md)):** the
> font→path outlining described below is **kept**; only the typeface changes, from
> Fraunces to **Inter Display** (OFL-1.1). An earlier draft of ADR-009 proposed
> dropping the outlining along with the serif — which would have been
> self-defeating, since the constraint analyzed in *Context* is exactly why it exists:
> GitHub loads no web font inside an `<img>`, so an un-outlined "Inter" renders as
> whatever sans the visitor's OS supplies. Body text stays system-safe.

## Context

GitHub renders the README SVGs through an `<img>` tag inside a sandbox that **loads no external web font** and **strips `@font-face`** (camo / sanitization). The SVGs declare `font-family: 'Inter'` / `'JetBrains Mono'` with a `system-ui` / `monospace` fallback: in practice every visitor sees **their own OS font**, not the one we picked. Real typographic control is therefore nil today.

The redesign aims for a **distinctive, premium** hero ("make a visitor's eyes pop"), and display typography is the #1 lever of that perception. The hero leads with the **signature arc** `embedded → mobile → cloud → ai` and the name, set in **Fraunces** (an editorial high-contrast serif, rare in dev profiles) — a face the GitHub sandbox will never serve as live text.

## Decision

**Outline to `<path>` vectors, at generation time, only the hero's display text** (the name + the arc step labels), in the chosen display face (**Fraunces**, SIL OFL).

- `generate.py` embeds the font file and converts the title glyphs to paths at build (a font→path step, e.g. via `fonttools`). Deterministic: same font + same text → same paths (preserves the `test_generation.py` 2-runs-identical guard).
- **Body text** (labels, values, mono details, status row) **stays in system-safe fonts** (`system-ui` / `-apple-system` / `monospace`). We do not outline everything — only where the "wow" is decided. This bounds the pipeline cost and the SVG weight.

## Considered options

- **Keep web `font-family` (Inter/JetBrains)** — deceptive status quo: rendering depends on the visitor's OS, no control, quality ceiling incompatible with the goal.
- **`@font-face` base64 inline** — tempting, but GitHub strips embedded CSS in SVG-as-`<img>` → unreliable.
- **Outline everything (body included)** — markedly heavier SVGs, non-selectable / non-translatable text everywhere, pipeline cost out of proportion for labels nobody judges to the font.
- **System-safe everywhere, titles included** — zero risk but an indistinct hero ("like everyone else"); sacrifices the primary goal.

## Consequences

**Positive**
- **Identical rendering for every visitor**, total typographic control over the hero.
- Unlocks a distinctive visual identity (editorial serif) otherwise impossible on GitHub.

**Negative**
- A font→path step in `generate.py` (glyph-conversion dependency) + Fraunces TTF committed to the repo (SIL OFL — embedding allowed).
- Outlined title text is **not selectable and not read as text** by default: accessibility then rests entirely on the SVG `aria-label` / `<title>` / `<desc>` (already present — to be maintained rigorously, and covered by i18n alt-text).
- Slightly heavier hero SVGs (paths > text). Acceptable, bounded to the hero.

## Success criteria

- The name + arc display in Fraunces **identically** on GitHub light and dark, regardless of the visitor's OS.
- `aria-label` / `<title>` / `<desc>` cover 100% of the outlined text (no accessibility regression).
- Body text stays system-safe (no drift toward full-outline).
