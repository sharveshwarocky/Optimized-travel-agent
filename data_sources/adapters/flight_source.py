"""Skiplagged flight adapter (gate doc: data_sources/adapters/skiplagged_flight_source.md).

GET /api/search.php?from=IATA&to=IATA&departDate=YYYY-MM-DD&format=v2 → JSON:
  airlines: {code: name}; flights: {id: {segments:[{airline, flight_number,
  departure{time,airport}, arrival{time,airport}, duration}], duration, count}};
  itineraries.outbound: [{flight, one_way_price}].
"""
from __future__ import annotations

from datetime import datetime

from data_sources.adapters.base import AdapterError, SourceAdapter, polite_get
from models.research_plan import HealthReport
from models.travel_request import TravelRequest

SKILAGGED_URL = ("https://skiplagged.com/api/search.php?from={frm}&to={to}"
                 "&departDate={date}&format=v2")

MAX_OPTIONS = 10
MAX_STOPS = 1


def parse_skiplagged(payload: dict, travel_date, passengers: int) -> list[dict]:
    """Pure parser (fixture-testable): payload → source-shaped flight dicts.

    one_way_price is per-person; total here stays per-person ×1 — the collector
    scales to party size (costs always computed in Python, guide §25).
    """
    airlines: dict = payload.get("airlines") or {}
    flights: dict = payload.get("flights") or {}
    itineraries = ((payload.get("itineraries") or {}).get("outbound")) or []

    out: list[dict] = []
    for iti in itineraries:
        fid = iti.get("flight")
        price = iti.get("one_way_price")
        flight = flights.get(fid)
        if not flight or not price or price <= 0:
            continue
        segments = flight.get("segments") or []
        if not segments:
            continue
        stops = max(0, int(flight.get("count", len(segments))) - 1)
        if stops > MAX_STOPS:
            continue
        try:
            dep_dt = datetime.fromisoformat(segments[0]["departure"]["time"])
            arr_dt = datetime.fromisoformat(segments[-1]["arrival"]["time"])
        except (KeyError, ValueError):
            continue
        # layover sanity: skip absurd routings (total > 2.5× sum of segment times + 4h)
        seg_minutes = sum(s.get("duration", 0) for s in segments) // 60
        total_minutes = flight.get("duration", 0) // 60
        if seg_minutes and total_minutes > seg_minutes + 300:
            continue

        def _fmt(seg) -> str:
            al = airlines.get(seg.get("airline"), seg.get("airline", ""))
            return f"{al} {seg.get('flight_number', '')}".strip()

        name = " + ".join(_fmt(s) for s in segments)
        out.append({
            "name": name,
            "airline": airlines.get(segments[0].get("airline"), segments[0].get("airline")),
            "from_airport": segments[0]["departure"]["airport"],
            "to_airport": segments[-1]["arrival"]["airport"],
            "departure": dep_dt,
            "arrival": arr_dt,
            "duration_minutes": total_minutes or seg_minutes,
            "stops": stops,
            "price_per_person": float(price),
            "segments": len(segments),
        })

    out.sort(key=lambda o: o["price_per_person"])
    return out[:MAX_OPTIONS]


class SkiplaggedSource(SourceAdapter):
    id = "skiplagged"

    async def health_check(self) -> HealthReport:
        try:
            from datetime import date, timedelta
            probe_date = (date.today() + timedelta(days=30)).isoformat()
            resp = await polite_get(
                f"https://skiplagged.com/api/search.php?from=MAA&to=BLR"
                f"&departDate={probe_date}&format=v2", host_key="skiplagged.com")
            ok = resp.json().get("itineraries") is not None
            return HealthReport(source_id=self.id, healthy=ok,
                                detail=f"HTTP {resp.status_code}")
        except (AdapterError, ValueError) as exc:
            return HealthReport(source_id=self.id, healthy=False, detail=str(exc)[:200])

    async def collect(self, req: TravelRequest) -> list[dict]:
        if not (req.source and req.destination and req.travel_date):
            raise AdapterError("route/date incomplete for flight search")
        frm = req.source.airport_code
        to = req.destination.airport_code
        if not frm or not to:
            raise AdapterError(
                f"no airport codes for {req.source.city}→{req.destination.city}")
        url = SKILAGGED_URL.format(frm=frm, to=to, date=req.travel_date.isoformat())
        resp = await polite_get(url, host_key="skiplagged.com")
        try:
            payload = resp.json()
        except ValueError as exc:
            raise AdapterError(f"skiplagged returned non-JSON: {exc}") from exc
        if "itineraries" not in payload:
            raise AdapterError(f"skiplagged error: {str(payload)[:120]}")
        return parse_skiplagged(payload, req.travel_date, req.effective_passengers())
