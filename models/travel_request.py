"""TravelRequest model (spec §6.1) — one-way trips in v1, extensible per D10."""
from __future__ import annotations

from datetime import date, time
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Mode = Literal["train", "bus", "flight", "own_car", "cab", "rental"]

ALL_MODES: tuple[Mode, ...] = ("train", "bus", "flight", "own_car", "cab", "rental")


class LocationRef(BaseModel):
    """A resolved location: city + optional station/airport/terminal hints."""

    city: str
    station_code: str | None = None      # e.g. "MAS", "SBC"
    airport_code: str | None = None      # IATA, e.g. "MAA", "BLR"
    bus_terminal: str | None = None
    resolved: bool = False               # True once geo.py matched a known city

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.city


class TravelRequest(BaseModel):
    """Accumulating structured travel request for one session."""

    model_config = {"validate_assignment": True}

    # Route
    source: LocationRef | None = None
    destination: LocationRef | None = None

    # Time
    travel_date: date | None = None
    preferred_departure_after: time | None = None
    arrival_deadline: time | None = None
    max_duration_hours: float | None = None
    date_flexible_days: int = 0

    # Travellers
    passengers: int | None = None        # total
    adults: int | None = None
    children: int = 0                    # affects comfort model, not seat math in v1
    elderly_travellers: int = 0

    # Budget
    budget: float | None = None
    budget_type: Literal["total", "per_person"] = "total"
    budget_flexibility: Literal["strict", "flexible"] = "flexible"

    # Comfort & preferences
    comfort_priority: Literal["low", "medium", "high"] = "medium"
    ac_required: bool | None = None      # None = no preference
    sleeper_preferred: bool | None = None
    overnight_allowed: bool | None = None  # None = no preference
    luggage_level: Literal["light", "normal", "heavy"] = "normal"
    urgency: Literal["low", "medium", "high"] = "low"
    preferred_modes: list[Mode] = Field(default_factory=list)
    avoided_modes: list[Mode] = Field(default_factory=list)

    # Extension points (D10: one-way only in v1, model must not preclude later)
    trip_type: Literal["one_way"] = "one_way"
    return_date: date | None = None      # rejected by CLI in v1 if set
    legs: list["TravelRequest"] | None = None  # reserved for multi-city

    # Session bookkeeping
    open_questions: list[str] = Field(default_factory=list)
    raw_user_text: list[str] = Field(default_factory=list)

    @field_validator("passengers", "adults")
    @classmethod
    def _positive(cls, v: int | None) -> int | None:
        if v is not None and v < 1:
            raise ValueError("passenger counts must be >= 1")
        return v

    @field_validator("return_date")
    @classmethod
    def _reject_round_trip(cls, v: date | None) -> date | None:
        if v is not None:
            raise ValueError("Round trips are not supported in v1 (one-way only).")
        return v

    def effective_passengers(self) -> int:
        """Total travellers; falls back to adults or 1."""
        if self.passengers:
            return self.passengers
        if self.adults:
            return self.adults + self.children + self.elderly_travellers
        return 1


# Forward ref resolution for the self-referential legs field
TravelRequest.model_rebuild()
