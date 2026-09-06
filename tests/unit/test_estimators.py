"""Estimator tests (D17-pattern): pricing bands, party math, constraint interplay."""
from datetime import date

from collectors.bus_estimator import bus_variants
from collectors.flight_estimator import flight_variants
from collectors.road_collector import compute_road_profile
from config import settings
from models.travel_request import TravelRequest
from services import normalizer
from utils.geo import resolve_city

DATE = date(2026, 9, 7)


def _req(pax=3, **kw):
    base = dict(source=resolve_city("Chennai"), destination=resolve_city("Bangalore"),
                travel_date=DATE, passengers=pax)
    base.update(kw)
    return TravelRequest(**base)


def test_bus_variants_cover_all_classes_and_departures():
    raws = bus_variants(347.0, _req())
    n_classes = len(settings.BUS_CLASSES_PER_SEAT_PER_KM)
    n_deps = len(settings.BUS_DEPARTURES)
    assert len(raws) == n_classes * n_deps
    assert all(r["data_type"] == "estimated" for r in raws)
    assert all(r["price_per_person"] > 0 for r in raws)


def test_bus_fare_math():
    rate = settings.BUS_CLASSES_PER_SEAT_PER_KM["AC Sleeper"]
    raws = bus_variants(400.0, _req())
    ac_sleeper = [r for r in raws if r["name"].startswith("AC Sleeper")]
    assert ac_sleeper
    assert ac_sleeper[0]["price_per_person"] == round(400.0 * rate, 0)
    assert ac_sleeper[0]["ac"] is True and ac_sleeper[0]["sleeper"] is True


def test_bus_min_fare_floor():
    raws = bus_variants(50.0, _req())
    assert all(r["price_per_person"] >= settings.BUS_MIN_FARE for r in raws)


def test_bus_overnight_flag_on_late_departure():
    raws = bus_variants(500.0, _req())  # ~11h journey → 22:30 dep arrives next day
    late = [r for r in raws if r["departure"].hour >= 22]
    assert late and all(r["overnight"] for r in late)


def test_bus_normalized_total_scales_with_party():
    req = _req(pax=4)
    raws = bus_variants(347.0, req)
    opts = normalizer.normalize(raws, req, "bus")
    o = opts[0]
    assert o.total_cost == round(o.cost_per_person * 4, 2)
    assert o.data_type == "estimated" and o.source == "computed:bus-formula"


def test_flight_variants_distance_bands_and_carriers():
    raws = flight_variants(347.0, _req())  # ≤500 km band
    base = settings.FLIGHT_DISTANCE_BANDS[0][2]
    assert len(raws) == len(settings.FLIGHT_CARRIER_MULTIPLIERS) * len(settings.FLIGHT_DEPARTURES)
    indi = [r for r in raws if r["airline"] == "IndiGo"]
    assert indi[0]["price_per_person"] == round(base * 1.0 * 1.12, 0)
    assert all(r["duration_minutes"] == max(60, round(347 / 650 * 60)) for r in raws)


def test_flight_estimates_refuse_long_haul():
    assert flight_variants(2000.0, _req()) == []


def test_flight_normalized_option_shape():
    req = _req(pax=3)
    raws = flight_variants(347.0, req)
    opts = normalizer.normalize(raws, req, "flight")
    o = opts[0]
    assert o.mode == "flight" and o.ac is True and o.stops == 0
    assert o.total_cost > o.cost_per_person  # 3 travellers
    assert o.door_to_door_duration_minutes > o.travel_duration_minutes  # airport overhead


def test_deadline_constraint_interacts_with_estimates():
    """Estimated options flow through the constraint engine like live ones."""
    from datetime import datetime, time
    from services.constraint_engine import evaluate_hard
    req = _req(pax=3, arrival_deadline=time(9, 0))
    raws = bus_variants(347.0, req)
    opts = normalizer.normalize(raws, req, "bus")
    rejected = [o for o in opts if evaluate_hard(o, req) == "arrival_deadline"]
    assert rejected  # some bus departures arrive after 09:00
    surviving = [o for o in opts if evaluate_hard(o, req) is None]
    assert surviving  # the 06:30 departure makes it


def test_road_profile_supports_estimators():
    """Integration: shared road profile feeds both estimators."""
    import asyncio

    async def go():
        profile = await compute_road_profile(_req())
        return profile

    profile = asyncio.run(go())
    assert profile is not None and profile.distance_km > 200
    buses = bus_variants(profile.distance_km, _req())
    flights = flight_variants(profile.distance_km, _req())
    assert buses and flights
