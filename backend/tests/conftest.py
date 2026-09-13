"""
API 테스트 공용 fixture.

주의: 이 파일은 fastapi/sqlalchemy 의존성이 필요하다.
현재 개발 샌드박스는 외부 네트워크(PyPI) 접근이 차단되어 있어 `pip install -r requirements.txt`를
실행하지 못했으므로, 이 테스트들은 로컬/CI 환경(의존성 설치 가능한 환경)에서 실행해야 한다.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.main import app
from app.api.deps import get_db

# 모델 전체 등록을 위해 import
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


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session):
    from fastapi.testclient import TestClient

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
