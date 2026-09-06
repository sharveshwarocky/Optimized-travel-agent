"""Fixture test: parser output → normalizer → TravelOption end-to-end (no network)."""
from datetime import date
from pathlib import Path

from data_sources.adapters.train_source import parse_erail_trains
from models.travel_request import TravelRequest
from services import normalizer
from utils.geo import resolve_city

FIXTURE = Path(__file__).resolve().parents[2] / "data_sources" / "fixtures" / "erail_trains_mas_sbc.txt"


def test_raw_to_travel_options():
    raw = FIXTURE.read_text(encoding="utf-8", errors="replace")
    trains = parse_erail_trains(raw, date(2026, 9, 7))
    req = TravelRequest(
        source=resolve_city("Chennai"), destination=resolve_city("Bangalore"),
        travel_date=date(2026, 9, 7), passengers=3)
    options = normalizer.normalize(trains, req, "train")
    assert len(options) >= 6  # several trains × classes
    o = options[0]
    assert o.mode == "train"
    assert o.total_cost == o.comfort_level is not None or o.total_cost > 0
    assert o.cost_per_person is not None
    assert o.door_to_door_duration_minutes and o.door_to_door_duration_minutes > 450
    assert o.comfort_level and 1 <= o.comfort_level <= 10
    assert o.comfort_notes
    assert o.data_type == "live" and o.source == "erail"


def test_class_split_produces_ac_and_nonac():
    raw = FIXTURE.read_text(encoding="utf-8", errors="replace")
    trains = parse_erail_trains(raw, date(2026, 9, 7))
    req = TravelRequest(
        source=resolve_city("Chennai"), destination=resolve_city("Bangalore"),
        travel_date=date(2026, 9, 7), passengers=3)
    options = normalizer.normalize(trains, req, "train")
    assert any(o.ac for o in options) and any(o.ac is False for o in options)
