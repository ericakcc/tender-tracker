"""Abstract base class for LLM backends."""

from abc import ABC, abstractmethod

from tender_tracker.models import Tender, TenderEvaluation


class LLMBackend(ABC):
    """Abstract interface for LLM-powered tender evaluation backends.

    This abstraction allows swapping between different LLM providers
    (vLLM, Claude, etc.) without changing the evaluator logic.
    """

    @abstractmethod
    async def evaluate(self, tender: Tender) -> TenderEvaluation:
        """Evaluate a single tender and return structured evaluation result.

        Args:
            tender: The tender to evaluate.

        Returns:
            Structured evaluation result with relevance score and recommendation.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Clean up resources (e.g., close HTTP clients)."""
        ...
