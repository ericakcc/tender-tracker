"""LLM backend configuration models."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

DEFAULT_TEAM_PROFILE = """團隊核心技術能力：

1. AI / ML / Deep Learning
2. 全端軟體開發
3. 資料工程與分析
4. 系統整合

請根據您的團隊能力自訂此檔案。
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
        default="",
        description="Team capabilities description for evaluation prompt",
    )
    team_profile_path: str = Field(
        default="",
        description="Path to external file containing team profile (overrides team_profile)",
    )

    @model_validator(mode="after")
    def load_team_profile_from_file(self) -> "LLMConfig":
        """Load team profile from file if path is specified."""
        if self.team_profile_path:
            path = Path(self.team_profile_path)
            if path.exists():
                self.team_profile = path.read_text(encoding="utf-8").strip()
        if not self.team_profile:
            self.team_profile = DEFAULT_TEAM_PROFILE
        return self
