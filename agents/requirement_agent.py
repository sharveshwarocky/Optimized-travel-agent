"""Requirement agent (spec §9.1/§10): NL → validated TravelRequest updates.

Pipeline per §10.2/§10.3:
1. LLM extraction against a JSON schema (one repair retry with the error appended)
2. Merge whatever validated with deterministic regex/dateparser fallback extraction
3. Critical-missing-field detection (never re-asking answered fields)
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ValidationError

from config.prompts import load_prompt
from llm.client import LLMUnavailable, get_client
from llm.schemas import EXTRACTION_SCHEMA
from memory.session_memory import SessionMemory
from utils.cost_utils import parse_rupee_amount
from utils.time_utils import parse_deadline_time, parse_duration_hours, parse_travel_date


class ExtractionLLM(BaseModel):
    """Pydantic validation target for LLM extraction JSON (§10.2)."""

    model_config = {"extra": "ignore"}

    source: str | None = None
    destination: str | None = None
    travel_date: str | None = None
    arrival_deadline: str | None = None
    preferred_departure_after: str | None = None
    max_duration_hours: float | None = None
    passengers: int | None = None
    budget: float | None = None
    budget_type: Literal["total", "per_person"] | None = None
    budget_flexibility: Literal["strict", "flexible"] | None = None
    comfort_priority: Literal["low", "medium", "high"] | None = None
    ac_required: bool | None = None
    sleeper_preferred: bool | None = None
    overnight_allowed: bool | None = None
    luggage_level: Literal["light", "normal", "heavy"] | None = None
    urgency: Literal["low", "medium", "high"] | None = None
    preferred_modes: list[str] = []
    avoided_modes: list[str] = []
    return_date: str | None = None
    overrides: list[str] = []

CRITICAL_FIELDS = ["source", "destination", "travel_date", "passengers"]

FOLLOWUP_TEXT = {
    "source": "Which city are you starting from?",
    "destination": "Where are you heading?",
    "travel_date": "What date are you travelling?",
    "passengers": "How many people are travelling?",
}


@dataclass
class ExtractionOutcome:
    confirmations: list[str] = field(default_factory=list)   # spoken updates (§13)
    fallback_used: bool = False
    fallback_notes: list[str] = field(default_factory=list)
    llm_error: str | None = None


def _fallback_extract(text: str) -> dict:
    """Regex/dateparser slot filling for common patterns (§10.3)."""
    t = (text or "").lower()
    updates: dict = {}

    m = re.search(r"from\s+([a-z][a-z\s]{2,25}?)(?:\s+to\s+|,|\.|$)", t)
    if m:
        updates["source"] = m.group(1).strip().title()
    m = re.search(r"to\s+([a-z][a-z\s]{2,25}?)(?:[,.]|$|\s+(?:tomorrow|today|next|on|by|we|i|budget|reach))", t)
    if m:
        updates["destination"] = m.group(1).strip().title()

    m = re.search(r"(\d+)\s*(?:people|persons|adults|travellers|passengers|of us|pax)", t)
    if m:
        updates["passengers"] = int(m.group(1))

    if any(w in t for w in ("tomorrow", "kal", "tmrw")):
        updates["travel_date"] = "tomorrow"
    elif any(w in t for w in ("today", "aaj")):
        updates["travel_date"] = "today"
    else:
        m = re.search(r"(?:on|for|date)\s+([a-z0-9]+(?:\s+[a-z0-9]+){0,3})", t)
        if m:
            candidate = m.group(1)
            if parse_travel_date(candidate):
                updates["travel_date"] = candidate

    amt = parse_rupee_amount(t)
    if amt and any(w in t for w in ("budget", "₹", "rs", "rupees", "spend")):
        updates["budget"] = amt

    m = re.search(r"before\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", t)
    if m:
        updates["arrival_deadline"] = f"{m.group(1)}{':' + m.group(2) if m.group(2) else ''} {m.group(3) or ''}".strip()

    if re.search(r"\bac\b", t) and any(w in t for w in ("need", "must", "require", "prefer", "want")):
        updates["ac_required"] = True
    if "no ac" in t or "non ac" in t or "non-ac" in t:
        updates["ac_required"] = False

    for mode in ("train", "bus", "flight", "cab", "rental"):
        if re.search(rf"\bno\s+{mode}s?\b", t) or re.search(rf"\bavoid\s+{mode}s?\b", t):
            updates.setdefault("avoided_modes", []).append(mode)

    if any(w in t for w in ("urgent", "asap", "immediately")):
        updates["urgency"] = "high"
    if "elderly" in t or "senior" in t or "parents" in t:
        updates["elderly_travellers"] = max(1, updates.get("elderly_travellers", 0) + 1)
    if "kid" in t or "child" in t:
        updates["children"] = max(1, updates.get("children", 0) + 1)

    return {k: v for k, v in updates.items() if v not in (None, [], "")}


def _coerce(extracted: dict) -> dict:
    """Keep only schema-known keys; pass through values for memory.merge."""
    allowed = {k for k in EXTRACTION_SCHEMA["properties"]}
    out = {k: v for k, v in extracted.items() if k in allowed and v not in (None, "", [])}
    out.pop("overrides", None)
    return out


async def extract_and_merge(memory: SessionMemory, user_text: str) -> ExtractionOutcome:
    outcome = ExtractionOutcome()
    memory.add_user_text(user_text)

    # 1) LLM extraction with Pydantic validation + one repair retry (§10.2)
    llm_updates: dict = {}
    client = get_client()
    if client.available:
        try:
            prompt = load_prompt("extraction", {
                "$MEMORY_JSON": json.dumps(memory.as_dict(), indent=1),
                "$USER_TEXT": user_text,
            })
            try:
                obj, err = await client.chat_json_validated(
                    prompt["system"], prompt["user"], ExtractionLLM.model_validate)
            except LLMUnavailable:
                obj, err = None, None
            if obj is not None:
                llm_updates = _coerce(obj.model_dump())
            else:
                outcome.llm_error = err or "validation failed after repair retry"
        except LLMUnavailable:
            pass

    # 2) Deterministic fallback always runs and merges (§10.3)
    fallback_updates = _fallback_extract(user_text)
    merged_updates: dict = dict(fallback_updates)
    for k, v in llm_updates.items():
        if k not in merged_updates or merged_updates[k] in (None, "", []):
            merged_updates[k] = v
    if fallback_updates:
        outcome.fallback_used = True
        outcome.fallback_notes = f"regex fallback filled: {', '.join(sorted(fallback_updates))}"
        outcome.fallback_notes = [outcome.fallback_notes]

    outcome.confirmations = memory.merge(merged_updates)
    return outcome


def missing_critical(memory: SessionMemory) -> list[str]:
    """Critical fields still missing (never re-asking, §13)."""
    r = memory.request
    missing = []
    if r.source is None:
        missing.append("source")
    if r.destination is None:
        missing.append("destination")
    if r.travel_date is None:
        missing.append("travel_date")
    if r.passengers is None and r.adults is None:
        missing.append("passengers")
    return [f for f in missing if not memory.has_asked(f)]
