# Adapter Gate: goodreturns.in (petrol price)

Status: **PASS (primary fuel-price source)**

| # | Criterion | Finding |
|---|-----------|---------|
| 1 | Accessibility | City pages e.g. `https://www.goodreturns.in/petrol-price-in-bangalore.html`; current ₹/L appears in `<title>` (`... Rs. 111.11/Ltr ...`) and page body. |
| 2 | Reliability (3 probes) | 200 OK; price present and current (dated "today") on all probes. |
| 3 | Rate limits | No blocking observed at interactive rates; adapter fetches ≤ 2 pages per run (origin + destination city). |
| 4 | ToS / robots | Public price-info pages; read-only use with attribution in provenance (`source: "goodreturns"`). |
| 5 | Anti-bot | None observed. |
| 6 | API fallback | Falls back to a settings-stored recent national average, labeled 🟡 `recent`. |

**Notes:** diesel price parsed from the same page family when needed; price is city-specific (we use max of origin/destination for conservative fuel cost).
