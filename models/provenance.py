"""Provenance metadata for every collected value (spec §6.3, guide §10/§21).

Rule: never present estimates as live data. Confidence dots:
🟢 live · 🟡 recent · 🟠 estimated · 🔴 unavailable
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

DataType = Literal["live", "recent", "estimated", "unavailable"]
Confidence = Literal["high", "medium", "low"]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


CONFIDENCE_DOT: dict[str, str] = {
    "live": "🟢",
    "recent": "🟡",
    "estimated": "🟠",
    "unavailable": "🔴",
}


class Provenance(BaseModel):
    """Metadata attached to an individual collected value."""

    value: Any = None
    source: str
    retrieved_at: datetime = Field(default_factory=utcnow)
    data_type: DataType = "live"
    confidence: Confidence = "high"

    @property
    def dot(self) -> str:
        return CONFIDENCE_DOT.get(self.data_type, "🔴")
