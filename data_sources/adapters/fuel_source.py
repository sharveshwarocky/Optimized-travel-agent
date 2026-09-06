"""goodreturns.in fuel-price adapter (gate doc: data_sources/adapters/goodreturns_fuel_source.md).

City page <title> looks like: 'Petrol Price in Bangalore, Petrol Rate Today
(6th Sep, 2026), Rs. 111.11/Ltr - Goodreturns' → parse 'Rs. NNN.NN/Ltr'.
Falls back to settings.FUEL_RECENT_FALLBACK_PER_LITRE labeled 🟡 recent.
"""
from __future__ import annotations

import re

from config import settings
from data_sources.adapters.base import AdapterError, SourceAdapter, polite_get
from models.provenance import Provenance, utcnow
from models.research_plan import HealthReport
from models.travel_request import LocationRef

PRICE_RE = re.compile(r"Rs\.?\s*(\d{2,3}(?:\.\d{1,2})?)\s*/?\s*L", re.IGNORECASE)
TITLE_RE = re.compile(r"<title>([^<]+)</title>", re.IGNORECASE)
DATE_RE = re.compile(r"\((\d{1,2})(?:st|nd|rd|th)?\s+(\w+),\s*(\d{4})\)")


def parse_fuel_price(html: str) -> float | None:
    """Pure parser: first Rs. NNN.NN/Ltr occurrence (title comes first)."""
    m = PRICE_RE.search(html or "")
    return float(m.group(1)) if m else None


def parse_page_date(html: str) -> str | None:
    m = DATE_RE.search(html or "")
    return f"{m.group(1)} {m.group(2)} {m.group(3)}" if m else None


class GoodreturnsFuelSource(SourceAdapter):
    id = "goodreturns"

    async def health_check(self) -> HealthReport:
        try:
            resp = await polite_get(
                "https://www.goodreturns.in/petrol-price-in-bangalore.html",
                host_key="www.goodreturns.in")
            return HealthReport(source_id=self.id, healthy=parse_fuel_price(resp.text) is not None,
                                detail="title price parsed" )
        except AdapterError as exc:
            return HealthReport(source_id=self.id, healthy=False, detail=str(exc)[:200])

    async def collect(self, req: TravelRequest) -> list[dict]:  # not a mode collector
        raise NotImplementedError

    async def petrol_price(self, city: LocationRef) -> Provenance:
        """₹/litre for the city as Provenance (never fabricated — falls back labeled)."""
        from utils.geo import _normalize  # local import to avoid cycle
        tried: set[str] = set()
        slug = settings.FUEL_CITY_SLUGS.get(_normalize(city.city))
        if not slug:
            # unmapped city: try the URL pattern directly (goodreturns uses
            # hyphenated lowercase city slugs); 'vellore' → 'petrol-price-in-vellore.html'
            slug = re.sub(r"[^a-z0-9]+", "-", _normalize(city.city)).strip("-")
        candidates = [s for s in (slug,) if s and s not in tried]
        for cand in candidates:
            tried.add(cand)
            try:
                resp = await polite_get(
                    f"https://www.goodreturns.in/petrol-price-in-{cand}.html",
                    host_key="www.goodreturns.in")
                price = parse_fuel_price(resp.text)
                if price:
                    return Provenance(value=price, source=f"goodreturns:{cand}",
                                      retrieved_at=utcnow(), data_type="live",
                                      confidence="high")
            except AdapterError:
                continue
        return Provenance(value=settings.FUEL_RECENT_FALLBACK_PER_LITRE,
                          source="settings-fallback", retrieved_at=utcnow(),
                          data_type="recent", confidence="medium")
