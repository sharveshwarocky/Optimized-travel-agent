"""Constraint engine (spec §11.1): hard constraints reject, soft ones penalize.

Runs before scoring. Rejects are recorded on the option so the conflict
resolution loop (§12) can explain exactly what clashed with reality.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from models.travel_option import TravelOption
from models.travel_request import TravelRequest


@dataclass
class ConstraintReport:
    surviving: list[TravelOption] = field(default_factory=list)
    rejected: list[TravelOption] = field(default_factory=list)
    violations_by_constraint: dict[str, int] = field(default_factory=dict)
    violation_examples: dict[str, str] = field(default_factory=dict)

    def summary_lines(self) -> list[str]:
        lines = []
        for constraint, count in sorted(self.violations_by_constraint.items(),
                                        key=lambda kv: -kv[1]):
            example = self.violation_examples.get(constraint, "")
            lines.append(f"{constraint}: eliminated {count} option(s) — e.g. {example}")
        return lines or ["no violations recorded"]


def evaluate_hard(opt: TravelOption, req: TravelRequest, relaxed: set[str] | None = None,
                  _all: bool = False) -> str | list[str] | None:
    """Return the violated hard constraint (name, or list when _all=True), or None.

    `relaxed` holds constraint keys skipped by the conflict loop (§12).
    """
    relaxed = relaxed or set()

    def _skip(name: str) -> bool:
        return name in relaxed

    violations: list[str] = []

    # avoided modes
    if not _skip("mode_avoided") and opt.mode in (req.avoided_modes or []):
        violations.append("mode_avoided")

    # budget (strict only — flexible budget is a soft penalty)
    if (not _skip("budget_strict") and req.budget is not None
            and req.budget_flexibility == "strict"
            and opt.total_cost is not None and opt.total_cost > req.budget + 0.01):
        violations.append("budget_strict")

    # arrival deadline
    if (not _skip("arrival_deadline") and req.arrival_deadline is not None
            and opt.arrival_time is not None):
        if opt.arrival_time.time() > req.arrival_deadline:
            violations.append("arrival_deadline")

    # AC mandatory
    if not _skip("ac_required") and req.ac_required is True and opt.ac is False:
        violations.append("ac_required")

    # overnight not allowed
    if not _skip("overnight_disallowed") and req.overnight_allowed is False and opt.overnight:
        violations.append("overnight_disallowed")

    # max duration
    if (not _skip("max_duration") and req.max_duration_hours is not None
            and opt.travel_duration_minutes is not None):
        if opt.travel_duration_minutes > req.max_duration_hours * 60:
            violations.append("max_duration")

    if _all:
        return violations
    return violations[0] if violations else None


def apply_soft_penalty(opt: TravelOption, req: TravelRequest) -> None:
    """Record soft-violation markers; scoring engine reads these (§11.1)."""
    notes: list[str] = []
    if (req.budget is not None and req.budget_flexibility == "flexible"
            and opt.total_cost is not None and opt.total_cost > req.budget):
        notes.append("over flexible budget")
    if req.ac_required is False and opt.ac is False:
        notes.append("non-AC (AC preferred)")
    if req.sleeper_preferred and opt.mode in ("bus",) and "sleeper" not in opt.name.lower():
        notes.append("sleeper preferred but not confirmed")
    if req.preferred_modes and opt.mode not in req.preferred_modes:
        notes.append("mode not explicitly preferred")
    if notes:
        opt.constraint_violations.extend(notes)


def filter_options(options: list[TravelOption], req: TravelRequest,
                   relaxed: set[str] | None = None) -> ConstraintReport:
    """Hard-filter all options; `relaxed` keys are skipped (conflict loop, §12)."""
    report = ConstraintReport()
    relaxed = relaxed or set()
    for opt in options:
        violated = evaluate_hard(opt, req, relaxed=relaxed)
        if violated:
            report.rejected.append(opt)
            report.violations_by_constraint[violated] = (
                report.violations_by_constraint.get(violated, 0) + 1)
            report.violation_examples.setdefault(
                violated, f"{opt.name} (₹{opt.total_cost:,.0f}, "
                          f"arr {opt.arrival_time.strftime('%H:%M') if opt.arrival_time else '?'})")
            opt.constraint_violations.append(violated)
        else:
            apply_soft_penalty(opt, req)
            report.surviving.append(opt)
    return report
