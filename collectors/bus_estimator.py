"""Bus estimator (D17-pattern): formula only, always 🟠 estimated.

Distance comes from the shared road profile (OSRM, straight-line fallback).
Fare = distance × per-seat-km service band (5 classes), floored at the
operator minimum. Durations use a documented 45 km/h average. Live bus data
stays unavailable per the research gate (abhibus_bus_source.md) — when a live
source passes later, BusCollector can prefer it exactly like the flight
collector does.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta

from config import settings
from models.travel_request import TravelRequest


def bus_variants(distance_km: float, req: TravelRequest) -> list[dict]:
    """Pure builder: distance + request → raw bus dicts (one per service class)."""
    duration_minutes = int(round(distance_km / settings.BUS_SPEED_KMH * 60.0))
    out: list[dict] = []
    travel_date = req.travel_date
    for service, rate in settings.BUS_CLASSES_PER_SEAT_PER_KM.items():
        fare_pp = max(settings.BUS_MIN_FARE, round(distance_km * rate, 0))
        is_sleeper = "Sleeper" in service
        is_ac = "AC" in service or "Volvo" in service
        for dep_str in settings.BUS_DEPARTURES:
            hh, mm = dep_str.split(":")
            if travel_date is None:
                continue  # caller guarantees a date; guard anyway
            dep = datetime.combine(travel_date, time(int(hh), int(mm)))
            arr = dep + timedelta(minutes=duration_minutes)
            out.append({
                "name": f"{service} bus — {req.source.city if req.source else '?'} to "
                        f"{req.destination.city if req.destination else '?'}",
                "source": "computed:bus-formula",
                "data_type": "estimated",
                "confidence": "medium",
                "operator": "typical operator rates (estimate)",
                "departure": dep,
                "arrival": arr,
                "duration_minutes": duration_minutes,
                "overnight": arr.date() > dep.date(),
                "price_per_person": fare_pp,
                "ac": is_ac,
                "sleeper": is_sleeper,
                "stops": 1 if distance_km > 300 else 0,
                "availability_status": None,
                "notes": [
                    f"≈{distance_km:g} km at {settings.BUS_SPEED_KMH:g} km/h average",
                    f"₹{rate:g}/seat-km {service.lower()} band (estimate)",
                ],
            })
    # sort by fare then departure for stable, readable output
    out.sort(key=lambda r: (r["price_per_person"], r["departure"]))
    return out
