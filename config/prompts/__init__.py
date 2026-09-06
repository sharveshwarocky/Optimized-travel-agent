"""Prompt loader: versioned templates in config/prompts/ (spec §10.2).

Templates contain $PLACEHOLDER tokens replaced at call time — never inline
strings in agent code.
"""
from __future__ import annotations

from pathlib import Path

_PROMPT_DIR = Path(__file__).resolve().parent


def load_prompt(name: str, replacements: dict[str, str]) -> dict[str, str]:
    """Load config/prompts/<name>.md and split on the first SYSTEM:/USER: markers.

    Files are written as:
        SYSTEM:
        <system text>
        USER MESSAGE:
        <user text>
    Returns {"system": ..., "user": ...} with $TOKENS substituted.
    """
    path = _PROMPT_DIR / f"{name}.md"
    raw = path.read_text(encoding="utf-8")
    for token, value in replacements.items():
        raw = raw.replace(token, value)

    lowered = raw.lower()
    sys_start = lowered.index("system:")
    user_marker = "user message:" if "user message:" in lowered else "user:"
    user_start = lowered.index(user_marker)
    system_text = raw[sys_start + len("system:"):user_start].strip()
    user_text = raw[user_start + len(user_marker):].strip()
    return {"system": system_text, "user": user_text}
