"""Worth-It engine (spec §11.3, guide §16): pairwise value comparisons computed
from structured data only. The reasoning agent restates these numbers — it must
never invent its own (§17.7).
"""
from __future__ import annotations

from dataclasses import dataclass

from models.travel_option import TravelOption
from models.travel_request import TravelRequest


@dataclass
class WorthItComparison:
    from_name: str
    to_name: str
    extra_cost: float            # to is more expensive than from (₹, whole party)
    minutes_saved: int           # door-to-door
    rupees_per_hour_saved: float | None
    comfort_gained: float        # comfort points
    rupees_per_comfort_point: float | None
    verdict: str                 # "worth_it" | "not_worth_it" | "marginal"
    reasoning: str               # cites computed numbers only


def _verdict(cph: float | None, req: TravelRequest) -> tuple[str, str]:
    """Value threshold scales with deadline pressure and budget slack."""
    if cph is None:
        return "marginal", "no time savings to price"
    # reference ₹/hour: budget-relative, deadline-adjusted
    threshold = 150.0
    if req.urgency == "high":
        threshold = 500.0
    elif req.urgency == "medium" or req.arrival_deadline:
        threshold = 300.0
    if req.budget_flexibility == "strict":
        threshold *= 0.6
    if cph <= threshold * 0.6:
        return "worth_it", f"₹{cph:,.0f}/hour saved is comfortably below the ~₹{threshold:,.0f}/hour value threshold for this trip"
    if cph <= threshold:
        return "marginal", f"₹{cph:,.0f}/hour saved is near the ~₹{threshold:,.0f}/hour value threshold for this trip"
    return "not_worth_it", f"₹{cph:,.0f}/hour saved exceeds the ~₹{threshold:,.0f}/hour value threshold for this trip"


def _budget_context(opt: TravelOption, req: TravelRequest) -> str | None:
    """Savings/cost expressed relative to the user's stated budget (§11.3)."""
    if req.budget is None or opt.total_cost is None:
        return None
    if opt.total_cost > req.budget:
        return f"₹{opt.total_cost - req.budget:,.0f} over the ₹{req.budget:,.0f} budget"
    return f"₹{req.budget - opt.total_cost:,.0f} left from the ₹{req.budget:,.0f} budget"


def compare_pair(cheaper: TravelOption, pricier: TravelOption,
                 req: TravelRequest) -> WorthItComparison | None:
    """Compare two options (cheaper → pricier) on ₹/hour saved and ₹/comfort point."""
    if cheaper.total_cost is None or pricier.total_cost is None:
        return None
    extra_cost = pricier.total_cost - cheaper.total_cost
    minutes_saved = None
    if (cheaper.door_to_door_duration_minutes and pricier.door_to_door_duration_minutes):
        minutes_saved = cheaper.door_to_door_duration_minutes - pricier.door_to_door_duration_minutes
    if extra_cost <= 0 and not minutes_saved:
        return None

    cph = None
    if extra_cost > 0 and minutes_saved and minutes_saved > 15:
        cph = extra_cost / (minutes_saved / 60.0)

    comfort_gained = (pricier.comfort_level or 5) - (cheaper.comfort_level or 5)
    rpc = (extra_cost / comfort_gained) if (extra_cost > 0 and comfort_gained > 0) else None

    verdict, reasoning = _verdict(cph, req)
    if comfort_gained >= 2 and (rpc is None or rpc <= 900):
        verdict = "worth_it" if verdict != "worth_it" else verdict
        reasoning += f"; comfort gain of {comfort_gained:g} points at ₹{rpc:,.0f}/point" if rpc else f"; comfort gain of {comfort_gained:g} points for the same price"

    # group economics context: own car per-person advantage
    if (pricier.mode == "own_car" and req.effective_passengers() >= 4
            and pricier.cost_per_person is not None):
        verdict = "worth_it" if verdict == "not_worth_it" else verdict
        reasoning += (f"; note: own-car cost is near-flat per person — "
                      f"₹{pricier.cost_per_person:,.0f}/person across {req.effective_passengers()} travellers")
    budget_ctx = _budget_context(pricier, req)
    if budget_ctx:
        reasoning += f"; {budget_ctx}"

    return WorthItComparison(
        from_name=cheaper.name, to_name=pricier.name,
        extra_cost=extra_cost, minutes_saved=minutes_saved or 0,
        rupees_per_hour_saved=cph, comfort_gained=comfort_gained,
        rupees_per_comfort_point=rpc, verdict=verdict, reasoning=reasoning,
    )


def worth_it_lines(ranked: list[TravelOption], req: TravelRequest) -> list[str]:
    """One comparison line per adjacent ranked pair (for output + reasoning agent)."""
    lines: list[str] = []
    for a, b in zip(ranked, ranked[1:]):
        cmp_ = compare_pair(a, b, req)
        if cmp_ is None:
            continue
        hours = cmp_.minutes_saved / 60.0
        if hours >= 0.25 and cmp_.extra_cost > 0:
            line = (f"{b.name}: {cmp_.extra_cost / max(1, req.effective_passengers()):,.0f}₹ more "
                    f"per person ({cmp_.extra_cost:,.0f}₹ total) for {hours:.1f} h saved "
                    f"door-to-door — {cmp_.verdict.replace('_', ' ')}")
        elif cmp_.extra_cost <= 0:
            line = f"{b.name}: similar cost, {hours:.1f} h {'slower' if hours > 0 else 'comparable'} — {cmp_.verdict.replace('_', ' ')}"
        else:
            line = f"{b.name}: cheaper by {abs(cmp_.extra_cost):,.0f}₹ but {abs(hours):.1f} h slower — {cmp_.verdict.replace('_', ' ')}"
        lines.append(line)
    return lines


def comparisons_for_llm(ranked: list[TravelOption], req: TravelRequest) -> list[dict]:
    """Structured comparisons for the reasoning agent (it restates, never computes)."""
    out = []
    for a, b in zip(ranked, ranked[1:]):
        cmp_ = compare_pair(a, b, req)
        if cmp_:
            out.append({
                "from": cmp_.from_name, "to": cmp_.to_name,
                "extra_cost_total": round(cmp_.extra_cost, 0),
                "minutes_saved_doortodoor": cmp_.minutes_saved,
                "rupees_per_hour_saved": round(cmp_.rupees_per_hour_saved, 0) if cmp_.rupees_per_hour_saved else None,
                "comfort_gained": cmp_.comfort_gained,
                "rupees_per_comfort_point": round(cmp_.rupees_per_comfort_point, 0) if cmp_.rupees_per_comfort_point else None,
                "verdict": cmp_.verdict, "reasoning": cmp_.reasoning,
            })
    return out
