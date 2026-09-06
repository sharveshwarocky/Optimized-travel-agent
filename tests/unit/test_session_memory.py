"""Session memory tests (spec §13): additive merges, latest-wins, never-re-ask."""
from datetime import date, time

from memory.session_memory import SessionMemory


def test_merge_route_and_date():
    m = SessionMemory()
    m.merge({"source": "Chennai", "destination": "Bangalore", "travel_date": "tomorrow"})
    assert m.request.source.city == "Chennai"
    assert m.request.destination.city == "Bangalore"
    assert m.request.travel_date == date.today() + __import__("datetime").timedelta(days=1)


def test_latest_wins_with_confirmation():
    m = SessionMemory()
    m.merge({"passengers": 2})
    confirmations = m.merge({"passengers": 4})
    assert m.request.passengers == 4
    assert any("4" in c for c in confirmations)


def test_no_confirmation_without_change():
    m = SessionMemory()
    m.merge({"passengers": 3})
    assert m.merge({"passengers": 3}) == []


def test_alias_resolution_updates():
    m = SessionMemory()
    m.merge({"destination": "Bangalore"})
    confirmations = m.merge({"destination": "Bengaluru"})
    assert m.request.destination.city == "Bengaluru"
    assert confirmations  # spoken override


def test_deadline_merge():
    m = SessionMemory()
    m.merge({"arrival_deadline": "before 6 PM"})
    assert m.request.arrival_deadline == time(18, 0)


def test_modes_merge_additive():
    m = SessionMemory()
    m.merge({"avoided_modes": ["flight"]})
    m.merge({"avoided_modes": ["bus"]})
    assert set(m.request.avoided_modes) == {"flight", "bus"}


def test_never_re_ask_tracking():
    m = SessionMemory()
    m.mark_asked("passengers")
    assert m.has_asked("passengers")
    assert not m.has_asked("budget")


def test_reset():
    m = SessionMemory()
    m.merge({"source": "Chennai", "passengers": 2})
    m.add_user_text("hello")
    m.reset()
    assert m.request.source is None
    assert m.request.passengers is None
    assert m.raw_user_text == []
    assert not m.asked_questions
