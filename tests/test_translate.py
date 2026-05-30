# cspell:ignore logicielle
from scripts.translate import TRANSLATABLE, translate_collection


def _fake(fr: str) -> str:
    return f"EN[{fr}]"


def test_translate_collection_writes_pure_language_files(tmp_path):
    items = [
        {"id": "architecture", "title": "Architecture logicielle", "priority": 1},
    ]

    written = translate_collection(
        "services", items, ["title"], cache_dir=tmp_path, translate_fn=_fake
    )

    # pure-FR mirror (cspell-fr target) and EN cache (cspell-en target)
    fr_file = tmp_path / "services" / "architecture__title.fr.txt"
    en_file = tmp_path / "services" / "architecture__title.en.json"
    assert fr_file.read_text(encoding="utf-8").strip() == "Architecture logicielle"
    assert "EN[Architecture logicielle]" in en_file.read_text(encoding="utf-8")
    assert written == 1


def test_translate_collection_skips_non_translatable_and_missing(tmp_path):
    items = [
        {"id": "a", "title": "Titre", "priority": 1},
        {"id": "b", "priority": 2},  # no title field
    ]

    written = translate_collection(
        "services", items, ["title"], cache_dir=tmp_path, translate_fn=_fake
    )

    assert written == 1  # only item a had a title
    assert not (tmp_path / "services" / "b__title.fr.txt").exists()


def test_translatable_map_covers_the_content_entities():
    # The clean first-class content entities must be translatable.
    assert "services" in TRANSLATABLE
    assert "modes" in TRANSLATABLE
    assert "methodology" in TRANSLATABLE
    assert set(TRANSLATABLE["services"]) == {"title", "short_description"}
