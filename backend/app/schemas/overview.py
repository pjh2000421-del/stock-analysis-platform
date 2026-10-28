"""
종합 기업 분석 / Simple View 스키마 (요구사항 23, 25).

점수 계산식은 투명하게 관리하며 (config 기반 weight), black-box 점수를 만들지 않는다.
"""
from __future__ import annotations

from pydantic import BaseModel


class ScoreBreakdown(BaseModel):
    """카테고리 점수 + 계산에 사용된 weight/구성요소를 함께 노출 (투명성 확보)."""

    category: str  # "valuation" | "growth" | "profitability" | "financial_health"
    score: float | None = None  # 0~100
    weight: float
    components: dict[str, float | None]  # 세부 지표별 정규화 점수
    is_na: bool = False


class CompositeScoreResponse(BaseModel):
    ticker: str
    scores: list[ScoreBreakdown]
    total_score: float | None = None
    weights_config_version: str


class SimpleLevel(BaseModel):
    label: str  # 예: "저렴", "보통", "비싼 편" (한국어 표시용, 하위호환을 위해 유지)
    detail: str  # 근거 문장, 단정적 표현 금지 (한국어)
    # 다국어 표시용: 프론트엔드가 code/detail_code로 locales/*.json의 문구를 찾아 표시한다.
    # 백엔드가 언어별 문장을 직접 만들지 않으므로 번역은 프론트엔드 한 곳에서만 관리된다.
    code: str | None = None  # 예: "expensive" | "moderate" | "cheap" | "insufficient_data"
    detail_code: str | None = None  # 예: "price_level", "news_average"
    params: dict[str, int | float | str] = {}  # 문구에 끼워 넣을 값 (예: {"count": 20})


class SimpleViewResponse(BaseModel):
    ticker: str
    company_name: str
    price_level: SimpleLevel
    growth_level: SimpleLevel
    profitability_level: SimpleLevel
    financial_health_level: SimpleLevel
    news_sentiment_level: SimpleLevel
    historical_similarity_level: SimpleLevel
    ai_outlook: SimpleLevel
    risk_factors: list[str]
    # risk_factors와 같은 순서의 코드 (프론트엔드 번역용)
    risk_factor_codes: list[str] = []
    disclaimer: str = "본 분석은 투자 권유가 아니며 투자 결과를 보장하지 않습니다."


class GlossaryTerm(BaseModel):
    term: str
    explanation_ko: str
    explanation_ja: str | None = None
    explanation_en: str | None = None
