"""Bus live-source stub (kept for gate history, D5 swap-friendliness).

The BusCollector now produces formula estimates (user decision), but this stub
remains so a future live adapter can be dropped in and preferred by the
collector — same pattern as the flight collector's live-first path.
"""
from __future__ import annotations

from data_sources.adapters.base import AdapterError, SourceAdapter
from models.research_plan import HealthReport
from models.travel_request import TravelRequest


class BusSourceStub(SourceAdapter):
    id = "bus-stub"

    async def health_check(self) -> HealthReport:
        return HealthReport(
            source_id=self.id, healthy=False,
            detail=("No live bus source passed the research gate (2026-09-06): abhibus is "
                    "JS-rendered with no discoverable endpoint; redbus.in unreachable."))

    async def collect(self, req: TravelRequest) -> list[dict]:
        raise AdapterError(
            "live bus data unavailable: no source passed the research gate "
            "(see data_sources/adapters/abhibus_bus_source.md)")
