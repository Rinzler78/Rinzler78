#!/usr/bin/env python3
"""Claims registry check: a claim is published only under an attestation (ADR-014).

A statement that needs evidence is wrapped, in the generated markdown, between
two HTML comments that GitHub does not render::

    <!-- claim:award-2017 -->The product whose apps I built won …<!-- /claim -->

The text between the markers is the claim's *public wording*. Its hash, per
language, is committed in ``data/claims.lock.json`` together with the date it
was attested — never the evidence, its pointer or any other private text.

Two modes:

``python -m scripts.claims check``
    CI mode, no private data needed. Every marker in the generated pages must
    resolve in the lock, and the hash of its wording must match the hash locked
    for the page's language. An unknown identifier or a reworded claim exits
    non-zero. A lock entry no page uses any more is reported as a warning only:
    it attests a wording that is no longer published, which is harmless, and
    the next ``lock`` run prunes it.

``python -m scripts.claims lock``
    Local mode, run by the author. Reads the private registry at
    ``$PROFILE_PRIVATE_DIR/claims.json``, requires an entry with valid evidence
    for every marker in the pages, requires the page wording to equal the
    registry wording, and rewrites the lock with the claims the pages use.
    Registry entries no page uses are never written: their identifiers stay
    private too.

Language is read from the page path: ``README.en.md`` and ``pages/en/`` are
English, every other generated page is French. Both wordings are locked, so
rewording either one needs a new attestation.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import pathlib
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import date

REPO = pathlib.Path(__file__).resolve().parent.parent
LOCK = REPO / "data" / "claims.lock.json"
LOCK_VERSION = 1
PRIVATE_DIR_ENV = "PROFILE_PRIVATE_DIR"
REGISTRY_NAME = "claims.json"
LANGS = ("fr", "en")
EVIDENCE_KINDS = (
    "public_source",
    "measured",
    "private_attestation",
    "author_statement",  # ADR-017: own-career facts nothing else can prove
)

_ID = re.compile(r"[a-z0-9][a-z0-9-]*")
# Loose on purpose: anything that looks like a claim marker is caught, then
# validated strictly, so a typo in a marker fails instead of being ignored.
_TOKEN = re.compile(r"<!--\s*(/?)claim\b(.*?)-->", re.DOTALL)
_OPEN_ARGS = re.compile(r":([^\s]+)\s*")


class ClaimError(Exception):
    """Raised when the pages, the lock or the registry cannot be trusted."""


@dataclass(frozen=True)
class Marker:
    """One occurrence of a claim in a generated page."""

    claim_id: str
    lang: str
    path: str
    line: int
    wording: str

    @property
    def where(self) -> str:
        return f"{self.path}:{self.line}"


@dataclass
class Report:
    """Outcome of ``check``: errors fail the build, warnings do not."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _require_id(claim_id: str) -> str:
    if not _ID.fullmatch(claim_id):
        raise ClaimError(
            f"invalid claim identifier {claim_id!r}: use lowercase letters, "
            "digits and hyphens"
        )
    return claim_id


def mark(claim_id: str, wording: str) -> str:
    """Wrap ``wording`` in the claim markers for ``claim_id``."""
    return f"<!-- claim:{_require_id(claim_id)} -->{wording}<!-- /claim -->"


def normalize(wording: str) -> str:
    """The form a wording is hashed in.

    Entities are decoded (the generator escapes ``&``), Unicode is composed and
    runs of whitespace collapse to one space, so a re-wrap of the template is
    not a rewording. Markdown emphasis is kept: it is part of what is said.
    """
    text = unicodedata.normalize("NFC", html.unescape(wording))
    return " ".join(text.split())


def digest(wording: str) -> str:
    return hashlib.sha256(normalize(wording).encode("utf-8")).hexdigest()


def _lang_of(rel: str) -> str:
    return "en" if rel == "README.en.md" or rel.startswith("pages/en/") else "fr"


def generated_pages(root: pathlib.Path) -> list[pathlib.Path]:
    """The generated markdown a visitor reads: both READMEs and the pages."""
    pages = [root / "README.md", root / "README.en.md"]
    pages += sorted((root / "pages").rglob("*.md"))
    return [p for p in pages if p.is_file()]


def _scan_text(text: str, rel: str) -> list[Marker]:
    found: list[Marker] = []
    open_id: str | None = None
    open_end = open_line = 0
    for token in _TOKEN.finditer(text):
        line = text.count("\n", 0, token.start()) + 1
        closing, args = token.group(1), token.group(2)
        if closing:
            if args.strip():
                raise ClaimError(f"{rel}:{line}: malformed close marker")
            if open_id is None:
                raise ClaimError(f"{rel}:{line}: close marker without an open one")
            wording = text[open_end : token.start()]
            found.append(Marker(open_id, _lang_of(rel), rel, open_line, wording))
            open_id = None
            continue
        args_match = _OPEN_ARGS.fullmatch(args)
        if not args_match or not _ID.fullmatch(args_match.group(1)):
            raise ClaimError(f"{rel}:{line}: malformed claim marker {token.group(0)}")
        if open_id is not None:
            raise ClaimError(f"{rel}:{line}: claim nested inside {open_id!r}")
        open_id, open_end, open_line = args_match.group(1), token.end(), line
    if open_id is not None:
        raise ClaimError(f"{rel}:{open_line}: unclosed claim {open_id!r}")
    return found


def scan_pages(root: pathlib.Path) -> list[Marker]:
    """Every claim marker in the generated pages under ``root``."""
    found: list[Marker] = []
    for page in generated_pages(root):
        rel = page.relative_to(root).as_posix()
        found += _scan_text(page.read_text(encoding="utf-8"), rel)
    return found


def _read_json(path: pathlib.Path, what: str) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ClaimError(f"{what} not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ClaimError(f"{what} is not valid JSON: {path}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("claims"), dict):
        raise ClaimError(f"{what} must be an object with a 'claims' map: {path}")
    return data


def check(root: pathlib.Path, lock_path: pathlib.Path) -> Report:
    """Compare the markers in the pages with the committed lock (CI mode)."""
    locked = _read_json(lock_path, "claims lock")["claims"]
    for claim_id, entry in locked.items():
        if not isinstance(entry, dict) or not isinstance(
            entry.get("wording_sha256"), dict
        ):
            raise ClaimError(
                f"lock entry {claim_id!r} must be an object with a 'wording_sha256' map"
            )
    report = Report()
    markers = scan_pages(root)
    for m in markers:
        entry = locked.get(m.claim_id)
        if entry is None:
            report.errors.append(
                f"{m.where}: claim {m.claim_id!r} is not in the lock — attest it "
                "in the private registry, then run `python -m scripts.claims lock`"
            )
            continue
        expected = entry["wording_sha256"].get(m.lang)
        if expected is None:
            report.errors.append(
                f"{m.where}: claim {m.claim_id!r} has no locked {m.lang} wording"
            )
        elif expected != digest(m.wording):
            report.errors.append(
                f"{m.where}: claim {m.claim_id!r} was reworded ({m.lang}) since "
                f"its attestation on {entry.get('attested', '?')} — re-attest it "
                "or restore the attested wording"
            )
    used = {m.claim_id for m in markers}
    for orphan in sorted(set(locked) - used):
        report.warnings.append(
            f"lock entry {orphan!r} is used by no page; the next lock run prunes it"
        )
    return report


def registry_path() -> pathlib.Path:
    """``$PROFILE_PRIVATE_DIR/claims.json``; no default, never a guess."""
    private = os.environ.get(PRIVATE_DIR_ENV, "").strip()
    if not private:
        raise ClaimError(
            f"{PRIVATE_DIR_ENV} is not set: the lock can only be rewritten "
            "where the private registry is reachable"
        )
    return pathlib.Path(private).expanduser() / REGISTRY_NAME


def _validated(claim_id: str, entry: object) -> dict:
    """Return the lockable part of a registry entry, or fail on weak evidence."""

    def fail(reason: str) -> ClaimError:
        return ClaimError(f"registry entry {claim_id!r}: {reason}")

    if not isinstance(entry, dict):
        raise fail("must be an object")
    wording = entry.get("wording")
    if not isinstance(wording, dict) or not all(
        isinstance(wording.get(lang), str) and wording[lang].strip() for lang in LANGS
    ):
        raise fail(f"wording must give a non-empty text for each of {LANGS}")
    if entry.get("evidence_kind") not in EVIDENCE_KINDS:
        raise fail(f"evidence_kind must be one of {EVIDENCE_KINDS}")
    pointer = entry.get("pointer")
    if not isinstance(pointer, str) or not pointer.strip():
        raise fail("pointer to the evidence is missing")
    attested = entry.get("attested")
    try:
        date.fromisoformat(str(attested))
    except ValueError as exc:
        raise fail("attested must be an ISO date (YYYY-MM-DD)") from exc
    return {"wording": {lang: wording[lang] for lang in LANGS}, "attested": attested}


def build_lock(root: pathlib.Path, registry: pathlib.Path) -> dict:
    """The lock content for the claims the pages use, from the registry."""
    entries = _read_json(registry, "private registry")["claims"]
    claims: dict[str, dict] = {}
    for m in scan_pages(root):
        if m.claim_id not in entries:
            raise ClaimError(
                f"{m.where}: claim {m.claim_id!r} has no entry in the private "
                "registry — it cannot be published unattested"
            )
        entry = _validated(m.claim_id, entries[m.claim_id])
        if normalize(m.wording) != normalize(entry["wording"][m.lang]):
            raise ClaimError(
                f"{m.where}: the {m.lang} wording of claim {m.claim_id!r} differs "
                "from the attested registry wording"
            )
        # Only the hashes and the date cross into the public repository.
        claims[m.claim_id] = {
            "wording_sha256": {lang: digest(entry["wording"][lang]) for lang in LANGS},
            "attested": entry["attested"],
        }
    return {"version": LOCK_VERSION, "claims": dict(sorted(claims.items()))}


def write_lock(
    root: pathlib.Path, registry: pathlib.Path, lock_path: pathlib.Path
) -> dict:
    lock = build_lock(root, registry)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(
        json.dumps(lock, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return lock


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m scripts.claims")
    parser.add_argument("mode", choices=("check", "lock"))
    parser.add_argument("--root", type=pathlib.Path, default=REPO)
    parser.add_argument("--lock", type=pathlib.Path, default=LOCK)
    args = parser.parse_args(argv)
    try:
        if args.mode == "lock":
            lock = write_lock(args.root, registry_path(), args.lock)
            print(f"[claims] lock rewritten: {len(lock['claims'])} claim(s)")
            return 0
        report = check(args.root, args.lock)
    except ClaimError as exc:
        print(f"[claims] error: {exc}", file=sys.stderr)
        return 1
    for warning in report.warnings:
        print(f"[claims] warning: {warning}", file=sys.stderr)
    for error in report.errors:
        print(f"[claims] error: {error}", file=sys.stderr)
    if report.errors:
        return 1
    print(f"[claims] OK: {len(scan_pages(args.root))} marker(s) match the lock")
    return 0


if __name__ == "__main__":
    sys.exit(main())
