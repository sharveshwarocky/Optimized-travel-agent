"""Reasoning agent (spec §4/§10): explanations grounded strictly in structured data.

Feeds the ranked options + computed worth-it comparisons to the LLM (which may
only restate provided numbers), with a deterministic template fallback (§10.3).
"""
from __future__ import annotations

import json

from config.prompts import load_prompt
from llm.client import LLMUnavailable, get_client
from llm.schemas import REASONING_SCHEMA
from models.travel_option import TravelOption
from models.travel_request import TravelRequest
from services.worth_it_engine import comparisons_for_llm
from utils.cost_utils import inr


def _option_summary(o: TravelOption) -> dict:
    return {
        "name": o.name,
        "mode": o.mode,
        "total_cost": o.total_cost,
        "cost_per_person": o.cost_per_person,
        "journey_minutes": o.travel_duration_minutes,
        "door_to_door_minutes": o.door_to_door_duration_minutes,
        "comfort": o.comfort_level,
        "ac": o.ac,
        "overnight": o.overnight,
        "data_type": o.data_type,
        "availability": o.availability_status,
        "notes": o.comfort_notes[:4],
    }


async def explain(memory, ranked: list[TravelOption], weights: dict,
                  profile: str, worth_it_lines: list[str]) -> dict:
    """Returns {"best_why": [...], "alternatives": [...], "grounded": bool}."""
    req: TravelRequest = memory.request
    comparison = {
        "user_profile": {
            "passengers": req.effective_passengers(),
            "budget_total": req.budget,
            "budget_flexibility": req.budget_flexibility,
            "arrival_deadline": req.arrival_deadline.strftime("%H:%M") if req.arrival_deadline else None,
            "comfort_priority": req.comfort_priority,
            "urgency": req.urgency,
        },
        "weights_profile": profile,
        "weights": weights,
        "options": [_option_summary(o) for o in ranked[:3]],
        "worth_it_comparisons": comparisons_for_llm(ranked, req),
        "worth_it_lines": worth_it_lines,
    }

    client = get_client()
    if client.available:
        try:
            prompt = load_prompt("reasoning", {
                "$REQUEST_JSON": json.dumps(memory.as_dict(), indent=1),
                "$COMPARISON_JSON": json.dumps(comparison, indent=1),
            })
            result = await client.chat_json(prompt["system"], prompt["user"], max_tokens=900)
            if result.parsed and result.parsed.get("best_why"):
                alts = [a for a in result.parsed.get("alternatives", [])
                        if isinstance(a, dict) and a.get("name")]
                return {"best_why": result.parsed["best_why"][:5],
                        "alternatives": alts[:2], "grounded": True, "llm": result.model}
        except LLMUnavailable:
            pass

    # ---- deterministic template fallback (§10.3: honest, less fluent) ----
    best = ranked[0]
    why: list[str] = []
    if req.budget is not None and best.total_cost is not None:
        if best.total_cost <= req.budget:
            why.append(f"Fits within your budget ({inr(best.total_cost)} of {inr(req.budget)}).")
        else:
            why.append(f"Lowest total cost among options meeting your constraints ({inr(best.total_cost)}).")
    else:
        why.append(f"Best overall balance of cost, time and comfort (score {best.overall_score}/100).")
    if req.arrival_deadline and best.arrival_time:
        headroom = (req.arrival_deadline.hour * 60 + req.arrival_deadline.minute) - \
                   (best.arrival_time.hour * 60 + best.arrival_time.minute)
        why.append(f"Arrives {best.arrival_time.strftime('%H:%M')}, {headroom} min before your deadline.")
    if best.door_to_door_duration_minutes:
        why.append(f"Door-to-door time ≈ {best.door_to_door_duration_minutes // 60}h {best.door_to_door_duration_minutes % 60:02d}m.")
    if best.comfort_level:
        why.append(f"Comfort {best.comfort_level}/10 — {best.comfort_notes[0] if best.comfort_notes else 'rule-based comfort estimate'}.")
    if best.data_type == "estimated":
        why.append("Cost is a formula-based estimate (🟠), not a live quote.")

    alternatives = []
    for o in ranked[1:3]:
        pros, cons = [], []
        if o.door_to_door_duration_minutes and best.door_to_door_duration_minutes:
            if o.door_to_door_duration_minutes < best.door_to_door_duration_minutes:
                pros.append("Faster door-to-door than the top pick.")
            else:
                cons.append("Slower door-to-door than the top pick.")
        if o.total_cost is not None and best.total_cost is not None:
            (pros if o.total_cost < best.total_cost else cons).append(
                f"{'Cheaper' if o.total_cost < best.total_cost else 'Costlier'}: {inr(o.total_cost)} vs {inr(best.total_cost)}.")
        if o.comfort_level and best.comfort_level and o.comfort_level > best.comfort_level:
            pros.append(f"Higher comfort ({o.comfort_level}/10).")
        alternatives.append({
            "name": o.name, "pros": pros or ["Reasonable alternative."],
            "cons": cons or ["No clear edge over the top pick."],
            "worth_it_line": worth_it_lines[len(alternatives)] if len(worth_it_lines) > len(alternatives) else "",
        })

    return {"best_why": why[:5], "alternatives": alternatives,
            "grounded": False, "llm": None}
