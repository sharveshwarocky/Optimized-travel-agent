"""Bus collector: currently an honest unavailable (gate FAIL, spec §3.3).

If a bus source passes the gate later, wire its adapter here and the rest of
the pipeline (normalizer → engines → UI) works unchanged.
"""
from __future__ import annotations

from collectors.base import BaseCollector, CollectResult
from data_sources.adapters.bus_source import BusSourceStub
from models.travel_request import TravelRequest


class BusCollector(BaseCollector):
    mode = "bus"
    adapter_id = "bus-stub"

    def __init__(self) -> None:
        super().__init__()
        self.adapter = BusSourceStub()

    async def _collect(self, req: TravelRequest) -> CollectResult:
        health = await self.adapter.health_check()
        return CollectResult(mode=self.mode, options=[], status="unavailable",
                             detail=health.detail or "bus source unavailable")
