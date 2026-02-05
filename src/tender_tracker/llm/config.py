"""LLM backend configuration models."""

from typing import Literal

from pydantic import BaseModel, Field

DEFAULT_TEAM_PROFILE = """團隊核心技術能力：

1. AI / ML / Deep Learning
2. 全端軟體開發
3. 資料工程與分析
4. 系統整合

請在 config.yaml 的 llm.team_profile 中自訂您的團隊能力。
"""


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
    team_profile: str = Field(
        default=DEFAULT_TEAM_PROFILE,
        description="Team capabilities description for evaluation prompt",
    )
