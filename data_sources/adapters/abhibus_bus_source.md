# Adapter Gate: abhibus.com / redbus.in (bus)

Status: **FAIL at build time (2026-09-06) for live data — mode ships 🟠 formula estimates instead (user decision), adapter stub kept for when a scrapeable source is found**

| # | Criterion | Finding |
|---|-----------|---------|
| 1 | Accessibility | abhibus search pages are JS-rendered shells (50 KB HTML, zero embedded fare/operator JSON, no `__NEXT_DATA__`). Search-result endpoints not discoverable in `init-1.3.23.js` / `masterScript.js`. |
| 2 | Reliability | N/A — no data endpoint found. |
| 3 | Rate limits | N/A. |
| 4 | ToS / robots | redbus.in timed out entirely (connection timeout at 20 s) during probes. |
| 5 | Anti-bot | Both OTAs are heavily client-rendered (a CAPTCHA/JS-challenge posture is typical for this vertical). |
| 6 | API fallback | Commercial bus APIs exist (SRDV, AbhiBus partner) but need paid keys — out of scope for free-tier v1. |

**Decision per spec §3.3 (D3 + D13):** no mocked data. Bus collector ships returning an honest `unavailable` result which the UI renders 🔴 with an explanation, and the adapter interface stays open so a RedBus/abhibus/RTC adapter can be dropped in later (tier-2 backlog: state RTC sites often have simpler server-rendered pages, e.g. ksrtc.in returned 302 → follow-up candidate).
