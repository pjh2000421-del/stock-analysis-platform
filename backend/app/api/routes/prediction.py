"""
AI 미래 주가 반응 예측 API (요구사항 37~39, 55) - Phase3.

ML 모델 학습 파이프라인이 아직 연결되지 않았으므로, 현재는 "예측 준비 중" 상태를
명확히 반환한다. 가짜 확신에 찬 수치를 보여주지 않는 것이 이 플랫폼의 핵심 원칙이다
(요구사항 61).
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.errors import NotFoundError
from app.schemas.prediction import PredictionResponse
from app.services import company_service

router = APIRouter(prefix="/companies", tags=["prediction"])


@router.get("/{ticker}/prediction", response_model=PredictionResponse)
def get_prediction(ticker: str, db: Session = Depends(get_db)):
    try:
        company_service.get_company_by_ticker(db, ticker)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # TODO(Phase3): ml/ 모듈 학습된 모델 로드 -> Feature 생성 -> 예측 -> SHAP 설명 연결
    return PredictionResponse(
        ticker=ticker,
        predicted_at=datetime.utcnow(),
        data_period_start="N/A",
        data_period_end="N/A",
        model_used="not_implemented_yet",
        last_trained_at=None,
        horizons=[],
        positive_factors=[],
        negative_factors=[],
        is_mock=True,
        disclaimer="AI 예측 기능은 Phase3에서 제공될 예정입니다. 현재는 데이터가 없습니다.",
    )
