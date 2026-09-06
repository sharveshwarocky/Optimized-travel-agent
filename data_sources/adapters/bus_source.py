"""Bus adapter stub (gate doc: data_sources/adapters/abhibus_bus_source.md).

Both probed OTA sources failed the research gate at build time (JS-only shells;
redbus.in unreachable). Per spec §3.3 the mode ships honestly 🔴 unavailable —
no fabricated data. The interface stays open: drop in a working adapter later
and the pipeline picks it up unchanged.
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
            detail=("No bus source passed the research gate (2026-09-06): abhibus is "
                    "JS-rendered with no discoverable endpoint; redbus.in unreachable."))

    async def collect(self, req: TravelRequest) -> list[dict]:
        raise AdapterError(
            "bus data unavailable: no source passed the research gate "
            "(see data_sources/adapters/abhibus_bus_source.md)")
