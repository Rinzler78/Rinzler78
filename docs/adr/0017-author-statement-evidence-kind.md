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

A fourth evidence kind, `author_statement`, is admitted in the private registry:

- it applies to facts of the author's **own career** that no document, measurement or
  public source can establish — a team size, a role, a scope of responsibility;
- each use is a registry entry like any other: identifier, wording in both languages,
  kind, a pointer recording when and in which context the statement was made, date;
- the lock file carries no kind, so the page does not distinguish it from other
  attested claims; the method section states that some facts rest on the author's
  statement.

It never applies to figures of impact or usage that a measurement could establish
(downloads, units sold, availability, satisfaction, performance ratios): those stay
under the three original kinds.

## Considered options

- **Keep ADR-014 unchanged** — removes true facts only because their evidence is lost.
- **Mark such claims "declared" on the page** — a team size labelled as declared reads
  as doubtful; the method section carries the caveat once instead.

## Consequences

**Positive**
- True career facts without surviving documents can be published, and every one is
  traceable in the registry.

**Negative**
- The guarantee weakens from "provable" to "provable or stated by the author" for
  career facts; the exclusion of impact figures bounds that weakening.

## Success criteria

- The claims check accepts `author_statement` and rejects unknown kinds.
- No impact or usage figure in the registry uses `author_statement`.
