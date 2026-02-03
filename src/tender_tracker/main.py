"""CLI entry point using click + rich."""

import asyncio
from datetime import date, timedelta
from pathlib import Path

import click
from loguru import logger
from rich.console import Console

from tender_tracker.config import load_config
from tender_tracker.evaluator import TenderEvaluator
from tender_tracker.filters import TenderFilter
from tender_tracker.models import Tender
from tender_tracker.reports import (
    render_evaluation_table,
    render_stats,
    render_tender_table,
)
from tender_tracker.sources.mlwmlw import MlwmlwSource
from tender_tracker.storage import TenderStorage

console = Console()


@click.group()
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to config.yaml",
)
@click.option(
    "--db", "db_path", type=click.Path(path_type=Path), default=None, help="SQLite DB path"
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.pass_context
def cli(ctx: click.Context, config_path: Path | None, db_path: Path | None, verbose: bool) -> None:
    """Taiwan government tender tracker for Star Fusion Group."""
    ctx.ensure_object(dict)

    if not verbose:
        logger.remove()
        logger.add(lambda msg: None)  # Suppress logs in non-verbose mode

    config = load_config(config_path)
    storage = TenderStorage(db_path)
    storage.init_db()

    ctx.obj["config"] = config
    ctx.obj["storage"] = storage


@cli.command()
@click.option(
    "--date",
    "target_date",
    type=click.DateTime(["%Y-%m-%d"]),
    default=None,
    help="Date (YYYY-MM-DD)",
)
@click.option("--days", type=int, default=1, help="Number of days to fetch")
@click.pass_context
def fetch(ctx: click.Context, target_date: date | None, days: int) -> None:
    """Fetch latest tenders and save to database."""
    config = ctx.obj["config"]
    storage: TenderStorage = ctx.obj["storage"]
    tender_filter = TenderFilter(config)

    start_date = target_date.date() if target_date else date.today()

    async def _fetch() -> list[Tender]:
        source = MlwmlwSource()
        all_tenders: list[Tender] = []
        try:
            for i in range(days):
                d = start_date - timedelta(days=i)
                tenders = await source.fetch_by_date(d)
                all_tenders.extend(tenders)
        finally:
            await source.close()
        return all_tenders

    with console.status("[bold green]正在抓取標案資料..."):
        all_tenders = asyncio.run(_fetch())

    if not all_tenders:
        console.print("[yellow]未找到任何標案。[/yellow]")
        return

    # Apply keyword filter for pre-screening
    filtered = tender_filter.keyword_filter(all_tenders)
    new_count = storage.upsert_tenders(filtered)
    storage.log_sync("mlwmlw", len(filtered), "success")

    console.print(
        f"[green]抓取完成：[/green]共 {len(all_tenders)} 筆，"
        f"關鍵字篩選後 {len(filtered)} 筆，"
        f"新增 {new_count} 筆。"
    )

    if filtered:
        render_tender_table(filtered[:20], title="最新標案（前 20 筆）")


@cli.command()
@click.argument("keyword")
@click.pass_context
def search(ctx: click.Context, keyword: str) -> None:
    """Search tenders by keyword."""
    storage: TenderStorage = ctx.obj["storage"]

    async def _search() -> list[Tender]:
        source = MlwmlwSource()
        try:
            return await source.search(keyword)
        finally:
            await source.close()

    with console.status(f"[bold green]搜尋「{keyword}」..."):
        tenders = asyncio.run(_search())

    if not tenders:
        console.print(f"[yellow]未找到「{keyword}」相關標案。[/yellow]")
        return

    new_count = storage.upsert_tenders(tenders)
    console.print(f"[green]找到 {len(tenders)} 筆，新增 {new_count} 筆。[/green]")
    render_tender_table(tenders[:20], title=f"搜尋結果：{keyword}")


@cli.command("list")
@click.option("--days", type=int, default=None, help="Only show tenders from last N days")
@click.option("--limit", type=int, default=50, help="Maximum number of results")
@click.option("--evaluated", is_flag=True, help="Only show evaluated tenders")
@click.pass_context
def list_tenders(ctx: click.Context, days: int | None, limit: int, evaluated: bool) -> None:
    """List tenders in the database."""
    storage: TenderStorage = ctx.obj["storage"]
    tenders = storage.list_tenders(days=days, limit=limit, evaluated_only=evaluated)

    if not tenders:
        console.print("[yellow]資料庫中沒有標案。[/yellow]")
        return

    render_tender_table(tenders, title=f"標案列表（共 {len(tenders)} 筆）")


@cli.command()
@click.option("--limit", type=int, default=10, help="Max tenders to evaluate")
@click.pass_context
def evaluate(ctx: click.Context, limit: int) -> None:
    """Evaluate unevaluated tenders using Claude AI."""
    storage: TenderStorage = ctx.obj["storage"]

    unevaluated_ids = storage.get_unevaluated_tender_ids()
    if not unevaluated_ids:
        console.print("[yellow]沒有待評估的標案。[/yellow]")
        return

    ids_to_eval = unevaluated_ids[:limit]
    tenders = [storage.get_tender(tid) for tid in ids_to_eval]
    tenders = [t for t in tenders if t is not None]

    console.print(f"[cyan]將評估 {len(tenders)} 筆標案...[/cyan]")

    evaluator = TenderEvaluator()
    results = []

    for tender in tenders:
        with console.status(f"[bold green]評估中：{tender.title[:30]}..."):
            tender_eval = evaluator.evaluate(tender)
            storage.save_evaluation(tender.tender_id, tender_eval)
            results.append((tender, tender_eval))

    render_evaluation_table(results)


@cli.command()
@click.pass_context
def report(ctx: click.Context) -> None:
    """Show summary statistics."""
    storage: TenderStorage = ctx.obj["storage"]
    stats = storage.get_stats()
    render_stats(stats)


@cli.command()
@click.option("--days", type=int, default=30, help="Number of days to show")
@click.pass_context
def history(ctx: click.Context, days: int) -> None:
    """Show tender tracking history for the last N days."""
    storage: TenderStorage = ctx.obj["storage"]
    tenders = storage.list_tenders(days=days, limit=200)

    if not tenders:
        console.print(f"[yellow]過去 {days} 天沒有追蹤記錄。[/yellow]")
        return

    console.print(f"[cyan]過去 {days} 天共追蹤 {len(tenders)} 筆標案。[/cyan]")
    render_tender_table(tenders[:50], title=f"近 {days} 天標案追蹤記錄")

    # Show evaluations if any
    evaluated = storage.list_tenders(days=days, limit=200, evaluated_only=True)
    if evaluated:
        results = []
        for tender in evaluated:
            evaluation = storage.get_evaluation(tender.tender_id)
            if evaluation:
                results.append((tender, evaluation))
        if results:
            render_evaluation_table(results, title="已評估標案")


if __name__ == "__main__":
    cli()
