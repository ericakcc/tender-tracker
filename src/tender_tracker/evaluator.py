"""AI-powered tender evaluation using pluggable LLM backends."""

import asyncio
from collections.abc import Callable

from loguru import logger

from tender_tracker.llm import LLMBackend, LLMConfig, get_backend
from tender_tracker.models import Tender, TenderEvaluation


class TenderEvaluator:
    """LLM-powered tender evaluation engine with pluggable backends.

    Supports both local vLLM deployment and Claude API through the
    LLMBackend abstraction layer.
    """

    def __init__(
        self,
        backend: LLMBackend | None = None,
        config: LLMConfig | None = None,
    ) -> None:
        """Initialize the evaluator with an LLM backend.

        Args:
            backend: Pre-configured LLMBackend instance. If provided, config is ignored.
            config: LLMConfig for creating a new backend. Uses default vLLM config if None.
        """
        if backend is not None:
            self._backend = backend
            self._owns_backend = False
        else:
            self._backend = get_backend(config or LLMConfig())
            self._owns_backend = True

    @property
    def backend(self) -> LLMBackend:
        """Get the underlying LLM backend."""
        return self._backend

    async def evaluate(self, tender: Tender) -> TenderEvaluation:
        """Evaluate a single tender using the configured LLM backend.

        Args:
            tender: The tender to evaluate.

        Returns:
            Structured evaluation result.
        """
        return await self._backend.evaluate(tender)

    async def evaluate_batch(
        self,
        tenders: list[Tender],
        concurrency: int = 20,
        on_result: Callable[[Tender, TenderEvaluation], None] | None = None,
    ) -> list[tuple[Tender, TenderEvaluation]]:
        """Evaluate multiple tenders in parallel.

        Args:
            tenders: List of tenders to evaluate.
            concurrency: Max number of parallel evaluations.
            on_result: Optional callback invoked after each evaluation completes.

        Returns:
            List of (tender, evaluation) tuples.
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def _eval(tender: Tender) -> tuple[Tender, TenderEvaluation]:
            async with semaphore:
                try:
                    evaluation = await self.evaluate(tender)
                    result = (tender, evaluation)
                except Exception as e:
                    logger.error("Failed to evaluate {}: {}", tender.tender_id, e)
                    fallback = TenderEvaluation(
                        suitable=False,
                        relevance_score=0.0,
                        reasoning=f"Evaluation failed: {e}",
                        recommended_action="review_further",
                        matched_capabilities=[],
                    )
                    result = (tender, fallback)
                if on_result:
                    on_result(*result)
                return result

        results = await asyncio.gather(*[_eval(t) for t in tenders])
        return list(results)

    async def close(self) -> None:
        """Close the underlying backend if owned by this evaluator."""
        if self._owns_backend:
            await self._backend.close()
