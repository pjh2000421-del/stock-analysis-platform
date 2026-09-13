"""
기업 마스터 정보.

주의: 이 테이블은 "종목명/티커/시장/업종" 정도의 가벼운 검색용 마스터 정보만 담는다.
가격/재무/뉴스 등 무거운 상세 데이터는 사용자가 검색했을 때 Lazy Loading으로 채워진다.
(요구사항 3: 전 종목 사전 다운로드 금지)
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    company_name: Mapped[str] = mapped_column(String(200), index=True)
    company_name_en: Mapped[str | None] = mapped_column(String(200), nullable=True)
    market: Mapped[str | None] = mapped_column(String(20), nullable=True)  # KOSPI/KOSDAQ 등
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # industry: 과거부터 사용해온 필드. KRX 상장법인목록(KSIC 기반) 원본 값이 그대로 들어있어
    # 투자분석용으로 부적절하다(예: "방송장비 및 전자기기"). 하위호환을 위해 값은 계속 채우되,
    # 신규 코드는 이 필드를 직접 쓰지 말고 raw_industry/investment_industry를 사용한다.
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    market_cap: Mapped[float | None] = mapped_column(Float, nullable=True)

    # --- 업종 분류 재구성 (raw vs investment 분리) ---
    # raw_industry: 기존 Provider(KRX 상장법인목록)가 반환한 원본 값. industry와 동일한 값을
    # 명시적인 이름으로 보존한다(삭제하지 않음).
    raw_industry: Mapped[str | None] = mapped_column(String(150), nullable=True)
    # investment_sector/industry/sub_industry: 실제 투자분석(Peer Comparison 등)에 사용하는 값.
    investment_sector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    investment_industry: Mapped[str | None] = mapped_column(String(150), nullable=True)
    investment_sub_industry: Mapped[str | None] = mapped_column(String(150), nullable=True)
    classification_system: Mapped[str | None] = mapped_column(String(30), nullable=True)
    classification_source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    classification_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    classification_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # 마지막으로 상세 데이터(가격/재무/뉴스)를 갱신한 시각들 - Lazy Loading 갱신 판단에 사용
    last_updated: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    prices_last_updated: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    financials_last_updated: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    news_last_updated: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    prices = relationship("DailyPrice", back_populates="company", cascade="all, delete-orphan")
    news_items = relationship("News", back_populates="company", cascade="all, delete-orphan")
    financial_statements = relationship(
        "FinancialStatement", back_populates="company", cascade="all, delete-orphan"
    )
    financial_metrics = relationship(
        "FinancialMetric", back_populates="company", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Company {self.ticker} {self.company_name}>"
