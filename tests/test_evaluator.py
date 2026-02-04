"""Tests for the AI evaluator module."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from claude_agent_sdk import ResultMessage

from tender_tracker.evaluator import TenderEvaluator
from tender_tracker.models import Tender, TenderEvaluation


def _make_result_message(structured_output: dict[str, Any] | None) -> ResultMessage:
    """Create a ResultMessage with structured_output."""
    return ResultMessage(
        subtype="success",
        duration_ms=100,
        duration_api_ms=80,
        is_error=False,
        num_turns=1,
        session_id="test-session",
        structured_output=structured_output,
    )


async def _mock_query_factory(structured_output: dict[str, Any] | None):
    """Create an async generator that yields a ResultMessage."""
    yield _make_result_message(structured_output)


class TestTenderEvaluator:
    """Tests for TenderEvaluator with mocked Claude Agent SDK."""

    @patch("tender_tracker.evaluator.query")
    @pytest.mark.asyncio
    async def test_evaluate_suitable_tender(self, mock_query: MagicMock) -> None:
        eval_data = {
            "suitable": True,
            "relevance_score": 0.85,
            "reasoning": "AI 客服系統與團隊 NLP/LLM 能力高度匹配",
            "recommended_action": "bid",
            "matched_capabilities": ["LLM 應用", "NLP", "全端開發"],
        }

        mock_query.return_value = _mock_query_factory(eval_data)

        evaluator = TenderEvaluator()
        tender = Tender(
            tender_id="T-001",
            title="AI 智慧客服系統建置案",
            org_name="數位發展部",
            procurement_type="勞務",
            budget_amount=500_000,
            source="mlwmlw",
        )

        result = await evaluator.evaluate(tender)

        assert isinstance(result, TenderEvaluation)
        assert result.suitable is True
        assert result.relevance_score == 0.85
        assert result.recommended_action == "bid"
        assert "LLM 應用" in result.matched_capabilities

    @patch("tender_tracker.evaluator.query")
    @pytest.mark.asyncio
    async def test_evaluate_unsuitable_tender(self, mock_query: MagicMock) -> None:
        eval_data = {
            "suitable": False,
            "relevance_score": 0.1,
            "reasoning": "辦公家具採購與團隊技術能力無關",
            "recommended_action": "skip",
            "matched_capabilities": [],
        }

        mock_query.return_value = _mock_query_factory(eval_data)

        evaluator = TenderEvaluator()
        tender = Tender(
            tender_id="T-002",
            title="辦公室桌椅採購",
            org_name="內政部",
            procurement_type="財物",
            budget_amount=200_000,
            source="mlwmlw",
        )

        result = await evaluator.evaluate(tender)

        assert result.suitable is False
        assert result.relevance_score == 0.1
        assert result.recommended_action == "skip"

    @patch("tender_tracker.evaluator.query")
    @pytest.mark.asyncio
    async def test_evaluate_no_structured_output_fallback(self, mock_query: MagicMock) -> None:
        mock_query.return_value = _mock_query_factory(None)

        evaluator = TenderEvaluator()
        tender = Tender(
            tender_id="T-003",
            title="Test",
            source="mlwmlw",
        )

        result = await evaluator.evaluate(tender)
        assert result.suitable is False
        assert result.relevance_score == 0.0
        assert result.recommended_action == "skip"

    @patch("tender_tracker.evaluator.query")
    @pytest.mark.asyncio
    async def test_evaluate_batch(self, mock_query: MagicMock) -> None:
        eval_data = {
            "suitable": True,
            "relevance_score": 0.7,
            "reasoning": "test",
            "recommended_action": "bid",
            "matched_capabilities": [],
        }

        mock_query.return_value = _mock_query_factory(eval_data)

        evaluator = TenderEvaluator()
        tenders = [
            Tender(tender_id="T-001", title="AI test 1", source="mlwmlw"),
            Tender(tender_id="T-002", title="AI test 2", source="mlwmlw"),
        ]

        # Mock query to return fresh generator each call
        mock_query.side_effect = lambda **kwargs: _mock_query_factory(eval_data)

        results = await evaluator.evaluate_batch(tenders)
        assert len(results) == 2
        for tender, evaluation in results:
            assert isinstance(evaluation, TenderEvaluation)

    @patch("tender_tracker.evaluator.query")
    @pytest.mark.asyncio
    async def test_evaluate_batch_handles_errors(self, mock_query: MagicMock) -> None:
        mock_query.side_effect = Exception("SDK Error")

        evaluator = TenderEvaluator()
        tenders = [Tender(tender_id="T-001", title="Test", source="mlwmlw")]

        results = await evaluator.evaluate_batch(tenders)
        assert len(results) == 1
        _, evaluation = results[0]
        assert evaluation.suitable is False
        assert evaluation.recommended_action == "review_further"
