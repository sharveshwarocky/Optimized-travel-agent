"""erail.in train adapter (gate doc: data_sources/adapters/erail_train_source.md).

getTrains.aspx returns plain text: one train per line, fields tilde-delimited:
  0: number, 1: name, 2/3: from name/code, 4/5: to name/code,
  6/7: boarding name/code, 8/9: destination name/code,
  10: dep HH.MM, 11: arr HH.MM, 12: duration HH.MM, 13: days-of-run bitmask (Mon-first),
  ... type token (SUPERFAST/...), fare blob "TYPE:km:f1,f2..:f1,..:..." where each
  colon-group is a class row of 6 comma values. Row→class order is an INFERENCE
  (confidence medium) — documented in the gate doc and surfaced in comfort_notes.
"""
from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta

from config import settings
from data_sources.adapters.base import AdapterError, SourceAdapter, polite_get
from models.research_plan import HealthReport
from models.travel_request import TravelRequest

ERAIL_URL = ("https://erail.in/rail/getTrains.aspx?Station_From={frm}&Station_To={to}"
             "&DataSource=0&Date={ddmmyyyy}")

# erail returns only trains running on the requested date, but the bitmask lets
# us double-check: index 0 = Monday (inferred from probes, confidence medium).
WEEKDAY_ORDER = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

# Inferred class-row labels via fare-per-km ratio bands (see gate doc).
# Ratio = fare / route-km against IRCTC GN-quota norms: 1A≈4.4, 2A≈2.7,
# 3A≈1.9, 3E≈1.65, CC≈1.5, SL≈0.75, 2S≈0.36. Validated on two fixture trains
# (22502, 16021 MAS→SBC): 1530/347=4.41→1A, 925/347=2.67→2A, 675/347=1.95→3A,
# 270/347=0.78→SL, 125/347=0.36→2S. Confidence: medium (documented inference).
CLASS_RATIO_BANDS: list[tuple[float, float, str]] = [
    (3.4, 9.9, "1A"), (2.2, 3.3, "2A"), (1.7, 2.15, "3A"),
    (1.3, 1.69, "3E"), (0.95, 1.29, "CC"), (0.5, 0.94, "SL"), (0.15, 0.49, "2S"),
]
AC_CLASSES = {"3A", "2A", "3E", "1A", "CC", "EC"}

_TRAIN_TYPES = {"SUPERFAST", "MAIL_EXPRESS", "EXPRESS", "PASSENGER", "VANDE_BHARAT",
                "SHATABDI", "RAJDHANI", "DURONTO", "TEJAS", "HUMSAFAR", "ANTYODAYA",
                " JAN SHATABDI", "SPECIAL"}


def _parse_clock(s: str) -> time | None:
    m = re.match(r"^(\d{1,2})[.:](\d{2})$", (s or "").strip())
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if 0 <= h <= 23 and 0 <= mi <= 59:
        return time(h, mi)
    return None


def _runs_on(bitmask: str, travel_date: date) -> bool | None:
    """True/False if decodable, None if the mask is missing/malformed."""
    if not bitmask or len(bitmask) < 7 or set(bitmask) - {"0", "1"}:
        return None
    idx = travel_date.weekday()  # Monday=0
    return bitmask[idx] == "1"


def _parse_fare_blob(token: str) -> dict:
    """'SUPERFAST:347:1530,...:925,...:...' → {'type','distance_km','classes'}.

    Class rows are UNLABELED; each row's class is identified by its
    fare-per-km ratio band (CLASS_RATIO_BANDS docstring above). Row 0 of each
    group is the general-quota fare (columns are quota variants).
    """
    parts = token.split(":")
    if len(parts) < 3:
        return {}
    distance = None
    try:
        distance = float(parts[1])
    except ValueError:
        pass
    classes: dict[str, float] = {}
    for group in parts[2:]:
        if not group or set(group) <= {",", ""}:
            continue
        values = []
        for v in group.split(","):
            try:
                fv = float(v)
                if fv > 0:
                    values.append(fv)
            except ValueError:
                continue
        if not values:
            continue
        fare = values[0]
        if distance and distance > 40:  # ratio needs a sane distance
            ratio = fare / distance
            label = None
            for lo, hi, name in CLASS_RATIO_BANDS:
                if lo <= ratio <= hi:
                    label = name
                    break
            if label and label not in classes:
                classes[label] = fare
    return {"type": parts[0], "distance_km": distance, "classes": classes}


def parse_erail_trains(raw: str, travel_date: date) -> list[dict]:
    """Pure parser (fixture-testable): raw text → source-shaped train dicts.

    Layout (from recorded fixture): route header, then '^' marks each train
    block. After '^': number, name, from-name/code, to-name/code, boarding
    name/code, dest name/code, dep HH.MM, arr HH.MM, dur HH.MM, days(7-char),
    …then a fare token 'TYPE:km:row0:row1:…' (6 comma values per class row).
    Lines starting '~~' are coach compositions — skipped.
    """
    out: list[dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if "^" not in line:
            continue
        right = line.split("^", 1)[1]
        f = right.split("~")
        if len(f) < 14:
            continue
        try:
            number = int(f[0].strip())
        except ValueError:
            continue
        dep_t = _parse_clock(f[10])
        dur_t = _parse_clock(f[12])
        if dep_t is None or dur_t is None:
            continue
        duration_minutes = dur_t.hour * 60 + dur_t.minute
        if duration_minutes <= 0:
            continue
        runs = _runs_on(f[13], travel_date)
        if runs is False:
            continue

        fare = {}
        traintype = None
        for token in f[14:]:
            if ":" in token and re.match(r"^[A-Z_]+:\d+:", token):
                fare = _parse_fare_blob(token)
                traintype = fare.get("type")
                break
        if traintype is None:
            for token in f[14:40]:
                if token.strip() in _TRAIN_TYPES:
                    traintype = token.strip()
                    break

        if not fare.get("classes") or len(fare["classes"]) < 2:
            continue

        dep_dt = datetime.combine(travel_date, dep_t)
        arr_dt = dep_dt + timedelta(minutes=duration_minutes)

        out.append({
            "number": number,
            "name": f[1].strip(),
            "from_code": f[7].strip(),
            "to_code": f[9].strip(),
            "departure": dep_dt,
            "arrival": arr_dt,
            "duration_minutes": duration_minutes,
            "overnight": arr_dt.date() > travel_date,
            "days_bitmask": f[13],
            "type": traintype,
            "distance_km": fare.get("distance_km"),
            "classes": fare["classes"],
        })
    return out


class ErailSource(SourceAdapter):
    id = "erail"

    async def health_check(self) -> HealthReport:
        try:
            resp = await polite_get(
                "https://erail.in/rail/getTrains.aspx?Station_From=MAS&Station_To=SBC"
                "&DataSource=0&Date=01-01-2026", host_key="erail.in")
            ok = "getTrains" not in resp.text and len(resp.text) > 200
            return HealthReport(source_id=self.id, healthy=ok,
                                detail=f"HTTP {resp.status_code}, {len(resp.text)}B")
        except AdapterError as exc:
            return HealthReport(source_id=self.id, healthy=False, detail=str(exc)[:200])

    async def collect(self, req: TravelRequest) -> list[dict]:
        if not (req.source and req.destination and req.travel_date):
            raise AdapterError("route/date incomplete for train search")
        frm, to = req.source.station_code, req.destination.station_code
        if not frm or not to:
            raise AdapterError(
                f"no station codes for {req.source.city}→{req.destination.city}")
        url = ERAIL_URL.format(frm=frm, to=to,
                               ddmmyyyy=req.travel_date.strftime("%d-%m-%Y"))
        resp = await polite_get(url, host_key="erail.in")
        trains = parse_erail_trains(resp.text, req.travel_date)
        if not trains:
            raise AdapterError("erail returned no usable train rows")
        return trains
