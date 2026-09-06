# Adapter Gate: skiplagged.com API (flight)

Status: **PASS on parser / FAIL on live access from Python runtime (2026-09-06) — collector tries live first, falls back to 🟠 formula estimates (user decision); parser + fixture tests retained for a future keyed API**

| # | Criterion | Finding |
|---|-----------|---------|
| 1 | Accessibility | `GET https://skiplagged.com/api/search.php?from=<IATA>&to=<IATA>&departDate=YYYY-MM-DD&format=v2` → JSON with `airlines`, `airports`, `flights`, `itineraries.outbound[{flight, one_way_price}]`. No key. |
| 2 | Reliability (3 probes) | 200 OK via curl at first, later probes show intermittent 403s; payload ~300 KB JSON when served. |
| 3 | Rate limits | Undocumented; adapter treats it gently (1 req/search + backoff). |
| 4 | ToS / robots | Unofficial API; read-only, one request per user-initiated search. |
| 5 | Anti-bot | **Cloudflare "Just a moment…" JS challenge is served based on client TLS fingerprint**: curl receives 200 + JSON, Python `httpx` receives 403 + challenge HTML on the identical request. This is exactly the anti-bot posture spec §7.1 warns about — defeating it (impersonation browsers, TLS spoofing) is out of scope for v1 per §17.8. |
| 6 | API fallback | None usable found at build time: ixigo/easemytrip are JS-rendered shells, redbus unreachable, Amadeus self-service free tier not confirmed for India domestic. Spec R1 worst case applies. |

**Decision per spec §3.3 + R1:** flight mode ships honestly 🔴 `unavailable` live. The parser (`parse_skiplagged`) is complete and covered by fixture tests (`tests/fixture_tests/test_skiplagged_fixture.py`) using the recorded 343 KB payload, so if the challenge posture changes or a keyed API is swapped in, the rest of the pipeline works unchanged. Recorded fixture: `data_sources/fixtures/skiplagged_maa_blr.json`.
