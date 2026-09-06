"""Geo resolution tests."""
from pathlib import Path

from models.travel_request import LocationRef
from utils.geo import (city_coords, city_size_class, parse_station_blob,
                       resolve_city)

FIXTURE = Path(__file__).resolve().parents[1] / "data" / "erail_stations_fixture.js"


def test_chennai_resolves():
    ref = resolve_city("Chennai")
    assert ref.resolved
    assert ref.station_code == "MAS"
    assert ref.airport_code == "MAA"


def test_alias_bengaluru():
    assert resolve_city("bengaluru").airport_code == "BLR"


def test_national_directory_resolves_small_towns():
    """Cities outside the curated table resolve against the bundled 9k-station dir."""
    for city, code in [("Narnaul", "NNL"), ("Katpadi", "KPD"), ("Nagercoil", "NJT"),
                       ("Rameswaram", "RMM"), ("Hampi", "HPT")]:
        ref = resolve_city(city)
        assert ref.resolved and ref.station_code == code, city


def test_spelling_alias_and_tourist_aliases():
    assert resolve_city("Kanyakumari").station_code == "CAPE"  # IR: Kanniyakumari
    assert resolve_city("Tuticorin").station_code == "TN"      # IR: Thoothukudi
    assert resolve_city("Ooty").station_code == "UAM"          # tourist alias


def test_suffix_stripping_matches_station_names():
    assert resolve_city("Vellore Cantt").station_code == "VLR"
    assert resolve_city("Mysore Junction").station_code == "MYS"


def test_unique_containment():
    """'gokarna' only appears in 'Gokarna Road' → unique match."""
    ref = resolve_city("Gokarna")
    assert ref.resolved and ref.station_code == "GOK"


def test_ambiguous_or_unknown_stay_unresolved():
    assert not resolve_city("Fakeville").resolved
    assert resolve_city("") is None  # empty input → no LocationRef at all


def test_parser_replays_recorded_fixture():
    pairs = parse_station_blob(FIXTURE.read_text(encoding="utf-8"))
    assert len(pairs) > 300
    codes = {c for c, _ in pairs}
    assert "MAS" in codes and "SBC" in codes


def test_city_coords():
    assert city_coords(resolve_city("chennai")) == (13.0827, 80.2707)
    assert city_coords(None) is None


def test_city_size_class():
    assert city_size_class(resolve_city("mumbai")) == "metro"
    assert city_size_class(resolve_city("mysore")) == "city"
    assert city_size_class(resolve_city("unknownville")) == "town"
    assert city_size_class(None) == "town"


def test_city_coords_uses_geocoded_latlon():
    ref = resolve_city("Katpadi")  # station-dir match: no table coords
    assert city_coords(ref) is None
    ref.lat, ref.lon = 12.9698, 79.1325
    assert city_coords(ref) == (12.9698, 79.1325)


def test_ensure_coords_fills_unknown_city():
    import asyncio
    from models.travel_request import TravelRequest

    async def fake_geocode(name):
        return (8.0792, 77.5499)

    import utils.geo as geo
    req = TravelRequest(source=resolve_city("Nowhereville"),
                        destination=resolve_city("Chennai"))
    orig = geo.geocode_city
    geo.geocode_city = fake_geocode
    try:
        asyncio.run(geo.ensure_coords(req))
    finally:
        geo.geocode_city = orig
    assert (req.source.lat, req.source.lon) == (8.0792, 77.5499)
    assert req.source.resolved
    assert req.destination.lat is None  # table city: no geocode needed


def test_location_ref_str():
    assert str(LocationRef(city="Chennai")) == "Chennai"
