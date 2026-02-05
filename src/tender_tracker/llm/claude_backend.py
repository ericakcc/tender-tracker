"""Claude backend using Claude Agent SDK for structured output."""

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
from loguru import logger

from tender_tracker.llm.base import LLMBackend
from tender_tracker.llm.config import LLMConfig
from tender_tracker.models import Tender, TenderEvaluation

SYSTEM_PROMPT_TEMPLATE = """你是一位專業的政府標案分析師，負責評估標案是否適合團隊投標。

以下是團隊的核心能力：
{team_profile}

請根據提供的標案資訊，評估此標案是否適合團隊投標。評估項目：
1. 此標案與團隊能力的匹配度（0.0 ~ 1.0）
2. 是否建議投標（bid / skip / review_further）
3. 匹配到哪些團隊能力
4. 判斷理由（請依照以下格式，每項不超過 20 字）：
   - 匹配點：與團隊哪些能力相關
   - 風險點：主要疑慮或不適合原因
   - 結論：一句話總結建議
"""

EVALUATION_PROMPT_TEMPLATE = """請評估以下標案：

標案資訊：
- 案號：{tender_id}
- 名稱：{title}
- 招標機關：{org_name}
- 採購類別：{procurement_type}
- 預算金額：{budget}
- 招標方式：{tender_method}
- 標的分類：{category}
"""


def format_evaluation_prompt(tender: Tender) -> str:
    """Format tender data into evaluation prompt.

    Args:
        tender: The tender to evaluate.

    Returns:
        Formatted prompt string.
    """
    budget_str = f"NT${tender.budget_amount:,.0f}" if tender.budget_amount else "未公告"
    return EVALUATION_PROMPT_TEMPLATE.format(
        tender_id=tender.tender_id,
        title=tender.title,
        org_name=tender.org_name,
        procurement_type=tender.procurement_type,
        budget=budget_str,
        tender_method=tender.tender_method,
        category=tender.category,
    )


class ClaudeBackend(LLMBackend):
    """Claude backend using Claude Agent SDK.

    Wraps the existing claude-agent-sdk integration into the LLMBackend interface
    for backwards compatibility.
    """

    def __init__(self, config: LLMConfig) -> None:
        """Initialize Claude backend.

        Args:
            config: LLM configuration (model name used from config).
        """
        self.config = config
        self._system_prompt = SYSTEM_PROMPT_TEMPLATE.format(team_profile=config.team_profile)
        # Map common model aliases to Claude model IDs
        self._model = self._resolve_model(config.model)

    def _resolve_model(self, model: str) -> str:
        """Resolve model alias to Claude model ID.

        Args:
            model: Model name or alias.

        Returns:
            Claude model ID.
        """
        model_aliases = {
            "claude-sonnet": "claude-sonnet-4-5-20250929",
            "claude-opus": "claude-opus-4-5-20251101",
            "claude-haiku": "claude-haiku-4-5-20251101",
        }
        return model_aliases.get(model, model)

    async def evaluate(self, tender: Tender) -> TenderEvaluation:
        """Evaluate a single tender using Claude Agent SDK.

        Args:
            tender: The tender to evaluate.

        Returns:
            Structured evaluation result.
        """
        prompt = format_evaluation_prompt(tender)

        logger.info("Evaluating tender: {} - {}", tender.tender_id, tender.title)

        result: TenderEvaluation | None = None
        async for message in query(
            prompt=prompt,
            options=ClaudeAgentOptions(
                model=self._model,
                system_prompt=self._system_prompt,
                output_format={
                    "type": "json_schema",
                    "schema": TenderEvaluation.model_json_schema(),
                },
                max_turns=2,
                allowed_tools=[],
            ),
        ):
            if isinstance(message, ResultMessage) and message.structured_output:
                result = TenderEvaluation.model_validate(message.structured_output)
                logger.info(
                    "Evaluation complete: score={:.2f}, action={}",
                    result.relevance_score,
                    result.recommended_action,
                )

        if result:
            return result

        logger.warning("No structured output returned, returning default skip evaluation")
        return TenderEvaluation(
            suitable=False,
            relevance_score=0.0,
            reasoning="Failed to get structured evaluation from Claude Agent SDK",
            recommended_action="skip",
            matched_capabilities=[],
        )

    async def close(self) -> None:
        """No-op for Claude backend (no persistent connections)."""
        pass
