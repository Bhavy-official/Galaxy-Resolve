import json
import re

import pytest

from app.pipeline import compliance
from app.pipeline.extract import parse_sections

URL_RE = re.compile(r"https?://|www\.", re.I)


def _row(siis_rows, rid):
    return next(r for r in siis_rows if r["id"] == rid)


def _handlers(siis):
    secs = parse_sections(siis["content"], siis["title"])
    ts = next(s.idx for s in secs if s.title == "Touch Sensitivity Setting")
    safe = next(s.idx for s in secs if s.title == "Safe Mode")
    ts_span = ("To turn off this feature, navigate to Settings, tap Display, and then tap the switch next to "
               "Touch sensitivity to disable it.")

    def enrich(system, user):
        return {
            "canonical_query": "Touchscreen input is laggy and delayed",
            "domain": "touch", "symptom": "lag", "trigger": "",
            "topic": "Touch Lag", "title": "Touch response lag", "kind": "Troubleshooting",
            "paraphrases": [
                "my touchscreen is super laggy", "screen input delay on my phone", "touch lag",
                "Why is my display so slow to respond to taps?", "phone touch delayed pls help samsung.com",
                "tuoch screen lagy", "Touch responsiveness is sluggish", "taps register late on screen",
                "screen reacts slowly when I touch it", "delayed touch response galaxy",
            ],
        }

    def extract(system, user):
        return {
            "steps": [
                {"section_id": ts, "text": "Navigate to Settings.", "source_span": ts_span},
                {"section_id": ts, "text": "Tap Display.", "source_span": ts_span},
                {"section_id": ts, "text": "Tap the switch next to Touch sensitivity to disable it.", "source_span": ts_span},
                # hallucination: not in the article -> grounding must drop it
                {"section_id": ts, "text": "Download the TechCorp Fixer app.", "source_span": "Download the TechCorp Fixer app."},
                # grounded step with an injected URL -> kept, URL scrubbed
                {"section_id": safe, "text": "Touch and hold Power off, then tap Safe mode (see https://www.samsung.com/us/support).",
                 "source_span": "Touch and hold Power off, then tap Safe mode."},
            ],
            "labels": [
                {"section_id": ts, "action_name": "Turn Off Touch Sensitivity", "description": "It will turn off touch sensitivity"},
                {"section_id": safe, "action_name": "Start Safe Mode",
                 "description": "It will start your phone in safe mode to find problem apps"},  # too long -> repair
            ],
        }

    def repair(system, user):
        idx = int(user.split(":")[0])
        return {"descriptions": [{"index": idx, "description": "It will start safe mode now"}]}

    return {"LLMEnrichment": enrich, "LLMExtraction": extract, "_RepairBatch": repair}


def test_llm_path_end_to_end_and_cache(make_engine, siis_rows):
    row = _row(siis_rows, "row_21")
    eng, fake = make_engine(_handlers(row["siis_response"]))
    q = row["original_query"]

    resp = eng.troubleshoot(q, row["siis_response"])
    meta = resp["meta"]
    assert meta["cache_hit"] is False and meta["fallback"] is None
    assert meta["model"] == "gemini-3.8-flash" and meta["cost_usd"] > 0
    assert set(fake.calls) == {"LLMEnrichment", "LLMExtraction", "_RepairBatch"}
    assert compliance.violations(resp, eng.catalog.all_uris) == []
    dump = json.dumps(resp["contexts"])
    assert not URL_RE.search(dump) and "samsung.com" not in dump
    assert "Fixer" not in dump  # hallucinated step dropped
    actions = resp["contexts"][0]["actions"]
    assert [a["category"] for a in actions] == ["auto", "critical"]
    ts = actions[0]
    assert ts["stepGroups"][0]["actionableDeeplink"]["deeplink"] == eng.catalog.by_id["DL-0125"]["deeplink"]
    assert ts["stepGroups"][0]["validationDeeplink"]["key"] == "Touch sensitivity"
    assert actions[1]["description"] == "It will start safe mode now"  # repaired once
    assert meta["grounding"] == {"kept": 4, "dropped": 1}

    # fast path: same query and an enrichment paraphrase hit the cache with zero LLM calls
    n_calls = len(fake.calls)
    hit = eng.troubleshoot(q, row["siis_response"])
    assert hit["meta"]["cache_hit"] is True and hit["contexts"] == resp["contexts"]
    para = eng.troubleshoot("my touch screen is really laggy and slow", None)
    assert para["meta"]["cache_hit"] is True
    assert len(fake.calls) == n_calls


def test_slot_guard_blocks_wrong_domain_hit(make_engine, siis_rows):
    row = _row(siis_rows, "row_21")
    eng, _ = make_engine(_handlers(row["siis_response"]))
    eng.troubleshoot(row["original_query"], row["siis_response"])
    miss = eng.troubleshoot("my battery drains really fast overnight", None)
    assert miss["meta"]["cache_hit"] is False
    assert miss["meta"]["fallback"] == "no_siis_context" and miss["contexts"] == []


def test_llm_failure_degrades_to_rules(make_engine, siis_rows):
    row = _row(siis_rows, "row_21")

    def boom(system, user):
        raise RuntimeError("upstream 529")

    eng, _ = make_engine({"LLMEnrichment": boom, "LLMExtraction": boom, "_RepairBatch": boom})
    resp = eng.troubleshoot(row["original_query"], row["siis_response"])
    assert resp["contexts"] and resp["meta"]["mode"] == "degraded"
    assert compliance.violations(resp, eng.catalog.all_uris) == []


def test_rules_mode_all_provided_queries_are_compliant(make_engine, siis_rows):
    eng, _ = make_engine(None, mode="rules")
    for row in siis_rows:
        resp = eng.troubleshoot(row["original_query"], row["siis_response"], use_cache=False)
        assert resp["meta"]["model"] == "rules"
        assert compliance.violations(resp, eng.catalog.all_uris) == [], row["id"]
        assert not URL_RE.search(json.dumps(resp))


def test_fallbacks(make_engine):
    eng, _ = make_engine(None, mode="rules")
    r = eng.troubleshoot("screen is black", None)
    assert r == {"contexts": [], "meta": r["meta"]} and r["meta"]["fallback"] == "no_siis_context"
    r = eng.troubleshoot("screen is black", {"title": "Pixels", "content": "Pixels are tiny dots that make up the display."})
    assert r["contexts"] == [] and r["meta"]["fallback"] == "no_match"


@pytest.mark.parametrize("rid", ["row_1", "row_14", "row_21"])
def test_manual_actions_never_have_deeplinks(make_engine, siis_rows, rid):
    eng, _ = make_engine(None, mode="rules")
    row = _row(siis_rows, rid)
    resp = eng.troubleshoot(row["original_query"], row["siis_response"], use_cache=False)
    for g in resp["contexts"]:
        for a in g["actions"]:
            if a["category"] == "manual":
                assert all(sg["actionableDeeplink"] is None for sg in a["stepGroups"])
