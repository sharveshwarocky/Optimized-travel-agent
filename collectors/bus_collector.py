"""Bus collector: formula estimates (D17-pattern) since the research gate failed.

Gate finding (2026-09-06): abhibus is JS-rendered with no discoverable
endpoint; redbus.in unreachable — live bus data ships 🔴. Per the user's
decision, the mode now produces 🟠 formula-based estimates through the same
pipeline (per-seat-km bands in settings). If a live source passes the gate
later, prefer it here exactly like the flight collector does.
"""
from __future__ import annotations

from collectors.base import BaseCollector, CollectResult
from collectors.bus_estimator import bus_variants
from collectors.road_collector import compute_road_profile
from services import normalizer


class BusCollector(BaseCollector):
    mode = "bus"
    adapter_id = "bus-formula"

    async def _collect(self, req) -> CollectResult:
        profile = await compute_road_profile(req)
        if profile is None:
            return CollectResult(mode=self.mode, options=[], status="unavailable",
                                 detail="route between cities unknown (not in city table)")
        raws = bus_variants(profile.distance_km, req)
        options = normalizer.normalize(raws, req, "bus")
        if not options:
            return CollectResult(mode=self.mode, options=[], status="empty",
                                 detail="no bus service classes for this distance")
        return CollectResult(mode=self.mode, options=options, status="ok",
                             detail=f"bus estimates for {profile.distance_km:g} km "
                                    f"({len(options)} services, 🟠 estimated — no live bus "
                                    f"source passed the research gate)")
