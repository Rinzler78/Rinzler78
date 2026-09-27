# ADR-017 — Author statement as an evidence kind

- **Status**: Accepted
- **Date**: 2026-09-27
- **Amends**: [ADR-014](0014-claims-evidence-registry.md) (admission rule)

## Context

ADR-014 admits a statement only with a public source, a measured artefact or a private
attestation pointing to evidence the author holds. Reviewing the published claims one by
one, some facts of the author's own career turned out to have no document behind them:
the size of a team he managed, for instance, when the team worked in repositories that
are no longer reachable and no organization chart was kept. Such a fact is neither
invented nor provable; under ADR-014 it could only be removed.

Measured evidence settles part of these cases. The commits of one employer's
repositories showed eight distinct contributors between 2015 and 2020, six active in
2019, which supports the team size stated for that employer. The other employer's
repositories showed a single contributor besides the author, which neither confirms nor
refutes the team size he states for it.

## Decision

A fourth evidence kind, `author_statement`, is admitted in the private registry. Each
use is a registry entry like any other: identifier, wording in both languages, kind, a
pointer recording when and in which context the statement was made, date. Every entry
of this kind declares a **scope**:

- `career` — facts of the author's own career that no document, measurement or public
  source can establish: a team size, a role, a scope of responsibility. They carry no
  mark on the page; the method section states once that some facts rest on the
  author's statement.
- `impact` — figures of impact or usage (availability, units deployed, satisfaction,
  delivery time) for which the author holds no evidence. Each such wording **must
  carry a visible mark** in both languages — "(selon l'auteur)" / "(per the author)" —
  so a reader can tell it from a proven figure. The check refuses to lock an `impact`
  statement whose wording lacks the mark; since the mark is part of the wording, the
  lock hash then keeps it on the page.

The lock file carries no kind and no scope.

## Considered options

- **Keep ADR-014 unchanged** — removes true facts only because their evidence is lost.
- **Mark every author statement on the page** — a team size labelled as declared reads
  as doubtful; career facts carry the caveat once, in the method section.
- **Admit impact figures without a mark** — nothing would tell them from measured ones;
  a reader who checks one and finds nothing doubts the whole page. Rejected by the
  author.

## Consequences

**Positive**
- True career facts without surviving documents can be published, and every one is
  traceable in the registry.

**Negative**
- The guarantee weakens from "provable" to "provable or stated by the author"; for
  impact figures the page says so next to the figure.

## Success criteria

- The claims check accepts `author_statement` with a scope and rejects unknown kinds.
- Every `impact` author statement on the page carries the mark in both languages.
