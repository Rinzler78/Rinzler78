#!/usr/bin/env python3
"""
translate.py — Populate the bilingual i18n cache (ADR-004).

For each translatable narrative field of the data collections, this writes two
pure-language files under ``i18n-cache/`` (repo root, outside ``data/`` so each
cspell config can check its own language):

- ``<entity>/<id>__<field>.fr.txt`` — the French source (checked by cspell-fr)
- ``<entity>/<id>__<field>.en.json`` — the English translation + metadata
  (checked by cspell-en), maintained by ``scripts/translator.Translator``.

Run it to refresh the cache (it calls DeepL only on a cache miss):

    python scripts/translate.py

The committed cache means the generator can render the EN README without a
network call or an API key; DeepL is only needed when a French source changes.
"""

from __future__ import annotations

import json
import pathlib
import sys
from collections.abc import Callable

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.translator import Translator  # noqa: E402

DATA = _REPO_ROOT / "data"
CACHE = _REPO_ROOT / "i18n-cache"

# entity (data/<entity>.json) -> translatable narrative field names
TRANSLATABLE: dict[str, list[str]] = {
    "services": ["title", "short_description"],
    "modes": ["label", "description"],
    "methodology": ["title", "body"],
}


def translate_collection(
    entity: str,
    items: list[dict],
    fields: list[str],
    cache_dir: pathlib.Path,
    translate_fn: Callable[[str], str],
) -> int:
    """Translate the given fields of each item, writing pure-language files.

    Returns the number of fields translated.
    """
    translator = Translator(cache_dir / entity, translate_fn)
    count = 0
    for item in items:
        item_id = item["id"]
        for field in fields:
            fr = item.get(field)
            if not fr:
                continue
            key = f"{item_id}__{field}"
            translator.translate(key, fr)
            fr_file = cache_dir / entity / f"{key}.fr.txt"
            fr_file.parent.mkdir(parents=True, exist_ok=True)
            fr_file.write_text(fr + "\n", encoding="utf-8")
            count += 1
    return count


def main() -> int:
    from scripts.deepl_backend import load_api_key, make_deepl_translate_fn

    translate_fn = make_deepl_translate_fn(load_api_key())
    total = 0
    for entity, fields in TRANSLATABLE.items():
        path = DATA / f"{entity}.json"
        items = json.loads(path.read_text(encoding="utf-8"))
        n = translate_collection(entity, items, fields, CACHE, translate_fn)
        print(f"[translate.py] {entity}: {n} fields")
        total += n
    print(f"[translate.py] OK — {total} fields cached under {CACHE}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
