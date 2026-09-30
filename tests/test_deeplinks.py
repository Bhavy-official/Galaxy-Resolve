import json
from pathlib import Path

import pytest

from app.pipeline.deeplinks import DUMMY_URI, dummy_payload
from app.pipeline.path_parser import direction_of, nav_targets
from app.pipeline.textutil import word_count
from app.pipeline.types import CandidateStep, GroupDraft

GOLD = json.loads((Path(__file__).resolve().parent.parent / "eval" / "gold_deeplinks.json").read_text(encoding="utf-8"))


def group_from(steps: list[str], direction: str | None = None) -> GroupDraft:
    path = [x for t in steps for x in nav_targets(t)[0]]
    return GroupDraft([CandidateStep(t, t, 0, "") for t in steps], path, direction or direction_of(steps))


@pytest.mark.parametrize("case", GOLD, ids=[g["name"] for g in GOLD])
def test_gold_deeplinks(catalog, case):
    m = catalog.match_group(group_from(case["steps"], case.get("direction")))
    got = m.entry["id"] if m.entry else m.kind
    assert got in case["expect"], (got, m.conf, m.query)


def test_matches_are_verbatim_catalog_entries(catalog):
    for case in GOLD:
        m = catalog.match_group(group_from(case["steps"], case.get("direction")))
        if m.actionable:
            assert catalog.is_valid_uri(m.actionable["deeplink"])
            if m.entry:
                assert m.actionable["deeplink"] == m.entry["deeplink"]
                assert m.actionable["description"] == m.entry["description"]


@pytest.mark.parametrize("screen", ["Storage", "Swipe for split screen", "Factory data reset", "a b c d e f", ""])
def test_dummy_payload_word_counts(screen):
    p = dummy_payload(screen)
    assert p["deeplink"] == DUMMY_URI
    assert 5 <= word_count(p["description"]) <= 7 and 5 <= word_count(p["message"]) <= 7


def test_catalog_never_indexes_uri_strings(catalog):
    assert all("voiceassist" not in d and "masked" not in d for d in catalog.docs)
