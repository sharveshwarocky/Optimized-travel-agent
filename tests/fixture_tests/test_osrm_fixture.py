"""Fixture test: OSRM parser + straight-line fallback (D14 — no network)."""
import json
from pathlib import Path

from data_sources.adapters.maps_source import parse_osrm, straight_line_estimate

FIXTURE = Path(__file__).resolve().parents[2] / "data_sources" / "fixtures" / "osrm_route_maa_blr.json"


def test_parse_route():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    route = parse_osrm(payload)
    # MAA→BLR ≈ 327 km road, ~4.1 h
    assert 250 < route["distance_km"] < 450
    assert 180 < route["duration_minutes"] < 420


def test_straight_line_fallback_plausible():
    est = straight_line_estimate(13.0827, 80.2707, 12.9716, 77.5946)
    assert 250 < est["distance_km"] < 500
    assert est["duration_minutes"] > 0
