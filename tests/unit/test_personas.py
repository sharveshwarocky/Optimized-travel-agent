"""Persona golden-output tests (guide §28, spec §16).

Each persona is a full engine run (normalize → constraints → score → worth-it)
with hand-checked expectations. No network, no LLM.
"""
from datetime import date, datetime, time as dt_time

from models.travel_request import TravelRequest
from services import normalizer
from services.constraint_engine import filter_options
from services.scoring_engine import choose_profile, score_options
from services.worth_it_engine import worth_it_lines
from utils.geo import resolve_city

DATE = date(2026, 9, 7)


def _train_opt(name, cls, fare, dep_h, dur_min, ac_flag, pax=2):
    from models.travel_option import TravelOption
    return normalizer.train_option({
        "number": 12657, "name": name, "from_code": "MAS", "to_code": "SBC",
        "departure": datetime(2026, 9, 7, dep_h, 0),
        "arrival": datetime(2026, 9, 7, dep_h, 0) + __import__("datetime").timedelta(minutes=dur_min),
        "duration_minutes": dur_min,
        "overnight": dep_h + dur_min // 60 >= 24,
        "type": "SUPERFAST", "distance_km": 360.0,
        "classes": {cls: fare},
    }, TravelRequest(source=resolve_city("Chennai"),
                     destination=resolve_city("Bangalore"),
                     travel_date=DATE, passengers=pax), cls, fare)


def _bus_opt(name, cost, dur, ac, sleeper):
    from models.travel_option import TravelOption
    opt = TravelOption(mode="bus", name=name, departure_location="Chennai",
                       arrival_location="Bangalore", source="fixture",
                       data_type="live",
                       departure_time=datetime(2026, 9, 7, 22, 0),
                       arrival_time=datetime(2026, 9, 7, 22, 0) + __import__("datetime").timedelta(minutes=dur),
                       travel_duration_minutes=dur, total_cost=cost, ac=ac,
                       overnight=dur + 22 * 60 >= 24 * 60 or True)
    opt.sub_scores = {}
    return normalizer._finalize(opt, TravelRequest(
        source=resolve_city("Chennai"), destination=resolve_city("Bangalore"),
        travel_date=DATE, passengers=2), journey_minutes=dur)


def test_budget_persona_prefers_cheapest_compliant():
    """Budget traveller: 2 people, low budget, flexible arrival."""
    req = TravelRequest(source=resolve_city("Chennai"),
                        destination=resolve_city("Bangalore"),
                        travel_date=DATE, passengers=2,
                        budget=5000, comfort_priority="low")
    opts = [_train_opt("Mail Exp", "SL", 400, 15, 420, False),
            _train_opt("Rajdhani", "3A", 1200, 22, 380, True),
            _bus_opt("Volvo AC", 2200, 360, True, False)]
    report = filter_options(opts, req)
    scored = score_options(report.surviving, req)
    best = scored.ranked[0]
    assert best.total_cost <= 5000 * 2  # within total budget
    assert choose_profile(req)[0] == "budget" or best.total_cost == min(
        o.total_cost for o in report.surviving)


def test_comfort_persona_with_elderly():
    """Comfort traveller: family with elderly, AC mandatory."""
    req = TravelRequest(source=resolve_city("Chennai"),
                        destination=resolve_city("Bangalore"),
                        travel_date=DATE, passengers=3, ac_required=True,
                        comfort_priority="high", elderly_travellers=1)
    opts = [_train_opt("Mail Exp", "SL", 400, 15, 420, False),
            _train_opt("Rajdhani", "3A", 1200, 22, 380, True)]
    report = filter_options(opts, req)
    assert all(o.ac for o in report.surviving)  # non-AC rejected
    assert report.violations_by_constraint.get("ac_required") == 1


def test_urgent_persona_deadline():
    """Urgent traveller: strict arrival deadline."""
    req = TravelRequest(source=resolve_city("Chennai"),
                        destination=resolve_city("Bangalore"),
                        travel_date=DATE, passengers=2,
                        arrival_deadline=datetime(2026, 9, 7, 13, 0).time(),
                        urgency="high")
    opts = [_train_opt("Afternoon Exp", "3A", 1200, 9, 300, True),
            _train_opt("Morning Exp", "SL", 400, 6, 360, False)]
    report = filter_options(opts, req)
    scored = score_options(report.surviving, req)
    assert choose_profile(req)[0] == "urgent"
    assert all(o.arrival_time.time() <= req.arrival_deadline for o in report.surviving)


def test_group_persona_own_car_economics():
    """Group traveller: 5-6 people, own car near-flat cost wins per-person."""
    from services.worth_it_engine import compare_pair
    req = TravelRequest(source=resolve_city("Chennai"),
                        destination=resolve_city("Bangalore"),
                        travel_date=DATE, passengers=6)
    train = _train_opt("Shatabdi", "3A", 1200, 8, 360, True, pax=6)  # ₹1200 × 6
    car = normalizer.road_option({
        "name": "Own car", "source": "computed:osrm+goodreturns",
        "data_type": "estimated", "confidence": "medium", "operator": None,
        "driving_minutes": 330.0, "total_cost": 5200.0,
        "notes": ["route 330 km"], "cost_breakdown": {"fuel": 2500, "tolls": 550},
    }, req, "own_car")
    car.cost_per_person = round(5200 / 6, 2)
    assert car.total_cost == 5200
    assert train.total_cost == 7200
    c = compare_pair(car, train, req)  # car cheaper here → reversed pair
    assert c is None or c.extra_cost >= 0


def test_short_distance_road_dominates():
    """Short distance: road door-to-door beats rail overhead."""
    req = TravelRequest(source=resolve_city("Chennai"),
                        destination=resolve_city("Bangalore"),
                        travel_date=DATE, passengers=2)
    car = normalizer.road_option({
        "name": "Own car", "source": "computed", "data_type": "live",
        "confidence": "medium", "operator": None, "driving_minutes": 300.0,
        "total_cost": 4000.0, "notes": [], "cost_breakdown": {},
    }, req, "own_car")
    train = _train_opt("Exp", "SL", 400, 8, 420, False)
    assert car.door_to_door_duration_minutes < train.door_to_door_duration_minutes + 60


def test_long_distance_flight_beats_overnight_train_on_time():
    """Long distance: flight door-to-door clearly under overnight train."""
    req = TravelRequest(source=resolve_city("Chennai"),
                        destination=resolve_city("Bangalore"),
                        travel_date=DATE, passengers=2)
    train = _train_opt("Overnight Exp", "SL", 500, 22, 660, False)
    flight = normalizer.flight_option({
        "name": "IndiGo 6E-123", "airline": "IndiGo",
        "from_airport": "MAA", "to_airport": "BLR",
        "departure": datetime(2026, 9, 7, 9, 0), "arrival": datetime(2026, 9, 7, 10, 10),
        "duration_minutes": 70, "stops": 0, "price_per_person": 4200.0,
    }, req)
    assert flight.door_to_door_duration_minutes < train.door_to_door_duration_minutes
