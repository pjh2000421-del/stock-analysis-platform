"""기업 검색/상세 스키마."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ClassificationOut(BaseModel):
    """투자분석용 산업분류 (요구사항: WICS 등 우선, 없으면 낮은 신뢰도로만 fallback)."""

    sector: str | None = None
    industry: str | None = None
    sub_industry: str | None = None
    system: str | None = None  # "WICS" | "FICS" | "KRX_RAW" | "DART_BUSINESS" | "UNKNOWN"
    source: str | None = None
    confidence: float | None = None
    updated_at: datetime | None = None


class RawClassificationOut(BaseModel):
    """KRX 상장법인목록(KSIC 기반) 원본 분류 - 참고용으로만 노출한다."""

    industry: str | None = None
    source: str = "finance_datareader (KRX 상장법인목록, KSIC 기반)"


class CompanySearchResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker: str
    company_name: str
    market: str | None = None
    sector: str | None = None
    industry: str | None = None
    investment_industry: str | None = None


class CompanyDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker: str
    company_name: str
    company_name_en: str | None = None
    market: str | None = None
    sector: str | None = None
    industry: str | None = None
    market_cap: float | None = None
    classification: ClassificationOut | None = None
    raw_classification: RawClassificationOut | None = None

    current_price: float | None = None
    price_change: float | None = None
    price_change_pct: float | None = None
    price_date: datetime | None = None

    last_updated: datetime | None = None


class CompanySearchResponse(BaseModel):
    query: str
    results: list[CompanySearchResult]
