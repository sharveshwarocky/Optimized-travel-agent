"""Worth-it engine tests (spec §11.3): computed comparisons only."""
from datetime import datetime

from models.travel_option import TravelOption
from models.travel_request import TravelRequest
from services.worth_it_engine import compare_pair, worth_it_lines


def _opt(**kw) -> TravelOption:
    base = dict(mode="train", name="Train", departure_location="A", arrival_location="B",
                source="erail", data_type="live",
                departure_time=datetime(2026, 9, 7, 8, 0),
                arrival_time=datetime(2026, 9, 7, 14, 0),
                travel_duration_minutes=360, door_to_door_duration_minutes=450,
                total_cost=2500.0, comfort_level=7)
    base.update(kw)
    return TravelOption(**base)


def test_rupees_per_hour():
    req = TravelRequest(passengers=2)
    cheaper = _opt(door_to_door_duration_minutes=450, total_cost=2500)
    pricier = _opt(name="Flight", mode="flight", door_to_door_duration_minutes=240,
                   total_cost=8000, comfort_level=8)
    c = compare_pair(cheaper, pricier, req)
    assert c is not None
    assert c.minutes_saved == 210
    assert c.rupees_per_hour_saved == (8000 - 2500) / 3.5
    assert c.verdict in ("worth_it", "marginal", "not_worth_it")


def test_no_time_savings_marginal():
    req = TravelRequest()
    c = compare_pair(_opt(), _opt(name="Same speed", door_to_door_duration_minutes=450,
                                  total_cost=4000), req)
    assert c is not None and c.rupees_per_hour_saved is None


def test_group_economics_own_car():
    req = TravelRequest(passengers=5)
    cheaper = _opt(total_cost=2500, cost_per_person=500)
    car = _opt(name="Own car", mode="own_car", door_to_door_duration_minutes=380,
               total_cost=4500, cost_per_person=900, comfort_level=7)
    c = compare_pair(cheaper, car, req)
    assert "near-flat per person" in c.reasoning


def test_worth_it_lines_format():
    req = TravelRequest(passengers=3, budget=6000)
    ranked = [
        _opt(name="Train", total_cost=2400, door_to_door_duration_minutes=450),
        _opt(name="Flight", mode="flight", total_cost=8000,
             door_to_door_duration_minutes=240, comfort_level=8),
    ]
    lines = worth_it_lines(ranked, req)
    assert len(lines) == 1
    assert "Flight" in lines[0] and "saved" in lines[0]
