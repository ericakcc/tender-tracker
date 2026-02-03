"""CLI report output with rich formatting."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from tender_tracker.models import Tender, TenderEvaluation

console = Console()


def render_tender_table(tenders: list[Tender], *, title: str = "標案列表") -> None:
    """Render a list of tenders as a rich table.

    Args:
        tenders: Tenders to display.
        title: Table title.
    """
    table = Table(title=title, show_lines=True)
    table.add_column("案號", style="cyan", width=16)
    table.add_column("名稱", style="white", width=40)
    table.add_column("機關", style="green", width=16)
    table.add_column("類別", style="yellow", width=6)
    table.add_column("預算", style="magenta", justify="right", width=14)
    table.add_column("截止日", style="red", width=12)
    table.add_column("來源", style="blue", width=8)

    for t in tenders:
        budget = f"NT${t.budget_amount:,.0f}" if t.budget_amount else "—"
        deadline = t.deadline.strftime("%Y/%m/%d") if t.deadline else "—"
        table.add_row(
            t.tender_id[:16],
            _truncate(t.title, 40),
            _truncate(t.org_name, 16),
            t.procurement_type or "—",
            budget,
            deadline,
            t.source,
        )

    console.print(table)


def render_evaluation_table(
    results: list[tuple[Tender, TenderEvaluation]],
    *,
    title: str = "AI 評估結果",
) -> None:
    """Render evaluation results as a rich table.

    Args:
        results: List of (tender, evaluation) tuples.
        title: Table title.
    """
    table = Table(title=title, show_lines=True)
    table.add_column("案號", style="cyan", width=16)
    table.add_column("名稱", style="white", width=30)
    table.add_column("分數", justify="right", width=6)
    table.add_column("適合", width=4)
    table.add_column("建議", style="yellow", width=14)
    table.add_column("匹配能力", style="green", width=24)
    table.add_column("理由", style="dim", width=30)

    for tender, evaluation in results:
        score_style = _score_style(evaluation.relevance_score)
        suitable_icon = "[green]✓[/green]" if evaluation.suitable else "[red]✗[/red]"
        action = _action_label(evaluation.recommended_action)
        capabilities = ", ".join(evaluation.matched_capabilities[:3])

        table.add_row(
            tender.tender_id[:16],
            _truncate(tender.title, 30),
            f"[{score_style}]{evaluation.relevance_score:.2f}[/{score_style}]",
            suitable_icon,
            action,
            _truncate(capabilities, 24) if capabilities else "—",
            _truncate(evaluation.reasoning, 30),
        )

    console.print(table)


def render_stats(stats: dict[str, int]) -> None:
    """Render summary statistics as a panel.

    Args:
        stats: Dictionary with statistic counts.
    """
    lines = [
        f"[cyan]標案總數：[/cyan]{stats.get('total_tenders', 0)}",
        f"[green]已評估：[/green]{stats.get('evaluated', 0)}",
        f"[yellow]適合投標：[/yellow]{stats.get('suitable', 0)}",
        f"[red]未評估：[/red]{stats.get('unevaluated', 0)}",
    ]
    panel = Panel("\n".join(lines), title="統計摘要", border_style="blue")
    console.print(panel)


def _truncate(text: str, max_len: int) -> str:
    """Truncate text with ellipsis if too long."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def _score_style(score: float) -> str:
    """Get rich style based on relevance score."""
    if score >= 0.7:
        return "bold green"
    if score >= 0.4:
        return "yellow"
    return "red"


def _action_label(action: str) -> str:
    """Get display label for recommended action."""
    labels = {
        "bid": "[bold green]建議投標[/bold green]",
        "skip": "[red]略過[/red]",
        "review_further": "[yellow]需進一步評估[/yellow]",
    }
    return labels.get(action, action)
