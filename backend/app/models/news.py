"""
뉴스 데이터.

저작권 문제를 피하기 위해 뉴스 본문 전체는 저장하지 않고
제목/요약/언론사/발행일/URL/추출된 Event 정보/Embedding 참조 중심으로 저장한다.
(요구사항 5)
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class News(Base):
    __tablename__ = "news"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)

    title: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)  # 언론사
    published_at: Mapped[datetime | None] = mapped_column(DateTime, index=True, nullable=True)
    url: Mapped[str] = mapped_column(String(1000), unique=True)

    # 감정 분석 (VADER 기반, SentimentProvider로 교체 가능)
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # compound
    sentiment_positive: Mapped[float | None] = mapped_column(Float, nullable=True)
    sentiment_neutral: Mapped[float | None] = mapped_column(Float, nullable=True)
    sentiment_negative: Mapped[float | None] = mapped_column(Float, nullable=True)

    importance_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0~100
    event_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    event_subtype: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # 뉴스 본문을 직접 저장하지 않고, 임베딩 벡터를 별도 저장소(파일/벡터DB)에 둔 뒤
    # 그 참조 키만 저장한다 (예: 파일 경로, 벡터DB 내부 ID 등).
    embedding_reference: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # 여러 언론사가 같은 사건을 보도한 경우, 최초로 저장된 대표 기사(News.id)를 가리킨다.
    # None이면 이 기사 자신이 대표(cluster head)이거나 아직 유사 기사가 없는 단독 기사.
    # 완전히 별개의 새 테이블 없이, 이미 존재하는 기사를 지우지 않고 서로 연결하기 위한
    # 최소한의 컬럼이다(Event Cluster).
    cluster_head_id: Mapped[int | None] = mapped_column(ForeignKey("news.id"), nullable=True, index=True)

    source_name: Mapped[str | None] = mapped_column(String(100), nullable=True)  # Provider 이름
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_mock: Mapped[bool] = mapped_column(default=False)  # Mock 데이터 여부 명확히 구분 (요구사항 67)

    company = relationship("Company", back_populates="news_items")
    events = relationship("NewsEvent", back_populates="news", cascade="all, delete-orphan")
