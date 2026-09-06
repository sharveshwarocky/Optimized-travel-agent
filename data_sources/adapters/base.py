"""Source adapter contract (spec §7.3) + polite HTTP plumbing (§17.8).

Adapters return raw, source-shaped data; collectors convert to TravelOption via
the normalizer. One dead source never aborts a run — failures are contained and
reported honestly (§3.3, §17.5).
"""
from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod

import httpx

from config import settings
from models.research_plan import HealthReport
from models.travel_request import TravelRequest


class AdapterError(Exception):
    """Any adapter failure — caught by collectors, never fatal to the run."""


_last_hit: dict[str, float] = {}


async def polite_get(url: str, *, host_key: str | None = None,
                     headers: dict | None = None) -> httpx.Response:
    """GET with per-host delay (robots-respecting pacing, §17.8), timeout,
    and one backoff-retry for transient errors."""
    key = host_key or httpx.URL(url).host
    merged = {"User-Agent": settings.HTTP_USER_AGENT, **(headers or {})}
    last_exc: Exception | None = None
    for attempt in range(2):  # one retry with backoff
        now = time.monotonic()
        wait = settings.REQUEST_DELAY_SECONDS - (now - _last_hit.get(key, 0.0))
        if wait > 0:
            await asyncio.sleep(wait)
        if attempt:
            await asyncio.sleep(1.5 * attempt)  # brief backoff before retry
        _last_hit[key] = time.monotonic()
        try:
            resp = await async_client().get(url, headers=merged,
                                            timeout=settings.HTTP_TIMEOUT_SECONDS,
                                            follow_redirects=True)
            resp.raise_for_status()
            return resp
        except httpx.HTTPError as exc:
            last_exc = exc
            status = getattr(exc, "response", None)
            if status is not None and status.status_code in (401, 403, 404):
                break  # permanent — don't retry
    raise AdapterError(f"GET {url} failed: {last_exc}") from last_exc


_client: httpx.AsyncClient | None = None


def async_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(follow_redirects=True)
    return _client


async def close_http() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


class SourceAdapter(ABC):
    """One adapter per external site/API — swap-friendly per D5."""

    id: str = "base"

    @abstractmethod
    async def health_check(self) -> HealthReport:
        """Cheap reachability/format probe before collection (spec §7.3)."""

    @abstractmethod
    async def collect(self, req: TravelRequest) -> list[dict]:
        """Return raw source-shaped dicts. Raise AdapterError on failure."""
