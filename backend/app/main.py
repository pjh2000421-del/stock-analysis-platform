"""
FastAPI 애플리케이션 진입점.

실행: uvicorn app.main:app --reload
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.api import api_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.init_db import init_db

settings = get_settings()
setup_logging()

app = FastAPI(
    title=settings.app_name,
    description="한국 주식 중심 금융 AI 분석 웹 플랫폼 API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    # 개발 편의를 위한 자동 테이블 생성 (Production은 Alembic 등 마이그레이션 권장)
    init_db()


@app.get("/")
def root() -> dict:
    return {
        "service": settings.app_name,
        "status": "ok",
        "docs": "/docs",
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


app.include_router(api_router, prefix="/api")
