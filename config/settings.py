"""Central settings (spec §5 config/settings.py): env loading, model slugs, timeouts,
door-to-door constants (§8), rate tables with last-verified notes (R4), reliability defaults (D12).

Never hardcode secrets here — .env only (safety rule 6).
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env")

# ---------------- LLM (D8: free/cheap models first, swappable) ----------------
OPENROUTER_API_KEY: str | None = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
LLM_MODEL: str = os.getenv("OPENROUTER_MODEL", "minimax/minimax-m3:free")
LLM_MODEL_FALLBACKS: list[str] = [
    m.strip() for m in os.getenv(
        "OPENROUTER_MODEL_FALLBACKS",
        "google/gemma-4-31b-it:free,nvidia/nemotron-3-super-120b-a12b:free",
    ).split(",") if m.strip()
]
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "45"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))

# ---------------- HTTP / scraping politeness (§17.8) ----------------
HTTP_TIMEOUT_SECONDS = float(os.getenv("HTTP_TIMEOUT_SECONDS", "25"))
COLLECTOR_TIMEOUT_SECONDS = float(os.getenv("COLLECTOR_TIMEOUT_SECONDS", "45"))
REQUEST_DELAY_SECONDS = float(os.getenv("REQUEST_DELAY_SECONDS", "1.0"))  # between hits to same host
HTTP_USER_AGENT = os.getenv(
    "HTTP_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
)

# ---------------- Door-to-door overheads (§8; minutes unless noted) ----------------
# Access legs (home→terminal etc.) come from CITY_ACCESS_MINUTES in
# services/door_to_door.py keyed on city size; only fixed per-mode buffers live here.
D2D = {
    "flight": {
        "reporting_minutes": 90,     # check-in/security buffer
        "exit_minutes": 30,          # baggage + exit
    },
    "train": {
        "buffer_minutes": 30,        # arrival buffer at station
        "exit_minutes": 15,
    },
    "bus": {
        "wait_minutes": 15,
    },
    "road": {
        "break_minutes_per_2h": 15,   # driving break allowance
        "traffic_buffer_pct": 0.15,   # traffic buffer
    },
}

# ---------------- Road cost model (D16/D17) ----------------
MILEAGE_KM_PER_LITRE = float(os.getenv("MILEAGE_KM_PER_LITRE", "15"))
FUEL_RECENT_FALLBACK_PER_LITRE = 105.0   # 🟡 recent fallback if goodreturns fails (R5)
TOLL_PER_KM = 1.6                        # ₹/km blended NH toll rate — see toll note below
TOLL_NOTE = ("Blended NH toll rate ₹/km; last verified 2026-09 (NHAI fee schedules, "
             "sample routes). Swap for api.data.gov.in NH fee dataset when a key is available (R5).")

# Cab outstation per-km bands (D17, R4) — last verified 2026-09 from published
# outstation rate cards of major operators (one-way, excludes tolls unless noted).
CAB_RATES_PER_KM = {
    "Hatchback": 12.0,
    "Sedan": 14.0,
    "SUV": 18.0,
}
CAB_DRIVER_ALLOWANCE = 300.0             # flat per trip day
CAB_MIN_FARE = 1500.0                    # minimum outstation charge
CAB_RATES_NOTE = "Outstation one-way bands; last verified 2026-09. Always 🟠 estimated (D17)."

# Self-drive rental (D17, R4) — last verified 2026-09 from published city rates.
RENTAL_PER_DAY = {
    "Hatchback": 1800.0,
    "Sedan": 2200.0,
    "SUV": 3000.0,
}
RENTAL_KM_CAP_PER_DAY = 300              # included km/day beyond which extra km applies
RENTAL_EXTRA_PER_KM = 12.0
RENTAL_NOTE = ("Self-drive daily bands with 300 km/day included; last verified 2026-09. "
               "Always 🟠 estimated (D17).")

# ---------------- Static reliability defaults (D12) ----------------
RELIABILITY_DEFAULTS: dict[str, int] = {
    "train": 8, "bus": 6, "flight": 8, "own_car": 7, "cab": 6, "rental": 6,
}

# ---------------- Scoring weight profiles (§11.2, guide §15) ----------------
# Keys: cost, time, comfort, conv, pref, schedule. LLM may suggest a profile;
# Python decides (rule table) — see services/scoring_engine.py.
WEIGHT_PROFILES: dict[str, dict[str, float]] = {
    "balanced":      {"cost": 0.25, "time": 0.20, "comfort": 0.15, "conv": 0.15, "pref": 0.15, "schedule": 0.10},
    "budget":        {"cost": 0.40, "time": 0.20, "comfort": 0.15, "conv": 0.10, "pref": 0.10, "schedule": 0.05},
    "comfort":       {"cost": 0.15, "time": 0.20, "comfort": 0.35, "conv": 0.20, "pref": 0.10, "schedule": 0.00},
    "urgent":        {"cost": 0.05, "time": 0.40, "comfort": 0.10, "conv": 0.15, "pref": 0.05, "schedule": 0.25},
    "group":         {"cost": 0.30, "time": 0.20, "comfort": 0.15, "conv": 0.15, "pref": 0.15, "schedule": 0.05},
}

# ---------------- Fuel price page slugs (goodreturns) ----------------
FUEL_CITY_SLUGS = {
    "chennai": "chennai", "bangalore": "bangalore", "bengaluru": "bangalore",
    "mumbai": "mumbai", "delhi": "delhi", "new delhi": "delhi", "hyderabad": "hyderabad",
    "pune": "pune", "kolkata": "kolkata", "ahmedabad": "ahmedabad", "jaipur": "jaipur",
    "coimbatore": "coimbatore", "madurai": "madurai", "mysore": "mysore", "mysuru": "mysore",
    "kochi": "kochi", "cochin": "kochi", "trivandrum": "trivandrum",
    "thiruvananthapuram": "trivandrum", "visakhapatnam": "visakhapatnam",
    "vijayawada": "vijayawada", "nagpur": "nagpur", "indore": "indore", "lucknow": "lucknow",
    "surat": "surat", "bhopal": "bhopal", "patna": "patna", "goa": "goa",
}
