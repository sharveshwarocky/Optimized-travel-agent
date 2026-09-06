"""Cab estimator (tier 2, D17): formula only, always 🟠 estimated.

Fare = distance × per-km band (hatchback/sedan/SUV) + driver allowance +
tolls, floored at the operator minimum. Rates carry a last-verified note (R4).
"""
from __future__ import annotations

from collectors.base import BaseCollector, CollectResult
from collectors.road_collector import compute_road_profile
from config import settings
from services import normalizer


def cab_variants(profile) -> list[dict]:
    """One raw per vehicle band, sharing the road profile."""
    out = []
    for band, rate in settings.CAB_RATES_PER_KM.items():
        fare = profile.distance_km * rate + settings.CAB_DRIVER_ALLOWANCE
        fare = max(fare, settings.CAB_MIN_FARE)
        out.append({
            "name": f"Cab ({band}) — outstation",
            "source": "computed:cab-formula",
            "data_type": "estimated",
            "confidence": "medium",
            "operator": "typical operator rates",
            "driving_minutes": profile.driving_minutes,
            "total_cost": round(fare, 0),
            "notes": profile.notes + [
                f"₹{rate:g}/km {band.lower()} + ₹{settings.CAB_DRIVER_ALLOWANCE:g} driver allowance"
                f"{' (minimum fare applied)' if fare <= settings.CAB_MIN_FARE else ''}",
            ],
            "cost_breakdown": {"fuel+driver (est.)": int(fare - profile.tolls),
                               "tolls": int(profile.tolls)},
        })
    return out


class CabCollector(BaseCollector):
    mode = "cab"
    adapter_id = "cab-formula"

    async def _collect(self, req) -> CollectResult:
        profile = await compute_road_profile(req)
        if profile is None:
            return CollectResult(mode=self.mode, options=[], status="unavailable",
                                 detail="route between cities unknown (not in city table)")
        options = normalizer.normalize(cab_variants(profile), req, "cab")
        return CollectResult(mode=self.mode, options=options, status="ok",
                             detail=f"cab estimates for {profile.distance_km} km (🟠 estimated, D17)")
