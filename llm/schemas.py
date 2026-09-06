"""Shared LLM JSON response schemas (spec §10.2, llm/schemas.py).

Kept as plain JSON-schema dicts — OpenRouter takes a JSON prompt contract, and
Pydantic re-validates the parsed result in Python (guide §24).
"""
from __future__ import annotations

EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "source": {"type": ["string", "null"]},
        "destination": {"type": ["string", "null"]},
        "travel_date": {"type": ["string", "null"], "description": "natural language date or null"},
        "arrival_deadline": {"type": ["string", "null"], "description": "e.g. '18:00' or '6 pm' or null"},
        "preferred_departure_after": {"type": ["string", "null"]},
        "max_duration_hours": {"type": ["number", "null"]},
        "passengers": {"type": ["integer", "null"]},
        "budget": {"type": ["number", "null"]},
        "budget_type": {"enum": ["total", "per_person", None]},
        "budget_flexibility": {"enum": ["strict", "flexible", None]},
        "comfort_priority": {"enum": ["low", "medium", "high", None]},
        "ac_required": {"type": ["boolean", "null"]},
        "sleeper_preferred": {"type": ["boolean", "null"]},
        "overnight_allowed": {"type": ["boolean", "null"]},
        "luggage_level": {"enum": ["light", "normal", "heavy", None]},
        "urgency": {"enum": ["low", "medium", "high", None]},
        "preferred_modes": {"type": "array", "items": {"enum": ["train", "bus", "flight", "own_car", "cab", "rental"]}},
        "avoided_modes": {"type": "array", "items": {"enum": ["train", "bus", "flight", "own_car", "cab", "rental"]}},
        "return_date": {"type": ["string", "null"], "description": "only if user explicitly mentions return travel"},
        "overrides": {"type": "array", "items": {"type": "string"},
                      "description": "fields that contradict earlier values (human-readable)"},
    },
    "additionalProperties": False,
}

PLANNING_SCHEMA = {
    "type": "object",
    "properties": {
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "mode": {"enum": ["train", "bus", "flight", "own_car", "cab", "rental"]},
                    "priority": {"type": "integer", "minimum": 1, "maximum": 3},
                    "reason": {"type": "string"},
                    "sources": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["mode"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["tasks"],
    "additionalProperties": False,
}

REASONING_SCHEMA = {
    "type": "object",
    "properties": {
        "best_why": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
        "alternatives": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "pros": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
                    "cons": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
                    "worth_it_line": {"type": "string"},
                },
                "required": ["name"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["best_why", "alternatives"],
    "additionalProperties": False,
}

CONFLICT_SCHEMA = {
    "type": "object",
    "properties": {
        "question": {"type": "string"},
        "conflict_summary": {"type": "string"},
    },
    "required": ["question", "conflict_summary"],
    "additionalProperties": False,
}
