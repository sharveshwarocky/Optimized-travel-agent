"""Flight collector: skiplagged adapter → normalizer → TravelOptions (spec §4).

Gate finding (2026-09-06): skiplagged serves a Cloudflare JS challenge to
Python's TLS fingerprint, so live collection is unavailable (spec R1 worst
case — honest 🔴, never fabricated). Parser + fixture tests stay green; swap
in a keyed flight API (Amadeus free tier) by replacing SkiplaggedSource.
"""
from __future__ import annotations

from collectors.base import BaseCollector, CollectResult
from data_sources.adapters.flight_source import SkiplaggedSource
from services import normalizer


class FlightCollector(BaseCollector):
    mode = "flight"
    adapter_id = "skiplagged"

    def __init__(self) -> None:
        super().__init__()
        self.adapter = SkiplaggedSource()

    async def _collect(self, req) -> CollectResult:
        health = await self.adapter.health_check()
        if not health.healthy:
            return CollectResult(mode=self.mode, options=[], status="unavailable",
                                 detail=f"skiplagged unhealthy: {health.detail}")
        raws = await self.adapter.collect(req)
        options = normalizer.normalize(raws, req, "flight")
        if not options:
            return CollectResult(mode=self.mode, options=[], status="empty",
                                 detail="no eligible flights (≤1 stop) found for this date")
        return CollectResult(mode=self.mode, options=options, status="ok",
                             detail=f"{len(options)} flight options from skiplagged (live)")
