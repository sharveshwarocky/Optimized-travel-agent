"""Flight estimator (D17-pattern): formula only, always 🟠 estimated.

Base fare from short-haul distance bands × carrier multiplier + ~12% taxes.
Duration from a documented 650 km/h cruise average. Routes beyond
FLIGHT_MAX_KM return no estimates (rail/car dominate; honest empty result).
"""
from __future__ import annotations

from datetime import datetime, time, timedelta

from config import settings
from models.travel_request import TravelRequest


def _base_fare(distance_km: float) -> float | None:
    for lo, hi, fare in settings.FLIGHT_DISTANCE_BANDS:
        if lo <= distance_km < hi:
            return fare
    return None


def flight_variants(distance_km: float, req: TravelRequest) -> list[dict]:
    """Pure builder: distance + request → raw flight dicts (carriers × departures)."""
    if distance_km > settings.FLIGHT_MAX_KM:
        return []
    base = _base_fare(distance_km)
    if base is None:
        return []
    duration_minutes = max(settings.FLIGHT_MIN_MINUTES,
                           int(round(distance_km / settings.FLIGHT_SPEED_KMH * 60.0)))
    travel_date = req.travel_date
    out: list[dict] = []
    for carrier, mult in settings.FLIGHT_CARRIER_MULTIPLIERS.items():
        price_pp = round(base * mult * (1 + settings.FLIGHT_TAXES_PCT), 0)
        for dep_str in settings.FLIGHT_DEPARTURES:
            hh, mm = dep_str.split(":")
            if travel_date is None:
                continue
            dep = datetime.combine(travel_date, time(int(hh), int(mm)))
            arr = dep + timedelta(minutes=duration_minutes)
            out.append({
                "name": f"{carrier} {req.source.airport_code or ''}"
                        f"→{req.destination.airport_code or ''} economy".replace("→→", "→"),
                "source": "computed:flight-formula",
                "data_type": "estimated",
                "confidence": "medium",
                "airline": carrier,
                "departure": dep,
                "arrival": arr,
                "duration_minutes": duration_minutes,
                "overnight": arr.date() > dep.date(),
                "price_per_person": price_pp,
                "stops": 0,
                "notes": [
                    f"distance band base ₹{base:g} × {mult:g} carrier factor + "
                    f"{settings.FLIGHT_TAXES_PCT:.0%} taxes (estimate)",
                ],
            })
    out.sort(key=lambda r: (r["price_per_person"], r["departure"]))
    return out
