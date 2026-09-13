"""
DB 세션 관리.

개발환경: SQLite / 운영환경: PostgreSQL(Supabase 포함)을
DATABASE_URL 값만으로 전환할 수 있도록 설계한다. (요구사항: DB 섹션)
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

_connect_args = {"check_same_thread": False} if settings.is_sqlite else {}

engine = create_engine(
    settings.database_url,
    connect_args=_connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI Dependency: 요청 단위 DB 세션 제공."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
