"""Planning agent (spec §9.2): decides which modes × sources to research.

LLM drafts the plan against a schema; Python validates it, drops unknown modes,
enforces avoided_modes, and falls back to the deterministic default plan (§10.3).
"""
from __future__ import annotations

import json

from config.prompts import load_prompt
from llm.client import LLMUnavailable, get_client
from llm.schemas import PLANNING_SCHEMA
from models.research_plan import ResearchPlan, default_research_plan
from models.travel_request import ALL_MODES
from utils.geo import city_coords


async def build_plan(memory) -> ResearchPlan:
    req = memory.request
    fallback = default_research_plan(req)

    client = get_client()
    if not client.available:
        return fallback

    context = dict(memory.as_dict())
    src, dst = city_coords(req.source), city_coords(req.destination)
    if src and dst:
        # rough straight-line km hint for the planner (LLM reasons, Python decides)
        from math import radians, sin, cos, asin, sqrt
        lat1, lon1, lat2, lon2 = map(radians, (*src, *dst))
        a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
        context["approx_distance_km"] = int(6371 * 2 * asin(sqrt(a)))

    try:
        prompt = load_prompt("planning", {"$REQUEST_JSON": json.dumps(context, indent=1)})
        result = await client.chat_json(prompt["system"], prompt["user"], max_tokens=700)
    except LLMUnavailable:
        return fallback

    if result.parsed is None:
        return fallback

    tasks = []
    seen = set()
    for t in result.parsed.get("tasks", []):
        if not isinstance(t, dict):
            continue
        mode = t.get("mode")
        if mode not in ALL_MODES or mode in seen:
            continue
        if mode in (req.avoided_modes or []):
            continue
        seen.add(mode)
        tasks.append(type(fallback.tasks[0])(
            mode=mode,
            priority=int(t.get("priority", 1)) if str(t.get("priority", "1")).isdigit() else 1,
            reason=str(t.get("reason", ""))[:200],
            sources=[str(s) for s in (t.get("sources") or [])][:3],
        ))
    if not tasks:
        return fallback

    # never let the LLM drop modes (D16: own car always computed; cab/rental are
    # local formulas; bus/flight have estimate fallbacks per user decision) —
    # the only exclusions are modes the user explicitly avoided
    planned = {t.mode for t in tasks}
    for mode in ALL_MODES:
        if mode not in planned and mode not in (req.avoided_modes or []):
            tasks.append(type(fallback.tasks[0])(mode=mode, priority=2,
                         reason="always researched (live or estimate fallback)"))
    return ResearchPlan(tasks=tasks, planned_by="llm")
