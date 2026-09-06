# Spec: Agentic AI Travel Decision Agent (India)

**Status:** Draft for review — no code written yet
**Source documents:** `agentic_ai_travel_project_guide.md` (project guide) + requirements interview (5 rounds)
**Date:** 2026-09-06

---

## 1. Summary

Build a terminal-based agentic AI travel decision agent for India. The user describes a trip in natural language; the agent converses to complete missing details, researches **real, current** travel options across 6 modes (train, bus, flight, own car, cab, rental/self-drive), normalizes them into a common model, filters them against hard constraints, scores them with a deterministic multi-criteria engine, performs a "worth-it" value analysis, and explains a ranked recommendation in the terminal.

**Core philosophy (from the guide):** LLM for understanding and reasoning. Python for tools, data, validation, calculations, and decisions. Real data for recommendations. Transparency when data is uncertain. Best value for the user — not merely cheapest or fastest.

---

## 2. Interview Decisions (binding)

| # | Decision | Choice |
|---|----------|--------|
| D1 | Project state | Blank slate — starting fresh |
| D2 | Spec goal | Full implementation plan (all phases) |
| D3 | Data sources | **Real sources from day one** (no mocked-data MVP) |
| D4 | Travel modes | All six: Train, Bus, Flight, Own Car, Cab, Rental/Self-Drive |
| D5 | Data acquisition | **Scraping-first with adapter pattern**; APIs as fallback; estimates only as last resort, always labeled |
| D6 | LLM usage | **Full agentic LLM use** — LLM drives extraction, missing-info detection, planning, reasoning, explanations; Python owns all calculations/filters/rankings |
| D7 | Conversation model | **Multi-turn conversational CLI** with session memory and focused follow-up questions |
| D8 | LLM provider | OpenRouter with **free/cheap models prioritized** (accept lower reasoning quality) |
| D9 | Unsatisfiable constraints | **Ask the user which constraint to relax** (do not silently show best-effort) |
| D10 | Trip scope | One-way trips only in v1, **extensible** data model (round-trip/multi-city later) |
| D11 | Source families to research | IRCTC/NTES-style trains; RedBus/abhibus buses; flight OTAs/APIs; Maps/tolls/fuel for road |
| D12 | Reliability modeling | **Skip in v1** (static punctuality scores deferred) |
| D13 | Timeline | **Fast: days** for the first delivery tier |
| D14 | Testing | Unit tests for engines + **recorded HTML/JSON fixtures** for collectors; no live E2E in CI |
| D15 | Scope vs pace tension | **Tiered delivery**: days-push delivers Train + Bus + Flight + Own Car end-to-end; Cab + Rental immediately after |
| D16 | Own car handling | **Always compute** the own-car option (fuel + tolls); user ignores it if irrelevant |
| D17 | Cab / rental data | **Formula-based estimates only** (road distance × typical per-km rates), always labeled `estimated`; no scraping attempt in v1 |
| D18 | Python tooling | **pip + venv + requirements.txt** (no uv/Poetry) |

---

## 3. Scope

### 3.1 In scope (v1)

- Multi-turn conversational CLI (Rich-based) with session memory
- Natural-language requirement extraction → validated Pydantic models
- Missing-information detection and follow-up questioning
- Research planning by the LLM (which modes/sources to investigate)
- Real data collection for **Train, Bus, Flight, Own Car** via scraping-first adapters
- Formula-based **estimated** data for Cab and Rental (tier 2 delivery, immediately after tier 1)
- Data normalization into a common `TravelOption` model with provenance metadata
- Constraint filtering (hard constraints rejected/penalized before scoring)
- Deterministic scoring engine with dynamic weights driven by user priorities
- Worth-it analysis (extra ₹ per hour saved, comfort tradeoffs, group economics)
- Ranked terminal output with data-confidence indicators (🟢🟡🟠🔴)
- LLM-generated explanations grounded strictly in structured comparison data
- Unit tests + recorded fixtures; graceful degradation when sources fail

### 3.2 Out of scope (v1)

- Booking or payment of any kind
- Round trips and multi-city/multi-leg journeys (data model must not preclude them — see §6.1)
- Live reliability/punctuality modeling (D12) — static `reliability_score` defaults only
- Web or GUI interface
- Price prediction or fare-drop alerts
- Non-India geographies
- Cab/rental live scraping (D17)
- Saving session history across program restarts (memory is per-session)

### 3.3 Explicitly resolved tensions

- **6 modes vs days-long timeline (D15):** tiered delivery. Tier 1 = full pipeline with Train + Bus + Flight + Own Car. Tier 2 (immediately after) = Cab + Rental as estimate-based modes wired into the same pipeline.
- **Real data vs fast timeline (D3 + D13):** no mocked-data phase; each mode ships when its collector + fixture tests pass. If a source is inaccessible at build time, the mode ships with `unavailable` status and a clear message rather than fake data.
- **Free models vs agentic complexity (D6 + D8):** agent design must tolerate weaker models — strict JSON-schema prompting, Pydantic validation with one retry, and deterministic fallbacks for every LLM step (see §10.3).

---

## 4. High-Level Workflow

```text
User Input (natural language, terminal)
    ↓
Requirement Agent (LLM)  →  TravelRequest (Pydantic-validated)
    ↓
Missing critical info?  →  Yes → ask focused follow-up → merge into memory → loop
    ↓ No
Planning Agent (LLM)  →  ResearchPlan (modes × sources × priority)
    ↓
Collector dispatch (Python) — parallel, per-mode adapters
    ├── train_collector    (scrape → parse → TravelOption list)
    ├── bus_collector      (scrape → parse → TravelOption list)
    ├── flight_collector   (scrape/API → parse → TravelOption list)
    ├── road_collector     (maps + tolls + fuel → own-car TravelOption)
    ├── cab_estimator      (formula → estimated TravelOption)   [tier 2]
    └── rental_estimator   (formula → estimated TravelOption)   [tier 2]
    ↓
Normalizer (Python) — enforce common TravelOption shape, attach provenance
    ↓
Constraint Engine (Python) — reject/penalize hard-constraint violations
    ↓
  If ZERO options survive → Conflict Resolution loop (see §12)
    ↓
Scoring Engine (Python) — dynamic weights from user priorities → ranked list
    ↓
Worth-It Engine (Python) — pairwise value comparisons (₹/hour saved, ₹/comfort point)
    ↓
Reasoning Agent (LLM) — explanation strictly from structured data
    ↓
Terminal Recommendation (Rich-formatted, confidence-labeled)
```

---

## 5. Architecture

```
project/
├── main.py                      # CLI entry point, session loop
├── config/
│   ├── settings.py              # env loading, model names, weights defaults, timeouts
│   └── prompts/                 # versioned LLM prompt templates (extraction, planning, reasoning)
├── agents/
│   ├── requirement_agent.py     # extraction + missing-info detection + follow-up questions
│   ├── planning_agent.py        # decides which modes/sources to research
│   ├── reasoning_agent.py       # final explanation generation
│   └── orchestrator.py          # wires agents → collectors → engines in order
├── llm/
│   ├── client.py                # OpenRouter client wrapper (retries, timeouts, cost logging)
│   └── schemas.py               # JSON schemas for structured outputs
├── collectors/
│   ├── base.py                  # BaseCollector ABC: collect() -> list[TravelOption], health checks
│   ├── train_collector.py
│   ├── bus_collector.py
│   ├── flight_collector.py
│   ├── road_collector.py        # own car: distance + tolls + fuel → cost & duration
│   ├── cab_estimator.py         # tier 2
│   └── rental_estimator.py      # tier 2
├── data_sources/
│   ├── adapters/                # one adapter per external site/API (swap-friendly, per D5)
│   │   ├── train_source.py      # e.g. IRCTC/NTES-style adapter
│   │   ├── bus_source.py        # e.g. RedBus/abhibus adapter
│   │   ├── flight_source.py     # OTA/API adapter
│   │   ├── maps_source.py       # road distance/duration
│   │   ├── toll_source.py
│   │   └── fuel_source.py
│   └── fixtures/                # recorded HTML/JSON per source for offline tests (D14)
├── models/
│   ├── travel_request.py        # §6.1
│   ├── travel_option.py         # §6.2
│   ├── research_plan.py
│   └── provenance.py            # value/source/timestamp/data_type/confidence (§6.3)
├── services/
│   ├── normalizer.py
│   ├── constraint_engine.py
│   ├── scoring_engine.py
│   ├── worth_it_engine.py
│   ├── comfort_model.py         # transparent rule-based comfort scoring (guide §18)
│   └── door_to_door.py          # overhead model per mode (guide §17)
├── memory/
│   └── session_memory.py        # in-process conversation state (guide §19)
├── ui/
│   ├── cli.py                   # Rich console, input loop
│   └── renderers.py             # recommendation tables, confidence dots, rankings
├── utils/
│   ├── time_utils.py            # dateparser for "tomorrow", "next Friday", deadlines
│   ├── cost_utils.py            # currency formatting, per-person math
│   └── geo.py                   # city name → station/airport/bus-terminal resolution
├── tests/
│   ├── unit/                    # engines, models, normalizer, comfort, scoring (pure Python)
│   ├── fixture_tests/           # collectors against recorded fixtures (D14)
│   └── data/                    # fixture files
├── requirements.txt
├── .env.example                 # OPENROUTER_API_KEY=...
├── .gitignore                   # .env, __pycache__/, *.pyc, .venv/, venv/
└── README.md
```

### 5.1 Stack (D18 + guide §23)

| Concern | Choice |
|---|---|
| Python | 3.11+ |
| LLM gateway | OpenRouter, free/cheap models first (D8); exact model slugs pinned in `config/settings.py` and swappable |
| Data models | Pydantic v2 (validate all LLM JSON) |
| HTTP | `httpx` (async, for parallel collection) |
| Scraping | `beautifulsoup4` + `lxml` first; `playwright` only for JS-heavy sources that prove necessary; no Selenium |
| Terminal UI | `rich` (no Textual in v1) |
| Dates | `dateparser` + stdlib `datetime` |
| Config | `.env` via `python-dotenv`; keys never committed (guide §27) |
| Tests | `pytest` (+ `pytest-asyncio`); fixtures only, no network in tests |

---

## 6. Data Models

### 6.1 `TravelRequest` (one-way, extensible per D10)

```python
class TravelRequest(BaseModel):
    # Route
    source: LocationRef | None          # resolved city + station/airport hints
    destination: LocationRef | None

    # Time
    travel_date: date | None
    preferred_departure_after: time | None
    arrival_deadline: time | None
    max_duration_hours: float | None
    date_flexible_days: int = 0

    # Travellers
    passengers: int | None              # total
    adults: int | None
    children: int = 0                   # affects comfort model, not seat math in v1
    elderly_travellers: int = 0

    # Budget
    budget: float | None
    budget_type: Literal["total", "per_person"] = "total"
    budget_flexibility: Literal["strict", "flexible"] = "flexible"

    # Comfort & preferences
    comfort_priority: Literal["low", "medium", "high"] = "medium"
    ac_required: bool | None            # None = no preference
    sleeper_preferred: bool | None
    overnight_allowed: bool | None      # None = no preference
    luggage_level: Literal["light", "normal", "heavy"] = "normal"
    urgency: Literal["low", "medium", "high"] = "low"
    preferred_modes: list[Mode] = []
    avoided_modes: list[Mode] = []

    # Extension points (D10: one-way only in v1, but model must not preclude later)
    trip_type: Literal["one_way"] = "one_way"     # later: "round_trip", "multi_city"
    return_date: date | None = None               # rejected by CLI in v1 if set
    legs: list["TravelRequest"] | None = None     # reserved for multi-city

    # Session bookkeeping
    open_questions: list[str] = []      # what the agent still needs
    raw_user_text: list[str] = []       # all user turns this session
```

**Extension rule:** adding round trips later must not require changing `TravelOption` (§6.2) — only `TravelRequest` gains fields and the orchestrator runs per-leg.

### 6.2 `TravelOption`

```python
class TravelOption(BaseModel):
    mode: Literal["train", "bus", "flight", "own_car", "cab", "rental"]
    name: str                           # "Shatabdi Express", "VRL Volvo Sleeper", ...
    operator: str | None

    departure_location: str
    arrival_location: str
    departure_time: datetime | None
    arrival_time: datetime | None
    travel_duration_minutes: int | None
    overnight: bool

    total_cost: float | None            # for the whole party
    cost_per_person: float | None
    ac: bool | None
    comfort_level: int | None           # 1–10, from comfort_model.py (transparent rules)
    comfort_notes: list[str] = []       # explainability: "AC sleeper", "2 stops"

    door_to_door_duration_minutes: int | None   # computed by door_to_door.py
    door_to_door_breakdown: dict[str, int] = {} # {"station_travel": 45, "buffer": 30, ...}

    availability_status: str | None     # "available", "waitlist 23", "sold out", None if unknown
    stops: int | None
    baggage_note: str | None

    # Provenance — every value-carrying option must have this (guide §21)
    source: str                         # adapter id, e.g. "irctc", "redbus"
    data_type: Literal["live", "recent", "estimated", "unavailable"]
    retrieved_at: datetime
    confidence: Literal["high", "medium", "low"]

    reliability_score: int = 7          # static per-mode default in v1 (D12)
```

### 6.3 `Provenance` (metadata attached to individual collected values)

```python
class Provenance(BaseModel):
    value: Any
    source: str
    retrieved_at: datetime
    data_type: Literal["live", "recent", "estimated", "unavailable"]
    confidence: Literal["high", "medium", "low"]
```

Rule (guide §10, §21): **never present estimates as live data**. The CLI renders: 🟢 live · 🟡 recent · 🟠 estimated · 🔴 unavailable. The LLM is never allowed to fill in prices, times, or availability — those fields exist only because a collector produced them.

---

## 7. Data Source Strategy (scraping-first, D5)

### 7.1 Research gate (before each adapter is built)

For **every** candidate source, document in `data_sources/adapters/<source>.md`:

1. Accessibility (public page? login wall? mobile site? JSON embedded in HTML?)
2. Reliability observed over ≥ 3 manual probes at different times
3. Rate-limit posture (what happens on rapid requests)
4. ToS / robots.txt stance — record it; prefer sources whose terms permit reading public schedule/price data
5. Anti-bot systems (CAPTCHA, JS challenge, fingerprinting)
6. Whether an official/partner API exists as fallback

A source failing the gate is swapped for another — no adapter is built on a source that was never probed (guide §11 rule).

### 7.2 Per-mode source plan (D11)

| Mode | Primary approach | Fallback | Notes |
|---|---|---|---|
| **Train** | IRCTC/NTES-style public schedule & availability pages (scrape) | Public rail info aggregators (RailYatri/ConfirmTkt-class) | Availability/waitlist may be behind anti-bot; if unattainable, ship schedules/prices with `availability_status: null` |
| **Bus** | RedBus / abhibus search results (scrape — operator, type, AC/sleeper, price, times) | Operator sites (state RTC sites often have simpler pages) | Pickup/drop points enrich door-to-door model |
| **Flight** | OTA/APIs — research Amadeus/Kiwi/Skyscanner-class options at build time | Scraping OTA search pages (heavier anti-bot; Playwright likely) | Prefer any usable free-tier API over scraping flights; flights are the most anti-bot-hostile vertical |
| **Own car** | Maps API/distance source for route km + duration; toll calculator source for tolls; fuel-price source for ₹/L | OSRM/OpenStreetMap routing if maps API unaffordable; static toll tables | Always computed (D16); deterministic Python math from three sub-sources |
| **Cab** (tier 2) | No scraping (D17). Formula: one-way road distance × per-km outstation rate bands (hatchback/sedan/SUV) + driver allowance + tolls | — | Always `data_type: "estimated"`, 🟠 |
| **Rental** (tier 2) | No scraping (D17). Formula: daily rental rate × days + fuel + tolls | — | Always `data_type: "estimated"`, 🟠 |

### 7.3 Adapter contract

```python
class SourceAdapter(ABC):
    id: str
    def health_check(self) -> HealthReport: ...        # called before collection
    def collect(self, req: TravelRequest) -> list[RawOption]: ...
```

- Collectors call adapters; adapters return raw, source-shaped data; collectors convert to `TravelOption` via the normalizer.
- Adapter failures are contained: one dead source never aborts the run. The output labels that mode 🔴 `unavailable` and the reasoning agent says so honestly.
- Every adapter has a recorded fixture (D14) captured at build time; tests replay fixtures, never the live web.

---

## 8. Door-to-Door Model (guide §17)

Deterministic Python module; per-mode overhead assumptions stored in `config/settings.py` (tunable, documented):

- **Flight:** airport travel + ~90 min reporting + flight + layovers + ~30 min exit + destination travel
- **Train:** station travel + ~30 min buffer + journey + ~15 min exit + destination travel
- **Bus:** pickup-point travel + ~15 min wait + journey + destination travel
- **Car/cab/rental:** driving duration + break allowance (~15 min per 2 h) + traffic buffer (~15%)

Origin/destination legs use maps distance sources; when a leg can't be measured, use a fixed city-size-based assumption and record it in `door_to_door_breakdown`.

---

## 9. Comfort Model (guide §18, transparent rules)

Rule-based (no LLM), explainable via `comfort_notes`:

- Base by class/type (e.g. 2S < sleeper < 3AC < 2AC < 1AC; seater < sleeper for overnight bus)
- Modifiers: AC ±, journey duration penalty beyond thresholds, transfers penalty, personal space, luggage fit
- Elderly/children present → penalize high-transfer and tight-connection options
- Output scale 1–10 banded: 1–3 low, 4–6 moderate, 7–8 high, 9–10 premium

---

## 10. LLM Integration (OpenRouter, D6 + D8)

### 10.1 Responsibilities split (guide §24–25)

| LLM does | Python does |
|---|---|
| Parse natural language → structured JSON | Validate JSON with Pydantic |
| Detect missing/critical info | Decide what "critical" means programmatically |
| Draft follow-up questions | Enforce never-re-ask (memory) |
| Produce research plan (modes × sources) | Dispatch collectors, timeouts, retries |
| Write final explanations | All arithmetic, filtering, scoring, ranking, worth-it math |

### 10.2 Structured output discipline

- Every LLM call uses a JSON schema (`llm/schemas.py`) + explicit "output only JSON" instruction
- Pydantic validation; on failure → **one** repair retry with the validation error appended → on second failure, deterministic fallback (§10.3)
- Prompt templates are versioned files in `config/prompts/`, not inline strings
- All calls log model, latency, and token usage to the terminal debug view

### 10.3 Degradation strategy for free/cheap models (D8)

- Extraction fallback: regex/dateparser-based slot filling for common patterns ("2 people", "tomorrow", "before 6 PM", ₹ amounts) merged with whatever LLM JSON validated
- Planning fallback: default research plan = all modes not explicitly avoided (Python-built)
- Reasoning fallback: template-based explanation assembled from the structured comparison (still honest, less fluent)
- The CLI reports which fallbacks fired (affects user trust in output quality)

---

## 11. Constraint & Scoring Engines

### 11.1 Constraint filtering (guide §13, run before scoring)

Hard constraints (default reject): over-budget when `budget_flexibility: strict`; misses `arrival_deadline`; `ac_required: true` and option non-AC; `overnight_allowed: false` and option overnight; mode in `avoided_modes`; `max_duration_hours` exceeded.

Soft constraints (penalize, don't reject): over-budget when flexible; `ac_required: false-but-preferred`; `sleeper_preferred` unmet; mode not in `preferred_modes`.

### 11.2 Scoring (guide §14–15, deterministic)

```text
Overall = w_cost·Cost + w_time·Time + w_comfort·Comfort
        + w_conv·Convenience + w_pref·PreferenceMatch + w_schedule·ScheduleFit
```

- All sub-scores normalized 0–100 across the surviving option set
- Dynamic weights chosen by a deterministic rule table keyed on `comfort_priority`, `urgency`, `budget_flexibility`, `arrival_deadline` presence (guide §15 profiles as starting point); LLM may *suggest* a profile, Python decides weights
- Every sub-score and weight is displayed in the final output (explainability requirement)

### 11.3 Worth-It Engine (guide §16)

Pairwise, from structured data only:

- ₹ per hour saved (door-to-door) between adjacent ranked options
- ₹ per comfort point gained
- Deadline context: time savings matter more when a deadline exists or urgency is high
- Group economics: own car cost is near-flat with passengers → per-person advantage at 4–6 travellers
- Budget context: savings expressed relative to the user's stated budget

The reasoning agent receives these computed comparisons and must not invent numbers.

---

## 12. Conflict Resolution (D9)

When **zero** options survive constraint filtering:

1. Report exactly which constraints conflict with reality (e.g. "no AC train arrives before 6 PM on this route")
2. Ask the user which constraint to relax via focused follow-up (deadline? budget? AC? mode?)
3. Apply the relaxation and re-run the pipeline
4. Loop max 3 times; then present the least-violating options clearly labeled as violating X, plus the honest option of changing date

This loop is Python-controlled; the LLM drafts the question text.

---

## 13. Conversation Memory (guide §19, D7)

- `session_memory.py` holds the accumulating `TravelRequest`, all user turns, and asked questions
- Follow-ups ask only for **critical** missing fields: source, destination, date, passenger count, plus any hard constraint the user implies (budget/deadline/AC)
- Never re-ask an answered field; "tomorrow" resolves against the current date at parse time
- Multi-turn merges are additive: latest statement wins on conflicts, with a spoken confirmation when it overrides an earlier value
- Memory lives for the terminal session only; `new` resets it

---

## 14. Terminal Output (guide §20–21)

1. **Data confidence banner** — per-mode 🟢🟡🟠🔴 status of what was found live vs estimated vs unavailable
2. **🥇 Best overall** — cost, per-person cost, duration, door-to-door, comfort, deadline check, and a "why" bullet list (LLM-written from structured data)
3. **🥈🥉 ranked alternatives** — score /100, pros, cons, worth-it comparison lines ("₹5,500 more for 3.5 h saved door-to-door — not worth it at this budget")
4. **Assumptions & estimates box** — every 🟠 value called out explicitly
5. Rich tables; scores and weights visible on request (`explain` command)

---

## 15. Delivery Plan (D13 + D15)

### Tier 1 — days-scale push (working end-to-end system)

1. **Day 0.5:** project scaffold, venv + requirements, OpenRouter client, TravelRequest model, extraction loop with follow-ups (testable with free model)
2. **Day 1:** source research & probes for all tier-1 modes; adapter gate documents written; fixtures captured; road math (maps+tolls+fuel) since it feeds own car immediately
3. **Day 2:** train + bus collectors → normalizer → constraint engine → scoring → ranked Rich output (even if flight/road pending)
4. **Day 3:** flight + own-car collectors; door-to-door model; worth-it engine; reasoning agent; confidence rendering
5. **Day 3.5:** conflict-resolution loop; unit + fixture test suite green; end-to-end manual run on the guide's §30 success-criteria prompt

Exit criteria: the §30-style success prompt runs end-to-end with real train/bus/flight/own-car data, correct constraint handling, and honest labeling.

### Tier 2 — immediately after tier 1

- Cab + rental estimators (D17) wired into the same pipeline
- Prompt/weight tuning from real usage
- Second source adapter per mode (redundancy)

### Deferred (backlog)

- Live reliability/punctuality (D12), round trips (D10), date-flexibility re-search, cab/rental scraping, Textual UI, session persistence

---

## 16. Testing Strategy (D14)

- **Unit (pure Python):** normalizer, constraint engine, scoring engine, worth-it engine, comfort model, door-to-door, time/cost utils, memory merge logic — including the §28 persona scenarios (budget, comfort/family+elderly, urgent, group 5–6, long distance, short distance) as golden-output tests
- **Fixture tests:** each collector replayed against recorded HTML/JSON in `tests/data/`; assertions on parsed option counts and key fields; no network in tests
- **LLM output tests:** recorded free-model responses as fixtures through the validation+retry path; degradation fallbacks tested by feeding malformed JSON
- **Manual E2E:** run the success-criteria prompt before each tier exit; document result in README
- Live source health is checked manually at build time (adapter gate), never in CI

---

## 17. Safety & Reliability Rules (guide §26, all mandatory)

1. Never invent prices, schedules, or availability — LLM outputs are excluded from all data fields by construction
2. Every option carries source, `retrieved_at`, `data_type`, `confidence`
3. Estimates are always 🟠-labeled and never rendered as live
4. LLM JSON is schema-validated with bounded retries; deterministic fallbacks exist for every LLM step
5. Unavailable data is reported as unavailable — the system degrades honestly rather than fabricating
6. API keys only in `.env`; `.env` gitignored; `.env.example` committed
7. Explanations cite computed comparison numbers, never LLM arithmetic
8. Adapter probing respects robots.txt/ToS findings; rate-limits honored with delays/backoff

---

## 18. Success Criteria (guide §30, adapted to D15)

Tier 1 succeeds if a user types the guide's success prompt (3 people, Chennai→Bangalore tomorrow, ₹6,000, AC+comfort, arrive before 7 PM, willing to pay a bit extra if worth it) and the system:

1. Extracts the request correctly and asks at most the truly necessary follow-ups
2. Gathers real train, bus, flight, and own-car options (or honestly reports a source unavailable)
3. Filters against constraints and, if nothing qualifies, runs the §12 relax loop
4. Ranks with visible, explainable scores and worth-it comparisons
5. Explains the recommendation from actual data with correct confidence labels
6. Completes the whole flow in the terminal within a reasonable interactive latency (parallel collection; per-collector timeouts so one slow site can't stall the run)

---

## 19. Open Questions / Risks

| # | Risk / open question | Mitigation |
|---|---|---|
| R1 | Flight scraping is heavily anti-bot; free flight APIs may lack India coverage or free tiers | Research gate at Day 1 decides API vs Playwright scrape; worst case flights ship 🔴 unavailable while other modes work |
| R2 | IRCTC availability data may be unattainable without login | Ship schedules/fares live, availability `null`; aggregators as fallback source |
| R3 | Free OpenRouter models may be rate-limited or flaky for agentic loops | Deterministic fallbacks (§10.3); model slug configurable; usage logging exposes problems early |
| R4 | Exact per-km cab rates and rental rates need one-time research to keep estimates honest | Values stored in settings with a "last verified" date and source note |
| R5 | Maps/toll/fuel sources each need their own access decision (API keys, quotas) | Research gate per source; OSRM + static toll tables as no-key fallbacks |
| R6 | "Days" timeline is aggressive even tiered | Exit criteria are per-tier; slipping affects tier 2 only, never ships fake data to save time |
