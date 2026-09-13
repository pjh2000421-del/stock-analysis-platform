"""Analysis Lab API (요구사항 40, 41, 55) - Phase3/5."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.errors import NotFoundError
from app.schemas.analysis import (
    AnalysisConfig,
    AnalysisJobCreated,
    AnalysisJobResult,
    AnalysisResultOut,
    ModelMetrics,
)
from app.services import analysis_service, company_service

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("/run", response_model=AnalysisJobCreated)
def run_analysis(config: AnalysisConfig, db: Session = Depends(get_db)):
    try:
        company = company_service.get_company_by_ticker(db, config.ticker)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    job = analysis_service.create_analysis_job(db, company, config)
    return AnalysisJobCreated(job_id=job.id, status=job.status)


@router.get("/{job_id}", response_model=AnalysisJobResult)
def get_analysis_result(job_id: int, db: Session = Depends(get_db)):
    job = analysis_service.get_analysis_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="분석 작업을 찾을 수 없습니다.")

    return AnalysisJobResult(
        job_id=job.id,
        status=job.status,
        config=AnalysisConfig(**job.config),
        results=[
            AnalysisResultOut(
                model=r.model,
                target=r.target,
                prediction=r.prediction,
                metrics=ModelMetrics(**r.metrics) if r.metrics else None,
                feature_importance=r.feature_importance,
                confidence=r.confidence,
                prediction_interval=r.prediction_interval,
            )
            for r in job.results
        ],
        error_message=job.error_message,
    )
