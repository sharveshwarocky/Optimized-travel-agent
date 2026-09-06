"""BaseCollector (spec §4, §7.3): runs an adapter inside a timeout and contains
failures. One dead source never aborts the run — it returns UnavailableResult
which flows through the pipeline as an honest 🔴 mode (§3.3, §17.5).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from config import settings
from data_sources.adapters.base import AdapterError
from models.travel_option import TravelOption
from models.travel_request import TravelRequest


@dataclass
class CollectResult:
    mode: str
    options: list[TravelOption]
    status: str                 # "ok" | "empty" | "unavailable"
    detail: str = ""            # human-readable explanation for the UI/reasoning agent


class UnavailableResult(CollectResult):
    def __init__(self, mode: str, detail: str):
        super().__init__(mode=mode, options=[], status="unavailable", detail=detail)


class BaseCollector:
    mode: str = "base"
    adapter_id: str = "base"

    def __init__(self) -> None:
        self.adapter = None  # set by subclass

    async def collect_with_timeout(self, req: TravelRequest) -> CollectResult:
        try:
            return await asyncio.wait_for(self._collect(req),
                                          timeout=settings.COLLECTOR_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            return UnavailableResult(self.mode,
                                     f"{self.mode} collector timed out after "
                                     f"{settings.COLLECTOR_TIMEOUT_SECONDS:.0f}s")
        except AdapterError as exc:
            return UnavailableResult(self.mode, str(exc))
        except Exception as exc:  # absolute containment: never abort the run
            return UnavailableResult(self.mode, f"{self.mode} collector failed: {exc}")

    async def _collect(self, req: TravelRequest) -> CollectResult:
        raise NotImplementedError
