#!/usr/bin/env python3
"""
translate.py — Populate the bilingual i18n cache and localize data (ADR-004).

For each translatable narrative field, this writes two pure-language files
under ``i18n-cache/`` (repo root, outside ``data/`` so each cspell config can
check its own language):

- ``<entity>/<key>.fr.txt`` — the French source (checked by cspell-fr)
- ``<entity>/<key>.en.json`` — the English translation + metadata (cspell-en),
  maintained by ``scripts/translator.Translator``.

Run it to refresh the cache (it calls DeepL only on a cache miss):

    python scripts/translate.py

``localize_data(data, cache_dir)`` returns a deep copy of the data bag with
every translatable field swapped to its cached English value (falling back to
the French source when a translation is missing), so the generator can render
the EN profile without a network call or an API key.
"""

from __future__ import annotations

import copy
import json
import pathlib
import re
import sys
from collections.abc import Callable

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.translator import Translator  # noqa: E402

DATA = _REPO_ROOT / "data"
CACHE = _REPO_ROOT / "i18n-cache"

# Collections (data/<entity>.json is a list of items with an `id`):
# entity -> translatable narrative field names.
TRANSLATABLE: dict[str, list[str]] = {
    "services": ["title", "short_description"],
    "modes": ["label", "description"],
    "methodology": ["title", "body"],
    "projects": ["description"],
    "domains": ["label"],
    "timeline": ["label", "description"],
    "experiences": ["role", "note"],
    "techs": ["notes"],
}

# Singletons (data/<entity>.json is an object): entity -> dotted field paths.
SINGLETONS: dict[str, list[str]] = {
    "profile": ["role", "tagline"],
    "content": [
        "approach.paragraph",
        "beyond_code.paragraph",
        "parcours.blockquote",
        "map.subheader",
    ],
}


def _get(obj: dict, path: str):
    cur = obj
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _set(obj: dict, path: str, value) -> None:
    parts = path.split(".")
    cur = obj
    for part in parts[:-1]:
        cur = cur[part]
    cur[parts[-1]] = value


def _singleton_key(path: str) -> str:
    return path.replace(".", "__")


def _item_key(item: dict) -> str:
    """Stable, filesystem-safe key for a collection item (id, else year)."""
    raw = str(item.get("id") or item.get("year") or "")
    return re.sub(r"[^A-Za-z0-9_-]", "_", raw)


def _write_fr_mirror(cache_dir: pathlib.Path, entity: str, key: str, fr: str) -> None:
    fr_file = cache_dir / entity / f"{key}.fr.txt"
    fr_file.parent.mkdir(parents=True, exist_ok=True)
    fr_file.write_text(fr + "\n", encoding="utf-8")


def translate_collection(
    entity: str,
    items: list[dict],
    fields: list[str],
    cache_dir: pathlib.Path,
    translate_fn: Callable[[str], str],
) -> int:
    """Translate the given fields of each item, writing pure-language files."""
    translator = Translator(cache_dir / entity, translate_fn)
    count = 0
    for item in items:
        for field in fields:
            fr = item.get(field)
            if not fr:
                continue
            key = f"{_item_key(item)}__{field}"
            translator.translate(key, fr)
            _write_fr_mirror(cache_dir, entity, key, fr)
            count += 1
    return count


def translate_singleton(
    entity: str,
    obj: dict,
    paths: list[str],
    cache_dir: pathlib.Path,
    translate_fn: Callable[[str], str],
) -> int:
    """Translate the given dotted paths of a singleton object."""
    translator = Translator(cache_dir / entity, translate_fn)
    count = 0
    for path in paths:
        fr = _get(obj, path)
        if not isinstance(fr, str) or not fr:
            continue
        key = _singleton_key(path)
        translator.translate(key, fr)
        _write_fr_mirror(cache_dir, entity, key, fr)
        count += 1
    return count


def _load_en(cache_dir: pathlib.Path, entity: str, key: str) -> str | None:
    path = cache_dir / entity / f"{key}.en.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8")).get("en")
    return None


def localize_data(data: dict, cache_dir: pathlib.Path) -> dict:
    """Deep-copy the data bag, swapping translatable fields to cached English.

    Missing translations fall back to the French source.
    """
    out = copy.deepcopy(data)
    for entity, fields in TRANSLATABLE.items():
        for item in out.get(entity, []):
            for field in fields:
                if item.get(field):
                    en = _load_en(cache_dir, entity, f"{_item_key(item)}__{field}")
                    if en:
                        item[field] = en
    for entity, paths in SINGLETONS.items():
        obj = out.get(entity)
        if not isinstance(obj, dict):
            continue
        for path in paths:
            if isinstance(_get(obj, path), str):
                en = _load_en(cache_dir, entity, _singleton_key(path))
                if en:
                    _set(obj, path, en)
    return out


def main() -> int:
    from scripts.deepl_backend import load_api_key, make_deepl_translate_fn

    translate_fn = make_deepl_translate_fn(load_api_key())
    total = 0
    for entity, fields in TRANSLATABLE.items():
        items = json.loads((DATA / f"{entity}.json").read_text(encoding="utf-8"))
        n = translate_collection(entity, items, fields, CACHE, translate_fn)
        print(f"[translate.py] {entity}: {n} fields")
        total += n
    for entity, paths in SINGLETONS.items():
        obj = json.loads((DATA / f"{entity}.json").read_text(encoding="utf-8"))
        n = translate_singleton(entity, obj, paths, CACHE, translate_fn)
        print(f"[translate.py] {entity}: {n} fields")
        total += n
    print(f"[translate.py] OK — {total} fields cached under {CACHE}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
