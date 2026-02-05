"""Tests for the vLLM backend module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tender_tracker.llm import LLMConfig, get_backend
from tender_tracker.llm.config import DEFAULT_TEAM_PROFILE
from tender_tracker.llm.vllm_backend import (
    SYSTEM_PROMPT_TEMPLATE,
    VLLMBackend,
    format_evaluation_prompt,
)
from tender_tracker.models import Tender, TenderEvaluation


class TestFormatEvaluationPrompt:
    """Tests for prompt formatting."""

    def test_format_with_budget(self) -> None:
        tender = Tender(
            tender_id="T-001",
            title="AI 系統建置",
            org_name="數位發展部",
            procurement_type="勞務",
            budget_amount=500_000,
            tender_method="公開招標",
            category="資訊服務",
            source="mlwmlw",
        )

        prompt = format_evaluation_prompt(tender)

        assert "T-001" in prompt
        assert "AI 系統建置" in prompt
        assert "數位發展部" in prompt
        assert "勞務" in prompt
        assert "NT$500,000" in prompt
        assert "公開招標" in prompt
        assert "資訊服務" in prompt

    def test_format_without_budget(self) -> None:
        tender = Tender(
            tender_id="T-002",
            title="測試標案",
            budget_amount=None,
            source="mlwmlw",
        )

        prompt = format_evaluation_prompt(tender)

        assert "T-002" in prompt
        assert "測試標案" in prompt
        assert "未公告" in prompt


class TestVLLMBackend:
    """Tests for VLLMBackend with mocked OpenAI client."""

    @pytest.fixture
    def mock_config(self) -> LLMConfig:
        return LLMConfig(
            backend="vllm",
            model="test-model",
            api_base="http://localhost:8000/v1",
            api_key="test-key",
            max_retries=2,
            temperature=0.1,
        )

    @pytest.mark.asyncio
    async def test_evaluate_success(self, mock_config: LLMConfig) -> None:
        """Test successful evaluation."""
        expected_result = TenderEvaluation(
            suitable=True,
            relevance_score=0.85,
            reasoning="高度相關",
            recommended_action="bid",
            matched_capabilities=["LLM", "NLP"],
        )

        with patch("tender_tracker.llm.vllm_backend.AsyncOpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_openai_cls.return_value = mock_client

            with patch("tender_tracker.llm.vllm_backend.instructor") as mock_instructor:
                mock_patched_client = MagicMock()
                mock_instructor.from_openai.return_value = mock_patched_client
                mock_instructor.Mode.JSON = "json"

                # Setup async mock for chat.completions.create
                mock_patched_client.chat.completions.create = AsyncMock(
                    return_value=expected_result
                )

                backend = VLLMBackend(mock_config)
                tender = Tender(
                    tender_id="T-001",
                    title="AI 系統",
                    source="mlwmlw",
                )

                result = await backend.evaluate(tender)

                assert result.suitable is True
                assert result.relevance_score == 0.85
                assert result.recommended_action == "bid"
                mock_patched_client.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_evaluate_failure_returns_fallback(self, mock_config: LLMConfig) -> None:
        """Test that evaluation failure returns a fallback result."""
        with patch("tender_tracker.llm.vllm_backend.AsyncOpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_openai_cls.return_value = mock_client

            with patch("tender_tracker.llm.vllm_backend.instructor") as mock_instructor:
                mock_patched_client = MagicMock()
                mock_instructor.from_openai.return_value = mock_patched_client
                mock_instructor.Mode.JSON = "json"

                # Simulate API error
                mock_patched_client.chat.completions.create = AsyncMock(
                    side_effect=Exception("API Error")
                )

                backend = VLLMBackend(mock_config)
                tender = Tender(
                    tender_id="T-001",
                    title="Test",
                    source="mlwmlw",
                )

                result = await backend.evaluate(tender)

                assert result.suitable is False
                assert result.relevance_score == 0.0
                assert result.recommended_action == "review_further"
                assert "failed" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_close(self, mock_config: LLMConfig) -> None:
        """Test closing the backend."""
        with patch("tender_tracker.llm.vllm_backend.AsyncOpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_client.close = AsyncMock()
            mock_openai_cls.return_value = mock_client

            with patch("tender_tracker.llm.vllm_backend.instructor") as mock_instructor:
                mock_instructor.from_openai.return_value = MagicMock()
                mock_instructor.Mode.JSON = "json"

                backend = VLLMBackend(mock_config)
                await backend.close()

                mock_client.close.assert_called_once()


class TestGetBackend:
    """Tests for the backend factory function."""

    def test_get_vllm_backend(self) -> None:
        """Test creating vLLM backend via factory."""
        config = LLMConfig(backend="vllm")

        with patch("tender_tracker.llm.vllm_backend.AsyncOpenAI"):
            with patch("tender_tracker.llm.vllm_backend.instructor") as mock_instructor:
                mock_instructor.Mode.JSON = "json"
                mock_instructor.from_openai.return_value = MagicMock()

                backend = get_backend(config)
                assert isinstance(backend, VLLMBackend)

    def test_get_claude_backend(self) -> None:
        """Test creating Claude backend via factory."""
        config = LLMConfig(backend="claude")

        from tender_tracker.llm.claude_backend import ClaudeBackend

        backend = get_backend(config)
        assert isinstance(backend, ClaudeBackend)

    def test_get_unknown_backend_raises(self) -> None:
        """Test that unknown backend raises ValueError."""
        config = LLMConfig()
        # Manually set invalid backend (bypass validation)
        object.__setattr__(config, "backend", "unknown")

        with pytest.raises(ValueError, match="Unknown LLM backend"):
            get_backend(config)


class TestSystemPrompt:
    """Tests for system prompt template."""

    def test_system_prompt_template_has_placeholder(self) -> None:
        """Verify system prompt template has team_profile placeholder."""
        assert "{team_profile}" in SYSTEM_PROMPT_TEMPLATE

    def test_system_prompt_template_contains_evaluation_instructions(self) -> None:
        """Verify system prompt template includes evaluation instructions."""
        assert "匹配度" in SYSTEM_PROMPT_TEMPLATE
        assert "0.0" in SYSTEM_PROMPT_TEMPLATE
        assert "1.0" in SYSTEM_PROMPT_TEMPLATE
        assert "bid" in SYSTEM_PROMPT_TEMPLATE
        assert "skip" in SYSTEM_PROMPT_TEMPLATE
        assert "review_further" in SYSTEM_PROMPT_TEMPLATE

    def test_system_prompt_formatted_with_team_profile(self) -> None:
        """Verify system prompt can be formatted with custom team profile."""
        custom_profile = "我們專精於 AI 和雲端技術"
        formatted = SYSTEM_PROMPT_TEMPLATE.format(team_profile=custom_profile)
        assert custom_profile in formatted
        assert "{team_profile}" not in formatted


class TestLLMConfigTeamProfile:
    """Tests for team profile in LLMConfig."""

    def test_default_team_profile(self) -> None:
        """Test that default team profile is used when none specified."""
        config = LLMConfig()
        assert config.team_profile == DEFAULT_TEAM_PROFILE

    def test_custom_team_profile(self) -> None:
        """Test that custom team_profile is used."""
        custom = "Custom team profile"
        config = LLMConfig(team_profile=custom)
        assert config.team_profile == custom


@pytest.mark.integration
class TestVLLMBackendIntegration:
    """Integration tests for vLLM backend (require running vLLM server)."""

    @pytest.mark.asyncio
    async def test_real_evaluation(self) -> None:
        """Test real evaluation against vLLM server.

        Requires vLLM server running at localhost:8000 with Qwen model.
        """
        config = LLMConfig(
            backend="vllm",
            model="Qwen/Qwen3-8B-Instruct",
            api_base="http://localhost:8000/v1",
        )

        backend = VLLMBackend(config)

        try:
            tender = Tender(
                tender_id="TEST-001",
                title="AI 智慧客服系統建置案",
                org_name="數位發展部",
                procurement_type="勞務",
                budget_amount=500_000,
                tender_method="公開招標",
                category="資訊服務",
                source="test",
            )

            result = await backend.evaluate(tender)

            # Basic validation
            assert isinstance(result, TenderEvaluation)
            assert 0.0 <= result.relevance_score <= 1.0
            assert result.recommended_action in ["bid", "skip", "review_further"]
            assert len(result.reasoning) > 0

            # AI-related tender should score higher
            assert result.relevance_score > 0.5

        finally:
            await backend.close()
