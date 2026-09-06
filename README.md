# Agentic AI Travel Decision Agent (India)

A terminal-based agentic AI travel decision agent. Describe a trip in plain
English — it converses to fill the gaps, researches **real, current** travel
options across six modes, normalizes them into one comparable model, filters
them against your hard constraints, scores them with a transparent
multi-criteria engine, runs a "worth-it" value analysis, and explains a ranked
recommendation in your terminal.

**Core philosophy:** LLM for understanding and reasoning. Python for tools,
data, validation, calculations, and decisions. Real data for recommendations.
Transparency when data is uncertain. Best value for the user — not merely
cheapest or fastest.

Note: Removed API Key by Default
---

## Quick start

```bash
# 1. Python 3.11+ (this build used 3.12.10)
python -m venv .venv
.venv\Scripts\activate            # Windows  (source .venv/bin/activate on POSIX)

# 2. Dependencies
pip install -r requirements.txt

# 3. Configure
copy .env.example .env            # then put your OpenRouter key inside
#   OPENROUTER_API_KEY=sk-or-...

# 4. Run
python main.py
```

Then just type your trip:

```text
We are 3 people travelling from Chennai to Bangalore tomorrow.
We have ₹6000 total, prefer AC and comfort, and need to reach before 7 PM.
We don't mind spending a little extra if the time saved is actually worth it.
```

The agent asks at most the truly necessary follow-ups, then researches and
ranks. Commands inside the session: `new` (reset memory) · `explain` (show
sub-scores and weights) · `quit`.

Without an API key the agent still works end-to-end in **deterministic
fallback mode** (regex extraction, template explanations) — nothing is
fabricated either way.

---

## Architecture

```
main.py                       CLI entry point
├── agents/                   requirement / planning / reasoning / orchestrator
├── llm/                      OpenRouter client (retries, model fallbacks, usage log) + JSON schemas
├── config/
│   ├── settings.py           env, timeouts, door-to-door constants, rate tables, weight profiles
│   └── prompts/              versioned prompt templates (extraction, planning, reasoning, conflict)
├── collectors/               one collector per mode (timeout + failure containment)
├── data_sources/
│   ├── adapters/             one adapter per external source + research-gate docs (.md)
│   └── fixtures/             recorded HTML/JSON for offline tests
├── models/                   TravelRequest, TravelOption, Provenance, ResearchPlan (Pydantic v2)
├── services/                 normalizer, constraint engine, scoring engine, worth-it engine,
│                             comfort model, door-to-door model
├── memory/                   per-session conversation state
├── ui/                       Rich CLI + renderers
└── tests/                    unit + fixture tests (no network in CI)
```

### How data confidence works

Every option carries source, retrieval time, data type, and confidence. The
terminal renders it as: 🟢 live · 🟡 recent · 🟠 estimated · 🔴 unavailable.
Estimates are **always** labeled — the LLM is never allowed to fill prices,
times, or availability. When a source is unreachable, the mode is reported
🔴 with the reason instead of showing made-up numbers.

### Source status (research gate, 2026-09-06)

| Mode | Source | Status |
|---|---|---|
| Train | erail.in public schedule/fare endpoint | 🟢 live — trains, times, days-of-run, per-class fares |
| City resolution | curated metro table + bundled erail national station dir (~9,100 stations) + OSM Nominatim geocoding fallback | any Indian rail-served town auto-resolves to its station code; coordinates for road math come from the table or Nominatim (`NOMINATIM_GEOCODE=false` to disable) |
| Bus | abhibus / redbus | 🟠 formula estimates (D17-pattern) — live sources are JS-only shells; estimator wires in, adapters swappable |
| Flight | skiplagged API + formula fallback | 🟠 formula estimates — live API works via curl but serves Cloudflare TLS-fingerprint challenges to Python; collector tries live first, falls back to 🟠 estimates (parser + fixtures retained) |
| Own car | OSRM routing + goodreturns fuel + blended toll table | 🟢 live computation (fuel+tolls, D16: always computed) |
| Cab | formula (D17): km × per-km band + driver allowance + tolls | 🟠 estimated |
| Rental | formula (D17): daily rate × days + fuel + tolls | 🟠 estimated |

Gate details per source: `data_sources/adapters/*.md`.

---

## Testing

```bash
pytest            # 107 tests: engines, models, memory, utils, estimators + recorded-fixture parser tests
```

- **Unit** — constraint/scoring/worth-it engines, comfort model, door-to-door,
  session memory, persona golden tests (budget / comfort+elderly / urgent /
  group / short / long distance).
- **Fixture** — every collector's parser replayed against recorded live
  payloads; zero network in tests.
- **LLM degradation** — malformed-JSON and unavailable-key paths tested;
  fallbacks are reported in the UI when they fire.
- **Manual E2E** — `python scripts/e2e_run.py` runs the success prompt through
  the live pipeline and saves `e2e_output.txt`.

## E2E result (2026-09-06, success prompt)

Extraction: 3 passengers · Chennai→Bangalore · tomorrow · ₹6,000 total ·
AC + high comfort · arrive before 19:00 (LLM + regex fallback merged; one
override spoken). Collection: train 🟢 9 live options (erail), own car 🟢
(327.3 km via OSRM, fuel ₹111.11/L live, tolls ₹524), bus 🟠 / flight 🟠 /
cab 🟠 / rental 🟠 formula estimates (every 🟠 value called out in the
assumptions box). Recommendation: own car
₹2,948 total (₹983/person), 4h08m journey, meets deadline, score 81/100 —
with grounded worth-it lines vs cab and train
alternatives. Full transcript: `e2e_output.txt`.

---

## Safety rules (enforced by construction)

1. The LLM never supplies prices, schedules, or availability — only collectors do.
2. Every value carries provenance (source / retrieved_at / data_type / confidence).
3. LLM JSON is schema-validated with one repair retry; every LLM step has a deterministic fallback.
4. Unavailable data is reported as unavailable — honest degradation, never fabricated.
5. API keys live only in `.env` (gitignored); `.env.example` is the committed template.
6. Explanations cite computed comparison numbers; the reasoning agent may not invent arithmetic.
7. HTTP politeness: per-host delays, backoff, retry only on transient errors.
