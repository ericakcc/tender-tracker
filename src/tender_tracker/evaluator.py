"""AI-powered tender evaluation using Claude API with structured output."""

import anthropic
from loguru import logger

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

EVALUATION_PROMPT = """你是一位專業的政府標案分析師，負責評估標案是否適合團隊投標。

以下是團隊的核心能力：
{team_profile}

請根據以下標案資訊，評估此標案是否適合團隊投標。

標案資訊：
- 案號：{tender_id}
- 名稱：{title}
- 招標機關：{org_name}
- 採購類別：{procurement_type}
- 預算金額：{budget}
- 招標方式：{tender_method}
- 標的分類：{category}

請評估：
1. 此標案與團隊能力的匹配度（0.0 ~ 1.0）
2. 是否建議投標（bid / skip / review_further）
3. 匹配到哪些團隊能力
4. 詳細的判斷理由
"""


class TenderEvaluator:
    """Claude API-based tender evaluation engine."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-5-20250514",
    ) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def evaluate(self, tender: Tender) -> TenderEvaluation:
        """Evaluate a single tender using Claude API.

        Args:
            tender: The tender to evaluate.

        Returns:
            Structured evaluation result.
        """
        budget_str = f"NT${tender.budget_amount:,.0f}" if tender.budget_amount else "未公告"

        prompt = EVALUATION_PROMPT.format(
            team_profile=TEAM_PROFILE,
            tender_id=tender.tender_id,
            title=tender.title,
            org_name=tender.org_name,
            procurement_type=tender.procurement_type,
            budget=budget_str,
            tender_method=tender.tender_method,
            category=tender.category,
        )

        logger.info("Evaluating tender: {} - {}", tender.tender_id, tender.title)

        response = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
            tools=[
                {
                    "name": "submit_evaluation",
                    "description": (
                        "Submit the structured evaluation result for a government tender."
                    ),
                    "input_schema": TenderEvaluation.model_json_schema(),
                }
            ],
            tool_choice={"type": "tool", "name": "submit_evaluation"},
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == "submit_evaluation":
                evaluation = TenderEvaluation.model_validate(block.input)
                logger.info(
                    "Evaluation complete: score={:.2f}, action={}",
                    evaluation.relevance_score,
                    evaluation.recommended_action,
                )
                return evaluation

        logger.warning("No tool_use block found, returning default skip evaluation")
        return TenderEvaluation(
            suitable=False,
            relevance_score=0.0,
            reasoning="Failed to get structured evaluation from API",
            recommended_action="skip",
            matched_capabilities=[],
        )

    def evaluate_batch(self, tenders: list[Tender]) -> list[tuple[Tender, TenderEvaluation]]:
        """Evaluate multiple tenders.

        Args:
            tenders: List of tenders to evaluate.

        Returns:
            List of (tender, evaluation) tuples.
        """
        results = []
        for tender in tenders:
            try:
                evaluation = self.evaluate(tender)
                results.append((tender, evaluation))
            except Exception as e:
                logger.error("Failed to evaluate tender {}: {}", tender.tender_id, e)
                fallback = TenderEvaluation(
                    suitable=False,
                    relevance_score=0.0,
                    reasoning=f"Evaluation failed: {e}",
                    recommended_action="review_further",
                    matched_capabilities=[],
                )
                results.append((tender, fallback))
        return results
