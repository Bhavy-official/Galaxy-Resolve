"""The only place that talks to an LLM. Structured output, token/cost logging, retries, timeout.

Provider: Google Gemini via its OpenAI-compatible endpoint. The `openai` SDK is
pointed at Google's base URL and authenticates with a Bearer token
(GEMINI_API_KEY from https://aistudio.google.com/apikey — free tier, no card).
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, TypeVar

from pydantic import BaseModel

from app.config import Settings, settings as default_settings

log = logging.getLogger("llm")

# USD per 1M tokens (input, output). Gemini API paid tier, text.
PRICING: dict[str, tuple[float, float]] = {
    "gemini-3.8-flash": (0.75, 3.75),
    "gemini-3.7-flash": (0.75, 3.75),
    "gemini-3.6-flash": (0.75, 3.75),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-2.5-pro": (1.25, 10.00),
}

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


@dataclass
class Usage:
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    calls: int = 0

    def add(self, other: "Usage") -> None:
        self.model = other.model or self.model
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cost_usd += other.cost_usd
        self.latency_ms += other.latency_ms
        self.calls += other.calls


@dataclass
class UsageTotals(Usage):
    pass


def cost_for(model: str, input_tokens: int, output_tokens: int) -> float:
    pin, pout = PRICING.get(model, PRICING["gemini-3.8-flash"])
    return (input_tokens * pin + output_tokens * pout) / 1_000_000


@dataclass
class LLMClient:
    cfg: Settings = field(default_factory=lambda: default_settings)
    client: Any = None  # injectable (tests pass a fake with .chat.completions.parse)
    totals: Usage = field(default_factory=Usage)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def __post_init__(self) -> None:
        if self.client is None and self.cfg.pipeline_mode != "rules" and self.has_credentials():
            import openai

            # Gemini's OpenAI-compatible endpoint: the SDK appends
            # /chat/completions to the base URL. Auth is a Bearer token.
            self.client = openai.OpenAI(
                api_key=os.getenv("GEMINI_API_KEY"),
                base_url=self.cfg.llm_base_url,
                timeout=self.cfg.llm_timeout_s,
                max_retries=self.cfg.llm_max_retries,
            )

    @staticmethod
    def has_credentials() -> bool:
        return bool(os.getenv("GEMINI_API_KEY"))

    @property
    def available(self) -> bool:
        return self.client is not None and self.cfg.pipeline_mode != "rules"

    @property
    def model(self) -> str:
        return self.cfg.llm_model

    def structured(self, system: str, user: str, schema: type[T], max_tokens: int = 4096) -> tuple[T, Usage]:
        """Structured output with automatic fallback.

        Prefers the SDK's ``chat.completions.parse`` (structured outputs). If
        the endpoint rejects ``response_format`` (e.g. HTTP 400), retries in
        JSON mode: the model is instructed to return a bare JSON object, which
        is then validated against the schema here.
        """
        if not self.available:
            raise LLMError("LLM not available (no GEMINI_API_KEY or PIPELINE_MODE=rules)")
        try:
            return self._structured_parse(system, user, schema, max_tokens)
        except LLMError as exc:
            msg = str(exc).lower()
            if "response_format" in msg or "not supported" in msg or "400" in msg or "bad request" in msg:
                log.warning("structured outputs unavailable (%s); falling back to JSON mode", exc)
                return self._structured_json(system, user, schema, max_tokens)
            raise

    def _structured_parse(self, system: str, user: str, schema: type[T], max_tokens: int) -> tuple[T, Usage]:
        t0 = time.perf_counter()
        try:
            resp = self.client.chat.completions.parse(
                model=self.model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format=schema,
            )
        except Exception as exc:  # SDK already retried transient errors
            raise LLMError(f"LLM call failed: {type(exc).__name__}: {exc}") from exc
        latency = (time.perf_counter() - t0) * 1000
        choice = resp.choices[0]
        if getattr(choice.message, "refusal", None):
            raise LLMError(f"LLM refused: {choice.message.refusal}")
        if choice.finish_reason == "length":
            raise LLMError("LLM stopped with length (max_tokens)")
        parsed = getattr(choice.message, "parsed", None)
        if parsed is None:
            raise LLMError("LLM returned no parsable structured output")
        u = getattr(resp, "usage", None)
        it = int(getattr(u, "prompt_tokens", 0) or 0)
        ot = int(getattr(u, "completion_tokens", 0) or 0)
        usage = Usage(self.model, it, ot, cost_for(self.model, it, ot), latency, 1)
        with self._lock:
            self.totals.add(usage)
        log.info(
            "llm schema=%s model=%s in=%d out=%d cost=$%.5f latency=%.0fms",
            schema.__name__, self.model, it, ot, usage.cost_usd, latency,
        )
        return parsed, usage

    def _structured_json(self, system: str, user: str, schema: type[T], max_tokens: int) -> tuple[T, Usage]:
        """JSON-mode fallback: ask for a bare JSON object, validate locally."""
        prompt = (
            user
            + "\n\nRespond with a single JSON object that matches the schema described above. "
            + "Return ONLY the JSON object: no markdown fences, no commentary, no other text."
        )
        t0 = time.perf_counter()
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            )
        except Exception as exc:  # SDK already retried transient errors
            raise LLMError(f"LLM call failed: {type(exc).__name__}: {exc}") from exc
        latency = (time.perf_counter() - t0) * 1000
        choice = resp.choices[0]
        if getattr(choice.message, "refusal", None):
            raise LLMError(f"LLM refused: {choice.message.refusal}")
        if choice.finish_reason == "length":
            raise LLMError("LLM stopped with length (max_tokens)")
        text = (getattr(choice.message, "content", None) or "").strip()
        if text.startswith("```"):  # tolerate fences even though we asked for none
            text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        try:
            data = json.loads(text)
        except Exception as exc:
            raise LLMError(f"LLM did not return valid JSON: {exc}") from exc
        try:
            parsed = schema.model_validate(data)
        except Exception as exc:
            raise LLMError(f"LLM JSON failed schema validation: {exc}") from exc
        u = getattr(resp, "usage", None)
        it = int(getattr(u, "prompt_tokens", 0) or 0)
        ot = int(getattr(u, "completion_tokens", 0) or 0)
        usage = Usage(self.model, it, ot, cost_for(self.model, it, ot), latency, 1)
        with self._lock:
            self.totals.add(usage)
        log.info(
            "llm schema=%s model=%s in=%d out=%d cost=$%.5f latency=%.0fms (json-mode)",
            schema.__name__, self.model, it, ot, usage.cost_usd, latency,
        )
        return parsed, usage

    def reset(self) -> UsageTotals:
        with self._lock:
            totals = UsageTotals(
                model=self.totals.model,
                input_tokens=self.totals.input_tokens,
                output_tokens=self.totals.output_tokens,
                cost_usd=self.totals.cost_usd,
                latency_ms=self.totals.latency_ms,
                calls=self.totals.calls,
            )
            self.totals = Usage()
        return totals
