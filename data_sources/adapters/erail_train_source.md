# Adapter Gate: erail.in (train)

Status: **PASS (primary train source)**

| # | Criterion | Finding |
|---|-----------|---------|
| 1 | Accessibility | Public `GET https://erail.in/rail/getTrains.aspx?Station_From=<CODE>&Station_To=<CODE>&DataSource=0&Date=DD-MM-YYYY`. Plain-text response, tilde/`^` delimited. No login. |
| 2 | Reliability (3 probes) | 200 OK in ~1.2 s on 2026-09-06 probes at different hours; response identical in shape each time. |
| 3 | Rate limits | No observed blocking on interactive-rate requests. Adapter enforces 1 req/s + backoff anyway. |
| 4 | ToS / robots | Public enquiry site (aggregator of IRCTC data). No robots.txt block observed on `/rail/getTrains.aspx`. Read-only use. |
| 5 | Anti-bot | None observed for this endpoint (plain text, no JS challenge). |
| 6 | API fallback | None needed; RailYatri/ConfirmTkt-class aggregators are candidates if erail changes. |

**Data returned per train:** number, name, origin/destination, dep/arr times, duration, days-of-run (7-char bitmask), type (SUPERFAST/MAIL_EXPRESS/...), and an embedded fare blob with per-class fares (several class rows, 6 fare values each; class labels not encoded — row order is the adapter's inference, confidence `medium`).

**Known gaps:** seat availability not exposed server-side without a separate JS/CAPTCHA flow → adapter sets `availability_status: null` (spec R2). Station codes resolved from a curated metro table in `utils/geo.py`; unknown cities → trains ship unavailable.
