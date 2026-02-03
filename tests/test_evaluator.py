"""Tests for the AI evaluator module."""

from unittest.mock import MagicMock, patch

from tender_tracker.evaluator import TenderEvaluator
from tender_tracker.models import Tender, TenderEvaluation


class TestTenderEvaluator:
    """Tests for TenderEvaluator with mocked Claude API."""

    def _make_mock_response(self, evaluation_data: dict) -> MagicMock:
        """Create a mock Claude API response with tool_use."""
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.name = "submit_evaluation"
        tool_block.input = evaluation_data

        response = MagicMock()
        response.content = [tool_block]
        return response

    @patch("tender_tracker.evaluator.anthropic.Anthropic")
    def test_evaluate_suitable_tender(self, mock_anthropic_cls: MagicMock) -> None:
        eval_data = {
            "suitable": True,
            "relevance_score": 0.85,
            "reasoning": "AI 客服系統與團隊 NLP/LLM 能力高度匹配",
            "recommended_action": "bid",
            "matched_capabilities": ["LLM 應用", "NLP", "全端開發"],
        }

        mock_client = MagicMock()
        mock_client.messages.create.return_value = self._make_mock_response(eval_data)
        mock_anthropic_cls.return_value = mock_client

        evaluator = TenderEvaluator()
        tender = Tender(
            tender_id="T-001",
            title="AI 智慧客服系統建置案",
            org_name="數位發展部",
            procurement_type="勞務",
            budget_amount=500_000,
            source="mlwmlw",
        )

        result = evaluator.evaluate(tender)

        assert isinstance(result, TenderEvaluation)
        assert result.suitable is True
        assert result.relevance_score == 0.85
        assert result.recommended_action == "bid"
        assert "LLM 應用" in result.matched_capabilities

    @patch("tender_tracker.evaluator.anthropic.Anthropic")
    def test_evaluate_unsuitable_tender(self, mock_anthropic_cls: MagicMock) -> None:
        eval_data = {
            "suitable": False,
            "relevance_score": 0.1,
            "reasoning": "辦公家具採購與團隊技術能力無關",
            "recommended_action": "skip",
            "matched_capabilities": [],
        }

        mock_client = MagicMock()
        mock_client.messages.create.return_value = self._make_mock_response(eval_data)
        mock_anthropic_cls.return_value = mock_client

        evaluator = TenderEvaluator()
        tender = Tender(
            tender_id="T-002",
            title="辦公室桌椅採購",
            org_name="內政部",
            procurement_type="財物",
            budget_amount=200_000,
            source="mlwmlw",
        )

        result = evaluator.evaluate(tender)

        assert result.suitable is False
        assert result.relevance_score == 0.1
        assert result.recommended_action == "skip"

    @patch("tender_tracker.evaluator.anthropic.Anthropic")
    def test_evaluate_no_tool_use_fallback(self, mock_anthropic_cls: MagicMock) -> None:
        text_block = MagicMock()
        text_block.type = "text"

        response = MagicMock()
        response.content = [text_block]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = response
        mock_anthropic_cls.return_value = mock_client

        evaluator = TenderEvaluator()
        tender = Tender(
            tender_id="T-003",
            title="Test",
            source="mlwmlw",
        )

        result = evaluator.evaluate(tender)
        assert result.suitable is False
        assert result.relevance_score == 0.0
        assert result.recommended_action == "skip"

    @patch("tender_tracker.evaluator.anthropic.Anthropic")
    def test_evaluate_batch(self, mock_anthropic_cls: MagicMock) -> None:
        eval_data = {
            "suitable": True,
            "relevance_score": 0.7,
            "reasoning": "test",
            "recommended_action": "bid",
            "matched_capabilities": [],
        }

        mock_client = MagicMock()
        mock_client.messages.create.return_value = self._make_mock_response(eval_data)
        mock_anthropic_cls.return_value = mock_client

        evaluator = TenderEvaluator()
        tenders = [
            Tender(tender_id="T-001", title="AI test 1", source="mlwmlw"),
            Tender(tender_id="T-002", title="AI test 2", source="mlwmlw"),
        ]

        results = evaluator.evaluate_batch(tenders)
        assert len(results) == 2
        for tender, evaluation in results:
            assert isinstance(evaluation, TenderEvaluation)

    @patch("tender_tracker.evaluator.anthropic.Anthropic")
    def test_evaluate_batch_handles_errors(self, mock_anthropic_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API Error")
        mock_anthropic_cls.return_value = mock_client

        evaluator = TenderEvaluator()
        tenders = [Tender(tender_id="T-001", title="Test", source="mlwmlw")]

        results = evaluator.evaluate_batch(tenders)
        assert len(results) == 1
        _, evaluation = results[0]
        assert evaluation.suitable is False
        assert evaluation.recommended_action == "review_further"
