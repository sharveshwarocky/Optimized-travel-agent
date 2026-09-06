"""City → station/airport/terminal resolution (spec §5 utils/geo.py).

A curated table for major Indian cities keeps the system key-free and offline-safe.
Unknown cities degrade gracefully: trains/flights ship unavailable for that route,
OSRM still works via coordinates (or falls back to straight-line estimates).
"""
from __future__ import annotations

from models.travel_request import LocationRef

# city → (station_code, airport_code, lat, lon)
CITY_DB: dict[str, tuple[str, str, float, float]] = {
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
    "vellore": ("VEL", None, 12.9165, 79.1325),
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


def _normalize(name: str) -> str:
    return (name or "").strip().lower().rstrip(".")


def resolve_city(name: str | None) -> LocationRef | None:
    """Resolve a free-text city name into a LocationRef with codes/coords if known."""
    if not name:
        return None
    key = _normalize(name)
    entry = CITY_DB.get(key)
    if not entry:
        # light aliasing: strip common suffixes
        for suffix in (" city", " junction", " jn"):
            if key.endswith(suffix):
                entry = CITY_DB.get(key[: -len(suffix)])
                if entry:
                    break
    if entry:
        station, airport, lat, lon = entry
        return LocationRef(city=name.strip().title(), station_code=station,
                           airport_code=airport, resolved=True)
    return LocationRef(city=name.strip().title(), resolved=False)


def city_coords(ref: LocationRef | None) -> tuple[float, float] | None:
    """Lat/lon for a LocationRef if we know the city."""
    if ref is None:
        return None
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
