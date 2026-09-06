"""Time utilities (spec §5): dateparser for natural dates, deadline math."""
from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta

import dateparser


def parse_travel_date(text: str, today: date | None = None) -> date | None:
    """Parse 'tomorrow', 'next Friday', '07 Sep', '2026-09-07' etc. against today."""
    today = today or date.today()
    t = (text or "").strip().lower()
    if not t:
        return None

    # fast paths dateparser may localize differently
    if t in ("today", "aaj"):
        return today
    if t in ("tomorrow", "tmrw", "tomorow", "kal"):
        return today + timedelta(days=1)
    if t in ("day after tomorrow",):
        return today + timedelta(days=2)
    m = re.match(r"in (\d+) days?", t)
    if m:
        return today + timedelta(days=int(m.group(1)))
    m = re.match(r"next (\w+day)", t)
    if m:
        target = _weekday(m.group(1))
        if target is not None:
            delta = (target - today.weekday()) % 7
            if delta == 0:
                delta = 7
            return today + timedelta(days=delta)
    if t == "this weekend" or t == "weekend":
        delta = (5 - today.weekday()) % 7 or 7 if today.weekday() > 5 else (5 - today.weekday()) % 7
        return today + timedelta(days=delta)

    parsed = dateparser.parse(
        t, settings={"RELATIVE_BASE": datetime.combine(today, time.min),
                     "PREFER_DATES_FROM": "future",
                     "DATE_ORDER": "DMY"}  # India: 07-09-2026 = 7 Sep
    )
    return parsed.date() if parsed else None


def parse_deadline_time(text: str) -> time | None:
    """Parse 'before 6 PM', 'by 19:30', 'reach before 7 pm' → time(19, 0)."""
    if not text:
        return None
    t = text.strip().lower()
    m = re.search(r"(\d{1,2})(?:[:.](\d{2}))?\s*(a\.?m\.?|p\.?m\.?|am|pm)?", t)
    if not m:
        parsed = dateparser.parse(t)
        return parsed.time() if parsed else None
    hour = int(m.group(1))
    minute = int(m.group(2) or 0)
    mer = (m.group(3) or "").replace(".", "")
    if mer in ("pm",) and hour != 12:
        hour += 12
    if mer in ("am",) and hour == 12:
        hour = 0
    if not mer and hour <= 12 and any(w in t for w in ("evening", "night")) and hour < 7:
        hour += 12
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return time(hour, minute)
    return None


def parse_duration_hours(text: str) -> float | None:
    """'within 10 hours', 'max 8h' → hours float."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\b", (text or "").lower())
    return float(m.group(1)) if m else None


def minutes_to_hm(minutes: int | float | None) -> str:
    if minutes is None:
        return "—"
    minutes = int(round(minutes))
    return f"{minutes // 60}h {minutes % 60:02d}m"


def departure_datetime(travel_date: date, clock: time) -> datetime:
    return datetime.combine(travel_date, clock)


def arrival_datetime(travel_date: date, clock: time, duration_minutes: int) -> datetime:
    """Arrival datetime handling past-midnight rollover for overnight journeys."""
    dep = datetime.combine(travel_date, clock)
    return dep + timedelta(minutes=duration_minutes)


def _weekday(name: str) -> int | None:
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    name = name.lower()
    for i, d in enumerate(days):
        if d.startswith(name[:3]):
            return i
    return None
