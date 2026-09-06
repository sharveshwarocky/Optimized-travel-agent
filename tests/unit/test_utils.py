"""Time + cost util tests."""
from datetime import date, time

from utils.cost_utils import inr, normalize_budget, parse_rupee_amount, per_person
from utils.time_utils import minutes_to_hm, parse_deadline_time, parse_travel_date


def test_parse_tomorrow():
    today = date(2026, 9, 6)
    assert parse_travel_date("tomorrow", today) == date(2026, 9, 7)


def test_parse_next_friday():
    today = date(2026, 9, 6)  # Sunday
    assert parse_travel_date("next friday", today) == date(2026, 9, 11)


def test_parse_explicit_date():
    assert parse_travel_date("07-09-2026", date(2026, 9, 6)) == date(2026, 9, 7)


def test_parse_garbage_returns_none():
    assert parse_travel_date("someday soon maybe", date(2026, 9, 6)) is None


def test_deadline_6pm():
    assert parse_deadline_time("reach before 6 PM") == time(18, 0)
    assert parse_deadline_time("by 19:30") == time(19, 30)
    assert parse_deadline_time("before 7 pm") == time(19, 0)


def test_inr_grouping():
    assert inr(1234567) == "₹12,34,567"
    assert inr(5000) == "₹5,000"
    assert inr(None) == "—"


def test_per_person():
    assert per_person(6000, 3) == 2000.0
    assert per_person(None, 3) is None


def test_normalize_budget():
    assert normalize_budget(2000, "per_person", 3) == 6000
    assert normalize_budget(6000, "total", 3) == 6000


def test_parse_rupee_amount():
    assert parse_rupee_amount("budget is ₹6k") == 6000.0
    assert parse_rupee_amount("we have rs 5,500") == 5500.0
    assert parse_rupee_amount("no money mentioned") is None


def test_minutes_to_hm():
    assert minutes_to_hm(390) == "6h 30m"
    assert minutes_to_hm(None) == "—"
