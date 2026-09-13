"""
뉴스 Event 구조화 / 과거 사건 주가반응 / 과거 유사사례 유사도.

Phase2 핵심 데이터 모델. Phase1에서는 테이블만 생성해두고
실제 채우는 로직(event_extraction, similarity 계산)은 Phase2에서 구현한다.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class NewsEvent(Base):
    """뉴스에서 추출된 구조화 Event 정보 (요구사항 9)."""

    __tablename__ = "news_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    news_id: Mapped[int] = mapped_column(ForeignKey("news.id"), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)

    event_type: Mapped[str] = mapped_column(String(50), index=True)
    event_subtype: Mapped[str | None] = mapped_column(String(50), nullable=True)
    product: Mapped[str | None] = mapped_column(String(200), nullable=True)
    technology: Mapped[str | None] = mapped_column(String(200), nullable=True)
    counterparty: Mapped[str | None] = mapped_column(String(200), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)

    amount_nominal: Mapped[float | None] = mapped_column(Float, nullable=True)  # 명목 금액(원)
    amount_real: Mapped[float | None] = mapped_column(Float, nullable=True)  # 물가조정 금액(원)
    amount_currency: Mapped[str | None] = mapped_column(String(10), default="KRW")

    revenue_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)  # amount / 당시 연매출
    market_cap_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)  # amount / 당시 시총
    assets_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)

    development_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    commercialization_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    contract_period: Mapped[str | None] = mapped_column(String(100), nullable=True)

    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sentiment: Mapped[float | None] = mapped_column(Float, nullable=True)
    importance: Mapped[float | None] = mapped_column(Float, nullable=True)

    event_date: Mapped[datetime | None] = mapped_column(DateTime, index=True, nullable=True)

    # DART 공시를 Anchor로 사용했는지 여부 (요구사항 12)
    dart_anchor_rcept_no: Mapped[str | None] = mapped_column(String(50), nullable=True)

    news = relationship("News", back_populates="events")
    market_reaction = relationship(
        "EventMarketReaction", back_populates="event", uselist=False, cascade="all, delete-orphan"
    )


class EventMarketReaction(Base):
    """Event Study: Event 전후 주가 반응 (요구사항 15)."""

    __tablename__ = "event_market_reactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("news_events.id"), unique=True, index=True)

    return_0d: Mapped[float | None] = mapped_column(Float, nullable=True)
    return_1d: Mapped[float | None] = mapped_column(Float, nullable=True)
    return_5d: Mapped[float | None] = mapped_column(Float, nullable=True)
    return_20d: Mapped[float | None] = mapped_column(Float, nullable=True)
    return_60d: Mapped[float | None] = mapped_column(Float, nullable=True)

    excess_return_1d: Mapped[float | None] = mapped_column(Float, nullable=True)
    excess_return_5d: Mapped[float | None] = mapped_column(Float, nullable=True)
    excess_return_20d: Mapped[float | None] = mapped_column(Float, nullable=True)
    excess_return_60d: Mapped[float | None] = mapped_column(Float, nullable=True)

    volatility_before: Mapped[float | None] = mapped_column(Float, nullable=True)  # Event 이전 20일
    volatility_after: Mapped[float | None] = mapped_column(Float, nullable=True)  # Event 이후 20일
    max_upside: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_drawdown: Mapped[float | None] = mapped_column(Float, nullable=True)

    benchmark_index: Mapped[str | None] = mapped_column(String(20), nullable=True)  # KOSPI 등
    industry_relative_return_5d: Mapped[float | None] = mapped_column(Float, nullable=True)

    event = relationship("NewsEvent", back_populates="market_reaction")


class HistoricalSimilarity(Base):
    """현재 Event와 과거 Event 간 유사도 계산 결과 (요구사항 11, 12)."""

    __tablename__ = "historical_similarity"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    current_event_id: Mapped[int] = mapped_column(ForeignKey("news_events.id"), index=True)
    historical_event_id: Mapped[int] = mapped_column(ForeignKey("news_events.id"), index=True)

    semantic_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    event_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    scale_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_score: Mapped[float] = mapped_column(Float, index=True)  # 0~100

    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
