"""Terminal renderers (spec §14): confidence banner, medal cards, rankings,
assumptions box, and the `explain` sub-score table. All Rich, no LLM.
"""
from __future__ import annotations

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from agents.orchestrator import PipelineResult
from models.travel_option import TravelOption
from utils.cost_utils import inr
from utils.time_utils import minutes_to_hm

MEDALS = ["🥇", "🥈", "🥉"]


def _dot(opt: TravelOption) -> str:
    from models.provenance import CONFIDENCE_DOT
    return CONFIDENCE_DOT.get(opt.data_type, "🔴")


def render_banner(result: PipelineResult, console) -> None:
    table = Table(title="Data confidence by mode", show_header=True, header_style="bold")
    table.add_column("Mode", style="cyan")
    table.add_column("Status")
    table.add_column("Detail", overflow="fold")
    for ms in result.mode_statuses:
        status_text = {"ok": "data found", "empty": "nothing matching",
                       "unavailable": "unavailable"}.get(ms.status, ms.status)
        table.add_row(ms.mode.replace("_", " "), f"{ms.dot} {status_text}",
                      ms.detail[:90])
    console.print(table)
    if result.planned_by == "fallback":
        console.print("[dim]research plan: deterministic default (LLM planner unavailable)[/dim]")


def render_recommendation(result: PipelineResult, req, console) -> None:
    ranked = result.ranked
    if not ranked:
        return
    pax = req.effective_passengers()
    best = ranked[0]
    why = result.explanation.get("best_why", [])

    lines = [
        f"[bold]Total cost:[/bold] {inr(best.total_cost)}"
        f"  ·  [bold]Per person:[/bold] {inr(best.cost_per_person)} ({pax} travellers)",
        f"[bold]Journey:[/bold] {minutes_to_hm(best.travel_duration_minutes)}"
        f"  ·  [bold]Door-to-door:[/bold] ≈ {minutes_to_hm(best.door_to_door_duration_minutes)}",
        f"[bold]Comfort:[/bold] {best.comfort_level}/10"
        f"  ·  [bold]AC:[/bold] {'yes' if best.ac else 'no' if best.ac is False else 'n/a'}"
        f"  ·  [bold]Data:[/bold] {_dot(best)} {best.data_type} (source: {best.source})",
    ]
    if req.arrival_deadline and best.arrival_time:
        headroom = (req.arrival_deadline.hour * 60 + req.arrival_deadline.minute) - \
                   (best.arrival_time.hour * 60 + best.arrival_time.minute)
        lines.append(f"[bold]Arrival:[/bold] {best.arrival_time.strftime('%H:%M')} — "
                     f"{'meets' if headroom >= 0 else 'MISSES'} your "
                     f"{req.arrival_deadline.strftime('%H:%M')} deadline"
                     + (f" ({headroom} min spare)" if headroom >= 0 else ""))
    if why:
        lines.append("")
        lines.append("[bold]Why it is recommended:[/bold]")
        lines.extend(f"  • {w}" for w in why)

    console.print(Panel("\n".join(lines), title=f"{MEDALS[0]} BEST OVERALL: {best.name}",
                        border_style="green", subtitle=f"score {best.overall_score}/100"))

    for i, opt in enumerate(ranked[1:3], start=2):
        alt_lines = [f"Score: [bold]{opt.overall_score}/100[/bold] · {_dot(opt)} {opt.data_type} · "
                     f"{inr(opt.total_cost)} · {minutes_to_hm(opt.travel_duration_minutes)} journey"]
        alt = result.explanation.get("alternatives", [])
        alt_data = next((a for a in alt if a.get("name") == opt.name), None)
        if alt_data:
            for p in alt_data.get("pros", []):
                alt_lines.append(f"  [green]+[/green] {p}")
            for c in alt_data.get("cons", []):
                alt_lines.append(f"  [red]−[/red] {c}")
            if alt_data.get("worth_it_line"):
                alt_lines.append(f"  [yellow]₹[/yellow] {alt_data['worth_it_line']}")
        if i - 1 < len(result.worth_it):
            alt_lines.append(f"  [dim]worth-it: {result.worth_it[i - 1]}[/dim]")
        medal = MEDALS[i] if i < len(MEDALS) else f"{i}."
        console.print(Panel("\n".join(alt_lines), title=f"{medal} {opt.name}",
                            border_style="blue"))


def render_assumptions(result: PipelineResult, console) -> None:
    """Every 🟠 value and assumption called out explicitly (§14.4)."""
    notes: list[str] = []
    for opt in result.all_options:
        if opt.data_type == "estimated":
            notes.append(f"🟠 {opt.name}: {inr(opt.total_cost)} — formula estimate (D17), not a live quote")
    for opt in result.ranked[:3]:
        assumed = [k for k in opt.door_to_door_breakdown if k.endswith("_assumed")]
        if assumed:
            base = [k.replace("_assumed", "") for k in assumed]
            notes.append(f"🟡 {opt.name}: access legs assumed ({', '.join(base)}) — "
                         f"city-size default, not measured")
    if any(ms.status == "unavailable" for ms in result.mode_statuses):
        for ms in result.mode_statuses:
            if ms.status == "unavailable":
                notes.append(f"🔴 {ms.mode.replace('_', ' ')}: {ms.detail[:110]}")
    if notes:
        console.print(Panel("\n".join(f"• {n}" for n in notes),
                            title="Assumptions & estimates", border_style="yellow"))


def render_fallbacks(result: PipelineResult, console) -> None:
    if result.fallbacks_fired:
        console.print(f"[dim]fallbacks fired: {'; '.join(result.fallbacks_fired)}[/dim]")
    console.print(f"[dim]LLM usage: {result.llm_usage}[/dim]")


def render_conflict(conflict, console, loop: int) -> None:
    console.print(Panel(
        "\n".join([f"[bold red]{conflict.summary}[/bold red]", "", conflict.question,
                   "", "[dim]Type the number of the constraint to relax, or 'keep' to see "
                   "least-violating options.[/dim]"]),
        title=f"⚠ Constraint conflict (attempt {loop}/3)", border_style="red"))


def render_relaxed_result(result: PipelineResult, console) -> None:
    console.print(Panel(
        "Three relaxation attempts didn't produce a clean winner. These options "
        "violate the fewest constraints (violations labeled). Changing the travel "
        "date is often the honest fix.", title="Least-violating options",
        border_style="red"))
    for opt in result.relaxed_result:
        viols = ", ".join(v.replace("_", " ") for v in opt.constraint_violations) or "none"
        console.print(f"• {opt.name} — {inr(opt.total_cost)}, "
                      f"{minutes_to_hm(opt.travel_duration_minutes)} — [red]violates: {viols}[/red]")


def render_explain(result: PipelineResult, console) -> None:
    """Scores and weights visible on request (§14.5)."""
    if not result.ranked:
        console.print("[dim]nothing ranked yet — run a search first[/dim]")
        return
    table = Table(title=f"Score breakdown (profile: {result.profile})")
    table.add_column("Option")
    for key in ("cost", "time", "comfort", "conv", "pref", "schedule"):
        table.add_column(f"{key}\n{result.weights.get(key, 0):.0%}", justify="right")
    table.add_column("Overall", justify="right", style="bold")
    for o in result.ranked[:5]:
        row = [o.name[:38]]
        for key in ("cost", "time", "comfort", "conv", "pref", "schedule"):
            row.append(f"{o.sub_scores.get(key, 0):.0f}")
        row.append(f"{o.overall_score:.0f}")
        table.add_row(*row)
    console.print(table)
