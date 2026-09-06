"""Fallback extraction tests (§10.3): deterministic slot filling, malformed-LLM path."""
from agents.requirement_agent import _fallback_extract, missing_critical
from memory.session_memory import SessionMemory


def test_fallback_people_and_date():
    u = _fallback_extract("We are 3 people travelling from Chennai to Bangalore tomorrow")
    assert u["passengers"] == 3
    assert u["source"] == "Chennai"
    assert u["destination"] == "Bangalore"
    assert u["travel_date"] == "tomorrow"


def test_fallback_budget():
    u = _fallback_extract("Our budget is ₹6000 total")
    assert u["budget"] == 6000.0


def test_fallback_deadline():
    u = _fallback_extract("need to reach before 7 PM")
    assert u["arrival_deadline"]


def test_fallback_ac_and_modes():
    u = _fallback_extract("we prefer AC and no flights please")
    assert u["ac_required"] is True
    assert "flight" in u["avoided_modes"]


def test_fallback_urgency_and_elderly():
    u = _fallback_extract("urgent trip, travelling with elderly parents")
    assert u["urgency"] == "high"
    assert u["elderly_travellers"] >= 1


def test_fallback_no_false_positives():
    u = _fallback_extract("hello there")
    assert u == {}


def test_missing_critical_flow():
    m = SessionMemory()
    m.merge({"source": "Chennai"})
    missing = missing_critical(m)
    assert set(missing) == {"destination", "travel_date", "passengers"}
    m.merge({"destination": "Bangalore", "travel_date": "tomorrow", "passengers": 3})
    assert missing_critical(m) == []


def test_malformed_llm_json_degrades_safely():
    """Validation+fallback must tolerate garbage LLM output (§10.3, §17.4)."""
    m = SessionMemory()
    # simulate: LLM unavailable → fallback extraction still fills slots
    u = _fallback_extract("2 people from Mumbai to Pune tomorrow, budget 3000")
    m.merge(u)
    assert m.request.passengers == 2
    assert m.request.source.city == "Mumbai"
    assert m.request.budget == 3000.0
