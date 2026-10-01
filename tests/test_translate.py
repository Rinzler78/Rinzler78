# cspell:ignore logicielle français indépendant peux éèàçù
import json

from scripts.translate import (
    SINGLETONS,
    TRANSLATABLE,
    localize_data,
    translate_collection,
    translate_singleton,
)


def _seed_en(cache_dir, entity, key, en):
    path = cache_dir / entity / f"{key}.en.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"en": en, "fr_hash": "x"}), encoding="utf-8")


def test_localize_data_swaps_collection_fields_to_english(tmp_path):
    _seed_en(tmp_path, "services", "architecture__title", "Software architecture")
    data = {"services": [{"id": "architecture", "title": "Architecture logicielle"}]}

    en = localize_data(data, tmp_path)

    assert en["services"][0]["title"] == "Software architecture"
    # original untouched (deep copy)
    assert data["services"][0]["title"] == "Architecture logicielle"


def test_localize_data_falls_back_to_french_when_translation_missing(tmp_path):
    data = {"services": [{"id": "x", "title": "Titre français"}]}

    en = localize_data(data, tmp_path)

    assert en["services"][0]["title"] == "Titre français"


def test_localize_data_swaps_singleton_dotted_paths(tmp_path):
    _seed_en(tmp_path, "profile", "role", "Freelance CTO")
    data = {"profile": {"role": "CTO indépendant"}}

    en = localize_data(data, tmp_path)

    assert en["profile"]["role"] == "Freelance CTO"


def test_translate_singleton_writes_pure_language_files(tmp_path):
    obj = {"approach": {"paragraph": "Bonjour le monde"}}

    n = translate_singleton(
        "content", obj, ["approach.paragraph"], tmp_path, lambda fr: f"EN[{fr}]"
    )

    assert n == 1
    assert (tmp_path / "content" / "approach__paragraph.fr.txt").exists()
    assert "profile" in SINGLETONS


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


def test_singleton_tree_paths_list_every_string_leaf_sorted():
    from scripts.translate import tree_paths

    obj = {"front": {"b": "x", "a": {"c": "y", "n": 3, "e": ""}}, "other": "z"}
    assert tree_paths(obj, "front") == ["front.a.c", "front.b"]


def test_localize_data_swaps_every_leaf_of_a_translated_tree(tmp_path):
    from scripts.translate import SINGLETON_TREES

    assert "front" in SINGLETON_TREES["content"]
    _seed_en(tmp_path, "content", "front__help__title", "How I can help")
    data = {"content": {"front": {"help": {"title": "Comment je peux aider"}}}}

    en = localize_data(data, tmp_path)

    assert en["content"]["front"]["help"]["title"] == "How I can help"


def test_every_front_string_has_an_english_entry_with_its_placeholders():
    # The front page copy is translated as a whole tree: a string added in
    # French without its English entry would ship French on README.en.md, and
    # an English entry that drops a placeholder would ship a raw brace.
    import pathlib
    import re
    import string

    from scripts.translate import CACHE, _get, _singleton_key, tree_paths

    root = pathlib.Path(__file__).resolve().parent.parent
    content = json.loads((root / "data" / "content.json").read_text("utf-8"))

    def fields(text: str) -> list[str]:
        return sorted({f for _, f, _, _ in string.Formatter().parse(text) if f})

    for path in tree_paths(content, "front"):
        entry = CACHE / "content" / f"{_singleton_key(path)}.en.json"
        assert entry.is_file(), f"no English entry for content.{path}"
        en = json.loads(entry.read_text("utf-8"))["en"]
        fr = _get(content, path)
        assert fields(en) == fields(fr), path
        assert not re.search(r"[éèàçù]", en), f"French left in English {path}"
