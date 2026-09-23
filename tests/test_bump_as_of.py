"""The weekly refresh is the only thing that moves the reference date."""

from __future__ import annotations

import json
from datetime import date

import scripts.bump_as_of as bump_as_of


def test_bump_writes_the_given_date(tmp_path, monkeypatch):
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"as_of": "2026-06-01"}), encoding="utf-8")
    monkeypatch.setattr(bump_as_of, "CONFIG", config)

    assert bump_as_of.bump(date(2026, 9, 23)) is True
    assert json.loads(config.read_text(encoding="utf-8"))["as_of"] == "2026-09-23"


def test_bump_is_idempotent(tmp_path, monkeypatch):
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"as_of": "2026-09-23"}), encoding="utf-8")
    monkeypatch.setattr(bump_as_of, "CONFIG", config)

    assert bump_as_of.bump(date(2026, 9, 23)) is False


def test_bump_keeps_the_file_schema_valid(tmp_path, monkeypatch):
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"as_of": "2026-06-01"}), encoding="utf-8")
    monkeypatch.setattr(bump_as_of, "CONFIG", config)

    bump_as_of.bump(date(2027, 1, 5))

    written = json.loads(config.read_text(encoding="utf-8"))
    assert set(written) == {"as_of"}
    date.fromisoformat(written["as_of"])
