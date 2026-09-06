"""Flight collector: live skiplagged first, formula estimates as fallback.

Gate finding (2026-09-06): skiplagged serves a Cloudflare TLS-fingerprint
challenge to Python httpx (works via curl) — live collection usually fails.
Per the user's decision, when live fails the collector produces 🟠
formula-based estimates (distance bands × carrier factors in settings) so the
mode always contributes comparable options. Provenance always distinguishes
the two paths.
"""
from __future__ import annotations

from collectors.base import BaseCollector, CollectResult
from collectors.flight_estimator import flight_variants
from collectors.road_collector import compute_road_profile
from data_sources.adapters.flight_source import SkiplaggedSource
from services import normalizer


class FlightCollector(BaseCollector):
    mode = "flight"
    adapter_id = "skiplagged|flight-formula"

    def __init__(self) -> None:
        super().__init__()
        self.adapter = SkiplaggedSource()

    async def _collect(self, req) -> CollectResult:
        # ---- 1) try live (kept swappable per D5) ----
        health = await self.adapter.health_check()
        if health.healthy:
            try:
                raws = await self.adapter.collect(req)
                options = normalizer.normalize(raws, req, "flight")
                if options:
                    return CollectResult(mode=self.mode, options=options, status="ok",
                                         detail=f"{len(options)} flight options from "
                                                f"skiplagged (live)")
            except Exception:
                pass  # fall through to estimates

        # ---- 2) formula estimates (D17-pattern, always labeled) ----
        profile = await compute_road_profile(req)
        if profile is None:
            return CollectResult(mode=self.mode, options=[], status="unavailable",
                                 detail="route between cities unknown (not in city table)")
        raws = flight_variants(profile.distance_km, req)
        if not raws:
            return CollectResult(
                mode=self.mode, options=[], status="unavailable",
                detail=f"route distance {profile.distance_km:g} km exceeds the "
                       f"{int(1600)} km short-haul estimate limit — rail/car dominate "
                       f"such routes; live flight source also unavailable "
                       f"(Cloudflare challenge)")
        options = []
        for raw in raws:
            options.append(normalizer.flight_option(
                raw, req, source="computed:flight-formula",
                data_type="estimated", confidence="medium",
                baggage_note="15 kg check-in + 7 kg cabin (typical economy allowance)"))
        return CollectResult(mode=self.mode, options=options, status="ok",
                             detail=f"flight estimates for {profile.distance_km:g} km "
                                    f"({len(options)} options, 🟠 estimated — live source "
                                    f"blocked by Cloudflare challenge)")
