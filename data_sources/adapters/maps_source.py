"""OSRM road-routing adapter (gate doc: data_sources/adapters/osrm_maps_source.md).

route/v1/driving/<lon1>,<lat1>;<lon2>,<lat2>?overview=false → routes[0].distance
(metres) and .duration (seconds). Falls back to a documented straight-line
estimate when the service is unreachable (marked 🟡 recent in provenance).
"""
from __future__ import annotations

import math

from config import settings
from data_sources.adapters.base import AdapterError, SourceAdapter, polite_get
from models.research_plan import HealthReport
from models.travel_request import TravelRequest

OSRM_URL = "https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"

# haversine → road factor for India (~1.25 detour index) at 45 km/h avg (fallback only)
ROAD_FACTOR = 1.25
FALLBACK_SPEED_KMH = 45.0


def parse_osrm(payload: dict) -> dict:
    """Pure parser: payload → {'distance_km': float, 'duration_minutes': float}."""
    routes = payload.get("routes") or []
    if not routes:
        raise AdapterError("OSRM: no routes in payload")
    r = routes[0]
    return {
        "distance_km": round(r["distance"] / 1000.0, 1),
        "duration_minutes": round(r["duration"] / 60.0, 1),
    }


def straight_line_estimate(lat1, lon1, lat2, lon2) -> dict:
    """Documented fallback when OSRM is down (🟡 recent, medium confidence)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dl / 2) ** 2
    km = 6371.0 * 2 * math.asin(math.sqrt(a)) * ROAD_FACTOR
    return {"distance_km": round(km, 1),
            "duration_minutes": round(km / FALLBACK_SPEED_KMH * 60.0, 1)}


class OSRMSource(SourceAdapter):
    id = "osrm"

    async def route(self, coord_from: tuple[float, float],
                    coord_to: tuple[float, float]) -> dict:
        lat1, lon1 = coord_from
        lat2, lon2 = coord_to
        url = OSRM_URL.format(lon1=lon1, lat1=lat1, lon2=lon2, lat2=lat2)
        resp = await polite_get(url, host_key="router.project-osrm.org")
        try:
            return parse_osrm(resp.json())
        except ValueError as exc:
            raise AdapterError(f"OSRM non-JSON: {exc}") from exc

    async def health_check(self) -> HealthReport:
        try:
            await self.route((13.0827, 80.2707), (12.9716, 77.5946))
            return HealthReport(source_id=self.id, healthy=True, detail="probe route OK")
        except AdapterError as exc:
            return HealthReport(source_id=self.id, healthy=False, detail=str(exc)[:200])

    async def collect(self, req: TravelRequest) -> list[dict]:  # not a mode collector
        raise NotImplementedError("OSRM is a sub-source; use route()/collect_route()")
