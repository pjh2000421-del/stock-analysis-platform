"""
개발용 DB 초기화 스크립트.

Production에서는 Alembic 등 마이그레이션 도구 사용을 권장하며,
이 함수는 개발 편의를 위한 create_all 방식이다.
"""
from app.db.base import Base
from app.db.session import engine

# 모든 모델을 import 해야 Base.metadata에 테이블이 등록된다.
from app.models import (  # noqa: F401
    analysis,
    company,
    event,
    financial,
    news,
    notification,
    persona,
    price,
    watchlist,
)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
    print("DB 테이블 생성 완료")
