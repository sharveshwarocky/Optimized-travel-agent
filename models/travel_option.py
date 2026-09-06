"""TravelOption model (spec §6.2) — the common normalized shape for all modes."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from models.provenance import Confidence, DataType
from models.travel_request import Mode


class TravelOption(BaseModel):
    model_config = {"validate_assignment": True}

    mode: Mode
    name: str                            # "Shatabdi Express", "VRL Volvo Sleeper", ...
    operator: str | None = None

    departure_location: str
    arrival_location: str
    departure_time: datetime | None = None
    arrival_time: datetime | None = None
    travel_duration_minutes: int | None = None
    overnight: bool = False

    total_cost: float | None = None      # for the whole party
    cost_per_person: float | None = None
    ac: bool | None = None
    comfort_level: int | None = None     # 1–10, from services/comfort_model.py
    comfort_notes: list[str] = Field(default_factory=list)

    door_to_door_duration_minutes: int | None = None
    door_to_door_breakdown: dict[str, int] = Field(default_factory=dict)

    availability_status: str | None = None   # "available", "waitlist 23", "sold out", None=unknown
    stops: int | None = None
    baggage_note: str | None = None

    # Provenance — every value-carrying option must have this (guide §21)
    source: str                          # adapter id, e.g. "erail", "skiplagged"
    data_type: DataType = "live"
    retrieved_at: datetime = Field(default_factory=datetime.now)
    confidence: Confidence = "high"

    reliability_score: int = 7           # static per-mode default in v1 (D12)

    # Engine outputs (filled by constraint/scoring engines; not part of collection)
    constraint_violations: list[str] = Field(default_factory=list)
    sub_scores: dict[str, float | str] = Field(default_factory=dict)  # str keys hold e.g. train class
    overall_score: float | None = None

    def display_cost(self) -> str:
        if self.total_cost is None:
            return "—"
        return f"₹{self.total_cost:,.0f}"
