"""City → station/airport/terminal resolution (spec §5 utils/geo.py).

Three-tier resolution:
1. Curated metro table (CITY_DB) — station + IATA airport codes + coordinates.
2. National station directory (data_sources/stations/india_stations.json, ~9,100
   entries built from erail's public /js/cmp/stations.js — see
   scripts/build_station_db.py). Covers essentially every rail-served Indian
   town including tourist aliases (Ooty→UAM, Kodaikanal→DG, Manali→SML).
3. OSM Nominatim geocoding for coordinates when no table entry matches
   (feeds road/estimate modes; NOMINATIM_GEOCODE=true in .env, on by default,
   auto-disabled in tests via PYTEST_CURRENT_TEST).

Unknown cities degrade gracefully: trains/flight-estimates ship unavailable
with a clear message; OSRM still routes via geocoded coordinates; fuel falls
back to the 🟡 settings rate. Nothing is ever fabricated.
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from models.travel_request import LocationRef

STATIONS_URL = "https://erail.in/js/cmp/stations.js"
_STATIONS_JSON = Path(__file__).resolve().parents[1] / "data_sources" / "stations" / "india_stations.json"

# city → (station_code, airport_code, lat, lon)
CITY_DB: dict[str, tuple[str, str | None, float, float]] = {
    "chennai": ("MAS", "MAA", 13.0827, 80.2707),
    "bangalore": ("SBC", "BLR", 12.9716, 77.5946),
    "bengaluru": ("SBC", "BLR", 12.9716, 77.5946),
    "mumbai": ("CSMT", "BOM", 19.0760, 72.8777),
    "delhi": ("NDLS", "DEL", 28.6139, 77.2090),
    "new delhi": ("NDLS", "DEL", 28.6139, 77.2090),
    "hyderabad": ("SC", "HYD", 17.3850, 78.4867),
    "secunderabad": ("SC", "HYD", 17.4399, 78.4983),
    "kolkata": ("HWH", "CCU", 22.5726, 88.3639),
    "pune": ("PUNE", "PNQ", 18.5204, 73.8567),
    "ahmedabad": ("ADI", "AMD", 23.0225, 72.5714),
    "jaipur": ("JP", "JAI", 26.9124, 75.7873),
    "coimbatore": ("CBE", "CJB", 11.0168, 76.9558),
    "madurai": ("MDU", "IXM", 9.9252, 78.1198),
    "mysore": ("MYS", "MYQ", 12.2958, 76.6394),
    "mysuru": ("MYS", "MYQ", 12.2958, 76.6394),
    "kochi": ("ERS", "COK", 9.9312, 76.2673),
    "cochin": ("ERS", "COK", 9.9312, 76.2673),
    "trivandrum": ("TVC", "TRV", 8.5241, 76.9366),
    "thiruvananthapuram": ("TVC", "TRV", 8.5241, 76.9366),
    "visakhapatnam": ("VSKP", "VTZ", 17.6868, 83.2185),
    "vijayawada": ("BZA", "VGA", 16.5062, 80.6480),
    "nagpur": ("NGP", "NAG", 21.1458, 79.0882),
    "indore": ("INDB", "IDR", 22.7196, 75.8577),
    "lucknow": ("LKO", "LKO", 26.8467, 80.9462),
    "surat": ("ST", "STV", 21.1702, 72.8311),
    "bhopal": ("BPL", "BHO", 23.2599, 77.4126),
    "patna": ("PNBE", "PAT", 25.5941, 85.1376),
    "goa": ("MAO", "GOI", 15.4909, 73.8278),
    "trichy": ("TPJ", "TRZ", 10.7905, 78.7047),
    "tiruchirappalli": ("TPJ", "TRZ", 10.7905, 78.7047),
    "salem": ("SA", "SXV", 11.6643, 78.1460),
    "vellore": ("VLR", None, 12.9022, 79.0611),
    "pondicherry": ("PDY", "PDY", 11.9416, 79.8083),
    "puducherry": ("PDY", "PDY", 11.9416, 79.8083),
    "tirupati": ("TPTY", "TIR", 13.6288, 79.4192),
    "guntur": ("GNT", None, 16.3067, 80.4365),
    "erode": ("ED", None, 11.3410, 77.7172),
    "tirunelveli": ("TEN", None, 8.7139, 77.7567),
    "warangal": ("WL", None, 17.9689, 79.5941),
    "kanpur": ("CNB", "KNU", 26.4499, 80.3319),
    "varanasi": ("BSB", "VNS", 25.3176, 82.9739),
    "amritsar": ("ASR", "ATQ", 31.6340, 74.8723),
    "chandigarh": ("CDG", "IXC", 30.7333, 76.7794),
    "bhubaneswar": ("BBS", "BBI", 20.2961, 85.8245),
    "guwahati": ("GHY", "GAU", 26.1445, 91.7362),
    "raipur": ("R", "RPR", 21.2514, 81.6296),
    "dehradun": ("DDN", "DED", 30.3165, 78.0322),
    "shimla": ("SML", None, 31.1048, 77.1734),
    "manali": (None, None, 32.2432, 77.1892),
    "goa-north": (None, None, 15.5527, 73.7517),
}

# Official vs colloquial spellings (IR uses "Kanniyakumari", port is "Thoothukudi").
SPELLING_ALIASES: dict[str, str] = {
    "kanyakumari": "kanniyakumari",
    "tuticorin": "thoothukudi",
    "tuticorin port": "thoothukudi",
    "trichur": "thrissur",
    "calicut": "kozhikode",
    "bangalore cant": "bangalore cant",
    "vizag": "visakhapatnam",
    "jammu": "jammu tawi",
    "pondy": "pondicherry",
    "bangalore city": "bangalore city",
    "trivandrum central": "thiruvananthapuram central",
    "allhabad": "prayagraj",
    "allahabad": "prayagraj",
    "benaras": "varanasi",
    "gurgaon": "gurugram",
    "poona": "pune",
    "calcutta": "kolkata",
    "madras": "chennai",
    "bombay": "mumbai",
}

_SUFFIXES = (" cantt", " cant", " town", " jn", " junction", " central", " ctrl")


def _normalize(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip().lower().rstrip("."))


def _variants(name: str) -> list[str]:
    """The name plus suffix-stripped and alias forms, most specific first."""
    key = _normalize(name)
    out: list[str] = [key]
    for suf in _SUFFIXES:
        if key.endswith(suf) and len(key) > len(suf):
            out.append(key[: -len(suf)])
    out.extend(SPELLING_ALIASES.get(v, "") for v in list(out))
    seen: set[str] = set()
    return [v for v in out if v and v not in seen and not seen.add(v)]  # type: ignore[func-returns-value]


# ---------------------------------------------------------------- station DB
def parse_station_blob(raw: str) -> list[list[str]]:
    """Pure parser (fixture-testable): erail stations.js → [[code, name], …].

    The blob is one giant comma string of alternating code/name tokens
    ('BIGN,10510461,ABB,Abada,…' — numeric tokens are internal ids, skipped).
    """
    m = re.search(r'"([^"]{200,})"', raw or "")
    if not m:
        return []
    toks = m.group(1).split(",")
    code_re = re.compile(r"^[A-Z0-9]{2,7}$")
    name_re = re.compile(r"^[A-Za-z0-9 .()&'/\-]+$")
    pairs: list[list[str]] = []
    i = 0
    while i < len(toks) - 1:
        c, n = toks[i], toks[i + 1]
        if (code_re.match(c) and name_re.match(n) and re.search(r"[A-Za-z]", n)
                and not c.isdigit()):
            pairs.append([c, n])
            i += 2
        else:
            i += 1
    return pairs


def _load_station_index() -> tuple[dict[str, list[tuple[str, str]]], list[tuple[str, str]]]:
    """name-key → [(code, name), …] plus the raw pair list (name order)."""
    try:
        pairs = [(c, n) for c, n in json.loads(_STATIONS_JSON.read_text(encoding="utf-8"))]
    except (OSError, ValueError):
        pairs = []
    by_name: dict[str, list[tuple[str, str]]] = {}
    for c, n in pairs:
        for v in _variants(n):
            by_name.setdefault(v, []).append((c, n))
    return by_name, pairs


_STATION_INDEX: tuple[dict[str, list[tuple[str, str]]], list[tuple[str, str]]] | None = None


def station_index() -> tuple[dict[str, list[tuple[str, str]]], list[tuple[str, str]]]:
    global _STATION_INDEX
    if _STATION_INDEX is None:
        _STATION_INDEX = _load_station_index()
    return _STATION_INDEX


# ---------------------------------------------------------------- geocoding
_geo_cache: dict[str, tuple[float, float] | None] = {}
_geo_lock = asyncio.Lock()
_last_geo_hit = 0.0


def geocoding_enabled() -> bool:
    """On by default; off in tests and when NOMINATIM_GEOCODE=false."""
    if "PYTEST_CURRENT_TEST" in __import__("os").environ:
        return False
    from config import settings
    return getattr(settings, "NOMINATIM_GEOCODE", True)


async def geocode_city(name: str) -> tuple[float, float] | None:
    """OSM Nominatim → (lat, lon) for an Indian city, cached + rate-limited.

    Returns None on any failure or a bogus name (Nominatim returns []) —
    callers degrade honestly (road modes ship unavailable, §17.5).
    """
    global _last_geo_hit
    key = _normalize(name)
    if not key or key in _geo_cache:
        return _geo_cache.get(key)
    if not geocoding_enabled():
        return None
    async with _geo_lock:
        if key in _geo_cache:
            return _geo_cache[key]
        loop = asyncio.get_running_loop()

        def _fetch() -> tuple[float, float] | None:
            import time
            import urllib.parse
            import urllib.request
            global _last_geo_hit
            wait = 1.1 - (time.monotonic() - _last_geo_hit)  # Nominatim: ≤1 req/s
            if wait > 0:
                time.sleep(wait)
            _last_geo_hit = time.monotonic()
            url = ("https://nominatim.openstreetmap.org/search?"
                   + urllib.parse.urlencode({"q": f"{name}, India", "format": "json",
                                             "limit": 1, "countrycodes": "in"}))
            req = urllib.request.Request(
                url, headers={"User-Agent": "travel-decision-agent/1.0 (route planning)"})
            data = json.loads(urllib.request.urlopen(req, timeout=15).read())
            if not data:
                return None
            return (float(data[0]["lat"]), float(data[0]["lon"]))

        try:
            coords = await loop.run_in_executor(None, _fetch)
        except Exception:
            coords = None
        _geo_cache[key] = coords
        return coords


async def ensure_coords(req) -> None:
    """Fill missing lat/lon for either leg before road-math modes run (§4)."""
    for ref in (req.source, req.destination):
        if ref is None or city_coords(ref) is not None:
            continue
        coords = await geocode_city(ref.city)
        if coords:
            ref.lat, ref.lon = coords
            ref.resolved = True


# ---------------------------------------------------------------- resolution
def resolve_city(name: str | None) -> LocationRef | None:
    """Free-text city → LocationRef with codes/coords if known (offline tiers
    1–2 here; coordinates-only tier 3 runs via ensure_coords in the pipeline)."""
    if not name or not str(name).strip():
        return None
    display = name.strip().title()
    for key in _variants(str(name)):
        entry = CITY_DB.get(key)
        if entry:
            station, airport, lat, lon = entry
            return LocationRef(city=display, station_code=station, airport_code=airport,
                               resolved=True)
    idx, _ = station_index()
    for key in _variants(str(name)):
        hits = idx.get(key)
        if hits:
            code, sname = hits[0]
            return LocationRef(city=display, station_code=code, resolved=True)
    # unique containment: "gokarna" → "Gokarna Road"; ambiguous names left unresolved
    base = _variants(str(name))[0]
    if len(base) >= 4:
        _, pairs = station_index()
        cands = [(c, n) for c, n in pairs if re.search(rf"\b{re.escape(base)}\b", n.lower())]
        if len(cands) == 1:
            return LocationRef(city=display, station_code=cands[0][0], resolved=True)
    return LocationRef(city=display, resolved=False)


def city_coords(ref: LocationRef | None) -> tuple[float, float] | None:
    """Lat/lon for a LocationRef: explicit geocode → CITY_DB → None."""
    if ref is None:
        return None
    if ref.lat is not None and ref.lon is not None:
        return (ref.lat, ref.lon)
    entry = CITY_DB.get(_normalize(ref.city))
    return (entry[2], entry[3]) if entry else None


def city_size_class(ref: LocationRef | None) -> str:
    """Rough metro class for default access-leg assumptions ('metro'|'city'|'town')."""
    if ref is None or not ref.resolved:
        return "town"
    key = _normalize(ref.city)
    metros = {"chennai", "bangalore", "bengaluru", "mumbai", "delhi", "new delhi",
              "hyderabad", "kolkata", "pune", "ahmedabad"}
    if key in metros:
        return "metro"
    if ref.station_code or ref.airport_code:
        return "city"
    return "town"
