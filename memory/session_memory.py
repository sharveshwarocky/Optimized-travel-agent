"""Session memory (spec §13, guide §19): accumulating TravelRequest + asked questions.

Rules enforced here:
- Never re-ask an answered field (asked_questions tracks every question asked).
- Latest statement wins on conflicts, with a spoken confirmation when it
  overrides an earlier value.
- `new` resets everything for the session (memory is per-session only).
"""
from __future__ import annotations

from models.travel_request import TravelRequest


class SessionMemory:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.request = TravelRequest()
        self.raw_user_text: list[str] = []
        self.asked_questions: set[str] = set()

    def add_user_text(self, text: str) -> list[str]:
        """Record a user turn; returns list of override confirmations to speak."""
        self.raw_user_text.append(text)
        self.request.raw_user_text = list(self.raw_user_text)
        return []

    def mark_asked(self, field_key: str) -> None:
        self.asked_questions.add(field_key)

    def has_asked(self, field_key: str) -> bool:
        return field_key in self.asked_questions

    def merge(self, updates: dict, overrides_reported: list[str] | None = None) -> list[str]:
        """Merge validated updates into the accumulating request (latest wins).

        Returns human-readable override confirmations (§13: 'spoken confirmation
        when it overrides an earlier value').
        """
        confirmations: list[str] = []
        r = self.request
        if "source" in updates and updates["source"]:
            city = str(updates["source"]).strip().title()
            if r.source and r.source.city.lower() != city.lower():
                confirmations.append(f"Updated source from {r.source.city} to {city}.")
                r.source = None  # force re-resolution below
            if r.source is None or not r.source.city:
                from utils.geo import resolve_city
                r.source = resolve_city(city)
        if "destination" in updates and updates["destination"]:
            city = str(updates["destination"]).strip().title()
            if r.destination and r.destination.city.lower() != city.lower():
                confirmations.append(f"Updated destination from {r.destination.city} to {city}.")
                r.destination = None
            if r.destination is None or not r.destination.city:
                from utils.geo import resolve_city
                r.destination = resolve_city(city)

        if "travel_date" in updates and updates["travel_date"]:
            from utils.time_utils import parse_travel_date
            d = parse_travel_date(str(updates["travel_date"])) \
                if isinstance(updates["travel_date"], str) else updates["travel_date"]
            if d and r.travel_date and d != r.travel_date:
                confirmations.append(f"Updated travel date from {r.travel_date.isoformat()} to {d.isoformat()}.")
            if d:
                r.travel_date = d

        if "arrival_deadline" in updates and updates["arrival_deadline"]:
            from utils.time_utils import parse_deadline_time
            t = parse_deadline_time(str(updates["arrival_deadline"])) \
                if isinstance(updates["arrival_deadline"], str) else updates["arrival_deadline"]
            if t and r.arrival_deadline and t != r.arrival_deadline:
                confirmations.append(f"Updated arrival deadline from {r.arrival_deadline.strftime('%H:%M')} to {t.strftime('%H:%M')}.")
            if t:
                r.arrival_deadline = t

        simple_fields = {
            "passengers": int, "budget": float, "budget_type": str,
            "budget_flexibility": str, "comfort_priority": str, "ac_required": None,
            "sleeper_preferred": None, "overnight_allowed": None,
            "luggage_level": str, "urgency": str,
            "preferred_departure_after": None, "max_duration_hours": float,
            "date_flexible_days": int, "elderly_travellers": int, "children": int,
        }
        for field, caster in simple_fields.items():
            if field in updates and updates[field] is not None:
                new = caster(updates[field]) if caster else updates[field]
                current = getattr(r, field)
                if current is not None and current != new:
                    confirmations.append(
                        f"Updated {field.replace('_', ' ')} from {current} to {new}.")
                if current is None or current != new:
                    setattr(r, field, new)

        for list_field in ("preferred_modes", "avoided_modes"):
            if updates.get(list_field):
                merged = list(dict.fromkeys(list(getattr(r, list_field)) + list(updates[list_field])))
                if merged != list(getattr(r, list_field)):
                    confirmations.append(f"Updated {list_field.replace('_', ' ')} to {', '.join(merged)}.")
                setattr(r, list_field, merged)

        confirmations.extend([c for c in (overrides_reported or []) if c not in confirmations])
        return confirmations

    def as_dict(self) -> dict:
        """Memory snapshot for prompts and debugging."""
        r = self.request
        return {
            "source": r.source.city if r.source else None,
            "destination": r.destination.city if r.destination else None,
            "travel_date": r.travel_date.isoformat() if r.travel_date else None,
            "arrival_deadline": r.arrival_deadline.strftime("%H:%M") if r.arrival_deadline else None,
            "passengers": r.passengers,
            "budget": r.budget,
            "budget_type": r.budget_type,
            "budget_flexibility": r.budget_flexibility,
            "comfort_priority": r.comfort_priority,
            "ac_required": r.ac_required,
            "sleeper_preferred": r.sleeper_preferred,
            "overnight_allowed": r.overnight_allowed,
            "luggage_level": r.luggage_level,
            "urgency": r.urgency,
            "preferred_modes": r.preferred_modes,
            "avoided_modes": r.avoided_modes,
        }
