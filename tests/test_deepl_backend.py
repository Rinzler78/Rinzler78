"""Behavior specs for the production DeepL backend.

The ``deepl`` package is not a test dependency: a fake module is injected into
``sys.modules`` so the factory's lazy ``import deepl`` resolves to the fake and
no network call is ever made.
"""
# cspell:ignore logicielle
# "Architecture logicielle" below is a deliberate French translation input.

import sys
import types

import pytest

from scripts.deepl_backend import load_api_key, make_deepl_translate_fn


class _FakeTextResult:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeDeeplClient:
    """Records construction and translate_text calls, returns a .text object."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.calls: list[dict[str, str]] = []

    def translate_text(
        self, text: str, *, source_lang: str, target_lang: str
    ) -> _FakeTextResult:
        self.calls.append(
            {"text": text, "source_lang": source_lang, "target_lang": target_lang}
        )
        return _FakeTextResult(f"<en>{text}</en>")


@pytest.fixture
def fake_deepl(monkeypatch):
    """Install a fake ``deepl`` module exposing a captured Translator instance."""
    captured: dict[str, _FakeDeeplClient] = {}

    def _translator_factory(api_key: str) -> _FakeDeeplClient:
        client = _FakeDeeplClient(api_key)
        captured["client"] = client
        return client

    module = types.ModuleType("deepl")
    module.Translator = _translator_factory
    monkeypatch.setitem(sys.modules, "deepl", module)
    return captured


def test_factory_returns_translated_text(fake_deepl):
    translate = make_deepl_translate_fn(api_key="key-123")

    result = translate("Architecture logicielle")

    assert result == "<en>Architecture logicielle</en>"


def test_factory_passes_default_langs(fake_deepl):
    translate = make_deepl_translate_fn(api_key="key-123")

    translate("Bonjour")

    call = fake_deepl["client"].calls[-1]
    assert call["source_lang"] == "FR"
    assert call["target_lang"] == "EN-US"


def test_factory_passes_custom_langs(fake_deepl):
    translate = make_deepl_translate_fn(
        api_key="key-123", source_lang="DE", target_lang="EN-GB"
    )

    translate("Hallo")

    call = fake_deepl["client"].calls[-1]
    assert call["source_lang"] == "DE"
    assert call["target_lang"] == "EN-GB"


def test_factory_forwards_api_key_to_client(fake_deepl):
    make_deepl_translate_fn(api_key="secret-key")

    assert fake_deepl["client"].api_key == "secret-key"


def test_load_api_key_reads_environment(monkeypatch):
    monkeypatch.setenv("DEEPL_API_KEY", "from-env:fx")

    assert load_api_key() == "from-env:fx"


def test_load_api_key_missing_raises(monkeypatch, tmp_path):
    monkeypatch.delenv("DEEPL_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="DEEPL_API_KEY"):
        load_api_key(env_path=tmp_path / "absent.env")


def test_load_api_key_reads_env_file(monkeypatch, tmp_path):
    monkeypatch.delenv("DEEPL_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# DeepL config\n\nOTHER=ignored\nDEEPL_API_KEY=from-file:fx\n",
        encoding="utf-8",
    )

    assert load_api_key(env_path=env_file) == "from-file:fx"


def test_load_api_key_strips_quotes_in_env_file(monkeypatch, tmp_path):
    monkeypatch.delenv("DEEPL_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text('DEEPL_API_KEY="quoted-key"\n', encoding="utf-8")

    assert load_api_key(env_path=env_file) == "quoted-key"


def test_load_api_key_env_takes_precedence_over_file(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPL_API_KEY", "env-wins")
    env_file = tmp_path / ".env"
    env_file.write_text("DEEPL_API_KEY=file-loses\n", encoding="utf-8")

    assert load_api_key(env_path=env_file) == "env-wins"
