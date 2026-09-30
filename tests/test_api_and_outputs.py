import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.schema import ContextDeeplinkResponse

ROOT = Path(__file__).resolve().parent.parent
URL_RE = re.compile(r"https?://|www\.", re.I)


@pytest.fixture
def client(make_engine, monkeypatch):
    import app.api as api

    eng, _ = make_engine(None, mode="rules")
    monkeypatch.setattr(api, "engine", eng)
    with TestClient(api.app) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_troubleshoot_roundtrip_pure_json(client, siis_rows):
    row = siis_rows[0]
    r = client.post("/v1/troubleshoot", json={"query": row["original_query"], "siis_response": row["siis_response"]})
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/json")
    assert r.text.lstrip().startswith("{") and "```" not in r.text
    body = r.json()
    ContextDeeplinkResponse.model_validate(body)
    assert body["meta"]["cache_hit"] is False
    again = client.post("/v1/troubleshoot", json={"query": row["original_query"]}).json()
    assert again["meta"]["cache_hit"] is True and again["contexts"] == body["contexts"]


def test_siis_as_plain_string_and_missing(client):
    r = client.post("/v1/troubleshoot", json={"query": "screen flickers", "siis_response": "Tap Settings. Tap Display."}).json()
    assert "contexts" in r
    r = client.post("/v1/troubleshoot", json={"query": "zzz unrelated"}).json()
    assert r["contexts"] == [] and r["meta"]["fallback"] == "no_siis_context"


SAMPLES = sorted((ROOT / "data" / "samples").glob("*.json"))


@pytest.mark.parametrize("path", SAMPLES, ids=[p.name for p in SAMPLES])
def test_samples_validate_against_schema(path):
    sample = json.loads(path.read_text(encoding="utf-8"))
    ContextDeeplinkResponse.model_validate(sample["response"])


def _keys(sample_resp):
    g = sample_resp["contexts"][0]
    a = g["actions"][0]
    sg = a["stepGroups"][0]
    return set(g), set(a), set(sg), set(sg["actionableDeeplink"])


def test_output_structure_matches_sample(make_engine, siis_rows):
    sample = json.loads(SAMPLES[0].read_text(encoding="utf-8"))["response"]
    eng, _ = make_engine(None, mode="rules")
    row = next(r for r in siis_rows if r["id"] == "row_21")
    ours = eng.troubleshoot(row["original_query"], row["siis_response"], use_cache=False)
    auto_first = {"contexts": [{**ours["contexts"][0], "actions": [a for a in ours["contexts"][0]["actions"] if a["category"] == "auto"]}]}
    assert _keys(auto_first) == _keys(sample)


def test_results_jsonl_is_clean(catalog):
    from app.pipeline import compliance

    path = ROOT / "results.jsonl"
    if not path.exists():
        pytest.skip("run scripts/prewarm.py first")
    text = path.read_text(encoding="utf-8")
    assert not URL_RE.search(text)
    for line in text.splitlines():
        rec = json.loads(line)
        assert compliance.violations(rec["response"], catalog.all_uris) == [], rec["id"]


def test_results_jsonl_has_query_variations():
    # Official scoring: 5 pts for 8-10 unique, diverse variations per query.
    path = ROOT / "results.jsonl"
    if not path.exists():
        pytest.skip("run scripts/prewarm.py first")
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 20, "results.jsonl should cover all provided queries"
    for line in lines:
        rec = json.loads(line)
        vs = rec.get("query_variations")
        assert isinstance(vs, list) and 8 <= len(vs) <= 10, rec["id"]
        assert len(set(vs)) == len(vs), f"duplicate variations in {rec['id']}"
        assert rec["query"] not in vs, f"original query listed as variation in {rec['id']}"
        assert all(isinstance(v, str) and v.strip() for v in vs), rec["id"]