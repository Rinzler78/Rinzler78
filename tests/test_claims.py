"""Claims are published only under an attestation the lock file proves (ADR-014).

The page carries claim markers; the committed lock carries a hash of each
claim's public wording per language. CI can check the page against the lock
without the private registry; only the author, holding the registry, can
rewrite the lock. These tests pin both halves and the privacy boundary: no
field of the private registry other than the wording hash and the attestation
date may ever reach the lock.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from scripts import claims

FR = "Le produit dont j'ai construit les apps a remporté un prix en 2017."
EN = "The product whose apps I built won an award in 2017."
POINTER = "evidence/sample-press-article.pdf"


def _page(root: pathlib.Path, rel: str, body: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _site(root: pathlib.Path, fr: str = FR, en: str = EN) -> pathlib.Path:
    """A minimal generated site: both READMEs and one page per language."""
    _page(root, "README.md", f"Intro.\n\n{claims.mark('award-2017', fr)}\n")
    _page(root, "README.en.md", f"Intro.\n\n{claims.mark('award-2017', en)}\n")
    _page(root, "pages/projects.md", f"| x | {claims.mark('award-2017', fr)} |\n")
    _page(root, "pages/en/projects.md", "No claim on this page.\n")
    return root


def _registry(path: pathlib.Path, **overrides) -> pathlib.Path:
    entry = {
        "wording": {"fr": FR, "en": EN},
        "evidence_kind": "public_source",
        "pointer": POINTER,
        "attested": "2026-09-26",
    }
    entry.update(overrides)
    path.write_text(
        json.dumps({"version": 1, "claims": {"award-2017": entry}}),
        encoding="utf-8",
    )
    return path


def _lock_for(root: pathlib.Path, registry: pathlib.Path) -> pathlib.Path:
    lock = root / "data" / "claims.lock.json"
    claims.write_lock(root, registry, lock)
    return lock


# --- marker convention ------------------------------------------------------


def test_mark_wraps_the_wording_in_an_open_and_close_comment():
    assert claims.mark("award-2017", "Won.") == (
        "<!-- claim:award-2017 -->Won.<!-- /claim -->"
    )


def test_mark_rejects_an_invalid_identifier():
    with pytest.raises(claims.ClaimError, match="identifier"):
        claims.mark("Award 2017", "Won.")


def test_markers_are_found_with_their_language(tmp_path):
    found = claims.scan_pages(_site(tmp_path))
    assert sorted((m.claim_id, m.lang, m.path) for m in found) == [
        ("award-2017", "en", "README.en.md"),
        ("award-2017", "fr", "README.md"),
        ("award-2017", "fr", "pages/projects.md"),
    ]


def test_wording_is_normalized_before_hashing():
    spaced = "Le  produit\n  dont   j'ai &amp; construit."
    assert claims.normalize(spaced) == "Le produit dont j'ai & construit."
    assert claims.digest(spaced) == claims.digest("Le produit dont j'ai & construit.")


def test_an_unclosed_marker_is_an_error(tmp_path):
    _page(tmp_path, "README.md", "<!-- claim:award-2017 -->Won, never closed.\n")
    with pytest.raises(claims.ClaimError, match="unclosed"):
        claims.scan_pages(tmp_path)


def test_a_nested_marker_is_an_error(tmp_path):
    inner = claims.mark("inner", "b")
    _page(tmp_path, "README.md", f"<!-- claim:outer -->a {inner}<!-- /claim -->\n")
    with pytest.raises(claims.ClaimError, match="nested"):
        claims.scan_pages(tmp_path)


def test_a_stray_close_marker_is_an_error(tmp_path):
    _page(tmp_path, "README.md", "Text.<!-- /claim -->\n")
    with pytest.raises(claims.ClaimError, match="close"):
        claims.scan_pages(tmp_path)


def test_a_malformed_open_marker_is_an_error(tmp_path):
    _page(tmp_path, "README.md", "<!-- claim:Bad Id -->x<!-- /claim -->\n")
    with pytest.raises(claims.ClaimError, match="malformed"):
        claims.scan_pages(tmp_path)


# --- check (CI mode) --------------------------------------------------------


def test_a_marker_resolves_with_a_matching_hash(tmp_path):
    root = _site(tmp_path)
    lock = _lock_for(root, _registry(tmp_path / "registry.json"))
    report = claims.check(root, lock)
    assert report.errors == []
    assert report.warnings == []


def test_a_reworded_claim_fails(tmp_path):
    root = _site(tmp_path)
    lock = _lock_for(root, _registry(tmp_path / "registry.json"))
    _page(root, "README.en.md", claims.mark("award-2017", EN + " Twice.") + "\n")
    report = claims.check(root, lock)
    assert len(report.errors) == 1
    assert "award-2017" in report.errors[0]
    assert "README.en.md" in report.errors[0]
    assert "reworded" in report.errors[0]


def test_an_unknown_claim_fails(tmp_path):
    root = _site(tmp_path)
    lock = _lock_for(root, _registry(tmp_path / "registry.json"))
    _page(root, "pages/en/projects.md", claims.mark("new-claim", "Big.") + "\n")
    report = claims.check(root, lock)
    assert any("new-claim" in e and "not in the lock" in e for e in report.errors)


def test_a_language_missing_from_the_lock_fails(tmp_path):
    root = _site(tmp_path)
    lock = root / "data" / "claims.lock.json"
    lock.parent.mkdir(parents=True)
    fr_only = {"wording_sha256": {"fr": claims.digest(FR)}, "attested": "2026-09-26"}
    lock.write_text(json.dumps({"version": 1, "claims": {"award-2017": fr_only}}))
    report = claims.check(root, lock)
    assert any("en" in e and "award-2017" in e for e in report.errors)


def test_an_orphaned_lock_entry_only_warns(tmp_path):
    root = _site(tmp_path)
    lock = _lock_for(root, _registry(tmp_path / "registry.json"))
    for rel in ("README.md", "README.en.md", "pages/projects.md"):
        _page(root, rel, "No claim any more.\n")
    report = claims.check(root, lock)
    assert report.errors == []
    assert report.warnings and "award-2017" in report.warnings[0]


def test_no_marker_and_an_empty_lock_passes(tmp_path):
    _page(tmp_path, "README.md", "Nothing claimed.\n")
    lock = tmp_path / "claims.lock.json"
    lock.write_text(json.dumps({"version": 1, "claims": {}}))
    assert claims.check(tmp_path, lock).errors == []


def test_a_malformed_lock_entry_is_an_error(tmp_path):
    lock = tmp_path / "claims.lock.json"
    lock.write_text(json.dumps({"version": 1, "claims": {"award-2017": "x"}}))
    with pytest.raises(claims.ClaimError, match="award-2017"):
        claims.check(_site(tmp_path), lock)


def test_a_malformed_close_marker_is_an_error(tmp_path):
    _page(tmp_path, "README.md", "<!-- claim:a -->x<!-- /claim a -->\n")
    with pytest.raises(claims.ClaimError, match="malformed close"):
        claims.scan_pages(tmp_path)


def test_a_registry_entry_that_is_not_an_object_is_refused(tmp_path):
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({"version": 1, "claims": {"award-2017": "x"}}))
    with pytest.raises(claims.ClaimError, match="object"):
        _lock_for(_site(tmp_path), registry)


def test_a_missing_lock_is_an_error(tmp_path):
    with pytest.raises(claims.ClaimError, match="lock"):
        claims.check(_site(tmp_path), tmp_path / "absent.json")


# --- lock (local mode) ------------------------------------------------------


def test_the_lock_holds_only_the_hashes_and_the_date(tmp_path):
    root = _site(tmp_path)
    lock = _lock_for(root, _registry(tmp_path / "registry.json"))
    assert json.loads(lock.read_text()) == {
        "version": 1,
        "claims": {
            "award-2017": {
                "wording_sha256": {"fr": claims.digest(FR), "en": claims.digest(EN)},
                "attested": "2026-09-26",
            }
        },
    }


def test_no_private_registry_field_is_ever_written_to_the_lock(tmp_path):
    root = _site(tmp_path)
    registry = _registry(
        tmp_path / "registry.json",
        evidence_kind="private_attestation",
        pointer="clients/sample-client/signed-statement.pdf",
        note="internal remark that must stay private",
    )
    text = _lock_for(root, registry).read_text()
    for private in (
        "clients/sample-client/signed-statement.pdf",
        "sample-client",
        "private_attestation",
        "evidence_kind",
        "pointer",
        "internal remark",
        "note",
        FR,
        EN,
    ):
        assert private not in text


def test_registry_entries_absent_from_the_pages_stay_out_of_the_lock(tmp_path):
    root = _site(tmp_path)
    registry = tmp_path / "registry.json"
    data = json.loads(_registry(registry).read_text())
    data["claims"]["unpublished-secret"] = data["claims"]["award-2017"]
    registry.write_text(json.dumps(data))
    text = _lock_for(root, registry).read_text()
    assert "unpublished-secret" not in text


def test_the_lock_is_deterministic(tmp_path):
    root = _site(tmp_path)
    registry = _registry(tmp_path / "registry.json")
    first = _lock_for(root, registry).read_text()
    assert _lock_for(root, registry).read_text() == first
    assert first.endswith("\n")


def test_lock_refuses_a_marker_without_a_registry_entry(tmp_path):
    root = _site(tmp_path)
    _page(root, "README.md", claims.mark("unattested", "Big.") + "\n")
    with pytest.raises(claims.ClaimError, match="unattested"):
        _lock_for(root, _registry(tmp_path / "registry.json"))


def test_lock_refuses_a_page_wording_that_differs_from_the_registry(tmp_path):
    root = _site(tmp_path, en=EN + " Reworded.")
    with pytest.raises(claims.ClaimError, match="differs"):
        _lock_for(root, _registry(tmp_path / "registry.json"))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("evidence_kind", "hearsay", "evidence_kind"),
        ("pointer", "", "pointer"),
        ("attested", "26/09/2026", "attested"),
        ("wording", {"fr": FR}, "wording"),
    ],
)
def test_lock_refuses_an_entry_without_valid_evidence(tmp_path, field, value, message):
    root = _site(tmp_path)
    registry = _registry(tmp_path / "registry.json", **{field: value})
    with pytest.raises(claims.ClaimError, match=message):
        _lock_for(root, registry)


def test_lock_refuses_a_malformed_registry(tmp_path):
    registry = tmp_path / "registry.json"
    registry.write_text("{not json")
    with pytest.raises(claims.ClaimError, match="registry"):
        _lock_for(_site(tmp_path), registry)
    registry.write_text(json.dumps({"award-2017": {}}))
    with pytest.raises(claims.ClaimError, match="claims"):
        _lock_for(_site(tmp_path), registry)


def test_lock_refuses_a_missing_registry(tmp_path):
    with pytest.raises(claims.ClaimError, match="registry"):
        _lock_for(_site(tmp_path), tmp_path / "absent.json")


def test_registry_path_requires_the_private_dir_variable(monkeypatch):
    monkeypatch.delenv("PROFILE_PRIVATE_DIR", raising=False)
    with pytest.raises(claims.ClaimError, match="PROFILE_PRIVATE_DIR"):
        claims.registry_path()


def test_registry_path_reads_the_private_dir_variable(monkeypatch, tmp_path):
    monkeypatch.setenv("PROFILE_PRIVATE_DIR", str(tmp_path))
    assert claims.registry_path() == tmp_path / "claims.json"


# --- CLI --------------------------------------------------------------------


def test_cli_check_passes_and_fails_with_exit_codes(tmp_path, capsys):
    root = _site(tmp_path)
    lock = _lock_for(root, _registry(tmp_path / "registry.json"))
    args = ["check", "--root", str(root), "--lock", str(lock)]
    assert claims.main(args) == 0
    _page(root, "README.md", claims.mark("award-2017", "Reworded.") + "\n")
    assert claims.main(args) == 1
    assert "reworded" in capsys.readouterr().err


def test_cli_check_reports_warnings_without_failing(tmp_path, capsys):
    root = _site(tmp_path)
    lock = _lock_for(root, _registry(tmp_path / "registry.json"))
    for rel in ("README.md", "README.en.md", "pages/projects.md"):
        _page(root, rel, "Nothing.\n")
    assert claims.main(["check", "--root", str(root), "--lock", str(lock)]) == 0
    assert "warning" in capsys.readouterr().err


def test_cli_lock_writes_from_the_env_registry(tmp_path, monkeypatch):
    root = _site(tmp_path)
    private = tmp_path / "private"
    private.mkdir()
    _registry(private / "claims.json")
    monkeypatch.setenv("PROFILE_PRIVATE_DIR", str(private))
    lock = tmp_path / "out.lock.json"
    assert claims.main(["lock", "--root", str(root), "--lock", str(lock)]) == 0
    assert "award-2017" in json.loads(lock.read_text())["claims"]


def test_cli_lock_without_the_env_fails_loudly(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("PROFILE_PRIVATE_DIR", raising=False)
    lock = tmp_path / "out.lock.json"
    assert claims.main(["lock", "--root", str(_site(tmp_path)), "--lock", str(lock)])
    assert "PROFILE_PRIVATE_DIR" in capsys.readouterr().err
    assert not lock.exists()


# --- the real repository ----------------------------------------------------


def test_the_committed_pages_resolve_in_the_committed_lock():
    report = claims.check(claims.REPO, claims.LOCK)
    assert report.errors == []


def test_author_statement_is_an_admitted_evidence_kind(tmp_path):
    # ADR-017: a fact of the author's own career that nothing else can prove
    # is admitted on his statement, recorded like any other attestation.
    root = _site(tmp_path)
    registry = _registry(
        tmp_path / "registry.json",
        evidence_kind="author_statement",
        scope="career",
        pointer="statement by the author, 2026-09-27",
    )
    lock = json.loads(_lock_for(root, registry).read_text())
    assert "award-2017" in lock["claims"]
    assert "author_statement" not in json.dumps(lock)


def test_author_statement_needs_a_scope(tmp_path):
    root = _site(tmp_path)
    registry = _registry(
        tmp_path / "registry.json",
        evidence_kind="author_statement",
        pointer="statement by the author, 2026-09-27",
    )
    with pytest.raises(claims.ClaimError, match="scope"):
        _lock_for(root, registry)


def test_stated_impact_figure_must_carry_the_mark_in_both_languages(tmp_path):
    # ADR-017: an impact figure resting on the author's statement is marked on
    # the page, so a reader can tell it from a proven one.
    root = _site(tmp_path)
    registry = _registry(
        tmp_path / "registry.json",
        evidence_kind="author_statement",
        scope="impact",
        pointer="statement by the author, 2026-09-27",
    )
    with pytest.raises(claims.ClaimError, match="mark"):
        _lock_for(root, registry)


def test_stated_impact_figure_with_the_mark_is_locked(tmp_path):
    fr = f"{FR} {claims.STATED_MARK['fr']}"
    en = f"{EN} {claims.STATED_MARK['en']}"
    root = _site(tmp_path, fr=fr, en=en)
    registry = _registry(
        tmp_path / "registry.json",
        wording={"fr": fr, "en": en},
        evidence_kind="author_statement",
        scope="impact",
        pointer="statement by the author, 2026-09-27",
    )
    assert "award-2017" in json.loads(_lock_for(root, registry).read_text())["claims"]
