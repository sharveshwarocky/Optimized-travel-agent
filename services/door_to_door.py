"""Door-to-door duration model (spec §8, guide §17) — deterministic Python.

Per-mode overheads live in config.settings.D2D. Access legs (home→station etc.)
use measured values when the caller has them, else city-size assumptions that
are recorded explicitly in door_to_door_breakdown (spec §8 requirement).
"""
from __future__ import annotations

from config import settings

CITY_ACCESS_MINUTES = {"metro": 45, "city": 35, "town": 25}  # home→terminal leg default


def _access(city_class: str, measured: int | None, label: str,
            breakdown: dict[str, int]) -> int:
    if measured is not None:
        breakdown[label] = int(measured)
        return int(measured)
    val = CITY_ACCESS_MINUTES.get(city_class, 25)
    breakdown[label] = val
    breakdown[f"{label}_assumed"] = 1  # marker: assumption, not measurement
    return val


def d2d_for_mode(mode: str, journey_minutes: int | None, *,
                 origin_class: str = "metro", dest_class: str = "metro",
                 access_origin_minutes: int | None = None,
                 access_dest_minutes: int | None = None,
                 driving_minutes: int | None = None) -> tuple[int, dict[str, int]]:
    """Total door-to-door minutes + full breakdown dict (spec §8)."""
    b: dict[str, int] = {}
    if journey_minutes is None:
        return 0, b
    mode = mode or "bus"

    if mode in ("own_car", "cab", "rental"):
        drive = driving_minutes if driving_minutes is not None else journey_minutes
        b["driving"] = int(drive)
        breaks = int(drive // 120) * settings.D2D["road"]["break_minutes_per_2h"]
        if breaks:
            b["break_allowance"] = breaks
        traffic = int(drive * settings.D2D["road"]["traffic_buffer_pct"])
        b["traffic_buffer"] = traffic
        total = drive + breaks + traffic
        return int(total), b

    if mode == "flight":
        o = _access(origin_class, access_origin_minutes, "airport_travel", b)
        d = _access(dest_class, access_dest_minutes, "destination_travel", b)
        b["reporting"] = settings.D2D["flight"]["reporting_minutes"]
        b["flight"] = int(journey_minutes)
        b["exit"] = settings.D2D["flight"]["exit_minutes"]
        return o + b["reporting"] + b["flight"] + b["exit"] + d, b

    if mode == "train":
        o = _access(origin_class, access_origin_minutes, "station_travel", b)
        d = _access(dest_class, access_dest_minutes, "destination_travel", b)
        b["buffer"] = settings.D2D["train"]["buffer_minutes"]
        b["journey"] = int(journey_minutes)
        b["exit"] = settings.D2D["train"]["exit_minutes"]
        return o + b["buffer"] + b["journey"] + b["exit"] + d, b

    # bus
    o = _access(origin_class, access_origin_minutes, "pickup_travel", b)
    d = _access(dest_class, access_dest_minutes, "destination_travel", b)
    b["wait"] = settings.D2D["bus"]["wait_minutes"]
    b["journey"] = int(journey_minutes)
    return o + b["wait"] + b["journey"] + d, b


def d2d_overhead_ratio(mode: str, journey_minutes: int | None) -> float:
    """Convenience: d2d / journey — used by scoring to expose hidden overhead."""
    total, _ = d2d_for_mode(mode, journey_minutes)
    return (total / journey_minutes) if journey_minutes else 1.0
