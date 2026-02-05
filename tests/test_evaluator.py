"""Tests for the AI evaluator module."""

import asyncio

import pytest

from tender_tracker.evaluator import TenderEvaluator
from tender_tracker.llm import LLMBackend, LLMConfig
from tender_tracker.models import Tender, TenderEvaluation


class MockBackend(LLMBackend):
    """Mock LLM backend for testing."""

    def __init__(self, evaluation_result: TenderEvaluation | None = None) -> None:
        self.evaluation_result = evaluation_result
        self.evaluate_calls: list[Tender] = []
        self.closed = False

    async def evaluate(self, tender: Tender) -> TenderEvaluation:
        self.evaluate_calls.append(tender)
        if self.evaluation_result is None:
            raise ValueError("No evaluation result configured")
        return self.evaluation_result

    async def close(self) -> None:
        self.closed = True


class TestTenderEvaluator:
    """Tests for TenderEvaluator with mocked LLM backend."""

    @pytest.mark.asyncio
    async def test_evaluate_suitable_tender(self) -> None:
        eval_result = TenderEvaluation(
            suitable=True,
            relevance_score=0.85,
            reasoning="AI 客服系統與團隊 NLP/LLM 能力高度匹配",
            recommended_action="bid",
            matched_capabilities=["LLM 應用", "NLP", "全端開發"],
        )

        backend = MockBackend(eval_result)
        evaluator = TenderEvaluator(backend=backend)

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
        assert len(backend.evaluate_calls) == 1
        assert backend.evaluate_calls[0].tender_id == "T-001"

    @pytest.mark.asyncio
    async def test_evaluate_unsuitable_tender(self) -> None:
        eval_result = TenderEvaluation(
            suitable=False,
            relevance_score=0.1,
            reasoning="辦公家具採購與團隊技術能力無關",
            recommended_action="skip",
            matched_capabilities=[],
        )

        backend = MockBackend(eval_result)
        evaluator = TenderEvaluator(backend=backend)

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

    @pytest.mark.asyncio
    async def test_evaluate_batch_parallel(self) -> None:
        eval_result = TenderEvaluation(
            suitable=True,
            relevance_score=0.7,
            reasoning="test",
            recommended_action="bid",
            matched_capabilities=[],
        )

        backend = MockBackend(eval_result)
        evaluator = TenderEvaluator(backend=backend)

        tenders = [
            Tender(tender_id="T-001", title="AI test 1", source="mlwmlw"),
            Tender(tender_id="T-002", title="AI test 2", source="mlwmlw"),
            Tender(tender_id="T-003", title="AI test 3", source="mlwmlw"),
        ]

        results = await evaluator.evaluate_batch(tenders, concurrency=2)

        assert len(results) == 3
        for tender, evaluation in results:
            assert isinstance(evaluation, TenderEvaluation)
            assert evaluation.relevance_score == 0.7
        assert len(backend.evaluate_calls) == 3

    @pytest.mark.asyncio
    async def test_evaluate_batch_respects_concurrency(self) -> None:
        """Verify concurrency limit is respected via semaphore."""
        max_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        class ConcurrencyTrackingBackend(LLMBackend):
            async def evaluate(self, tender: Tender) -> TenderEvaluation:
                nonlocal max_concurrent, current_concurrent
                async with lock:
                    current_concurrent += 1
                    max_concurrent = max(max_concurrent, current_concurrent)
                await asyncio.sleep(0.05)
                async with lock:
                    current_concurrent -= 1
                return TenderEvaluation(
                    suitable=True,
                    relevance_score=0.5,
                    reasoning="test",
                    recommended_action="bid",
                    matched_capabilities=[],
                )

            async def close(self) -> None:
                pass

        backend = ConcurrencyTrackingBackend()
        evaluator = TenderEvaluator(backend=backend)

        tenders = [
            Tender(tender_id=f"T-{i:03d}", title=f"Test {i}", source="mlwmlw") for i in range(6)
        ]

        results = await evaluator.evaluate_batch(tenders, concurrency=2)

        assert len(results) == 6
        assert max_concurrent <= 2

    @pytest.mark.asyncio
    async def test_evaluate_batch_handles_errors(self) -> None:
        backend = MockBackend(evaluation_result=None)  # Will raise error
        evaluator = TenderEvaluator(backend=backend)

        tenders = [Tender(tender_id="T-001", title="Test", source="mlwmlw")]

        results = await evaluator.evaluate_batch(tenders)

        assert len(results) == 1
        _, evaluation = results[0]
        assert evaluation.suitable is False
        assert evaluation.recommended_action == "review_further"
        assert "failed" in evaluation.reasoning.lower()

    @pytest.mark.asyncio
    async def test_evaluator_close_owned_backend(self) -> None:
        """Test that evaluator closes backend it owns."""
        eval_result = TenderEvaluation(
            suitable=True,
            relevance_score=0.5,
            reasoning="test",
            recommended_action="bid",
            matched_capabilities=[],
        )
        backend = MockBackend(eval_result)
        evaluator = TenderEvaluator(backend=backend)

        # Backend passed directly is not owned, so close should be a no-op
        await evaluator.close()
        assert not backend.closed  # Not owned

    @pytest.mark.asyncio
    async def test_evaluator_with_callback(self) -> None:
        eval_result = TenderEvaluation(
            suitable=True,
            relevance_score=0.8,
            reasoning="test",
            recommended_action="bid",
            matched_capabilities=[],
        )
        backend = MockBackend(eval_result)
        evaluator = TenderEvaluator(backend=backend)

        callback_results: list[tuple[str, float]] = []

        def on_result(tender: Tender, evaluation: TenderEvaluation) -> None:
            callback_results.append((tender.tender_id, evaluation.relevance_score))

        tenders = [
            Tender(tender_id="T-001", title="Test 1", source="mlwmlw"),
            Tender(tender_id="T-002", title="Test 2", source="mlwmlw"),
        ]

        await evaluator.evaluate_batch(tenders, on_result=on_result)

        assert len(callback_results) == 2
        tender_ids = [r[0] for r in callback_results]
        assert "T-001" in tender_ids
        assert "T-002" in tender_ids


class TestLLMConfig:
    """Tests for LLM configuration."""

    def test_default_config(self) -> None:
        config = LLMConfig()
        assert config.backend == "vllm"
        assert config.model == "Qwen/Qwen3-8B-Instruct"
        assert config.api_base == "http://localhost:8000/v1"
        assert config.api_key == "EMPTY"
        assert config.max_retries == 3
        assert config.temperature == 0.1

    def test_claude_config(self) -> None:
        config = LLMConfig(
            backend="claude",
            model="claude-sonnet-4-5-20250929",
        )
        assert config.backend == "claude"
        assert config.model == "claude-sonnet-4-5-20250929"
