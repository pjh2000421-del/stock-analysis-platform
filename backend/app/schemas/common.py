"""공통 Enum 및 응답 스키마."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class EventType(str, Enum):
    """뉴스 Event 대분류 (요구사항 9)."""

    SUPPLY_CONTRACT = "SUPPLY_CONTRACT"
    NEW_PRODUCT = "NEW_PRODUCT"
    NEW_TECHNOLOGY = "NEW_TECHNOLOGY"
    RND = "RND"
    PATENT = "PATENT"
    M_AND_A = "M_AND_A"
    CAPEX = "CAPEX"
    EARNINGS = "EARNINGS"
    REGULATION = "REGULATION"
    LEGAL = "LEGAL"
    MANAGEMENT = "MANAGEMENT"
    DIVIDEND = "DIVIDEND"
    BUYBACK = "BUYBACK"
    CAPITAL_INCREASE = "CAPITAL_INCREASE"
    SUPPLY_CHAIN = "SUPPLY_CHAIN"
    GEOPOLITICAL = "GEOPOLITICAL"
    PARTNERSHIP = "PARTNERSHIP"
    PRODUCT_LAUNCH = "PRODUCT_LAUNCH"
    PRODUCTION = "PRODUCTION"
    GUIDANCE = "GUIDANCE"
    OTHER = "OTHER"


class DevelopmentStage(str, Enum):
    RESEARCH = "research"
    PROTOTYPE = "prototype"
    DEVELOPMENT_COMPLETE = "development_complete"
    MASS_PRODUCTION = "mass_production"
    COMMERCIALIZATION = "commercialization"


class ContractStage(str, Enum):
    DISCUSSION = "discussion"
    MOU = "MOU"
    CONTRACT_SIGNED = "contract_signed"
    DELIVERY = "delivery"
    REVENUE_RECOGNITION = "revenue_recognition"


class ConfidenceLevel(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class Locale(str, Enum):
    KO = "ko"
    JA = "ja"
    EN = "en"


class DataSourceMeta(BaseModel):
    """모든 외부/계산 데이터에 부착 가능한 출처 메타데이터."""

    source_name: str | None = None
    source_url: str | None = None
    retrieved_at: datetime | None = None
    data_period: str | None = None
    calculation_method: str | None = None
    is_estimated: bool = False


class ValueWithSource(BaseModel):
    """값 하나 + 출처 정보를 함께 표현 (N/A 허용)."""

    value: float | None = None
    meta: DataSourceMeta | None = None
    is_na: bool = False
    na_reason: str | None = None
    # 값이 없는 이유가 데이터 부족이 아니라 "적자/자본잠식" 등 구조적인 상태라서
    # 지표(배수) 자체가 의미를 갖지 못하는 경우 True. 화면에서는 일반 "N/A" 대신
    # na_reason에 담긴 짧은 라벨("적자", "자본잠식")을 그대로 보여준다.
    is_deficit: bool = False


class Disclaimer(BaseModel):
    text_ko: str = "본 분석은 투자 권유가 아니며 투자 결과를 보장하지 않습니다."
    text_ja: str = "本分析は投資勧誘ではなく、投資結果を保証するものではありません。"
    text_en: str = "This analysis is not investment advice and does not guarantee investment outcomes."
