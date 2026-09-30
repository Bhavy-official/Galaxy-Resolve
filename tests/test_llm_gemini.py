"""LLM client: Google Gemini wiring via its OpenAI-compatible endpoint, pricing, fallback."""
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from app.config import settings
from app.llm import LLMClient, LLMError, cost_for
from app.pipeline.enrich import LLMEnrichment

ENRICH_PAYLOAD = {
    "canonical_query": "Screen flickers on the Galaxy phone",
    "domain": "display",
    "symptom": "flicker",
    "trigger": "",
    "topic": "display flicker",
    "title": "Fix screen flicker",
    "kind": "Troubleshooting",
    "paraphrases": ["my display keeps flickering", "screen flashes on and off"],
}


def _usage_ns(it=100, ot=50):
    return SimpleNamespace(prompt_tokens=it, completion_tokens=ot)


class _ParseFailsCreateJson:
    """Stands in for openai.OpenAI().chat.completions.

    parse() raises like an endpoint that rejects response_format; create()
    returns a bare JSON object (the JSON-mode fallback path).
    """

    def __init__(self, payload):
        self.payload = payload
        self.parse_calls = 0
        self.create_calls = 0
        self.create_kwargs = None

    def parse(self, **kwargs):
        self.parse_calls += 1
        raise Exception("400 {'error': {'message': 'response_format json_schema is not supported'}}")

    def create(self, **kwargs):
        self.create_calls += 1
        self.create_kwargs = kwargs
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        parsed=None, content=json.dumps(self.payload), refusal=None
                    ),
                    finish_reason="stop",
                )
            ],
            usage=_usage_ns(),
        )


def _client_with(completions, monkeypatch, mode="auto"):
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaTestSecret")
    cfg = replace(settings, pipeline_mode=mode)
    return LLMClient(cfg, client=SimpleNamespace(chat=SimpleNamespace(completions=completions)))


def test_has_credentials_reads_gemini_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert LLMClient.has_credentials() is False
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaTestSecret")
    assert LLMClient.has_credentials() is True


def test_cost_for_gemini_pricing():
    # $0.75 / 1M input, $3.75 / 1M output (gemini-3.8-flash)
    assert cost_for("gemini-3.8-flash", 1_000_000, 1_000_000) == pytest.approx(4.50)
    assert cost_for("gemini-2.5-flash", 2_000_000, 0) == pytest.approx(0.60)


def test_default_model_is_gemini():
    assert settings.llm_model == "gemini-3.8-flash"
    assert settings.llm_base_url == "https://generativelanguage.googleapis.com/v1beta/openai"


def test_structured_falls_back_to_json_mode(monkeypatch):
    completions = _ParseFailsCreateJson(ENRICH_PAYLOAD)
    client = _client_with(completions, monkeypatch)
    out, usage = client.structured("system", "user", LLMEnrichment, max_tokens=500)

    assert completions.parse_calls == 1
    assert completions.create_calls == 1
    assert isinstance(out, LLMEnrichment)
    assert out.domain == "display" and out.symptom == "flicker"
    # usage still logged from the JSON-mode response
    assert usage.input_tokens == 100 and usage.output_tokens == 50
    assert usage.cost_usd == pytest.approx(cost_for("gemini-3.8-flash", 100, 50))
    # totals accumulate
    assert client.totals.cost_usd == pytest.approx(usage.cost_usd)


def test_structured_fallback_tolerates_fences_and_validates_schema(monkeypatch):
    payload = dict(ENRICH_PAYLOAD)
    completions = _ParseFailsCreateJson(payload)
    client = _client_with(completions, monkeypatch)
    orig_create = completions.create

    def fenced_create(**kwargs):
        resp = orig_create(**kwargs)
        resp.choices[0].message.content = "```json\n" + resp.choices[0].message.content + "\n```"
        return resp

    completions.create = fenced_create
    out, _ = client.structured("system", "user", LLMEnrichment, max_tokens=500)
    assert out.canonical_query == "Screen flickers on the Galaxy phone"


def test_structured_fallback_rejects_bad_json(monkeypatch):
    completions = _ParseFailsCreateJson(ENRICH_PAYLOAD)

    def bad_create(**kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(parsed=None, content="not json at all", refusal=None),
                    finish_reason="stop",
                )
            ],
            usage=_usage_ns(),
        )

    completions.create = bad_create
    client = _client_with(completions, monkeypatch)
    with pytest.raises(LLMError, match="valid JSON"):
        client.structured("system", "user", LLMEnrichment, max_tokens=500)


def test_non_beta_errors_do_not_fallback(monkeypatch):
    class AlwaysFails:
        def parse(self, **kwargs):
            raise Exception("503 overloaded")
        def create(self, **kwargs):  # pragma: no cover - must not be called
            raise AssertionError("fallback must not trigger on 503")

    client = _client_with(AlwaysFails(), monkeypatch)
    with pytest.raises(LLMError, match="LLM call failed"):
        client.structured("system", "user", LLMEnrichment, max_tokens=500)
