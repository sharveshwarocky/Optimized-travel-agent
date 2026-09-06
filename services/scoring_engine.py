"""Scoring engine (spec §11.2): deterministic, transparent, 0–100 normalized.

Overall = w_cost·Cost + w_time·Time + w_comfort·Comfort + w_conv·Convenience
        + w_pref·PreferenceMatch + w_schedule·ScheduleFit

Weights come from a Python rule table keyed on comfort_priority / urgency /
budget_flexibility / deadline presence (guide §15 profiles). The LLM may
*suggest* a profile; Python decides.
"""
from __future__ import annotations

from dataclasses import dataclass

from config import settings
from models.travel_option import TravelOption
from models.travel_request import TravelRequest


@dataclass
class ScoredSet:
    ranked: list[TravelOption]
    weights: dict[str, float]
    profile: str


def choose_profile(req: TravelRequest) -> tuple[str, dict[str, float]]:
    """Deterministic rule table (§11.2, guide §15). Returns (profile, weights)."""
    if req.urgency == "high" or (req.urgency == "medium" and req.arrival_deadline):
        return "urgent", settings.WEIGHT_PROFILES["urgent"]
    if req.comfort_priority == "high":
        return "comfort", settings.WEIGHT_PROFILES["comfort"]
    if (req.budget_flexibility == "strict" and req.comfort_priority == "low") or \
       (req.budget_flexibility == "strict" and req.comfort_priority == "medium"):
        return "budget", settings.WEIGHT_PROFILES["budget"]
    if req.effective_passengers() >= 5:
        return "group", settings.WEIGHT_PROFILES["group"]
    return "balanced", settings.WEIGHT_PROFILES["balanced"]


def _minmax(values: list[float | None], invert: bool) -> list[float]:
    """Normalize to 0–100 (higher = better). None → worst (or 0 when all None)."""
    present = [v for v in values if v is not None]
    if not present:
        return [50.0] * len(values)
    lo, hi = min(present), max(present)
    out = []
    for v in values:
        if v is None:
            out.append(0.0 if not invert else 0.0)
            continue
        if hi == lo:
            out.append(80.0)
            continue
        score = (v - lo) / (hi - lo) * 100.0
        out.append(100.0 - score if invert else score)
    return out


def score_options(options: list[TravelOption], req: TravelRequest) -> ScoredSet:
    profile, weights = choose_profile(req)
    if not options:
        return ScoredSet([], weights, profile)

    # ---- sub-scores (all 0–100, higher better) ----
    cost_score = _minmax([o.cost_per_person for o in options], invert=True)
    time_score = _minmax([o.door_to_door_duration_minutes for o in options], invert=True)
    comfort_score = [float(o.comfort_level or 5) * 10.0 for o in options]

    # convenience: reliability (D12 static) + fewer stops + lower d2d overhead
    conv_score = []
    for o in options:
        overhead = 0.0
        if o.door_to_door_duration_minutes and o.travel_duration_minutes:
            overhead = o.door_to_door_duration_minutes / max(1, o.travel_duration_minutes)
        c = (o.reliability_score or 7) * 8.0          # ≤80
        c += max(0.0, 20.0 - (o.stops or 0) * 10.0)   # ≤20
        c -= max(0.0, (overhead - 1.4)) * 25.0        # hidden-overhead drag
        conv_score.append(max(0.0, min(100.0, c)))

    # preference match: 100 base minus soft-violation markers
    pref_score = []
    for o in options:
        s = 100.0
        if "over flexible budget" in o.constraint_violations:
            s -= 35.0
        if "non-AC (AC preferred)" in o.constraint_violations:
            s -= 25.0
        if "sleeper preferred but not confirmed" in o.constraint_violations:
            s -= 10.0
        if "mode not explicitly preferred" in o.constraint_violations:
            s -= 15.0
        pref_score.append(max(0.0, s))

    # schedule fit: departure window + deadline headroom
    sched_score = []
    for o in options:
        s = 60.0
        if req.arrival_deadline and o.arrival_time:
            headroom_min = (
                req.arrival_deadline.hour * 60 + req.arrival_deadline.minute
                - o.arrival_time.hour * 60 - o.arrival_time.minute
            )
            if headroom_min >= 120:
                s = 100.0
            elif headroom_min >= 60:
                s = 85.0
            elif headroom_min >= 30:
                s = 70.0
            else:
                s = 55.0
        if req.preferred_departure_after and o.departure_time:
            dep = o.departure_time.hour * 60 + o.departure_time.minute
            want = req.preferred_departure_after.hour * 60 + req.preferred_departure_after.minute
            if dep >= want:
                s = min(100.0, s + 15.0)
        sched_score.append(s)

    for i, o in enumerate(options):
        o.sub_scores.update({
            "cost": round(cost_score[i], 1),
            "time": round(time_score[i], 1),
            "comfort": round(comfort_score[i], 1),
            "conv": round(conv_score[i], 1),
            "pref": round(pref_score[i], 1),
            "schedule": round(sched_score[i], 1),
        })
        o.overall_score = round(
            weights["cost"] * cost_score[i]
            + weights["time"] * time_score[i]
            + weights["comfort"] * comfort_score[i]
            + weights["conv"] * conv_score[i]
            + weights["pref"] * pref_score[i]
            + weights["schedule"] * sched_score[i], 1)

    ranked = sorted(options, key=lambda o: o.overall_score or 0, reverse=True)
    return ScoredSet(ranked, weights, profile)
