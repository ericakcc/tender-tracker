"""Shared test fixtures."""

from datetime import datetime
from pathlib import Path

import pytest

from tender_tracker.config import AppConfig, BudgetConfig
from tender_tracker.models import Tender
from tender_tracker.storage import TenderStorage


@pytest.fixture
def sample_tender() -> Tender:
    """A sample AI-related tender."""
    return Tender(
        tender_id="TEST-2026-001",
        title="AI 智慧客服系統建置案",
        org_name="數位發展部",
        procurement_type="勞務",
        tender_method="公開招標",
        budget_amount=500_000.0,
        deadline=datetime(2026, 3, 1),
        open_date=datetime(2026, 3, 15),
        url="https://example.com/tender/001",
        category="資訊服務",
        source="mlwmlw",
        publish_date=datetime(2026, 1, 15),
        fetched_at=datetime(2026, 2, 1),
    )


@pytest.fixture
def sample_tenders() -> list[Tender]:
    """A collection of diverse sample tenders for filter testing."""
    return [
        Tender(
            tender_id="T-001",
            title="AI 智慧客服系統建置案",
            org_name="數位發展部",
            procurement_type="勞務",
            budget_amount=500_000.0,
            source="mlwmlw",
        ),
        Tender(
            tender_id="T-002",
            title="辦公室桌椅採購",
            org_name="內政部",
            procurement_type="財物",
            budget_amount=200_000.0,
            source="mlwmlw",
        ),
        Tender(
            tender_id="T-003",
            title="大型語言模型應用開發案",
            org_name="國家科學及技術委員會",
            procurement_type="勞務",
            budget_amount=2_000_000.0,
            source="mlwmlw",
        ),
        Tender(
            tender_id="T-004",
            title="機器學習資料分析平台",
            org_name="台北市政府",
            procurement_type="勞務",
            budget_amount=10_000_000.0,  # Over budget max
            source="mlwmlw",
        ),
        Tender(
            tender_id="T-005",
            title="道路修繕工程",
            org_name="桃園市政府",
            procurement_type="工程",
            budget_amount=5_000_000.0,
            source="mlwmlw",
        ),
        Tender(
            tender_id="T-006",
            title="雲端服務平台建置",
            org_name="經濟部",
            procurement_type="勞務",
            budget_amount=1_500_000.0,
            source="mlwmlw",
        ),
        Tender(
            tender_id="T-007",
            title="電腦視覺影像辨識系統",
            org_name="國防部",
            procurement_type="勞務",
            budget_amount=None,  # No budget info
            source="mlwmlw",
        ),
    ]


@pytest.fixture
def test_config() -> AppConfig:
    """Test configuration."""
    return AppConfig(
        keywords=["AI", "人工智慧", "機器學習", "大型語言模型", "雲端", "電腦視覺"],
        orgs=["數位發展部", "國家科學及技術委員會"],
        budget=BudgetConfig(min=150_000, max=3_000_000),
        procurement_types=["勞務"],
    )


@pytest.fixture
def tmp_db(tmp_path: Path) -> TenderStorage:
    """A temporary SQLite database for testing."""
    storage = TenderStorage(tmp_path / "test.db")
    storage.init_db()
    yield storage
    storage.close()
