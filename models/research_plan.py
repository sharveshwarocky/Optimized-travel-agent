"""Research plan (LLM-produced, Python-validated) and source health reports (spec §5, §7.3)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from models.provenance import utcnow
from models.travel_request import ALL_MODES, Mode


class ResearchTask(BaseModel):
    mode: Mode
    priority: int = 1                    # 1 = research first
    reason: str = ""                     # why the planner included this mode
    sources: list[str] = Field(default_factory=list)  # adapter ids, may be empty → default


class ResearchPlan(BaseModel):
    """Which modes × sources to investigate. LLM drafts; Python validates and falls back."""

    tasks: list[ResearchTask] = Field(default_factory=list)
    planned_by: Literal["llm", "fallback"] = "fallback"

    def modes(self) -> list[Mode]:
        return [t.mode for t in self.tasks]


def default_research_plan(req) -> ResearchPlan:
    """Deterministic fallback plan (§10.3): every mode not explicitly avoided.

    Cab/rental are always included — they are local formula estimators (D17);
    own car is always computed per D16.
    """
    avoided = set(req.avoided_modes or [])
    tasks = [
        ResearchTask(mode=m, priority=1 if m in ("train", "bus", "flight") else 2,
                     reason="default plan (LLM planner unavailable)")
        for m in ALL_MODES
        if m not in avoided
    ]
    return ResearchPlan(tasks=tasks, planned_by="fallback")


class HealthReport(BaseModel):
    """Result of a source adapter health check (spec §7.3)."""

    source_id: str
    healthy: bool
    detail: str = ""
    checked_at: datetime = Field(default_factory=utcnow)
