"""Narrative-field translation with a committed cache (ADR-004).

Public surface:
- ``Translation`` dataclass (fr, en, fr_hash, manual, reviewed).
- ``Translator(cache_dir, translate_fn)`` resolves a French string to its
  English translation, caching the result on disk so the backend (DeepL) is
  only called when the source changes.

The DeepL call is injected as ``translate_fn`` so the cache logic is testable
without any network. The cache is content-keyed by a SHA-256 of the French
source: a cache hit (same hash) skips the backend; a ``manual`` entry is never
overwritten; ``reviewed`` is preserved across hits.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path


@dataclass(frozen=True)
class Translation:
    fr: str
    en: str
    fr_hash: str
    manual: bool
    reviewed: bool


def _hash(fr: str) -> str:
    return sha256(fr.encode("utf-8")).hexdigest()


class Translator:
    def __init__(self, cache_dir: Path, translate_fn: Callable[[str], str]) -> None:
        self._cache_dir = Path(cache_dir)
        self._translate_fn = translate_fn

    def translate(self, key: str, fr: str) -> Translation:
        path = self._cache_dir / f"{key}.en.json"
        fr_hash = _hash(fr)

        if path.exists():
            cached = json.loads(path.read_text(encoding="utf-8"))
            if cached.get("manual"):
                return Translation(
                    fr,
                    cached["en"],
                    cached.get("fr_hash", ""),
                    True,
                    cached.get("reviewed", False),
                )
            if cached.get("fr_hash") == fr_hash:
                return Translation(
                    fr,
                    cached["en"],
                    fr_hash,
                    False,
                    cached.get("reviewed", False),
                )

        en = self._translate_fn(fr)
        record = {"fr_hash": fr_hash, "en": en, "manual": False, "reviewed": False}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return Translation(fr, en, fr_hash, False, False)
