# Adapter Gate: OSRM public demo (road distance/duration)

Status: **PASS (primary road-routing source — no key)**

| # | Criterion | Finding |
|---|-----------|---------|
| 1 | Accessibility | `GET https://router.project-osrm.org/route/v1/driving/<lon1>,<lat1>;<lon2>,<lat2>?overview=false` → JSON `routes[0].distance` (m), `.duration` (s). |
| 2 | Reliability (3 probes) | 200 OK < 1 s. MAA→BLR probe: 327.3 km / 4.12 h — plausible against known ~350 km road distance. |
| 3 | Rate limits | Public demo server: fair-use, ~1 req/s. Adapter adds caching + backoff. |
| 4 | ToS / robots | OSM data is ODbL; demo server is fair-use. Light, cached, read-only use is within norms. |
| 5 | Anti-bot | None observed. |
| 6 | API fallback | Google Maps Directions API key could replace it via the same adapter interface (settings supports it). |

**Usage:** road_collector uses it for route distance/duration (own car, cab, rental); door_to_door.py uses it for origin/destination access legs when coordinates exist, else city-size assumptions recorded in `door_to_door_breakdown`.
