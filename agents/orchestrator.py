"""Orchestrator (spec §4): wires agents → collectors → engines in order.

Collection is parallel (asyncio) with per-collector timeouts. Zero survivors
triggers conflict data (§12) that the CLI turns into a focused question; the
CLI applies the chosen relaxation and re-runs this pipeline (max 3 loops).
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field

from collectors.base import CollectResult
from collectors.bus_collector import BusCollector
from collectors.cab_estimator import CabCollector
from collectors.flight_collector import FlightCollector
from collectors.rental_estimator import RentalCollector
from collectors.road_collector import RoadCollector
from collectors.train_collector import TrainCollector
from config.prompts import load_prompt
from data_sources.adapters.base import close_http
from llm.client import LLMUnavailable, get_client, usage_log
from models.provenance import CONFIDENCE_DOT
from models.travel_option import TravelOption
from models.travel_request import ALL_MODES
from agents.planning_agent import build_plan
from agents.reasoning_agent import explain
from services.constraint_engine import ConstraintReport, filter_options
from services.scoring_engine import score_options
from services.worth_it_engine import worth_it_lines


@dataclass
class ModeStatus:
    mode: str
    status: str          # ok | empty | unavailable
    detail: str
    dot: str             # 🟢🟡🟠🔴


@dataclass
class ConflictInfo:
    summary: str
    question: str
    relaxable: list[str]           # constraint keys the user may relax
    violation_lines: list[str]     # exactly which constraints clashed (§12.1)


@dataclass
class PipelineResult:
    mode_statuses: list[ModeStatus] = field(default_factory=list)
    all_options: list[TravelOption] = field(default_factory=list)
    report: ConstraintReport | None = None
    ranked: list[TravelOption] = field(default_factory=list)
    weights: dict = field(default_factory=dict)
    profile: str = "balanced"
    worth_it: list[str] = field(default_factory=list)
    explanation: dict = field(default_factory=dict)
    planned_by: str = "fallback"
    fallbacks_fired: list[str] = field(default_factory=list)
    conflict: ConflictInfo | None = None
    relaxed_constraints: list[str] = field(default_factory=list)
    relaxed_result: list[TravelOption] = field(default_factory=list)  # least-violating (§12.4)
    llm_usage: str = ""

    @property
    def has_results(self) -> bool:
        return bool(self.ranked) or bool(self.relaxed_result)


_COLLECTORS = {
    "train": TrainCollector, "bus": BusCollector, "flight": FlightCollector,
    "own_car": RoadCollector, "cab": CabCollector, "rental": RentalCollector,
}


def _status_dot(result: CollectResult) -> str:
    if result.status == "unavailable":
        return CONFIDENCE_DOT["unavailable"]
    if result.status == "empty":
        return CONFIDENCE_DOT["recent"]
    types = {o.data_type for o in result.options}
    if "live" in types:
        return CONFIDENCE_DOT["live"]
    if "recent" in types:
        return CONFIDENCE_DOT["recent"]
    if "estimated" in types:
        return CONFIDENCE_DOT["estimated"]
    return CONFIDENCE_DOT["unavailable"]


async def draft_conflict_question(req, violation_lines: list[str]) -> ConflictInfo:
    """§12: Python computes the conflicts; the LLM only drafts the question text."""
    relaxable_candidates = []
    if req.arrival_deadline:
        relaxable_candidates.append("arrival_deadline")
    if req.budget is not None:
        relaxable_candidates.append("budget")
    if req.ac_required:
        relaxable_candidates.append("ac")
    if req.overnight_allowed is False:
        relaxable_candidates.append("overnight")
    if req.max_duration_hours:
        relaxable_candidates.append("max_duration")
    if req.avoided_modes:
        relaxable_candidates.append("avoided_modes")
    if not relaxable_candidates:
        relaxable_candidates = ["budget", "arrival_deadline"]

    question = ("No options meet all your constraints. Which should I relax first? "
                + " / ".join(r.replace("_", " ") for r in relaxable_candidates[:3]) + "?")
    summary = "Your constraints eliminated every option: " + " ".join(violation_lines[:2])

    client = get_client()
    if client.available:
        try:
            prompt = load_prompt("conflict", {
                "$REQUEST_JSON": json.dumps({
                    "budget": req.budget, "budget_flexibility": req.budget_flexibility,
                    "arrival_deadline": req.arrival_deadline.strftime("%H:%M") if req.arrival_deadline else None,
                    "ac_required": req.ac_required, "overnight_allowed": req.overnight_allowed,
                    "max_duration_hours": req.max_duration_hours,
                    "avoided_modes": req.avoided_modes,
                }, indent=1),
                "$CONFLICTS_JSON": json.dumps(violation_lines[:6], indent=1),
            })
            result = await client.chat_json(prompt["system"], prompt["user"], max_tokens=300)
            if result.parsed and result.parsed.get("question"):
                question = result.parsed["question"]
                summary = result.parsed.get("conflict_summary", summary)
        except LLMUnavailable:
            pass

    return ConflictInfo(summary=summary, question=question,
                        relaxable=relaxable_candidates, violation_lines=violation_lines)


async def run_pipeline(memory, relaxed_constraints: list[str] | None = None) -> PipelineResult:
    """Full pipeline (spec §4). `relaxed_constraints` lists hard constraints to skip
    (conflict-loop relaxations applied by the CLI, §12)."""
    relaxed = set(relaxed_constraints or [])
    req = memory.request
    result = PipelineResult(relaxed_constraints=list(relaxed))

    # ---- geo: fill coordinates for cities outside the curated table (§5) ----
    from utils import geo
    await geo.ensure_coords(req)

    # ---- planning ----
    plan = await build_plan(memory)
    result.planned_by = plan.planned_by
    if plan.planned_by == "fallback":
        result.fallbacks_fired.append("planning fallback (deterministic default plan)")

    # ---- parallel collection with per-collector timeouts ----
    wanted = [m for m in ALL_MODES if m in plan.modes()]
    coros = [_COLLECTORS[m]().collect_with_timeout(req) for m in wanted]
    collected: list[CollectResult] = list(await asyncio.gather(*coros, return_exceptions=True))
    for i, r in enumerate(collected):
        if isinstance(r, Exception):  # absolute containment
            r = CollectResult(mode=wanted[i], options=[], status="unavailable",
                              detail=f"collector crashed: {r}")
        result.all_options.extend(r.options)
        result.mode_statuses.append(
            ModeStatus(mode=r.mode, status=r.status, detail=r.detail, dot=_status_dot(r)))
    result.mode_statuses.sort(key=lambda ms: ALL_MODES.index(ms.mode))

    # ---- constraint filtering ----
    result.report = filter_options(result.all_options, req, relaxed=relaxed)

    # ---- zero survivors → conflict info for the CLI loop (§12) ----
    if not result.report.surviving:
        result.conflict = await draft_conflict_question(req, result.report.summary_lines())
        # least-violating presentation after loop exhaustion (§12.4)
        if len(relaxed) >= 3:
            result.relaxed_result = least_violating(result.all_options, req)[:3]
        await close_http()
        result.llm_usage = usage_log.summary()
        return result

    # ---- scoring + worth-it + reasoning ----
    scored = score_options(result.report.surviving, req)
    result.ranked = scored.ranked
    result.weights = scored.weights
    result.profile = scored.profile
    result.worth_it = worth_it_lines(scored.ranked, req)
    result.explanation = await explain(memory, scored.ranked, scored.weights,
                                       scored.profile, result.worth_it)
    if not result.explanation.get("grounded"):
        result.fallbacks_fired.append("reasoning fallback (template explanation)")

    await close_http()
    result.llm_usage = usage_log.summary()
    return result


def least_violating(options: list[TravelOption], req) -> list[TravelOption]:
    """§12.4: options with the fewest hard-constraint violations, clearly labeled."""
    from services.constraint_engine import evaluate_hard

    def _violations(o: TravelOption) -> list[str]:
        # count all violated hard constraints (not just one)
        v = evaluate_hard(o, req, _all=True)
        return v

    scored = [(o, _violations(o)) for o in options]
    scored.sort(key=lambda pair: len(pair[1]))
    out = []
    for o, viols in scored[:3]:
        o.constraint_violations = list(dict.fromkeys(o.constraint_violations + viols))
        out.append(o)
    return out
