"""CLI entry point using click + rich."""

import asyncio
import csv
from datetime import date, timedelta
from pathlib import Path

import click
from loguru import logger
from rich.console import Console

from tender_tracker.config import load_config
from tender_tracker.evaluator import TenderEvaluator
from tender_tracker.models import Tender, TenderEvaluation
from tender_tracker.reports import (
    render_evaluation_table,
    render_stats,
    render_tender_table,
)
from tender_tracker.sources.ebuying import EbuyingSource
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
    """Taiwan government tender tracker with AI-powered evaluation."""
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
    storage: TenderStorage = ctx.obj["storage"]

    start_date = target_date.date() if target_date else date.today()

    async def _fetch() -> list[Tender]:
        mlwmlw = MlwmlwSource()
        ebuying = EbuyingSource()
        all_tenders: list[Tender] = []
        try:
            for i in range(days):
                d = start_date - timedelta(days=i)
                mlwmlw_result, ebuying_result = await asyncio.gather(
                    mlwmlw.fetch_by_date(d),
                    ebuying.fetch_by_date(d),
                )
                all_tenders.extend(mlwmlw_result)
                all_tenders.extend(ebuying_result)
        finally:
            await asyncio.gather(mlwmlw.close(), ebuying.close())
        return all_tenders

    with console.status("[bold green]正在抓取標案資料..."):
        all_tenders = asyncio.run(_fetch())

    if not all_tenders:
        console.print("[yellow]未找到任何標案。[/yellow]")
        return

    new_count = storage.upsert_tenders(all_tenders)
    storage.log_sync("mlwmlw+ebuying", len(all_tenders), "success")

    console.print(f"[green]抓取完成：[/green]共 {len(all_tenders)} 筆，新增 {new_count} 筆。")

    if all_tenders:
        render_tender_table(all_tenders[:20], title="最新標案（前 20 筆）")


@cli.command()
@click.argument("keyword")
@click.pass_context
def search(ctx: click.Context, keyword: str) -> None:
    """Search tenders by keyword."""
    config = ctx.obj["config"]
    storage: TenderStorage = ctx.obj["storage"]

    async def _search() -> list[Tender]:
        mlwmlw = MlwmlwSource()
        ebuying = EbuyingSource(categories=config.ebuying_categories)
        try:
            mlwmlw_result, ebuying_result = await asyncio.gather(
                mlwmlw.search(keyword),
                ebuying.search(keyword),
            )
            return mlwmlw_result + ebuying_result
        finally:
            await asyncio.gather(mlwmlw.close(), ebuying.close())

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
@click.option("--concurrency", "-c", type=int, default=20, help="Max parallel evaluations")
@click.pass_context
def evaluate(ctx: click.Context, limit: int, concurrency: int) -> None:
    """Evaluate unevaluated tenders using AI (vLLM or Claude)."""
    config = ctx.obj["config"]
    storage: TenderStorage = ctx.obj["storage"]

    unevaluated_ids = storage.get_unevaluated_tender_ids()
    if not unevaluated_ids:
        console.print("[yellow]沒有待評估的標案。[/yellow]")
        return

    ids_to_eval = unevaluated_ids[:limit]
    tenders = [storage.get_tender(tid) for tid in ids_to_eval]
    tenders = [t for t in tenders if t is not None]

    backend_name = config.llm.backend.upper()
    model_name = config.llm.model
    console.print(f"[cyan]將評估 {len(tenders)} 筆標案（{backend_name}: {model_name}）...[/cyan]")

    evaluator = TenderEvaluator(config=config.llm)

    def _save(tender: Tender, tender_eval: TenderEvaluation) -> None:
        storage.save_evaluation(tender.tender_id, tender_eval)

    async def _run() -> list[tuple[Tender, TenderEvaluation]]:
        try:
            return await evaluator.evaluate_batch(tenders, concurrency=concurrency, on_result=_save)
        finally:
            await evaluator.close()

    with console.status(f"[bold green]平行評估中（並發 {concurrency}）..."):
        results = asyncio.run(_run())

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


_ACTION_LABELS: dict[str, str] = {
    "bid": "建議投標",
    "skip": "略過",
    "review_further": "需進一步評估",
}

_CSV_FIELDS = [
    "案號",
    "名稱",
    "招標機關",
    "採購類別",
    "招標方式",
    "預算金額",
    "截止日期",
    "開標日期",
    "標的分類",
    "資料來源",
    "公告日期",
    "抓取時間",
    "連結",
    "相關度",
    "適合投標",
    "建議行動",
    "匹配能力",
    "判斷理由",
]


@cli.command()
@click.option(
    "--output",
    "-o",
    "output_path",
    type=click.Path(path_type=Path),
    default="tenders_export.csv",
    help="Output CSV file path",
)
@click.option("--days", type=int, default=None, help="Only export tenders from last N days")
@click.option("--evaluated", is_flag=True, help="Only export evaluated tenders")
@click.pass_context
def export(ctx: click.Context, output_path: Path, days: int | None, evaluated: bool) -> None:
    """Export tenders to CSV file."""
    storage: TenderStorage = ctx.obj["storage"]
    tenders = storage.list_tenders(days=days, limit=100_000, evaluated_only=evaluated)

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS)
        writer.writeheader()

        for tender in tenders:
            evaluation = storage.get_evaluation(tender.tender_id)

            row: dict[str, str] = {
                "案號": tender.tender_id,
                "名稱": tender.title,
                "招標機關": tender.org_name,
                "採購類別": tender.procurement_type,
                "招標方式": tender.tender_method,
                "預算金額": str(tender.budget_amount) if tender.budget_amount is not None else "",
                "截止日期": tender.deadline.strftime("%Y/%m/%d") if tender.deadline else "",
                "開標日期": tender.open_date.strftime("%Y/%m/%d") if tender.open_date else "",
                "標的分類": tender.category,
                "資料來源": tender.source,
                "公告日期": tender.publish_date.strftime("%Y/%m/%d") if tender.publish_date else "",
                "抓取時間": tender.fetched_at.strftime("%Y/%m/%d %H:%M"),
                "連結": tender.url,
                "相關度": "",
                "適合投標": "",
                "建議行動": "",
                "匹配能力": "",
                "判斷理由": "",
            }

            if evaluation:
                row["相關度"] = str(evaluation.relevance_score)
                row["適合投標"] = "是" if evaluation.suitable else "否"
                row["建議行動"] = _ACTION_LABELS.get(
                    evaluation.recommended_action, evaluation.recommended_action
                )
                row["匹配能力"] = ", ".join(evaluation.matched_capabilities)
                row["判斷理由"] = evaluation.reasoning

            writer.writerow(row)

    console.print(f"[green]已匯出 {len(tenders)} 筆標案至 {output_path}[/green]")


if __name__ == "__main__":
    cli()
