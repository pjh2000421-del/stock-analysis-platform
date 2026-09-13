"""
Analysis Lab 모델 학습/백테스트/실시간 예측 오케스트레이션 (Phase3 MVP).

feature_matrix.py가 만든 (X, y)를 받아 시계열 교차검증(ml/validation.py)으로 백테스트
성능을 추정하고, 확보된 데이터 전체로 다시 학습한 모델로 "지금 시점" 예측 1건을 만든다.
Auto Compare(여러 모델을 한 번에 실행)도 이 모듈에서 처리한다 - 모델 하나가 실패해도
(패키지 미설치, task_type 불일치 등) 예외를 던지지 않고 status가 담긴 dict로 돌려줘서
나머지 모델은 계속 진행할 수 있게 한다 (ml/registry.py의 auto_compare()와 같은 원칙).
"""
from __future__ import annotations

import numpy as np
from sklearn.preprocessing import MinMaxScaler

from app.core.errors import ProviderUnavailableError
from app.core.logging import get_logger
from app.ml.registry import get_model
from app.ml.validation import time_series_split, walk_forward_split
from app.schemas.analysis import ModelType, ScalerType, ValidationMethod

logger = get_logger(__name__)

_REGRESSION_METRIC_KEYS = ("mae", "rmse", "r2", "directional_accuracy")
_CLASSIFICATION_METRIC_KEYS = ("accuracy", "precision", "recall", "f1", "roc_auc")

# Auto Compare에서 task_type별로 시도할 후보 모델. xgboost는 회귀만 지원해 분류 후보에서 제외.
_REGRESSION_CANDIDATES = [ModelType.LINEAR_REGRESSION.value, ModelType.RANDOM_FOREST.value, ModelType.XGBOOST.value]
_CLASSIFICATION_CANDIDATES = [ModelType.LOGISTIC_REGRESSION.value, ModelType.RANDOM_FOREST.value]


def _make_folds(n_samples: int, validation_method: ValidationMethod):
    if validation_method == ValidationMethod.WALK_FORWARD:
        initial_train_size = max(int(n_samples * 0.6), 10)
        step = max(n_samples // 10, 1)
        folds = walk_forward_split(n_samples, initial_train_size=initial_train_size, step=step)
    else:
        folds = time_series_split(n_samples)
    return [f for f in folds if len(f.train_idx) > 0 and len(f.test_idx) > 0]


def _average_metrics(fold_metrics: list[dict], keys: tuple[str, ...]) -> dict:
    averaged: dict[str, float | None] = {}
    for key in keys:
        values = [m[key] for m in fold_metrics if m.get(key) is not None]
        averaged[key] = float(np.mean(values)) if values else None
    return averaged


def _scale_fit_transform(train: np.ndarray, other: np.ndarray, scaler_type: ScalerType) -> tuple[np.ndarray, np.ndarray]:
    """ml/preprocessing.py의 fit_scaler_on_train_only()와 같은 원칙: Train으로만 fit하고
    Test(또는 실시간 예측 시점의 latest_features)에는 transform만 적용한다 (Data Leakage 방지,
    요구사항 31). scaler="none"이면 원본 그대로 돌려준다."""
    if scaler_type != ScalerType.MINMAX:
        return train, other
    scaler = MinMaxScaler(feature_range=(0, 1))
    train_scaled = scaler.fit_transform(train)
    other_scaled = scaler.transform(other)
    return train_scaled, other_scaled


def _confidence_from_metrics(task_type: str, metrics: dict) -> str | None:
    score = metrics.get("directional_accuracy") if task_type == "regression" else metrics.get("accuracy")
    if score is None:
        return None
    if score >= 0.6:
        return "High"
    if score >= 0.52:
        return "Medium"
    return "Low"


def run_one_model(
    model_type: str,
    task_type: str,
    X: np.ndarray,
    y: np.ndarray,
    feature_columns: list[str],
    latest_features: np.ndarray,
    validation_method: ValidationMethod,
    scaler_type: ScalerType = ScalerType.MINMAX,
) -> dict:
    """단일 모델을 시계열 교차검증으로 백테스트하고, 전체 데이터로 재학습해 "현재 시점"
    예측 1건을 만든다. 실패해도 예외를 던지지 않고 status가 담긴 dict를 돌려준다."""
    if model_type == ModelType.XGBOOST.value and task_type == "classification":
        # registry.get_model()의 xgboost 분기는 task_type을 검사하지 않고 항상 회귀
        # 모델(XGBoostRegressionModel)을 돌려준다 - 그대로 두면 0/1 라벨을 회귀 대상으로
        # 학습해버려서 조용히 의미 없는 결과가 나온다. 여기서 미리 막는다.
        return {
            "model": model_type,
            "status": "error",
            "message": "XGBoost는 현재 회귀 예측 대상에서만 지원됩니다(UP_DOWN 등 분류 대상은 아직 미지원).",
        }

    folds = _make_folds(len(y), validation_method)
    if not folds:
        return {"model": model_type, "status": "error", "message": "교차검증에 필요한 데이터가 부족합니다."}

    metric_keys = _CLASSIFICATION_METRIC_KEYS if task_type == "classification" else _REGRESSION_METRIC_KEYS
    fold_metrics: list[dict] = []
    residuals: list[float] = []

    try:
        for fold in folds:
            X_train_fold, X_test_fold = _scale_fit_transform(X[fold.train_idx], X[fold.test_idx], scaler_type)
            try:
                model = get_model(model_type, task_type=task_type)
                model.fit(X_train_fold, y[fold.train_idx])
                fold_metrics.append(model.evaluate(X_test_fold, y[fold.test_idx]))
                if task_type == "regression":
                    pred = model.predict(X_test_fold)
                    residuals.extend((y[fold.test_idx] - pred).tolist())
            except ValueError as exc:
                # 예: 분류에서 이 fold의 Train 구간에 클래스가 하나만 존재하는 경우
                # (초반 fold에서 흔함) - 이 fold만 건너뛰고 나머지 fold로 계속 진행한다.
                logger.info("%s: fold 하나 건너뜀 (%s)", model_type, exc)
                continue

        if not fold_metrics:
            return {
                "model": model_type,
                "status": "error",
                "message": "모든 교차검증 fold가 실패했습니다 (데이터가 한쪽 클래스로 치우쳤을 수 있습니다).",
            }

        # 실시간 예측("지금 시점")용: 확보된 데이터 전체로 다시 학습한다. Scaler도 전체
        # Train(=X 전체)로만 fit하고 latest_features에는 transform만 적용한다.
        X_all_scaled, latest_scaled = _scale_fit_transform(X, latest_features.reshape(1, -1), scaler_type)
        final_model = get_model(model_type, task_type=task_type)
        final_model.fit(X_all_scaled, y)
    except ProviderUnavailableError as exc:
        return {"model": model_type, "status": "unavailable", "message": str(exc)}
    except ValueError as exc:
        # 예: task_type과 맞지 않는 model_type 조합 (registry.get_model이 발생시킴)
        return {"model": model_type, "status": "error", "message": str(exc)}
    except Exception as exc:  # noqa: BLE001 - 모델 하나의 예기치 못한 실패가 Job 전체를 죽이면 안 됨
        logger.exception("모델 학습 실패: %s", model_type)
        return {"model": model_type, "status": "error", "message": f"모델 학습 중 오류: {exc}"}

    avg_metrics = _average_metrics(fold_metrics, metric_keys)
    latest_X = latest_scaled
    prediction_interval = None

    if task_type == "classification":
        pred_class = int(final_model.predict(latest_X)[0])
        prediction = {"direction": "UP" if pred_class == 1 else "DOWN"}
        if hasattr(final_model, "predict_proba"):
            try:
                prediction["probability_up"] = float(final_model.predict_proba(latest_X)[0][1])
            except (IndexError, ValueError):
                pass
    else:
        pred_value = float(final_model.predict(latest_X)[0])
        prediction = {"value": pred_value}
        if residuals:
            std = float(np.std(residuals))
            prediction_interval = {"lower": pred_value - 1.96 * std, "upper": pred_value + 1.96 * std}

    feature_importance = None
    if hasattr(final_model, "feature_importance"):
        try:
            feature_importance = final_model.feature_importance(feature_columns)
        except Exception:  # noqa: BLE001 - 부가 정보이므로 실패해도 결과 자체는 유지한다
            feature_importance = None

    return {
        "model": model_type,
        "status": "ok",
        "metrics": avg_metrics,
        "prediction": prediction,
        "prediction_interval": prediction_interval,
        "feature_importance": feature_importance,
        "confidence": _confidence_from_metrics(task_type, avg_metrics),
        "n_folds": len(folds),
    }


def run_models(
    model_choice: ModelType,
    task_type: str,
    X: np.ndarray,
    y: np.ndarray,
    feature_columns: list[str],
    latest_features: np.ndarray,
    validation_method: ValidationMethod,
    scaler_type: ScalerType = ScalerType.MINMAX,
) -> list[dict]:
    """단일 모델이면 그 모델 하나, AUTO_COMPARE면 task_type에 맞는 후보 모델을 모두 실행한다."""
    if model_choice == ModelType.AUTO_COMPARE:
        candidates = _CLASSIFICATION_CANDIDATES if task_type == "classification" else _REGRESSION_CANDIDATES
    else:
        candidates = [model_choice.value]

    return [
        run_one_model(m, task_type, X, y, feature_columns, latest_features, validation_method, scaler_type)
        for m in candidates
    ]
