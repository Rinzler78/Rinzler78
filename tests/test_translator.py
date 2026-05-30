# cspell:ignore Bonjour Bonsoir Salut Texte logicielle complètement différent
# French fixtures below are deliberate translation inputs.
import json

from scripts.translator import Translator, _hash


class _Counter:
    """Fake DeepL: records calls and returns a deterministic pseudo-EN."""

    def __init__(self):
        self.calls = []

    def __call__(self, fr: str) -> str:
        self.calls.append(fr)
        return f"EN[{fr}]"


def test_cache_miss_calls_translator_and_writes_cache(tmp_path):
    fake = _Counter()
    tr = Translator(cache_dir=tmp_path, translate_fn=fake)

    result = tr.translate("services/architecture__title", "Architecture logicielle")

    assert result.en == "EN[Architecture logicielle]"
    assert result.manual is False
    assert result.reviewed is False
    assert fake.calls == ["Architecture logicielle"]
    # cache file written
    cache = tmp_path / "services" / "architecture__title.en.json"
    assert cache.exists()


def test_cache_hit_same_source_skips_backend(tmp_path):
    fake = _Counter()
    tr = Translator(cache_dir=tmp_path, translate_fn=fake)

    tr.translate("k", "Bonjour")  # miss → 1 call
    again = tr.translate("k", "Bonjour")  # hit → no call

    assert again.en == "EN[Bonjour]"
    assert len(fake.calls) == 1


def test_changed_source_retranslates(tmp_path):
    fake = _Counter()
    tr = Translator(cache_dir=tmp_path, translate_fn=fake)

    tr.translate("k", "Bonjour")
    result = tr.translate("k", "Bonsoir")  # different fr → retranslate

    assert result.en == "EN[Bonsoir]"
    assert fake.calls == ["Bonjour", "Bonsoir"]


def test_manual_entry_is_never_overwritten(tmp_path):
    fake = _Counter()
    tr = Translator(cache_dir=tmp_path, translate_fn=fake)
    # seed a manual cache entry with a stale fr_hash
    cache = tmp_path / "k.en.json"
    cache.write_text(
        json.dumps(
            {"fr_hash": "stale", "en": "Hand-tuned", "manual": True, "reviewed": True}
        ),
        encoding="utf-8",
    )

    result = tr.translate("k", "Texte complètement différent")

    assert result.en == "Hand-tuned"  # backend NOT called, manual kept
    assert result.manual is True
    assert result.reviewed is True
    assert fake.calls == []


def test_reviewed_flag_preserved_on_hit(tmp_path):
    fake = _Counter()
    tr = Translator(cache_dir=tmp_path, translate_fn=fake)
    cache = tmp_path / "k.en.json"
    fr = "Salut"
    cache.write_text(
        json.dumps(
            {"fr_hash": _hash(fr), "en": "Hi", "manual": False, "reviewed": True}
        ),
        encoding="utf-8",
    )

    result = tr.translate("k", fr)

    assert result.en == "Hi"
    assert result.reviewed is True
    assert fake.calls == []
