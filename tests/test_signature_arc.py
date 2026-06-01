"""Signature arc: the curated embedded → mobile → cloud → ai narrative.

The arc nodes (switch year + signature words) are *curated* on the relevant
domains (editorial, user-validated years), and `build_signature_arc` is their
single source. `content.boot_log` must stay consistent with those years.
"""

import json
import re
from pathlib import Path

from scripts.view_builder import build_signature_arc

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def test_signature_arc_is_ordered_with_validated_years_and_signatures():
    domains = [
        {
            "id": "embedded",
            "label": "Embedded & Systems",
            "order": 1,
            "arc_order": 1,
            "arc_label": "embedded",
            "arc_year": 2006,
            "arc_signature": "C · Windows CE · drivers",
        },
        {
            "id": "mobile",
            "label": "Mobile",
            "order": 2,
            "arc_order": 2,
            "arc_label": "mobile",
            "arc_year": 2011,
            "arc_signature": "iOS · NFC · Xamarin",
        },
        {"id": "languages", "label": "Languages", "order": 3},  # not in the arc
        {
            "id": "devops",
            "label": "DevOps & Infrastructure",
            "order": 5,
            "arc_order": 3,
            "arc_label": "cloud",
            "arc_year": 2020,
            "arc_signature": "Docker · CI/CD · .NET Core",
        },
        {
            "id": "ai-llm",
            "label": "AI & LLM",
            "order": 6,
            "arc_order": 4,
            "arc_label": "ai",
            "arc_year": 2023,
            "arc_signature": "LLM · RAG",
        },
    ]

    arc = build_signature_arc(domains)

    assert [n["label"] for n in arc] == ["embedded", "mobile", "cloud", "ai"]
    assert [n["year"] for n in arc] == [2006, 2011, 2020, 2023]
    # NFC belongs to mobile (Ingenico, iOS, 2011), never to embedded.
    assert "NFC" in arc[1]["signature"]
    assert "NFC" not in arc[0]["signature"]
    # Domains without arc_order are excluded.
    assert all(n["label"] != "Languages" for n in arc)


def test_signature_arc_ignores_unspecified_order():
    arc = build_signature_arc([{"id": "x", "label": "X", "order": 1}])
    assert arc == []


# boot_log line -> arc node label it must agree with.
_BOOT_LOG_TO_ARC = {
    "embedded": "embedded",
    "mobile": "mobile",
    "cloud": "cloud",
    "llm": "ai",
}


def test_arc_gradient_stops_are_valid_palette_keys():
    # The hero ribbon gradient encodes the arc (warm origin -> cool ai). Stops
    # are palette keys so they resolve per-palette (light + dark).
    theme = json.loads((DATA / "theme.json").read_text(encoding="utf-8"))
    stops = theme["patterns"]["arc"]["stops"]
    assert len(stops) == 4  # one warm->cool step per arc node
    for key in stops:
        assert key in theme["palette"], f"{key} missing from dark palette"
        assert key in theme["palette_light"], f"{key} missing from light palette"


def test_boot_log_years_match_the_signature_arc():
    domains = json.loads((DATA / "domains.json").read_text(encoding="utf-8"))
    content = json.loads((DATA / "content.json").read_text(encoding="utf-8"))
    arc_year = {n["label"]: n["year"] for n in build_signature_arc(domains)}

    for line in content["boot_log"]["lines"]:
        m = re.match(r"\[\w+\]\s+(\w+)\.ko\s+.*?(\d{4})", line)
        if not m:
            continue
        node = _BOOT_LOG_TO_ARC.get(m.group(1))
        if node is None:
            continue
        assert int(m.group(2)) == arc_year[node], (
            f"boot_log {m.group(1)}.ko {m.group(2)} != arc {node} {arc_year[node]}"
        )
