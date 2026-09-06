"""Rental estimator (tier 2, D17): formula only, always 🟠 estimated.

Cost = daily rate × ceil(days) + extra-km charges beyond the daily cap +
fuel + tolls. Rates carry a last-verified note (R4).
"""
from __future__ import annotations

import math

from collectors.base import BaseCollector, CollectResult
from collectors.road_collector import compute_road_profile
from config import settings
from services import normalizer


def rental_variants(profile) -> list[dict]:
    """One raw per vehicle band, sharing the road profile."""
    days = max(1, math.ceil(profile.driving_minutes / (10 * 60)))  # ~10h driving days
    out = []
    for band, rate in settings.RENTAL_PER_DAY.items():
        cost = days * rate
        included_km = days * settings.RENTAL_KM_CAP_PER_DAY
        extra_km = max(0.0, profile.distance_km - included_km)
        extra = extra_km * settings.RENTAL_EXTRA_PER_KM
        total = cost + extra + profile.fuel_cost + profile.tolls
        out.append({
            "name": f"Self-drive {band} ({days} day{'s' if days > 1 else ''})",
            "source": "computed:rental-formula",
            "data_type": "estimated",
            "confidence": "medium",
            "operator": "typical self-drive rates",
            "driving_minutes": profile.driving_minutes,
            "total_cost": round(total, 0),
            "notes": profile.notes + [
                f"rental ₹{rate:g}/day × {days} + fuel ₹{profile.fuel_cost:.0f} + tolls ₹{profile.tolls:.0f}"
                + (f" + extra-km ₹{extra:.0f}" if extra else ""),
            ],
            "cost_breakdown": {"rental (est.)": int(cost + extra),
                               "fuel": int(profile.fuel_cost), "tolls": int(profile.tolls)},
        })
    return out


class RentalCollector(BaseCollector):
    mode = "rental"
    adapter_id = "rental-formula"

    async def _collect(self, req) -> CollectResult:
        profile = await compute_road_profile(req)
        if profile is None:
            return CollectResult(mode=self.mode, options=[], status="unavailable",
                                 detail="route between cities unknown (not in city table)")
        options = normalizer.normalize(rental_variants(profile), req, "rental")
        return CollectResult(mode=self.mode, options=options, status="ok",
                             detail=f"rental estimates for {profile.distance_km} km (🟠 estimated, D17)")
