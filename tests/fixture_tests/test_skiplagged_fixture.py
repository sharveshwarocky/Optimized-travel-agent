"""Fixture test: skiplagged parser against recorded JSON (D14 — no network)."""
import json
from datetime import date
from pathlib import Path

from data_sources.adapters.flight_source import parse_skiplagged

FIXTURE = Path(__file__).resolve().parents[2] / "data_sources" / "fixtures" / "skiplagged_maa_blr.json"


def test_fixture_exists():
    assert FIXTURE.exists()


def test_parses_flights():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    flights = parse_skiplagged(payload, date(2026, 9, 7), passengers=3)
    assert 1 <= len(flights) <= 10
    f = flights[0]
    assert f["name"] and f["airline"]
    assert f["from_airport"] == "MAA" and f["to_airport"] == "BLR"
    assert f["price_per_person"] > 0
    assert f["duration_minutes"] > 0
    assert f["stops"] in (0, 1)


def test_sorted_by_price():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    flights = parse_skiplagged(payload, date(2026, 9, 7), passengers=3)
    prices = [f["price_per_person"] for f in flights]
    assert prices == sorted(prices)


def test_stops_filter():
    """MAX_STOPS=1: no 2-stop routings slip through."""
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    flights = parse_skiplagged(payload, date(2026, 9, 7), passengers=3)
    assert all(f["stops"] <= 1 for f in flights)
