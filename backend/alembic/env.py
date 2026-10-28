"""
Alembic 환경 설정.

기존에는 app/db/init_db.py의 Base.metadata.create_all()만으로 개발 DB 스키마를
관리했다(주석에도 "Production에서는 Alembic 등 마이그레이션 도구 사용을 권장"이라고
명시되어 있었음). create_all()은 "테이블이 없으면 만든다"만 할 뿐 기존 테이블의 컬럼
추가/변경/삭제를 추적하지 못해, 배포된 DB(특히 SQLite가 아닌 운영 DB로 전환한 이후)의
스키마를 안전하게 변경할 방법이 없었다. 이 파일은 그 빈틈을 메우기 위한 Alembic 표준
env.py이며, DB 접속정보는 alembic.ini에 별도로 두지 않고 항상 app.core.config.get_settings()
(.env의 DATABASE_URL)에서 가져와 설정이 한 곳(.env)으로 유지되게 한다.
"""
from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# backend/ 디렉터리를 sys.path에 추가해 "app.xxx" 형태의 import가 동작하게 한다
# (uvicorn 실행과 달리 alembic은 backend/ 밖에서 실행될 수도 있기 때문).
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402

# 모든 모델을 import해야 Base.metadata에 테이블이 등록된다
# (app/db/init_db.py의 기존 목록과 동일하게 유지 - 새 모델 추가 시 두 곳 모두 갱신 필요).
from app.models import (  # noqa: E402,F401
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

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# .env의 DATABASE_URL로 alembic.ini의 sqlalchemy.url을 덮어쓴다 (설정 단일화).
config.set_main_option("sqlalchemy.url", get_settings().database_url)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# autogenerate가 비교할 모델 메타데이터
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """`alembic upgrade head --sql` 등 오프라인(SQL 스크립트만 생성) 모드."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """실제 DB에 연결해 마이그레이션을 적용하는 일반 모드."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
