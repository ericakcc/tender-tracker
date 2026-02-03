"""Tests for the SQLite storage layer."""

from tender_tracker.models import Tender, TenderEvaluation
from tender_tracker.storage import TenderStorage


class TestTenderStorage:
    """Tests for TenderStorage CRUD operations."""

    def test_upsert_tender_insert(self, tmp_db: TenderStorage, sample_tender: Tender) -> None:
        is_new = tmp_db.upsert_tender(sample_tender)
        assert is_new is True

    def test_upsert_tender_update(self, tmp_db: TenderStorage, sample_tender: Tender) -> None:
        tmp_db.upsert_tender(sample_tender)
        is_new = tmp_db.upsert_tender(sample_tender)
        assert is_new is False

    def test_get_tender_found(self, tmp_db: TenderStorage, sample_tender: Tender) -> None:
        tmp_db.upsert_tender(sample_tender)
        result = tmp_db.get_tender(sample_tender.tender_id)
        assert result is not None
        assert result.tender_id == sample_tender.tender_id
        assert result.title == sample_tender.title

    def test_get_tender_not_found(self, tmp_db: TenderStorage) -> None:
        result = tmp_db.get_tender("NONEXISTENT")
        assert result is None

    def test_upsert_tenders_batch(
        self, tmp_db: TenderStorage, sample_tenders: list[Tender]
    ) -> None:
        new_count = tmp_db.upsert_tenders(sample_tenders)
        assert new_count == len(sample_tenders)

        # Second upsert should return 0 new
        new_count = tmp_db.upsert_tenders(sample_tenders)
        assert new_count == 0

    def test_list_tenders(self, tmp_db: TenderStorage, sample_tenders: list[Tender]) -> None:
        tmp_db.upsert_tenders(sample_tenders)
        results = tmp_db.list_tenders()
        assert len(results) == len(sample_tenders)

    def test_list_tenders_with_limit(
        self, tmp_db: TenderStorage, sample_tenders: list[Tender]
    ) -> None:
        tmp_db.upsert_tenders(sample_tenders)
        results = tmp_db.list_tenders(limit=3)
        assert len(results) == 3

    def test_list_tenders_with_days(
        self, tmp_db: TenderStorage, sample_tenders: list[Tender]
    ) -> None:
        tmp_db.upsert_tenders(sample_tenders)
        results = tmp_db.list_tenders(days=1)
        # All sample tenders have fetched_at = now, so they should all match
        assert len(results) == len(sample_tenders)

    def test_save_and_get_evaluation(self, tmp_db: TenderStorage, sample_tender: Tender) -> None:
        tmp_db.upsert_tender(sample_tender)

        evaluation = TenderEvaluation(
            suitable=True,
            relevance_score=0.85,
            reasoning="AI 客服系統與團隊 NLP/LLM 能力高度匹配",
            recommended_action="bid",
            matched_capabilities=["LLM 應用", "NLP", "全端開發"],
        )
        tmp_db.save_evaluation(sample_tender.tender_id, evaluation)

        result = tmp_db.get_evaluation(sample_tender.tender_id)
        assert result is not None
        assert result.suitable is True
        assert result.relevance_score == 0.85
        assert result.recommended_action == "bid"
        assert "LLM 應用" in result.matched_capabilities

    def test_get_evaluation_not_found(self, tmp_db: TenderStorage) -> None:
        result = tmp_db.get_evaluation("NONEXISTENT")
        assert result is None

    def test_get_unevaluated_tender_ids(
        self, tmp_db: TenderStorage, sample_tenders: list[Tender]
    ) -> None:
        tmp_db.upsert_tenders(sample_tenders)

        # All should be unevaluated
        unevaluated = tmp_db.get_unevaluated_tender_ids()
        assert len(unevaluated) == len(sample_tenders)

        # Evaluate one
        evaluation = TenderEvaluation(
            suitable=True,
            relevance_score=0.9,
            reasoning="test",
            recommended_action="bid",
            matched_capabilities=[],
        )
        tmp_db.save_evaluation(sample_tenders[0].tender_id, evaluation)

        unevaluated = tmp_db.get_unevaluated_tender_ids()
        assert len(unevaluated) == len(sample_tenders) - 1

    def test_log_sync(self, tmp_db: TenderStorage) -> None:
        tmp_db.log_sync("mlwmlw", 42, "success")
        # No assertion on return, just verify no error

    def test_get_stats(self, tmp_db: TenderStorage, sample_tenders: list[Tender]) -> None:
        tmp_db.upsert_tenders(sample_tenders)

        stats = tmp_db.get_stats()
        assert stats["total_tenders"] == len(sample_tenders)
        assert stats["evaluated"] == 0
        assert stats["suitable"] == 0
        assert stats["unevaluated"] == len(sample_tenders)

    def test_get_stats_empty(self, tmp_db: TenderStorage) -> None:
        stats = tmp_db.get_stats()
        assert stats["total_tenders"] == 0
