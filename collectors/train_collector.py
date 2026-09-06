"""Train collector: erail adapter → normalizer → TravelOptions (spec §4)."""
from __future__ import annotations

from collectors.base import BaseCollector, CollectResult
from data_sources.adapters.train_source import ErailSource
from services import normalizer


class TrainCollector(BaseCollector):
    mode = "train"
    adapter_id = "erail"

    def __init__(self) -> None:
        super().__init__()
        self.adapter = ErailSource()

    async def _collect(self, req) -> CollectResult:
        health = await self.adapter.health_check()
        if not health.healthy:
            return CollectResult(mode=self.mode, options=[], status="unavailable",
                                 detail=f"erail unhealthy: {health.detail}")
        raws = await self.adapter.collect(req)
        options = normalizer.normalize(raws, req, "train")
        if not options:
            return CollectResult(mode=self.mode, options=[], status="empty",
                                 detail="no trains with parseable fares on this route/date")
        return CollectResult(mode=self.mode, options=options, status="ok",
                             detail=f"{len(options)} train options from erail (live)")
