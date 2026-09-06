"""Scoring engine tests (spec §11.2): deterministic, transparent, dynamic weights."""
from datetime import date, datetime, time

from models.travel_option import TravelOption
from models.travel_request import TravelRequest
from services.scoring_engine import choose_profile, score_options


def _opt(**kw) -> TravelOption:
    base = dict(mode="train", name="T Express", departure_location="A",
                arrival_location="B", source="erail", data_type="live",
                departure_time=datetime(2026, 9, 7, 8, 0),
                arrival_time=datetime(2026, 9, 7, 14, 0),
                travel_duration_minutes=360, door_to_door_duration_minutes=450,
                total_cost=5000.0, cost_per_person=1666.7, comfort_level=7, ac=True)
    base.update(kw)
    return TravelOption(**base)


def test_urgent_profile_on_deadline():
    req = TravelRequest(urgency="high")
    profile, weights = choose_profile(req)
    assert profile == "urgent" and weights["time"] == 0.40


def test_comfort_profile():
    profile, _ = choose_profile(TravelRequest(comfort_priority="high"))
    assert profile == "comfort"


def test_budget_profile_strict():
    profile, _ = choose_profile(TravelRequest(budget_flexibility="strict"))
    assert profile == "budget"


def test_group_profile():
    profile, _ = choose_profile(TravelRequest(passengers=6))
    assert profile == "group"


def test_scores_in_range_and_ranked():
    req = TravelRequest(passengers=3, budget=8000)
    opts = [_opt(), _opt(name="Cheap slow", mode="bus", total_cost=2000,
                         cost_per_person=666.7, comfort_level=4,
                         door_to_door_duration_minutes=540),
            _opt(name="Fast pricey", mode="flight", total_cost=12000,
                 cost_per_person=4000, comfort_level=8,
                 door_to_door_duration_minutes=300)]
    ranked = score_options(opts, req).ranked
    assert len(ranked) == 3
    scores = [o.overall_score for o in ranked]
    assert scores == sorted(scores, reverse=True)
    assert all(0 <= s <= 100 for s in scores)
    for o in ranked:
        assert o.sub_scores.get("cost") is not None
        assert o.sub_scores.get("time") is not None
        for k in ("cost", "time", "comfort", "conv", "pref", "schedule"):
            assert k in o.sub_scores


def test_sub_scores_complete_for_explain():
    req = TravelRequest(arrival_deadline=time(18, 0))
    ranked = score_options([_opt()], req).ranked
    assert set(ranked[0].sub_scores) == {"cost", "time", "comfort", "conv", "pref", "schedule"}
