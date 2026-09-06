"""OpenRouter client wrapper (spec §10, llm/client.py).

- Retries, timeouts, model fallbacks, cost/token logging (§10.2)
- Raises LLMUnavailable on any failure so every agent can degrade to its
  deterministic fallback (§10.3) instead of fabricating data (§17).
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Callable

import httpx
from pydantic import ValidationError

from config import settings


class LLMUnavailable(Exception):
    """Raised when no LLM could be reached or coerced into valid JSON."""


@dataclass
class UsageLog:
    """In-process log of LLM calls for the CLI debug view (§10.2)."""

    entries: list[dict] = field(default_factory=list)

    def add(self, **kw) -> None:
        self.entries.append(kw)

    def summary(self) -> str:
        if not self.entries:
            return "no LLM calls"
        n = len(self.entries)
        toks = sum(e.get("total_tokens") or 0 for e in self.entries)
        secs = sum(e.get("latency_s") or 0 for e in self.entries)
        return f"{n} calls · {toks} tokens · {secs:.1f}s total"


usage_log = UsageLog()


@dataclass
class LLMResult:
    content: str          # raw text (usually JSON)
    parsed: dict | None   # parsed JSON if extractable
    model: str
    fallback_fired: bool = False
    error: str | None = None


_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def extract_json(text: str) -> dict | None:
    """Best-effort JSON extraction from a model reply (handles ``` fences, prose)."""
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = _JSON_BLOCK.search(text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    return None


class OpenRouterClient:
    """Thin async wrapper over OpenRouter chat completions with model fallbacks."""

    def __init__(self) -> None:
        self.api_key = settings.OPENROUTER_API_KEY
        self.models: list[str] = [settings.LLM_MODEL] + [
            m for m in settings.LLM_MODEL_FALLBACKS if m != settings.LLM_MODEL
        ]
        self._client = httpx.AsyncClient(
            base_url=settings.OPENROUTER_BASE_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "https://localhost",
                "X-Title": "travel-decision-agent",
            },
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    async def chat_json(self, system: str, user: str, *, max_tokens: int = 1200,
                        temperature: float = 0.2) -> LLMResult:
        """One JSON-constrained completion across the model fallback chain.

        Tries each configured model once; returns the first parseable JSON.
        If none parse but one produced text, returns it with parsed=None so the
        caller can run its one repair retry (§10.2).
        """
        if not self.available:
            raise LLMUnavailable("OPENROUTER_API_KEY not configured — running deterministic fallback")

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        last_err: str | None = None
        last_text: str | None = None
        last_model: str | None = None

        for model in self.models:
            started = time.monotonic()
            try:
                resp = await self._client.post(
                    "/chat/completions",
                    json={
                        "model": model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "response_format": {"type": "json_object"},
                    },
                )
            except httpx.HTTPError as exc:
                last_err = f"{model}: {exc}"
                usage_log.add(model=model, latency_s=round(time.monotonic() - started, 2),
                              total_tokens=None, error=last_err)
                continue

            latency = round(time.monotonic() - started, 2)
            if resp.status_code != 200:
                last_err = f"{model}: HTTP {resp.status_code}: {resp.text[:120]}"
                usage_log.add(model=model, latency_s=latency, total_tokens=None, error=last_err)
                continue

            data = resp.json()
            choice = (data.get("choices") or [{}])[0]
            text = ((choice.get("message") or {}).get("content") or "").strip()
            usage = data.get("usage") or {}
            usage_log.add(model=model, latency_s=latency,
                          total_tokens=usage.get("total_tokens"),
                          error=None)
            if not text:
                last_err = f"{model}: empty completion"
                continue
            parsed = extract_json(text)
            last_text, last_model = text, model
            if parsed is not None:
                return LLMResult(content=text, parsed=parsed, model=model)
            last_err = f"{model}: unparseable JSON"

        return LLMResult(content=last_text or "", parsed=None,
                         model=last_model or "none", fallback_fired=True, error=last_err)

    async def chat_json_validated(self, system: str, user: str,
                                  validator: Callable[[dict], object], *,
                                  max_tokens: int = 1200,
                                  temperature: float = 0.2) -> tuple[object | None, str | None]:
        """JSON completion + Pydantic validation with ONE repair retry (§10.2).

        On validation failure the error is appended and the model is asked to
        correct its own JSON once. On second failure → (None, error) so the
        caller degrades to its deterministic fallback (§10.3).
        """
        messages: list[dict] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        repair_used = False
        last_err: str | None = None

        for model in self.models:
            while True:
                started = time.monotonic()
                try:
                    resp = await self._client.post(
                        "/chat/completions",
                        json={"model": model, "messages": messages,
                              "temperature": temperature, "max_tokens": max_tokens,
                              "response_format": {"type": "json_object"}},
                    )
                except httpx.HTTPError as exc:
                    last_err = f"{model}: {exc}"
                    usage_log.add(model=model, latency_s=round(time.monotonic() - started, 2),
                                  total_tokens=None, error=last_err)
                    break  # next model

                latency = round(time.monotonic() - started, 2)
                if resp.status_code != 200:
                    last_err = f"{model}: HTTP {resp.status_code}"
                    usage_log.add(model=model, latency_s=latency, total_tokens=None, error=last_err)
                    break  # next model

                data = resp.json()
                text = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
                usage = data.get("usage") or {}
                usage_log.add(model=model, latency_s=latency,
                              total_tokens=usage.get("total_tokens"), error=None)
                parsed = extract_json(text or "")
                if parsed is None:
                    last_err = f"{model}: unparseable JSON"
                    break  # next model
                try:
                    obj = validator(parsed)
                    return obj, None
                except ValidationError as exc:
                    last_err = f"{model}: schema errors {[str(e['msg']) for e in exc.errors()[:3]]}"
                    if repair_used:
                        return None, last_err
                    repair_used = True
                    messages = messages + [
                        {"role": "assistant", "content": text or ""},
                        {"role": "user", "content":
                         f"Your JSON failed validation: {exc.errors()[:4]}. "
                         "Output ONLY the corrected JSON object, no prose."},
                    ]
                    continue
        return None, last_err

    async def aclose(self) -> None:
        await self._client.aclose()


shared_client: OpenRouterClient | None = None


def get_client() -> OpenRouterClient:
    global shared_client
    if shared_client is None:
        shared_client = OpenRouterClient()
    return shared_client
