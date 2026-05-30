"""Production DeepL backend for the i18n Translator (ADR-004).

Public surface:
- ``make_deepl_translate_fn(api_key, source_lang, target_lang)`` returns a
  ``translate_fn`` (``str -> str``, French to English) suitable for injection
  into ``scripts.translator.Translator``. The ``deepl`` package is imported
  lazily inside the factory so importing this module never requires it.
- ``load_api_key(env_path=None)`` resolves ``DEEPL_API_KEY`` from the process
  environment, falling back to a ``.env`` file at the repo root (or a caller
  provided path). It raises ``RuntimeError`` when the key is absent rather than
  silently degrading.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

_API_KEY_VAR = "DEEPL_API_KEY"
_REPO_ROOT = Path(__file__).resolve().parent.parent


def make_deepl_translate_fn(
    api_key: str,
    source_lang: str = "FR",
    target_lang: str = "EN-US",
) -> Callable[[str], str]:
    """Build a French-to-English ``translate_fn`` backed by the DeepL API.

    The ``deepl`` client is created eagerly (so a bad key fails fast) but the
    import is lazy so this module imports without the package installed.
    """
    import deepl

    client = deepl.Translator(api_key)

    def translate(fr: str) -> str:
        result = client.translate_text(
            fr,
            source_lang=source_lang,
            target_lang=target_lang,
        )
        return result.text

    return translate


def _parse_env_file(env_path: Path) -> dict[str, str]:
    """Parse a ``.env`` file into a dict, ignoring blanks and ``#`` comments."""
    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("'\"")
    return values


def load_api_key(env_path: Path | None = None) -> str:
    """Return the DeepL API key from the environment or a ``.env`` file.

    Resolution order: the ``DEEPL_API_KEY`` process environment variable wins;
    otherwise the ``.env`` file (``env_path`` or the repo-root default) is
    consulted. A missing key raises ``RuntimeError`` (no silent fallback).
    """
    env_value = os.environ.get(_API_KEY_VAR)
    if env_value:
        return env_value

    path = env_path if env_path is not None else _REPO_ROOT / ".env"
    if path.exists():
        file_value = _parse_env_file(path).get(_API_KEY_VAR)
        if file_value:
            return file_value

    raise RuntimeError(
        f"{_API_KEY_VAR} is not set. Export it or add it to a .env file "
        f"(expected at {path})."
    )
