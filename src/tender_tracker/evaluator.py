"""AI-powered tender evaluation using Claude Agent SDK with structured output."""

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
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

SYSTEM_PROMPT = f"""你是一位專業的政府標案分析師，負責評估標案是否適合團隊投標。

以下是團隊的核心能力：
{TEAM_PROFILE}

請根據提供的標案資訊，評估此標案是否適合團隊投標。評估項目：
1. 此標案與團隊能力的匹配度（0.0 ~ 1.0）
2. 是否建議投標（bid / skip / review_further）
3. 匹配到哪些團隊能力
4. 詳細的判斷理由
"""

EVALUATION_PROMPT = """請評估以下標案：

標案資訊：
- 案號：{tender_id}
- 名稱：{title}
- 招標機關：{org_name}
- 採購類別：{procurement_type}
- 預算金額：{budget}
- 招標方式：{tender_method}
- 標的分類：{category}
"""


class TenderEvaluator:
    """Claude Agent SDK-based tender evaluation engine."""

    async def evaluate(self, tender: Tender) -> TenderEvaluation:
        """Evaluate a single tender using Claude Agent SDK.

        Args:
            tender: The tender to evaluate.

        Returns:
            Structured evaluation result.
        """
        budget_str = f"NT${tender.budget_amount:,.0f}" if tender.budget_amount else "未公告"

        prompt = EVALUATION_PROMPT.format(
            tender_id=tender.tender_id,
            title=tender.title,
            org_name=tender.org_name,
            procurement_type=tender.procurement_type,
            budget=budget_str,
            tender_method=tender.tender_method,
            category=tender.category,
        )

        logger.info("Evaluating tender: {} - {}", tender.tender_id, tender.title)

        result: TenderEvaluation | None = None
        async for message in query(
            prompt=prompt,
            options=ClaudeAgentOptions(
                system_prompt=SYSTEM_PROMPT,
                output_format={
                    "type": "json_schema",
                    "schema": TenderEvaluation.model_json_schema(),
                },
                max_turns=3,
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

    async def evaluate_batch(self, tenders: list[Tender]) -> list[tuple[Tender, TenderEvaluation]]:
        """Evaluate multiple tenders.

        Args:
            tenders: List of tenders to evaluate.

        Returns:
            List of (tender, evaluation) tuples.
        """
        results: list[tuple[Tender, TenderEvaluation]] = []
        for tender in tenders:
            try:
                evaluation = await self.evaluate(tender)
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
