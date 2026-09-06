"""Geo resolution tests."""
from models.travel_request import LocationRef
from utils.geo import city_coords, city_size_class, resolve_city


def test_chennai_resolves():
    ref = resolve_city("Chennai")
    assert ref.resolved
    assert ref.station_code == "MAS"
    assert ref.airport_code == "MAA"


def test_alias_bengaluru():
    assert resolve_city("bengaluru").airport_code == "BLR"


def test_unknown_city_flags_unresolved():
    ref = resolve_city("Narnaul")
    assert not ref.resolved
    assert ref.city == "Narnaul"


def test_city_coords():
    assert city_coords(resolve_city("chennai")) == (13.0827, 80.2707)
    assert city_coords(None) is None


def test_city_size_class():
    assert city_size_class(resolve_city("mumbai")) == "metro"
    assert city_size_class(resolve_city("mysore")) == "city"
    assert city_size_class(resolve_city("unknownville")) == "town"
    assert city_size_class(None) == "town"


def test_location_ref_str():
    assert str(LocationRef(city="Chennai")) == "Chennai"
