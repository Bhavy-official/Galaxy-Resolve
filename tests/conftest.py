from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402
from app.embed import get_models  # noqa: E402


@pytest.fixture(scope="session")
def models():
    return get_models().load()


@pytest.fixture(scope="session")
def catalog(models):
    from app.pipeline.deeplinks import Catalog

    return Catalog(settings.deeplinks_path, models)


@pytest.fixture(scope="session")
def siis_rows() -> list[dict[str, Any]]:
    return json.loads((ROOT / "data" / "siis_responses.json").read_text(encoding="utf-8"))["responses"]


class FakeCompletions:
    """Stands in for openai.OpenAI().chat.completions; routes on the requested response schema."""

    def __init__(self, handlers: dict[str, Callable[[str, str], Any]]) -> None:
        self.handlers = handlers
        self.calls: list[str] = []

    def _body(self, schema: type, system: str, user: str) -> SimpleNamespace:
        name = schema.__name__
        self.calls.append(name)
        parsed = self.handlers[name](system, user)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        parsed=schema.model_validate(parsed) if isinstance(parsed, dict) else parsed,
                        content=json.dumps(parsed) if isinstance(parsed, dict) else None,
                        refusal=None,
                    ),
                    finish_reason="stop",
                )
            ],
            usage=SimpleNamespace(prompt_tokens=1200, completion_tokens=300),
        )

    def parse(self, *, model: str, max_tokens: int, messages: list, response_format: type) -> SimpleNamespace:
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        user = next((m["content"] for m in messages if m["role"] == "user"), "")
        return self._body(response_format, system, user)

    def create(self, *, model: str, max_tokens: int, messages: list, **kwargs) -> SimpleNamespace:
        # JSON-mode fallback path: no schema is passed, so route through the
        # single registered handler and serialize its output as bare JSON text.
        if len(self.handlers) != 1:
            raise AssertionError("FakeCompletions.create needs exactly one handler to infer the schema")
        schema_name = next(iter(self.handlers))
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        user = next((m["content"] for m in messages if m["role"] == "user"), "")
        parsed = self.handlers[schema_name](system, user)
        text = json.dumps(parsed) if isinstance(parsed, dict) else parsed.model_dump_json()
        self.calls.append(schema_name)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(parsed=None, content=text, refusal=None),
                    finish_reason="stop",
                )
            ],
            usage=SimpleNamespace(prompt_tokens=1200, completion_tokens=300),
        )


@pytest.fixture
def make_engine(models, tmp_path):
    from app.engine import Engine
    from app.llm import LLMClient

    def _make(handlers: dict | None = None, **overrides):
        cfg = replace(settings, cache_db=tmp_path / "cache.sqlite3", pipeline_mode=overrides.pop("mode", "auto"), **overrides)
        fake = FakeCompletions(handlers) if handlers is not None else None
        llm = LLMClient(cfg, client=SimpleNamespace(chat=SimpleNamespace(completions=fake)) if fake else None)
        if fake is None:
            llm.client = None  # force rules mode even if the developer has a key in .env
        eng = Engine(cfg, llm=llm, models=models).load()
        return eng, fake

    return _make
