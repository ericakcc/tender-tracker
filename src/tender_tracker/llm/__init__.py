"""LLM backend abstraction layer for pluggable model providers.

This module provides a unified interface for LLM-powered tender evaluation,
supporting both local vLLM deployment and Claude API as backends.

Example usage:
    from tender_tracker.llm import LLMConfig, get_backend

    config = LLMConfig(backend="vllm", model="Qwen/Qwen3-8B-Instruct")
    backend = get_backend(config)

    evaluation = await backend.evaluate(tender)
    await backend.close()
"""

from tender_tracker.llm.base import LLMBackend
from tender_tracker.llm.config import LLMConfig

__all__ = ["LLMBackend", "LLMConfig", "get_backend"]


def get_backend(config: LLMConfig) -> LLMBackend:
    """Factory function to create the appropriate LLM backend.

    Args:
        config: LLM configuration specifying backend type and parameters.

    Returns:
        An LLMBackend instance configured according to the provided config.

    Raises:
        ValueError: If an unknown backend type is specified.
    """
    if config.backend == "claude":
        from tender_tracker.llm.claude_backend import ClaudeBackend

        return ClaudeBackend(config)
    elif config.backend == "vllm":
        from tender_tracker.llm.vllm_backend import VLLMBackend

        return VLLMBackend(config)
    else:
        raise ValueError(f"Unknown LLM backend: {config.backend}")
