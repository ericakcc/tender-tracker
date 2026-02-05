"""LLM backend configuration models."""

from typing import Literal

from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    """Configuration for LLM backend selection and parameters."""

    backend: Literal["vllm", "claude"] = Field(
        default="vllm",
        description="LLM backend to use: 'vllm' for local vLLM server, 'claude' for Claude API",
    )
    model: str = Field(
        default="Qwen/Qwen3-8B-Instruct",
        description="Model name/path for the backend",
    )
    api_base: str = Field(
        default="http://localhost:8000/v1",
        description="Base URL for OpenAI-compatible API (vLLM server)",
    )
    api_key: str = Field(
        default="EMPTY",
        description="API key (use 'EMPTY' for local vLLM server)",
    )
    max_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum retries for structured output parsing",
    )
    temperature: float = Field(
        default=0.1,
        ge=0.0,
        le=2.0,
        description="Sampling temperature (lower = more deterministic)",
    )
