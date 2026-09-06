"""Fixture test: goodreturns fuel parser (D14 — no network)."""
from pathlib import Path

from data_sources.adapters.fuel_source import parse_fuel_price, parse_page_date

FIXTURE = Path(__file__).resolve().parents[2] / "data_sources" / "fixtures" / "goodreturns_petrol_bangalore.html"


def test_parses_price_from_title():
    html = FIXTURE.read_text(encoding="utf-8", errors="replace")
    price = parse_fuel_price(html)
    assert price is not None
    assert 90 < price < 130  # realistic Bangalore petrol band (₹/L)


def test_parses_page_date():
    html = FIXTURE.read_text(encoding="utf-8", errors="replace")
    assert parse_page_date(html) is not None
