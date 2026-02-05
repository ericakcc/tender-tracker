"""vLLM backend using OpenAI-compatible API with Instructor for structured output."""

import instructor
from loguru import logger
from openai import AsyncOpenAI

from tender_tracker.llm.base import LLMBackend
from tender_tracker.llm.config import LLMConfig
from tender_tracker.models import Tender, TenderEvaluation

TEAM_PROFILE = """光聚晶電聯合（Star Fusion Group）核心技術能力：

1. AI / ML / Deep Learning 模型開發
   - 大型語言模型 (LLM) 應用與微調
   - 生成式 AI 應用開發
   - 電腦視覺與影像辨識
   - 自然語言處理 (NLP)

2. 全端軟體開發
   - Web 應用程式開發（前端 + 後端）
   - API 設計與實作
   - 雲端原生架構

3. 資料工程與分析
   - 資料平台建置
   - 數據分析儀表板
   - ETL 管線開發

4. 遊戲技術
   - 遊戲引擎技術（大宇資訊經驗）
   - 互動式 3D 應用
   - VR/AR 技術應用

5. 資安（安瑞-KY）
   - 資訊安全解決方案
   - 資安稽核與顧問

6. 支付系統（紅陽科技）
   - 電子支付整合
   - 金流系統開發
"""

SYSTEM_PROMPT = f"""你是一位專業的政府標案分析師，負責評估標案是否適合團隊投標。

以下是團隊的核心能力：
{TEAM_PROFILE}

請根據提供的標案資訊，評估此標案是否適合團隊投標。評估項目：
1. 此標案與團隊能力的匹配度（0.0 ~ 1.0）
2. 是否建議投標（bid / skip / review_further）
3. 匹配到哪些團隊能力
4. 判斷理由（請依照以下格式，每項不超過 20 字）：
   - 匹配點：與團隊哪些能力相關
   - 風險點：主要疑慮或不適合原因
   - 結論：一句話總結建議

請以 JSON 格式回覆，嚴格按照指定的 schema。"""

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


class VLLMBackend(LLMBackend):
    """vLLM backend using OpenAI-compatible API with Instructor.

    Uses the Instructor library for reliable structured output parsing
    with automatic retry on validation failures.
    """

    def __init__(self, config: LLMConfig) -> None:
        """Initialize vLLM backend.

        Args:
            config: LLM configuration with api_base, model, etc.
        """
        self.config = config
        self._raw_client = AsyncOpenAI(
            base_url=config.api_base,
            api_key=config.api_key,
        )
        self.client = instructor.from_openai(
            self._raw_client,
            mode=instructor.Mode.JSON,
        )

    async def evaluate(self, tender: Tender) -> TenderEvaluation:
        """Evaluate a single tender using vLLM with structured output.

        Args:
            tender: The tender to evaluate.

        Returns:
            Structured evaluation result.
        """
        prompt = format_evaluation_prompt(tender)

        logger.info("Evaluating tender: {} - {}", tender.tender_id, tender.title)

        try:
            result = await self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                response_model=TenderEvaluation,
                max_retries=self.config.max_retries,
                temperature=self.config.temperature,
            )

            logger.info(
                "Evaluation complete: score={:.2f}, action={}",
                result.relevance_score,
                result.recommended_action,
            )
            return result

        except Exception as e:
            logger.error("vLLM evaluation failed for {}: {}", tender.tender_id, e)
            return TenderEvaluation(
                suitable=False,
                relevance_score=0.0,
                reasoning=f"vLLM evaluation failed: {e}",
                recommended_action="review_further",
                matched_capabilities=[],
            )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._raw_client.close()
