"""
Analysis Lab Job Service (요구사항 40, 41) - Phase3 MVP.

Phase1에서는 AnalysisConfig를 받아 analysis_jobs 테이블에 안전하게 저장/조회하는
기본 골격만 제공했고(Job은 무조건 "not_implemented"), 이번에 실제 ML 학습/추론
파이프라인(ml/feature_matrix.py + ml/pipeline.py)을 연결했다.

지금은 이 서비스가 요청 안에서 동기적으로 학습까지 끝내고 응답한다(별도 백그라운드
Job 큐가 아직 없음 - 이 플랫폼 다른 곳에도 없는 패턴). 데이터 부족/아직 지원하지 않는
설정 조합은 AnalysisDataError로 명확히 알리고(요구사항 74), 그 외 예기치 못한 오류도
전체 요청을 죽이지 않고 status="failed" + error_message로 응답한다(Provider Fallback과
같은 원칙 - news_service.py 등 참고).

MVP 범위는 app/ml/feature_matrix.py 모듈 docstring 참고 (지원 Feature 그룹/예측대상).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.errors import AnalysisDataError
from app.core.logging import get_logger
from app.ml.feature_matrix import build_feature_matrix
from app.ml.pipeline import run_models
from app.models.analysis import AnalysisJob, AnalysisResult
from app.models.company import Company
from app.schemas.analysis import AnalysisConfig

logger = get_logger(__name__)


def _run_pipeline(db: Session, job: AnalysisJob, company: Company, config: AnalysisConfig) -> None:
    matrix = build_feature_matrix(db, company, config)

    X = matrix.X_train_df.to_numpy(dtype=float)
    y = matrix.y.to_numpy()
    latest_features = matrix.latest_features.to_numpy(dtype=float)

    model_results = run_models(
        config.model,
        matrix.task_type,
        X,
        y,
        matrix.feature_columns,
        latest_features,
        config.validation_method,
        config.scaler,
    )

    ok_results = [r for r in model_results if r["status"] == "ok"]
    if not ok_results:
        messages = "; ".join(f"{r['model']}: {r.get('message', r['status'])}" for r in model_results)
        raise AnalysisDataError(f"선택한 모델로 학습에 실패했습니다 ({messages}).")

    for r in ok_results:
        db.add(
            AnalysisResult(
                job_id=job.id,
                model=r["model"],
                target=config.target.value,
                prediction=r["prediction"],
                metrics=r["metrics"],
                feature_importance=r["feature_importance"],
                confidence=r["confidence"],
                prediction_interval=r["prediction_interval"],
            )
        )

    notes: list[str] = []
    if matrix.skipped_feature_groups:
        notes.append("아직 지원되지 않아 제외된 Feature: " + ", ".join(matrix.skipped_feature_groups))
    failed_models = [r for r in model_results if r["status"] != "ok"]
    if failed_models:
        notes.append(
            "일부 모델은 결과에서 제외됨: "
            + "; ".join(f"{r['model']}({r.get('message', r['status'])})" for r in failed_models)
        )

    job.status = "done"
    job.error_message = " / ".join(notes) if notes else None


def create_analysis_job(db: Session, company: Company, config: AnalysisConfig) -> AnalysisJob:
    job = AnalysisJob(company_id=company.id, config=config.model_dump(mode="json"), status="running")
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        _run_pipeline(db, job, company, config)
    except AnalysisDataError as exc:
        job.status = "failed"
        job.error_message = str(exc)
    except Exception as exc:  # noqa: BLE001 - 분석 파이프라인의 예기치 못한 오류가 API 전체를 죽이면 안 됨
        logger.exception("Analysis Job 실행 중 예기치 못한 오류: job_id=%s", job.id)
        job.status = "failed"
        job.error_message = f"분석 실행 중 예기치 못한 오류가 발생했습니다: {exc}"
    finally:
        job.finished_at = datetime.utcnow()
        db.add(job)
        db.commit()
        db.refresh(job)

    return job


def get_analysis_job(db: Session, job_id: int) -> AnalysisJob | None:
    return db.get(AnalysisJob, job_id)
