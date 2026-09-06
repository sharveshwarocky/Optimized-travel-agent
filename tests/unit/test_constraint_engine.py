"""Constraint engine tests (spec §11.1) incl. conflict-loop relaxation (§12)."""
from datetime import date, datetime, time

from models.travel_option import TravelOption
from models.travel_request import TravelRequest
from services.constraint_engine import evaluate_hard, filter_options


def _opt(**kw) -> TravelOption:
    base = dict(mode="train", name="T Express", departure_location="A",
                arrival_location="B", source="erail", data_type="live",
                departure_time=datetime(2026, 9, 7, 8, 0),
                arrival_time=datetime(2026, 9, 7, 14, 0),
                travel_duration_minutes=360, total_cost=5000.0, ac=True)
    base.update(kw)
    return TravelOption(**base)


def test_no_violation_when_request_empty():
    req = TravelRequest()
    assert evaluate_hard(_opt(), req) is None


def test_strict_budget_rejects():
    req = TravelRequest(budget=4000, budget_flexibility="strict")
    assert evaluate_hard(_opt(total_cost=4500), req) == "budget_strict"
    assert evaluate_hard(_opt(total_cost=4000), req) is None


def test_flexible_budget_does_not_reject():
    req = TravelRequest(budget=4000, budget_flexibility="flexible")
    assert evaluate_hard(_opt(total_cost=4500), req) is None


def test_arrival_deadline_rejects():
    req = TravelRequest(arrival_deadline=time(13, 0))
    assert evaluate_hard(_opt(arrival_time=datetime(2026, 9, 7, 14, 0)), req) == "arrival_deadline"


def test_ac_required_rejects_nonac():
    req = TravelRequest(ac_required=True)
    assert evaluate_hard(_opt(ac=False), req) == "ac_required"


def test_overnight_disallowed():
    req = TravelRequest(overnight_allowed=False)
    late = _opt(overnight=True,
                departure_time=datetime(2026, 9, 7, 22, 0),
                arrival_time=datetime(2026, 9, 8, 5, 0))
    assert evaluate_hard(late, req) == "overnight_disallowed"


def test_max_duration():
    req = TravelRequest(max_duration_hours=5)
    assert evaluate_hard(_opt(travel_duration_minutes=360), req) == "max_duration"


def test_avoided_mode():
    req = TravelRequest(avoided_modes=["flight"])
    assert evaluate_hard(_opt(mode="flight"), req) == "mode_avoided"


def test_filter_and_relaxation():
    req = TravelRequest(budget=4000, budget_flexibility="strict", ac_required=True)
    opts = [_opt(total_cost=4500),                      # violates budget only
            _opt(name="B", total_cost=3000, ac=False)]  # violates AC only
    report = filter_options(opts, req)
    assert len(report.surviving) == 0
    assert set(report.violations_by_constraint) == {"budget_strict", "ac_required"}

    report2 = filter_options(opts, req, relaxed={"budget_strict"})
    assert len(report2.surviving) == 1
    assert report2.surviving[0].name == "T Express"  # the 4500 one now passes


def test_all_violations_mode():
    req = TravelRequest(budget=100, budget_flexibility="strict",
                        arrival_deadline=time(9, 0), ac_required=True)
    opt = _opt(ac=False, total_cost=9999)
    viols = evaluate_hard(opt, req, _all=True)
    assert set(viols) == {"budget_strict", "arrival_deadline", "ac_required"}
