"""Pydantic data models for tenders and evaluations."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ProcurementType(StrEnum):
    """Government procurement types."""

    ENGINEERING = "工程"
    GOODS = "財物"
    SERVICES = "勞務"


class RecommendedAction(StrEnum):
    """Recommended actions for a tender evaluation."""

    BID = "bid"
    SKIP = "skip"
    REVIEW_FURTHER = "review_further"


class Tender(BaseModel):
    """A government tender record."""

    tender_id: str = Field(description="標案案號")
    title: str = Field(description="標案名稱")
    org_name: str = Field(default="", description="招標機關")
    procurement_type: str = Field(default="", description="採購類別（工程/財物/勞務）")
    tender_method: str = Field(default="", description="招標方式")
    budget_amount: float | None = Field(default=None, description="預算金額")
    deadline: datetime | None = Field(default=None, description="截止收件日期")
    open_date: datetime | None = Field(default=None, description="開標日期")
    url: str = Field(default="", description="標案連結")
    category: str = Field(default="", description="標的分類")
    source: str = Field(description="資料來源")
    publish_date: datetime | None = Field(default=None, description="公告日期")
    fetched_at: datetime = Field(default_factory=datetime.now, description="抓取時間")


class TenderEvaluation(BaseModel):
    """AI evaluation result for a tender."""

    suitable: bool = Field(description="是否適合團隊投標")
    relevance_score: float = Field(ge=0.0, le=1.0, description="相關度分數 0.0 ~ 1.0")
    reasoning: str = Field(description="判斷理由")
    recommended_action: RecommendedAction = Field(description="建議行動")
    matched_capabilities: list[str] = Field(default_factory=list, description="匹配到的團隊能力")
