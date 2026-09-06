"""Own-car collector (D16: always computed).

Deterministic Python math from three sub-sources (spec §7.2):
  distance/duration ← OSRM (🟢 live, fallback 🟡 documented straight-line)
  fuel price        ← goodreturns (🟢 live, fallback 🟡 recent)
  tolls             ← blended ₹/km table in settings (🟡 recent, R5)
Cost = (km / mileage) × ₹/L + km × toll_rate. Road math feeds cab/rental too.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from collectors.base import BaseCollector, CollectResult
from config import settings
from data_sources.adapters.fuel_source import GoodreturnsFuelSource
from data_sources.adapters.maps_source import OSRMSource
from services import normalizer
from utils.geo import city_coords


@dataclass
class RoadProfile:
    distance_km: float
    driving_minutes: float
    fuel_price: float          # ₹/L actually used
    fuel_provenance: str       # "live" | "recent"
    fuel_price_source: str
    tolls: float
    fuel_cost: float
    total_cost: float          # fuel + tolls (vehicle-only; cab/rental add on top)
    notes: list[str] = field(default_factory=list)
    route_data_type: str = "live"


async def compute_road_profile(req) -> RoadProfile | None:
    """Shared road math for own_car/cab/rental. None when route unknown."""
    src = city_coords(req.source)
    dst = city_coords(req.destination)
    if not src or not dst:
        return None
    osrm = OSRMSource()
    route: dict
    data_type = "live"
    try:
        route = await osrm.route(src, dst)
    except Exception:
        from data_sources.adapters.maps_source import straight_line_estimate
        route = straight_line_estimate(src[0], src[1], dst[0], dst[1])
        data_type = "recent"
        route["notes_fallback"] = True

    fuel_src = GoodreturnsFuelSource()
    p1 = await fuel_src.petrol_price(req.source)
    p2 = await fuel_src.petrol_price(req.destination)
    fuel_price = max(p1.value, p2.value)   # conservative: pricier side of the route
    fuel_prov = "live" if (p1.data_type == "live" or p2.data_type == "live") else "recent"
    fuel_src_name = f"{p1.source} / {p2.source}"

    km = route["distance_km"]
    litres = km / settings.MILEAGE_KM_PER_LITRE
    fuel_cost = litres * fuel_price
    tolls = km * settings.TOLL_PER_KM
    notes = [
        f"route {km} km via {'OSRM' if route.get('notes_fallback') is None else 'straight-line fallback'}",
        f"fuel {litres:.1f} L @ ₹{fuel_price:.2f}/L ({fuel_prov})",
        f"tolls ₹{tolls:.0f} (blended ₹{settings.TOLL_PER_KM}/km)",
    ]
    return RoadProfile(
        distance_km=km,
        driving_minutes=route["duration_minutes"],
        fuel_price=fuel_price,
        fuel_provenance=fuel_prov,
        fuel_price_source=fuel_src_name,
        tolls=round(tolls, 0),
        fuel_cost=round(fuel_cost, 0),
        total_cost=round(fuel_cost + tolls, 0),
        notes=notes,
        route_data_type=data_type,
    )


class RoadCollector(BaseCollector):
    mode = "own_car"
    adapter_id = "osrm+goodreturns"

    def __init__(self) -> None:
        super().__init__()

    async def _collect(self, req) -> CollectResult:
        profile = await compute_road_profile(req)
        if profile is None:
            return CollectResult(mode=self.mode, options=[], status="unavailable",
                                 detail="route between cities unknown (not in city table)")
        raw = {
            "name": f"Own car — {req.source.city if req.source else '?'} to "
                    f"{req.destination.city if req.destination else '?'}",
            "source": "computed:osrm+goodreturns",
            "data_type": profile.route_data_type if profile.fuel_provenance == "live" else "recent",
            "confidence": "medium" if profile.route_data_type == "live" else "low",
            "operator": None,
            "driving_minutes": profile.driving_minutes,
            "total_cost": profile.total_cost,
            "notes": profile.notes,
            "cost_breakdown": {"fuel": int(profile.fuel_cost), "tolls": int(profile.tolls)},
        }
        options = normalizer.normalize([raw], req, "own_car")
        return CollectResult(mode=self.mode, options=options, status="ok",
                             detail=f"own car computed: {profile.distance_km} km, "
                                    f"₹{profile.total_cost:.0f} (fuel+tolls)")
