"""Tests for the CSV export command."""

import csv
from datetime import datetime
from pathlib import Path

from click.testing import CliRunner

from tender_tracker.main import cli
from tender_tracker.models import Tender, TenderEvaluation
from tender_tracker.storage import TenderStorage

EXPECTED_HEADERS = [
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


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Read CSV file and return (headers, rows)."""
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        rows = list(reader)
    return list(headers), rows


class TestExportCommand:
    """Tests for the 'export' CLI command."""

    def test_export_basic_csv(
        self, tmp_db: TenderStorage, sample_tender: Tender, tmp_path: Path
    ) -> None:
        """Basic export produces correct CSV headers and row data."""
        tmp_db.upsert_tender(sample_tender)
        output_path = tmp_path / "out.csv"

        runner = CliRunner()
        result = runner.invoke(
            cli, ["--db", str(tmp_db._db_path), "export", "-o", str(output_path)]
        )

        assert result.exit_code == 0
        assert output_path.exists()

        headers, rows = _read_csv(output_path)
        assert headers == EXPECTED_HEADERS
        assert len(rows) == 1

        row = rows[0]
        assert row["案號"] == sample_tender.tender_id
        assert row["名稱"] == sample_tender.title
        assert row["招標機關"] == sample_tender.org_name
        assert row["採購類別"] == sample_tender.procurement_type
        assert row["資料來源"] == sample_tender.source
        # Evaluation fields should be empty
        assert row["相關度"] == ""
        assert row["適合投標"] == ""
        assert row["建議行動"] == ""
        assert row["匹配能力"] == ""
        assert row["判斷理由"] == ""

    def test_export_with_evaluation(
        self, tmp_db: TenderStorage, sample_tender: Tender, tmp_path: Path
    ) -> None:
        """Export includes AI evaluation data when available."""
        tmp_db.upsert_tender(sample_tender)
        evaluation = TenderEvaluation(
            suitable=True,
            relevance_score=0.85,
            reasoning="AI 客服系統與團隊能力高度匹配",
            recommended_action="bid",
            matched_capabilities=["AI/ML", "全端開發"],
        )
        tmp_db.save_evaluation(sample_tender.tender_id, evaluation)

        output_path = tmp_path / "out.csv"
        runner = CliRunner()
        result = runner.invoke(
            cli, ["--db", str(tmp_db._db_path), "export", "-o", str(output_path)]
        )

        assert result.exit_code == 0

        _, rows = _read_csv(output_path)
        assert len(rows) == 1

        row = rows[0]
        assert row["相關度"] == "0.85"
        assert row["適合投標"] == "是"
        assert row["建議行動"] == "建議投標"
        assert row["匹配能力"] == "AI/ML, 全端開發"
        assert row["判斷理由"] == "AI 客服系統與團隊能力高度匹配"

    def test_export_empty_db(self, tmp_db: TenderStorage, tmp_path: Path) -> None:
        """Export with empty DB produces CSV with headers only."""
        output_path = tmp_path / "out.csv"

        runner = CliRunner()
        result = runner.invoke(
            cli, ["--db", str(tmp_db._db_path), "export", "-o", str(output_path)]
        )

        assert result.exit_code == 0
        assert output_path.exists()

        headers, rows = _read_csv(output_path)
        assert headers == EXPECTED_HEADERS
        assert len(rows) == 0

    def test_export_days_filter(self, tmp_db: TenderStorage, tmp_path: Path) -> None:
        """--days filter only exports recent tenders."""
        # Recent tender
        recent = Tender(
            tender_id="RECENT-001",
            title="Recent tender",
            source="mlwmlw",
            fetched_at=datetime.now(),
        )
        # Old tender (fetched_at far in the past)
        old = Tender(
            tender_id="OLD-001",
            title="Old tender",
            source="mlwmlw",
            fetched_at=datetime(2020, 1, 1),
        )
        tmp_db.upsert_tender(recent)
        tmp_db.upsert_tender(old)

        output_path = tmp_path / "out.csv"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--db", str(tmp_db._db_path), "export", "-o", str(output_path), "--days", "7"],
        )

        assert result.exit_code == 0
        _, rows = _read_csv(output_path)
        assert len(rows) == 1
        assert rows[0]["案號"] == "RECENT-001"

    def test_export_evaluated_filter(
        self, tmp_db: TenderStorage, sample_tenders: list[Tender], tmp_path: Path
    ) -> None:
        """--evaluated filter only exports tenders with evaluations."""
        tmp_db.upsert_tenders(sample_tenders)

        # Evaluate only the first tender
        evaluation = TenderEvaluation(
            suitable=False,
            relevance_score=0.3,
            reasoning="不太相關",
            recommended_action="skip",
            matched_capabilities=[],
        )
        tmp_db.save_evaluation(sample_tenders[0].tender_id, evaluation)

        output_path = tmp_path / "out.csv"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--db", str(tmp_db._db_path), "export", "-o", str(output_path), "--evaluated"],
        )

        assert result.exit_code == 0
        _, rows = _read_csv(output_path)
        assert len(rows) == 1
        assert rows[0]["案號"] == sample_tenders[0].tender_id

    def test_export_utf8_bom(
        self, tmp_db: TenderStorage, sample_tender: Tender, tmp_path: Path
    ) -> None:
        """CSV file starts with UTF-8 BOM for Excel compatibility."""
        tmp_db.upsert_tender(sample_tender)
        output_path = tmp_path / "out.csv"

        runner = CliRunner()
        runner.invoke(cli, ["--db", str(tmp_db._db_path), "export", "-o", str(output_path)])

        raw = output_path.read_bytes()
        assert raw[:3] == b"\xef\xbb\xbf"

    def test_export_recommended_action_labels(self, tmp_db: TenderStorage, tmp_path: Path) -> None:
        """RecommendedAction enum values are mapped to Chinese labels."""
        tenders_and_actions = [
            ("ACT-001", "bid", "建議投標"),
            ("ACT-002", "skip", "略過"),
            ("ACT-003", "review_further", "需進一步評估"),
        ]
        for tender_id, action, _ in tenders_and_actions:
            tender = Tender(tender_id=tender_id, title=f"Test {tender_id}", source="mlwmlw")
            tmp_db.upsert_tender(tender)
            evaluation = TenderEvaluation(
                suitable=True,
                relevance_score=0.5,
                reasoning="test",
                recommended_action=action,
                matched_capabilities=[],
            )
            tmp_db.save_evaluation(tender_id, evaluation)

        output_path = tmp_path / "out.csv"
        runner = CliRunner()
        runner.invoke(cli, ["--db", str(tmp_db._db_path), "export", "-o", str(output_path)])

        _, rows = _read_csv(output_path)
        by_id = {r["案號"]: r for r in rows}

        for tender_id, _, expected_label in tenders_and_actions:
            assert by_id[tender_id]["建議行動"] == expected_label
