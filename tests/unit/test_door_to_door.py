"""Door-to-door model tests (spec §8)."""
from services.door_to_door import d2d_for_mode


def test_flight_overhead():
    total, b = d2d_for_mode("flight", 90, origin_class="metro", dest_class="metro")
    # 45 (access) + 90 (reporting) + 90 (flight) + 30 (exit) + 45 (egress) = 300
    assert total == 300
    assert b["reporting"] == 90 and b["exit"] == 30
    assert b["airport_travel_assumed"] == 1  # assumption explicitly recorded


def test_train_overhead_measured_access():
    total, b = d2d_for_mode("train", 300, origin_class="metro", dest_class="metro",
                            access_origin_minutes=20, access_dest_minutes=25)
    # 20 + 30 + 300 + 15 + 25 = 390
    assert total == 390
    assert "station_travel_assumed" not in b


def test_bus_overhead():
    total, b = d2d_for_mode("bus", 420, origin_class="city", dest_class="city")
    assert b["wait"] == 15
    assert total == 35 + 15 + 420 + 35  # default city access legs both sides


def test_car_breaks_and_traffic():
    total, b = d2d_for_mode("own_car", 240)  # 4h drive
    assert b["break_allowance"] == 30       # 15 min per 2h
    assert b["traffic_buffer"] == 36        # 15% of 240
    assert total == 240 + 30 + 36


def test_unknown_journey_zero():
    total, b = d2d_for_mode("train", None)
    assert total == 0 and b == {}
