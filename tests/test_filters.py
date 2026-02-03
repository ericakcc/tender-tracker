"""Tests for the tender filter engine."""

from tender_tracker.config import AppConfig, BudgetConfig
from tender_tracker.filters import TenderFilter
from tender_tracker.models import Tender


class TestTenderFilter:
    """Tests for TenderFilter multi-criteria filtering."""

    def test_keyword_filter_matches_title(
        self, test_config: AppConfig, sample_tenders: list[Tender]
    ) -> None:
        f = TenderFilter(test_config)
        results = f.keyword_filter(sample_tenders)
        titles = [t.title for t in results]
        assert "AI 智慧客服系統建置案" in titles
        assert "辦公室桌椅採購" not in titles

    def test_keyword_filter_matches_multiple(
        self, test_config: AppConfig, sample_tenders: list[Tender]
    ) -> None:
        f = TenderFilter(test_config)
        results = f.keyword_filter(sample_tenders)
        # Should match AI, 大型語言模型, 機器學習, 雲端, 電腦視覺
        assert len(results) >= 5

    def test_full_filter_excludes_over_budget(
        self, test_config: AppConfig, sample_tenders: list[Tender]
    ) -> None:
        f = TenderFilter(test_config)
        results = f.filter(sample_tenders)
        # T-004 has budget 10M which exceeds max 3M
        ids = [t.tender_id for t in results]
        assert "T-004" not in ids

    def test_full_filter_excludes_non_service(
        self, test_config: AppConfig, sample_tenders: list[Tender]
    ) -> None:
        f = TenderFilter(test_config)
        results = f.filter(sample_tenders)
        # T-005 is 工程 type, should be excluded
        ids = [t.tender_id for t in results]
        assert "T-005" not in ids

    def test_full_filter_includes_no_budget(
        self, test_config: AppConfig, sample_tenders: list[Tender]
    ) -> None:
        f = TenderFilter(test_config)
        results = f.filter(sample_tenders)
        # T-007 has no budget, should be included (keyword + type match)
        ids = [t.tender_id for t in results]
        assert "T-007" in ids

    def test_empty_keywords_matches_all(self, sample_tenders: list[Tender]) -> None:
        config = AppConfig(
            keywords=[],
            procurement_types=[],
            budget=BudgetConfig(min=0, max=999_999_999),
        )
        f = TenderFilter(config)
        results = f.filter(sample_tenders)
        assert len(results) == len(sample_tenders)

    def test_filter_combined_criteria(
        self, test_config: AppConfig, sample_tenders: list[Tender]
    ) -> None:
        f = TenderFilter(test_config)
        results = f.filter(sample_tenders)

        for t in results:
            # All results should have matching keywords
            text = f"{t.title} {t.category}".lower()
            assert any(kw.lower() in text for kw in test_config.keywords), (
                f"Tender {t.tender_id} doesn't match any keyword"
            )

            # Budget should be in range or None
            if t.budget_amount is not None:
                assert t.budget_amount <= test_config.budget.max
                assert t.budget_amount >= test_config.budget.min

    def test_filter_budget_range_edge_cases(self) -> None:
        config = AppConfig(
            keywords=["test"],
            budget=BudgetConfig(min=100, max=200),
            procurement_types=[],
        )
        f = TenderFilter(config)

        tenders = [
            Tender(tender_id="1", title="test A", budget_amount=99, source="test"),
            Tender(tender_id="2", title="test B", budget_amount=100, source="test"),
            Tender(tender_id="3", title="test C", budget_amount=150, source="test"),
            Tender(tender_id="4", title="test D", budget_amount=200, source="test"),
            Tender(tender_id="5", title="test E", budget_amount=201, source="test"),
        ]
        results = f.filter(tenders)
        ids = [t.tender_id for t in results]
        assert "1" not in ids  # Below min
        assert "2" in ids  # At min
        assert "3" in ids  # In range
        assert "4" in ids  # At max
        assert "5" not in ids  # Above max
