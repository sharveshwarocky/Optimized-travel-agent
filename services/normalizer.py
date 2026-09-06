"""Normalizer (spec §4/§12): raw source dicts → common TravelOption shape.

All arithmetic happens here in Python (guide §25). Comfort comes from
services/comfort_model.py, door-to-door from services/door_to_door.py.
Provenance (source/data_type/confidence) is attached from the collector context
— the LLM never touches these fields (§17.1).
"""
from __future__ import annotations

from datetime import datetime

from models.provenance import utcnow
from models.travel_option import TravelOption
from models.travel_request import TravelRequest
from services import comfort_model, door_to_door
from utils.cost_utils import per_person
from utils.geo import city_size_class


def _base_option(req: TravelRequest, *, mode: str, name: str, source: str,
                 data_type: str, confidence: str) -> TravelOption:
    return TravelOption(
        mode=mode, name=name,
        departure_location=req.source.city if req.source else "?",
        arrival_location=req.destination.city if req.destination else "?",
        source=source, data_type=data_type, confidence=confidence,
        retrieved_at=utcnow(),
    )


def _finalize(opt: TravelOption, req: TravelRequest, *, journey_minutes: int | None,
              driving_minutes: int | None = None, extra_notes: list[str] | None = None) -> TravelOption:
    """Compute comfort + door-to-door + per-person cost for any option."""
    pax = req.effective_passengers()
    opt.cost_per_person = per_person(opt.total_cost, pax)
    o_class = city_size_class(req.source) if req.source else "town"
    d_class = city_size_class(req.destination) if req.destination else "town"

    if opt.mode in ("own_car", "cab", "rental"):
        total, breakdown = door_to_door.d2d_for_mode(
            opt.mode, journey_minutes, origin_class=o_class, dest_class=d_class,
            driving_minutes=driving_minutes)
    else:
        total, breakdown = door_to_door.d2d_for_mode(
            opt.mode, journey_minutes, origin_class=o_class, dest_class=d_class)
    opt.door_to_door_duration_minutes = total or None
    opt.door_to_door_breakdown = breakdown

    comfort, notes = comfort_model.comfort_for(
        opt.mode, ac=opt.ac, sleeper=bool(opt.sub_scores.get("_sleeper", False)),
        train_class=opt.sub_scores.get("_train_class"),
        duration_minutes=journey_minutes, stops=opt.stops,
        overnight=opt.overnight, elderly=req.elderly_travellers,
        children=req.children, luggage=req.luggage_level)
    if extra_notes:
        notes.extend(extra_notes)
    opt.comfort_notes = notes
    opt.comfort_level = comfort
    if opt.reliability_score is None:
        from config import settings
        opt.reliability_score = settings.RELIABILITY_DEFAULTS.get(opt.mode, 7)
    return opt


def train_option(raw: dict, req: TravelRequest, cls: str, fare: float) -> TravelOption:
    """raw = erail train dict; one option per (train, class)."""
    from datetime import timedelta
    opt = _base_option(
        req, mode="train", name=f"{raw['number']} {raw['name']} ({cls})",
        source="erail", data_type="live", confidence="medium")
    opt.operator = "Indian Railways"
    opt.departure_time = raw["departure"]
    opt.arrival_time = raw["arrival"]
    opt.travel_duration_minutes = raw["duration_minutes"]
    opt.overnight = raw["overnight"]
    opt.total_cost = round(fare * req.effective_passengers(), 2)
    opt.ac = cls in ("3A", "2A", "1A", "3E", "EA", "CC", "EC")
    opt.stops = 0
    opt.availability_status = None  # IRCTC availability not exposed server-side (gate R2)
    opt.baggage_note = "free allowance varies by class" if cls != "SL" else None
    opt.sub_scores = {"_train_class": cls, "_fare": fare}
    opt.comfort_notes.append("fare class-row mapping inferred (erail blob unlabeled)")
    return _finalize(opt, req, journey_minutes=raw["duration_minutes"])


def flight_option(raw: dict, req: TravelRequest, source: str = "skiplagged",
                  data_type: str = "live", confidence: str = "high",
                  baggage_note: str | None = None) -> TravelOption:
    opt = _base_option(req, mode="flight", name=raw["name"],
                       source=source, data_type=data_type, confidence=confidence)
    opt.operator = raw.get("airline")
    opt.departure_time = raw["departure"]
    opt.arrival_time = raw["arrival"]
    opt.travel_duration_minutes = int(round(float(raw["duration_minutes"])))
    opt.overnight = (raw["arrival"].date() > raw["departure"].date())
    price_pp = float(raw["price_per_person"])
    opt.total_cost = round(price_pp * req.effective_passengers(), 2)
    opt.cost_per_person = round(price_pp, 2)
    opt.ac = True
    opt.stops = raw.get("stops", 0)
    opt.availability_status = None
    opt.baggage_note = baggage_note
    return _finalize(opt, req, journey_minutes=int(round(float(raw["duration_minutes"]))))


def bus_option(raw: dict, req: TravelRequest) -> TravelOption:
    """raw from bus estimator: per-seat fare × party, sleeper flag from source."""
    opt = _base_option(req, mode="bus", name=raw["name"],
                       source=raw["source"], data_type=raw["data_type"],
                       confidence=raw["confidence"])
    opt.operator = raw.get("operator")
    opt.departure_time = raw["departure"]
    opt.arrival_time = raw["arrival"]
    opt.travel_duration_minutes = int(round(float(raw["duration_minutes"])))
    opt.overnight = raw.get("overnight", False)
    fare_pp = float(raw["price_per_person"])
    opt.total_cost = round(fare_pp * req.effective_passengers(), 2)
    opt.cost_per_person = round(fare_pp, 2)
    opt.ac = raw.get("ac")
    opt.stops = raw.get("stops", 0)
    opt.availability_status = raw.get("availability_status")
    opt.sub_scores = {"_sleeper": raw.get("sleeper", False)}
    return _finalize(opt, req, journey_minutes=int(round(float(raw["duration_minutes"]))),
                     extra_notes=list(raw.get("notes", [])))


def road_option(raw: dict, req: TravelRequest, mode: str) -> TravelOption:
    """raw from road_collector: distance/duration/fuel/tolls + kind-specific naming/costs."""
    opt = _base_option(req, mode=mode, name=raw["name"], source=raw["source"],
                       data_type=raw["data_type"], confidence=raw["confidence"])
    opt.operator = raw.get("operator")
    opt.travel_duration_minutes = int(round(float(raw["driving_minutes"])))
    opt.total_cost = raw["total_cost"]
    opt.ac = True
    opt.stops = 0
    opt.overnight = False
    notes = list(raw.get("notes", []))
    opt.door_to_door_breakdown.update(raw.get("cost_breakdown", {}))
    return _finalize(opt, req, journey_minutes=raw["driving_minutes"],
                     driving_minutes=raw["driving_minutes"],
                     extra_notes=notes)


def normalize(raws: list[dict], req: TravelRequest, mode: str) -> list[TravelOption]:
    """Dispatch raw collector output → TravelOptions for a mode."""
    out: list[TravelOption] = []
    for raw in raws:
        try:
            if mode == "train":
                for cls, fare in raw["classes"].items():
                    out.append(train_option(raw, req, cls, fare))
            elif mode == "flight":
                out.append(flight_option(raw, req))
            elif mode == "bus":
                out.append(bus_option(raw, req))
            elif mode in ("own_car", "cab", "rental"):
                out.append(road_option(raw, req, mode))
        except Exception:  # one malformed row never aborts the batch
            continue
    return out
