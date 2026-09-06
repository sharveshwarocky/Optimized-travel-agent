# Agentic AI Travel Decision Agent — Project Guide

## 1. Project Overview

Build a terminal-based **Agentic AI Travel Decision Agent for India** using:

- Python
- OpenRouter API
- LLM-based natural language understanding and reasoning
- Web scraping as the preferred data acquisition method
- APIs as fallback or supplementary sources
- Real-time travel information wherever feasible

The system receives a user's travel request in natural language and recommends the **best travel option based on overall value**, not simply the cheapest option.

---

# 2. Core Problem Statement

Users often need to choose between:

- 🚆 Train
- 🚌 Bus
- ✈️ Flight
- 🚗 Own Car
- 🚕 Cab
- 🚙 Rental / Self-Drive Car

Choosing the best option depends on multiple factors such as:

- Cost
- Travel duration
- Comfort
- AC preference
- Arrival deadline
- Number of travellers
- Door-to-door convenience
- Overnight travel
- Luggage
- Elderly or children travelling
- Reliability
- Value for money

The system must analyze these factors and provide a personalized recommendation.

---

# 3. Primary Goal

Create an agentic AI system that can:

1. Understand natural language travel requests.
2. Extract structured travel requirements.
3. Identify missing information.
4. Ask follow-up questions.
5. Plan which travel modes and data sources to investigate.
6. Gather real-time travel data.
7. Prefer web scraping where practical.
8. Use APIs where scraping is unavailable or unreliable.
9. Normalize data from multiple sources.
10. Filter options that violate user constraints.
11. Compare options using multiple criteria.
12. Determine what is actually worth choosing.
13. Rank alternatives.
14. Explain the recommendation clearly in the terminal.

---

# 4. Scope

## Geographic Scope

India only.

## Interface

Terminal / Command Line Interface (CLI).

## Data Type

Real-time or currently available travel data wherever possible.

If real-time data cannot be retrieved:

- Use a reliable API if available.
- Use a clearly labeled estimate only as a final fallback.
- Never present estimated data as live data.

---

# 5. Example User Input

```text
We are 2 people travelling from Chennai to Bangalore tomorrow.
Our total budget is around ₹5000. We prefer AC and comfort.
We need to reach before 6 PM and don't want an exhausting journey.
```

The system should understand this without requiring the user to fill out a form.

---

# 6. Information to Extract

The AI should attempt to extract the following attributes from natural language.

## Location

- Source
- Destination

## Time

- Travel date
- Preferred departure time
- Latest arrival time
- Maximum travel duration
- Date flexibility

## Travellers

- Number of travellers
- Adults
- Children
- Elderly travellers

## Budget

- Total budget
- Per-person budget
- Budget flexibility

## Comfort

- Comfort priority
- AC preference
- Sleeper preference
- Seater preference
- Avoid overnight travel
- Maximum acceptable journey duration

## Transport Preferences

- Preferred transport modes
- Avoided transport modes
- Openness to alternatives

## Other Factors

- Luggage
- Urgency
- Door-to-door convenience
- Reliability preference
- Cost vs time preference

---

# 7. Example Structured Requirement Object

```python
travel_request = {
    "source": "Chennai",
    "destination": "Bangalore",
    "travel_date": "2026-09-07",
    "passengers": 2,
    "budget": 5000,
    "budget_type": "total",
    "ac_preferred": True,
    "comfort_priority": "high",
    "arrival_deadline": "18:00",
    "overnight_allowed": False,
    "max_duration_hours": None,
    "preferred_modes": [],
    "avoided_modes": [],
    "elderly_travellers": 0,
    "children": 0,
    "luggage_level": "normal"
}
```

The schema may be expanded as the project develops.

---

# 8. Agentic Workflow

The system should follow this high-level workflow.

```text
User Input
    ↓
Requirement Agent
    ↓
Extract Requirements
    ↓
Are Important Details Missing?
    ↓
Yes → Ask Follow-Up Questions
No
    ↓
Planning Agent
    ↓
Choose Research Tasks and Data Sources
    ↓
Collect Travel Options
    ├── Train
    ├── Bus
    ├── Flight
    └── Road / Car
    ↓
Normalize Data
    ↓
Validate and Filter Constraints
    ↓
Decision Engine
    ↓
Score and Rank Options
    ↓
Worth-It Analysis
    ↓
Reasoning Agent
    ↓
Terminal Recommendation
```

---

# 9. Agent Responsibilities

## 9.1 Requirement Agent

Responsibilities:

- Understand natural language.
- Extract travel attributes.
- Detect missing critical information.
- Maintain conversation context.
- Ask focused follow-up questions.

Example:

```text
User:
I want to travel from Chennai to Bangalore.

Agent:
What date are you planning to travel?
```

After multiple turns, the system should combine information into one complete request.

---

## 9.2 Planning Agent

Responsibilities:

- Determine which travel modes should be researched.
- Determine which tools or data sources to use.
- Avoid unnecessary searches.
- Create a research plan.

Example:

```text
Research Plan:
1. Search trains between Chennai and Bangalore.
2. Search AC buses.
3. Search flights.
4. Calculate own-car travel cost.
5. Compare door-to-door travel time.
```

---

## 9.3 Research Agents / Tools

The system should collect information for:

### Train

Potential data:

- Train name
- Train number
- Departure
- Arrival
- Duration
- Ticket classes
- Price
- AC availability
- Sleeper/seating
- Availability
- Waiting list status if possible

### Bus

Potential data:

- Operator
- Bus type
- AC/non-AC
- Sleeper/seater
- Price
- Departure
- Arrival
- Duration
- Pickup point
- Drop point

### Flight

Potential data:

- Airline
- Flight price
- Departure
- Arrival
- Flight duration
- Stops / layovers
- Baggage information if available

### Own Car

Potential data:

- Road distance
- Estimated driving duration
- Fuel requirement
- Fuel cost
- Tolls
- Parking if relevant

### Cab

Potential data:

- Estimated fare
- Duration
- Vehicle type
- Convenience

### Rental / Self-Drive

Potential data:

- Rental cost
- Fuel cost
- Toll cost
- Travel duration
- Additional conditions if relevant

---

# 10. Data Collection Strategy

The preferred order is:

```text
1. Web Scraping
        ↓
2. Reliable API
        ↓
3. Reliable Estimate
```

Every collected value should ideally include metadata.

Example:

```python
{
    "value": 1250,
    "source": "source_name",
    "retrieved_at": "timestamp",
    "data_type": "live",
    "confidence": "high"
}
```

Possible data types:

- `live`
- `recent`
- `estimated`
- `unavailable`

The system must clearly communicate uncertainty.

---

# 11. Important Data Source Research

Before implementing scraping, research:

- Official or publicly accessible railway data sources.
- Bus operator or aggregator data sources.
- Flight search sources or APIs.
- Road distance and route sources.
- Toll calculation sources.
- Fuel price sources.

## Important Rule

Do not build the entire project around a source without checking:

- Accessibility
- Reliability
- Rate limits
- Terms of service
- Robots restrictions
- CAPTCHA or anti-bot systems
- Availability of APIs

Use adapters so data sources can be replaced later.

---

# 12. Data Normalization

All travel options should eventually use a common format.

Example:

```python
travel_option = {
    "mode": "train",
    "name": "Example Express",
    "operator": "Example Operator",

    "departure_location": "Chennai",
    "arrival_location": "Bangalore",

    "departure_time": "08:00",
    "arrival_time": "14:30",

    "travel_duration_minutes": 390,

    "total_cost": 2400,
    "cost_per_person": 1200,

    "ac": True,
    "comfort_level": 8,

    "overnight": False,

    "door_to_door_duration_minutes": 450,

    "reliability_score": 8,

    "source": "example_source",
    "data_type": "live",
    "confidence": "high"
}
```

This structure allows all transport modes to be compared fairly.

---

# 13. Constraint Filtering

Before scoring, eliminate or penalize options that violate critical constraints.

Examples:

## Budget Constraint

```text
Option Cost > Available Budget
```

Possible result:

- Reject option.
- Or retain it as an over-budget alternative with a penalty.

## Arrival Deadline

```text
Arrival Time > Required Arrival Time
```

Result:

- Reject unless user allows flexibility.

## AC Requirement

If AC is mandatory:

```text
Non-AC options receive major penalty or are removed.
```

## Overnight Restriction

If the user does not want overnight travel:

```text
Overnight options are removed or heavily penalized.
```

Critical constraints should generally be handled before preference scoring.

---

# 14. Decision Engine

The decision engine is the core of the project.

It must evaluate:

- Cost
- Travel time
- Comfort
- Convenience
- Schedule compatibility
- Arrival deadline
- Reliability
- User preferences
- Value for money

A basic scoring model may be:

```text
Overall Score =
    Cost Score × Cost Weight
  + Time Score × Time Weight
  + Comfort Score × Comfort Weight
  + Convenience Score × Convenience Weight
  + Reliability Score × Reliability Weight
  + Preference Match Score × Preference Weight
```

The weights must change depending on the user's priorities.

---

# 15. Dynamic Weighting

## Budget-Focused User

Example:

```text
Cost:        40%
Time:        20%
Comfort:     15%
Convenience: 15%
Reliability: 10%
```

## Comfort-Focused User

Example:

```text
Cost:        15%
Time:        20%
Comfort:     35%
Convenience: 20%
Reliability: 10%
```

## Urgent User

Example:

```text
Cost:         5%
Time:        40%
Comfort:     10%
Convenience: 15%
Reliability: 20%
Schedule:    10%
```

The LLM can help interpret user intent, but the final numeric ranking should preferably be performed by deterministic Python logic.

---

# 16. Worth-It Analysis

This is one of the main differentiators of the project.

The system should not simply identify:

```text
Cheapest Option
Fastest Option
```

It should answer:

```text
Is paying more actually worth the benefit for this user?
```

Example:

```text
Train:
₹2,500
6 hours

Flight:
₹8,000
2 hours
```

The system should consider:

- Additional money spent
- Time saved
- User budget
- Number of travellers
- Deadline
- Comfort difference
- Door-to-door travel time

Example reasoning:

```text
The flight saves approximately 3.5 hours door-to-door but costs
₹5,500 more. Since the user has no urgent arrival requirement and
has a limited budget, the additional cost does not provide enough
value.
```

This analysis should be generated from actual structured comparison data.

---

# 17. Door-to-Door Travel Time

Do not compare only the listed journey duration.

## Flight

Potential total duration:

```text
Travel to airport
+ airport reporting time
+ flight duration
+ layover time
+ baggage/exit time
+ airport to destination
```

## Train

Potential total duration:

```text
Travel to station
+ waiting buffer
+ train duration
+ exit time
+ destination travel
```

## Bus

Potential total duration:

```text
Travel to pickup point
+ waiting time
+ bus journey
+ destination travel
```

## Car

Potential total duration:

```text
Driving duration
+ expected breaks
+ traffic buffer
```

This helps make comparisons realistic.

---

# 18. Comfort Model

Comfort should be based on transport-specific attributes.

Potential factors:

- AC availability
- Sleeper availability
- Seating quality
- Personal space
- Journey duration
- Overnight travel
- Number of transfers
- Elderly travellers
- Children travelling

Example comfort scale:

```text
1–3  → Low Comfort
4–6  → Moderate Comfort
7–8  → High Comfort
9–10 → Premium Comfort
```

The comfort score should be explainable and preferably calculated using transparent rules.

---

# 19. Conversation Memory

The agent should maintain state during the terminal session.

Example:

```text
User:
I need to travel from Chennai to Bangalore.

Agent:
When are you travelling?

User:
Tomorrow.

Agent:
How many people?

User:
Three, and we prefer AC.
```

The final state should become:

```python
{
    "source": "Chennai",
    "destination": "Bangalore",
    "date": "tomorrow",
    "passengers": 3,
    "ac_preferred": True
}
```

Avoid asking for information that has already been provided.

---

# 20. Recommendation Output

The terminal output should contain:

## Best Overall Recommendation

```text
🥇 BEST OVERALL: AC TRAIN

Total Cost: ₹2,400
Cost Per Person: ₹1,200
Travel Duration: 5h 30m
Door-to-Door Time: Approximately 6h 15m
Comfort: 8/10
AC: Yes
Arrival Deadline: Meets Requirement

Why It Is Recommended:
- Fits comfortably within the budget.
- Meets the arrival deadline.
- Provides high comfort.
- Better value than a flight.
- Less exhausting than road travel.
```

## Ranked Alternatives

```text
🥈 FLIGHT
Score: 82/100

Pros:
- Fastest option.

Cons:
- Significantly more expensive.
- Airport overhead reduces actual time savings.


🥉 AC BUS
Score: 74/100

Pros:
- Affordable.
- AC available.

Cons:
- Longer journey.
- Lower comfort than train.
```

---

# 21. Data Confidence Layer

Every recommendation should indicate data reliability.

Example:

```text
🟢 Live / verified data
🟡 Recently fetched data
🟠 Estimated data
🔴 Data unavailable or unreliable
```

Example:

```text
Train Price: ₹1,200 🟢
Flight Price: ₹4,800 🟢
Cab Estimate: ₹6,500 🟠
```

Never allow the LLM to invent travel prices or schedules.

---

# 22. Recommended Architecture

```text
project/
│
├── main.py
│
├── config/
│   └── settings.py
│
├── agents/
│   ├── requirement_agent.py
│   ├── planning_agent.py
│   ├── reasoning_agent.py
│   └── travel_agent.py
│
├── tools/
│   ├── train_tool.py
│   ├── bus_tool.py
│   ├── flight_tool.py
│   ├── car_tool.py
│   └── search_tool.py
│
├── data_sources/
│   ├── train_sources.py
│   ├── bus_sources.py
│   ├── flight_sources.py
│   └── road_sources.py
│
├── models/
│   ├── travel_request.py
│   ├── travel_option.py
│   └── user_preferences.py
│
├── services/
│   ├── requirement_parser.py
│   ├── data_normalizer.py
│   ├── scoring_engine.py
│   ├── constraint_engine.py
│   └── worth_it_engine.py
│
├── utils/
│   ├── time_utils.py
│   ├── cost_utils.py
│   └── formatting.py
│
├── memory/
│   └── session_memory.py
│
├── tests/
│
├── requirements.txt
│
├── .env
│
└── README.md
```

The exact structure may evolve, but responsibilities should remain separated.

---

# 23. Suggested Technology Stack

## Core

- Python 3.11+
- OpenRouter API
- Environment variables using `.env`

## LLM

Use OpenRouter for:

- Natural language requirement extraction
- Missing information detection
- Research planning
- Explanation generation

## Data Models

Recommended:

- Pydantic

## HTTP

Possible libraries:

- requests
- httpx

## Web Scraping

Potential libraries:

- BeautifulSoup
- Playwright
- Selenium only if truly required

Prefer lightweight methods first.

## Terminal UI

Potential libraries:

- Rich
- Textual if a more advanced interface is needed

Recommended initial choice:

- Rich

## Date Parsing

Possible:

- dateparser
- Python datetime

---

# 24. OpenRouter Usage Strategy

Do not send raw user input directly into an unrestricted prompt and trust everything returned.

Use structured outputs where possible.

Recommended flow:

```text
User Input
    ↓
OpenRouter LLM
    ↓
Structured Requirement JSON
    ↓
Pydantic Validation
    ↓
Python Application Logic
```

Example concept:

```python
class TravelRequest(BaseModel):
    source: str | None
    destination: str | None
    passengers: int | None
    budget: float | None
    travel_date: str | None
    arrival_deadline: str | None
    ac_preferred: bool | None
```

The LLM should interpret language.

Python should control:

- Calculations
- Filtering
- Scoring
- Ranking
- Validation

This reduces hallucination risk.

---

# 25. Agentic AI Design Principle

The LLM should be responsible mainly for:

- Understanding
- Planning
- Tool selection
- Asking questions
- Reasoning and explanations

Python should be responsible mainly for:

- Fetching data
- Calculating values
- Validating information
- Applying constraints
- Scoring
- Ranking

This creates a better architecture than allowing the LLM to control everything blindly.

---

# 26. Important Safety and Reliability Rules

The system must:

1. Never invent prices.
2. Never invent schedules.
3. Clearly label estimated information.
4. Track the source of collected information.
5. Track when information was collected.
6. Validate LLM structured output.
7. Handle unavailable data gracefully.
8. Avoid exposing API keys.
9. Store API keys in `.env`.
10. Provide explanations based on actual comparison data.

---

# 27. Example `.env`

```env
OPENROUTER_API_KEY=your_key_here
```

Never commit `.env` to GitHub.

Use `.gitignore`:

```text
.env
__pycache__/
*.pyc
.venv/
venv/
```

---

# 28. Development Roadmap

## Phase 1 — Foundation

- Set up Python project.
- Configure virtual environment.
- Configure OpenRouter API.
- Create terminal interface.
- Create data models.
- Implement natural language requirement extraction.

Goal:

```text
Human Language → Structured Travel Request
```

---

## Phase 2 — Conversation Agent

- Add session memory.
- Detect missing attributes.
- Ask follow-up questions.
- Merge answers into the travel request.

Goal:

```text
Incomplete Request → Interactive Complete Request
```

---

## Phase 3 — Travel Data Research

Implement one travel mode at a time.

Recommended order:

1. Train
2. Bus
3. Flight
4. Own Car
5. Cab
6. Rental

For each mode:

- Identify sources.
- Build data collectors.
- Normalize results.
- Handle failures.

---

## Phase 4 — Data Normalization

Convert all sources into:

```python
TravelOption
```

Goal:

```text
Train Data
Bus Data
Flight Data
Car Data
      ↓
Common Data Model
```

---

## Phase 5 — Decision Engine

Implement:

- Constraint filtering
- Cost scoring
- Time scoring
- Comfort scoring
- Convenience scoring
- Reliability scoring
- Preference matching
- Dynamic weighting

Goal:

```text
Options → Scores → Rankings
```

---

## Phase 6 — Worth-It Engine

Implement comparison logic.

Examples:

- Extra money per hour saved.
- Extra cost per comfort improvement.
- Group travel economics.
- Door-to-door time tradeoffs.

Goal:

```text
"Cheapest" → "Best Value for This User"
```

---

## Phase 7 — Reasoning and Explanation

Use the LLM to generate:

- Best option explanation.
- Alternative explanations.
- Tradeoffs.
- Personalized recommendations.

The explanation must use actual structured data.

---

## Phase 8 — Testing

Test cases should include:

### Budget Traveller

```text
2 people
Low budget
Flexible arrival
```

### Comfort Traveller

```text
Family
AC mandatory
Elderly traveller
```

### Urgent Traveller

```text
Strict arrival deadline
```

### Group Traveller

```text
5–6 people
Own car comparison
```

### Long Distance

```text
Train vs flight
```

### Short Distance

```text
Car vs bus vs train
```

---

# 29. MVP Recommendation

Do not try to build everything perfectly on Day 1.

Recommended MVP:

```text
Natural Language Input
        ↓
Requirement Extraction
        ↓
Follow-Up Questions
        ↓
Train + Bus + Flight + Own Car Data
        ↓
Normalized Options
        ↓
Scoring
        ↓
Ranked Recommendation
```

Add cab, rental, advanced reliability, and deeper comfort models afterward.

---

# 30. Success Criteria

The project is successful if a user can type something like:

```text
We are 3 people travelling from Chennai to Bangalore tomorrow.
We have ₹6000 total, prefer AC and comfort, and need to reach
before 7 PM. We don't mind spending a little extra if the time
saved is actually worth it.
```

And the system can:

1. Understand the request.
2. Ask only necessary follow-up questions.
3. Gather relevant current travel options.
4. Compare multiple travel modes.
5. Respect constraints.
6. Analyze cost, time, comfort, and convenience.
7. Determine whether additional spending is worth the benefit.
8. Rank alternatives.
9. Explain the recommendation clearly.
10. Display everything in the terminal.

---

# 31. Final Project Vision

> Build an intelligent, agentic AI-powered travel decision system for India that understands natural language travel requirements, autonomously gathers current transportation information, evaluates multiple travel modes using personalized multi-criteria analysis, and recommends the option that provides the best overall value rather than simply the lowest price.

---

# 32. Guiding Principle

**LLM for understanding and reasoning.**

**Python for tools, data, validation, calculations, and decisions.**

**Real data for recommendations.**

**Transparency when data is uncertain.**

**Best value for the user, not merely cheapest or fastest.**

---

# NEXT STEP

Before writing the main agent logic:

1. Finalize the project architecture.
2. Research viable Indian data sources for trains, buses, flights, and road travel.
3. Identify which sources support scraping and which require APIs.
4. Define the exact `TravelRequest` and `TravelOption` Pydantic models.
5. Set up OpenRouter and test structured requirement extraction.
6. Build the first end-to-end MVP with mocked data before connecting real sources.

Then gradually replace mocked data with real data collectors.
