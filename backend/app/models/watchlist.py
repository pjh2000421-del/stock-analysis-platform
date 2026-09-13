"""
사용자 / 관심기업(Watchlist).

요구사항 54: 초기 버전은 복잡한 인증 없이 간단한 local/demo user로 동작하되,
향후 실제 Authentication Provider(OAuth 등)를 붙이기 쉽도록 User 테이블을 분리해둔다.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

DEMO_USER_ID = 1  # 인증 시스템 도입 전까지 사용하는 기본 데모 사용자 ID


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), default="Demo User")
    email: Mapped[str | None] = mapped_column(String(200), nullable=True, unique=True)
    is_demo: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Watchlist(Base):
    __tablename__ = "watchlists"
    __table_args__ = (UniqueConstraint("user_id", "company_id", name="uq_watchlist_user_company"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), default=DEMO_USER_ID, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # 뉴스 알림 필터 (요구사항 48) - 전체 뉴스 여부와 관심 Event Type 목록
    notify_all_news: Mapped[bool] = mapped_column(default=False)
    notify_event_types: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )  # 콤마로 구분된 event_type 목록, None이면 "중요 뉴스만"

    company = relationship("Company")
