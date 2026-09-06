"""Comfort model (spec §9, guide §18) — transparent rules, zero LLM.

Every point adjustment is explained in comfort_notes. Scale 1–10:
1–3 low · 4–6 moderate · 7–8 high · 9–10 premium.
"""
from __future__ import annotations

TRAIN_CLASS_BASE = {"1A": 10, "EA": 10, "2A": 9, "3A": 7, "3E": 6, "SL": 4, "2S": 2}

LONG_RIDE_PENALTY = {          # mode → [(threshold_minutes, penalty)]
    "train": [(18 * 60, 2), (12 * 60, 1)],
    "bus": [(14 * 60, 2), (8 * 60, 1)],
    "flight": [(6 * 60, 1)],
    "own_car": [(10 * 60, 2), (6 * 60, 1)],
    "cab": [(10 * 60, 2), (6 * 60, 1)],
    "rental": [(10 * 60, 2), (6 * 60, 1)],
}


def comfort_for(mode: str, *, ac: bool | None = None, sleeper: bool | None = None,
                train_class: str | None = None, duration_minutes: int | None = None,
                stops: int | None = None, overnight: bool = False,
                elderly: int = 0, children: int = 0,
                luggage: str = "normal") -> tuple[int, list[str]]:
    """Return (score 1–10, notes). Deterministic and explainable."""
    notes: list[str] = []
    score = 5.0
    mode = mode or "bus"

    # ---- base by class/type ----
    if mode == "train":
        base = TRAIN_CLASS_BASE.get(train_class or "", 4)
        score = base
        notes.append(f"train class {train_class or 'unknown'} base {base}/10")
    elif mode == "bus":
        if ac and sleeper:
            score = 7.0; notes.append("AC sleeper bus base 7/10")
        elif ac:
            score = 5.5; notes.append("AC seater bus base 5.5/10")
        elif sleeper:
            score = 4.0; notes.append("non-AC sleeper base 4/10")
        else:
            score = 2.5; notes.append("non-AC seater base 2.5/10")
    elif mode == "flight":
        score = 7.5; notes.append("economy flight base 7.5/10")
    elif mode in ("own_car", "rental"):
        score = 6.5; notes.append("private car base 6.5/10 (own space, flexible stops)")
    elif mode == "cab":
        score = 6.5; notes.append("chauffeured cab base 6.5/10 (own space, no driving fatigue)")

    # ---- AC modifier (where not already class-implied) ----
    if mode == "train" and train_class:
        if train_class in ("SL", "2S") and ac is True:
            score = min(score, 4.5)  # AC requested but only non-AC class exists
            notes.append("AC requested but class is non-AC")
    if mode in ("own_car", "cab", "rental") and ac is False:
        pass  # cars assumed ventilated; no penalty

    # ---- duration penalties ----
    if duration_minutes:
        for threshold, pen in LONG_RIDE_PENALTY.get(mode, []):
            if duration_minutes > threshold:
                score -= pen
                notes.append(f"long journey {duration_minutes // 60}h penalty -{pen}")
                break

    # ---- transfers/stops ----
    if stops:
        pen = min(2, int(stops))
        score -= pen
        notes.append(f"{stops} stop(s) penalty -{pen}")
        if elderly or children:
            score -= 1
            notes.append("transfers with elderly/children extra -1")

    # ---- overnight nuances ----
    if overnight:
        if sleeper or (mode == "train" and train_class in ("SL", "3A", "2A", "1A", "3E")):
            notes.append("overnight with sleeping berth — saves a hotel night")
        else:
            score -= 1.5
            notes.append("overnight in seated accommodation -1.5")

    # ---- luggage fit ----
    if luggage == "heavy" and mode in ("bus", "flight"):
        score -= 0.5
        notes.append("heavy luggage in shared baggage -0.5")
    if luggage == "heavy" and mode in ("own_car", "cab", "rental"):
        notes.append("heavy luggage fits easily in a car")

    return max(1, min(10, round(score))), notes


def comfort_band(score: int | None) -> str:
    if score is None:
        return "—"
    if score <= 3:
        return "low"
    if score <= 6:
        return "moderate"
    if score <= 8:
        return "high"
    return "premium"
