"""The generation reference date is committed, never read from the clock.

Scores, levels and row order derive from exposure hours, and hours accrue for
every ongoing experience. Reading the system clock therefore makes the output
drift month by month: the same revision regenerates differently tomorrow, the
`git diff --exit-code` CI step breaks on its own, and the pre-commit
`generate-profile` hook rewrites files on an unrelated commit.

The reference date lives in `data/config.json` instead, so a revision pins its
own output. The weekly refresh workflow bumps it deliberately.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path

import scripts.generate as gen

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "data" / "config.json"
OUTPUTS = ("README.md", "README.en.md")


def _read_outputs() -> dict[str, str]:
    out = {name: (ROOT / name).read_text(encoding="utf-8") for name in OUTPUTS}
    for svg in sorted((ROOT / "assets" / "svg").rglob("*.svg")):
        out[str(svg.relative_to(ROOT))] = svg.read_text(encoding="utf-8")
    for page in sorted((ROOT / "pages").rglob("*.md")):
        out[str(page.relative_to(ROOT))] = page.read_text(encoding="utf-8")
    return out


def test_config_carries_the_reference_date():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    datetime.date.fromisoformat(config["as_of"])


def test_reference_date_comes_from_config():
    expected = json.loads(CONFIG.read_text(encoding="utf-8"))["as_of"]
    assert gen.reference_date() == datetime.date.fromisoformat(expected)


def test_generation_ignores_the_system_clock(monkeypatch):
    gen.main()
    before = _read_outputs()

    class _Clock(datetime.date):
        @classmethod
        def today(cls):  # a visitor regenerating five years later
            return cls(2031, 7, 14)

    monkeypatch.setattr(gen, "date", _Clock)
    gen.main()

    assert _read_outputs() == before
