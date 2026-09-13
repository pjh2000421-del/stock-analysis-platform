"""
공통 Mixin.

SourceMetadataMixin: 외부에서 가져오거나 계산한 모든 수치에 대해
출처(source_name), 출처 URL, 조회 시각, 계산식, 추정 여부를 기록한다.
(요구사항: 출처 기록 - source_name/source_url/retrieved_at/calculation_method/is_estimated)
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column


class SourceMetadataMixin:
    source_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    calculation_method: Mapped[str | None] = mapped_column(String(300), nullable=True)
    is_estimated: Mapped[bool] = mapped_column(Boolean, default=False)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
