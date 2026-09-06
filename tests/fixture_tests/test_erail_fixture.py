"""Fixture test: erail parser against recorded live HTML/JSON (D14 — no network)."""
from datetime import date
from pathlib import Path

from data_sources.adapters.train_source import parse_erail_trains

FIXTURE = Path(__file__).resolve().parents[2] / "data_sources" / "fixtures" / "erail_trains_mas_sbc.txt"


def test_fixture_exists():
    assert FIXTURE.exists(), "recorded erail fixture missing"


def test_parses_trains_with_fares():
    raw = FIXTURE.read_text(encoding="utf-8", errors="replace")
    travel_date = date(2026, 9, 7)
    trains = parse_erail_trains(raw, travel_date)
    assert len(trains) >= 2, f"expected several trains, got {len(trains)}"

    t = trains[0]
    assert isinstance(t["number"], int)
    assert t["name"]
    assert t["departure"].date() == travel_date
    assert t["duration_minutes"] > 0
    assert len(t["classes"]) >= 3, "expected ≥3 classes via ratio-band labeling"
    assert all(f > 80 for f in t["classes"].values())


def test_fares_plausible_magnitude():
    """MAS→SBC ~347 km: 2S≈₹125, SL≈₹270, 3A≈₹675, 2A≈₹925, 1A≈₹1530."""
    raw = FIXTURE.read_text(encoding="utf-8", errors="replace")
    trains = parse_erail_trains(raw, date(2026, 9, 7))
    fares = [f for t in trains for f in t["classes"].values()]
    assert fares and all(80 <= f <= 5000 for f in fares)
    t = trains[0]
    if "2S" in t["classes"] and "1A" in t["classes"]:
        assert t["classes"]["2S"] < t["classes"]["1A"]


def test_overnight_flag():
    raw = FIXTURE.read_text(encoding="utf-8", errors="replace")
    trains = parse_erail_trains(raw, date(2026, 9, 7))
    assert any(t["overnight"] or t["arrival"].hour < 12 for t in trains)
