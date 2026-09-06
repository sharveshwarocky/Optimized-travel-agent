"""Model tests (spec §6)."""
from datetime import date, time

import pytest
from pydantic import ValidationError

from models.provenance import Provenance
from models.travel_option import TravelOption
from models.travel_request import LocationRef, TravelRequest


def test_travel_request_defaults():
    r = TravelRequest()
    assert r.trip_type == "one_way"
    assert r.budget_type == "total"
    assert r.passengers is None
    assert r.effective_passengers() == 1


def test_effective_passengers_prefers_total():
    r = TravelRequest(passengers=3, adults=2)
    assert r.effective_passengers() == 3
    r2 = TravelRequest(adults=2, children=1)
    assert r2.effective_passengers() == 3


def test_round_trip_rejected_in_v1():
    with pytest.raises(ValidationError):
        TravelRequest(return_date=date(2026, 9, 10))


def test_negative_passengers_rejected():
    with pytest.raises(ValidationError):
        TravelRequest(passengers=0)


def test_provenance_dot():
    p = Provenance(value=500, source="x", data_type="live", confidence="high")
    assert p.dot == "🟢"
    assert Provenance(value=None, source="x", data_type="estimated").dot == "🟠"


def test_travel_option_required_fields():
    o = TravelOption(mode="train", name="Test Express", departure_location="A",
                     arrival_location="B", source="erail", data_type="live")
    assert o.reliability_score == 7
    assert o.display_cost() == "—"
    o.total_cost = 2500.0
    assert "₹2,500" in o.display_cost()
