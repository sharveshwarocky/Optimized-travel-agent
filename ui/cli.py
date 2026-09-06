"""CLI session loop (spec §4/§13/§14): multi-turn conversation, focused follow-ups,
conflict-relax loop, `new`/`explain`/`quit` commands.
"""
from __future__ import annotations

import asyncio

from rich.console import Console
from rich.panel import Panel

from agents.orchestrator import PipelineResult, run_pipeline
from agents.requirement_agent import FOLLOWUP_TEXT, extract_and_merge, missing_critical
from llm.client import get_client, usage_log
from memory.session_memory import SessionMemory
from ui import renderers

console = Console()

_last_result: PipelineResult | None = None

WELCOME = """[bold]Agentic AI Travel Decision Agent (India)[/bold]
Describe your trip in plain language — e.g. "We are 3 people travelling from
Chennai to Bangalore tomorrow. We have ₹6000 total, prefer AC and comfort, and
need to reach before 7 PM."

Commands: [bold]new[/bold] = reset session · [bold]explain[/bold] = show score
breakdown · [bold]quit[/bold] = exit"""


async def handle_search(memory: SessionMemory) -> None:
    global _last_result
    relaxed: list[str] = []
    result: PipelineResult | None = None

    for loop in range(1, 4):  # conflict loop max 3 (§12.4)
        with console.status("[bold green]Researching trains, buses, flights and road options…"):
            result = await run_pipeline(memory, relaxed_constraints=relaxed)

        renderers.render_banner(result, console)

        if result.ranked:
            renderers.render_recommendation(result, memory.request, console)
            renderers.render_assumptions(result, console)
            renderers.render_fallbacks(result, console)
            _last_result = result
            return

        if result.conflict is None:
            console.print("[red]No options could be collected for this route.[/red]")
            renderers.render_assumptions(result, console)
            _last_result = result
            return

        # zero survivors → ask which constraint to relax (D9)
        renderers.render_conflict(result.conflict, console, loop)
        answer = console.input("[bold]Your choice:[/bold] ").strip().lower()
        if answer in ("keep", "none", "skip"):
            renderers.render_relaxed_result(result, console)
            renderers.render_assumptions(result, console)
            _last_result = result
            return
        chosen = None
        for i, key in enumerate(result.conflict.relaxable[:3], start=1):
            if answer == str(i) or answer == key:
                chosen = key
                break
        if chosen is None:
            console.print("[yellow]Unrecognized — relaxing the top suggestion.[/yellow]")
            chosen = result.conflict.relaxable[0]
        relaxed.append(chosen)
        console.print(f"[green]Relaxing '{chosen.replace('_', ' ')}' and re-running…[/green]")

    if result is not None:
        renderers.render_relaxed_result(result, console)
        renderers.render_assumptions(result, console)
        _last_result = result


async def _ask_followups(memory: SessionMemory, missing: list[str]) -> None:
    """Focused follow-up questions for critical missing fields (§13)."""
    for field in missing:
        q = FOLLOWUP_TEXT.get(field, f"What is your {field.replace('_', ' ')}?")
        console.print(f"[bold yellow]{q}[/bold yellow]")
        memory.mark_asked(field)
        try:
            ans = console.input("[bold cyan]You >[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            raise
        if ans.lower() in ("quit", "exit"):
            raise KeyboardInterrupt
        outcome = await extract_and_merge(memory, ans)
        for c in outcome.confirmations:
            console.print(f"[dim]• {c}[/dim]")


async def session_loop() -> None:
    global _last_result
    memory = SessionMemory()
    client = get_client()
    console.print(Panel(WELCOME, border_style="cyan"))
    if not client.available:
        console.print("[yellow]No OPENROUTER_API_KEY found — running in deterministic "
                      "fallback mode (regex extraction, template explanations).[/yellow]")

    while True:
        try:
            text = console.input("\n[bold cyan]You >[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text:
            continue
        cmd = text.lower()
        if cmd in ("quit", "exit", "q"):
            break
        if cmd == "new":
            memory.reset()
            usage_log.entries.clear()
            _last_result = None
            console.print("[green]Session reset.[/green]")
            continue
        if cmd == "explain":
            if _last_result is not None:
                renderers.render_explain(_last_result, console)
            else:
                console.print("[dim]nothing ranked yet — run a search first[/dim]")
            continue

        try:
            outcome = await extract_and_merge(memory, text)
        except KeyboardInterrupt:
            break
        for c in outcome.confirmations:
            console.print(f"[dim]• {c}[/dim]")

        missing = missing_critical(memory)
        if missing:
            try:
                await _ask_followups(memory, missing)
            except KeyboardInterrupt:
                break
            remaining = missing_critical(memory)
            if remaining:
                console.print(f"[yellow]Still need: {', '.join(remaining)}[/yellow]")
                continue

        # round trips rejected in v1 (D10)
        if memory.request.return_date:
            console.print("[yellow]Round trips aren't supported in v1 — searching one-way only.[/yellow]")

        await handle_search(memory)


def main() -> None:
    try:
        asyncio.run(session_loop())
    except KeyboardInterrupt:
        pass
    finally:
        console.print("[dim]goodbye[/dim]")
