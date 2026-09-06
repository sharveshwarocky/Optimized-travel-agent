"""Manual end-to-end run of the guide §30 success prompt (spec §16/§18).

Runs the real pipeline — LLM extraction (OpenRouter), live collectors
(erail / skiplagged / OSRM / goodreturns + formula estimators), engines,
renderers — without the interactive console, so it can be executed in one shot.

Usage:  .venv/Scripts/python.exe scripts/e2e_run.py
"""
import asyncio
import io
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rich.console import Console

from agents.orchestrator import run_pipeline
from agents.requirement_agent import extract_and_merge, missing_critical
from memory.session_memory import SessionMemory
from ui import renderers

SUCCESS_PROMPT = (
    "We are 3 people travelling from Chennai to Bangalore tomorrow. "
    "We have ₹6000 total, prefer AC and comfort, and need to reach before 7 PM. "
    "We don't mind spending a little extra if the time saved is actually worth it."
)

FOLLOWUP_ANSWERS = ["3", "tomorrow"]  # stock answers if the agent needs follow-ups


async def main() -> None:
    console = Console(file=io.StringIO(), width=110, legacy_windows=False)
    memory = SessionMemory()

    console.print(f"[bold]E2E prompt:[/bold] {SUCCESS_PROMPT}")
    outcome = await extract_and_merge(memory, SUCCESS_PROMPT)
    for c in outcome.confirmations:
        console.print(f"[dim]• {c}[/dim]")
    console.print(f"[dim]fallback used: {outcome.fallback_used} | llm: {outcome.llm_error or 'ok'}[/dim]")

    missing = missing_critical(memory)
    for field in missing:
        q = {"source": "Which city are you starting from?",
             "destination": "Where are you heading?",
             "travel_date": "What date are you travelling?",
             "passengers": "How many people are travelling?"}.get(field, field)
        console.print(f"[yellow]{q}[/yellow]")
        memory.mark_asked(field)
        ans = FOLLOWUP_ANSWERS.pop(0) if FOLLOWUP_ANSWERS else "3"
        console.print(f"You > {ans}")
        await extract_and_merge(memory, ans)

    result = await run_pipeline(memory)

    # reprint banner + results into the captured console
    renderers.render_banner(result, console)
    if result.ranked:
        renderers.render_recommendation(result, memory.request, console)
        renderers.render_assumptions(result, console)
        renderers.render_fallbacks(result, console)
    elif result.conflict:
        console.print(f"[red]{result.conflict.summary}[/red]")
        console.print(result.conflict.question)
        console.print(f"relaxable: {result.conflict.relaxable}")
    else:
        renderers.render_assumptions(result, console)

    out = console.file.getvalue()
    Path("e2e_output.txt").write_text(out, encoding="utf-8")
    print(out)
    print(f"\n>>> saved to e2e_output.txt ({len(out)} chars)")


if __name__ == "__main__":
    asyncio.run(main())
