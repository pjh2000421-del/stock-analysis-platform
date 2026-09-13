"""
모델 Registry + Auto Compare (요구사항 34, 35, 42).

AnalysisConfig.model 값에 따라 적절한 BaseModel 구현체를 생성하고,
"Auto Compare" 선택 시 여러 모델을 동일 Dataset/Split에서 비교한다.
"""
from __future__ import annotations

import numpy as np

from app.core.errors import ProviderUnavailableError
from app.core.logging import get_logger
from app.ml.base_model import BaseModel
from app.ml.models.linear_model import LinearRegressionModel, LogisticRegressionModel
from app.ml.models.random_forest_model import (
    RandomForestClassificationModel,
    RandomForestRegressionModel,
)

logger = get_logger(__name__)

REGRESSION_MODELS: dict[str, type[BaseModel]] = {
    "linear_regression": LinearRegressionModel,
    "random_forest": RandomForestRegressionModel,
}
CLASSIFICATION_MODELS: dict[str, type[BaseModel]] = {
    "logistic_regression": LogisticRegressionModel,
    "random_forest": RandomForestClassificationModel,
}


def get_model(model_type: str, task_type: str = "regression", **kwargs) -> BaseModel:
    if model_type == "xgboost":
        from app.ml.models.xgboost_model import XGBoostRegressionModel

        return XGBoostRegressionModel(**kwargs)

    if model_type in ("ann", "lstm"):
        raise ProviderUnavailableError(
            model_type, "딥러닝 모델은 TensorFlow 설치 및 시퀀스 데이터 준비가 필요합니다 (TODO)."
        )

    registry = CLASSIFICATION_MODELS if task_type == "classification" else REGRESSION_MODELS
    model_cls = registry.get(model_type)
    if model_cls is None:
        raise ValueError(f"지원하지 않는 모델입니다: {model_type} (task_type={task_type})")
    return model_cls(**kwargs)


def auto_compare(
    model_types: list[str],
    task_type: str,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
) -> list[dict]:
    """
    요구사항 35: 여러 모델을 동일 Dataset/Split에서 비교.
    특정 모델(예: xgboost 미설치)이 사용 불가하면 해당 모델만 건너뛰고 나머지는 계속 진행한다.
    """
    results = []
    for model_type in model_types:
        try:
            model = get_model(model_type, task_type=task_type)
            model.fit(X_train, y_train)
            metrics = model.evaluate(X_test, y_test)
            results.append({"model": model_type, "metrics": metrics, "status": "ok"})
        except ProviderUnavailableError as exc:
            logger.info("Auto Compare에서 모델 제외(%s): %s", model_type, exc)
            results.append({"model": model_type, "metrics": None, "status": "unavailable", "message": str(exc)})
        except Exception as exc:  # noqa: BLE001
            logger.exception("Auto Compare 모델 실행 실패: %s", model_type)
            results.append({"model": model_type, "metrics": None, "status": "error", "message": str(exc)})
    return results


def feature_ablation(
    feature_groups: dict[str, np.ndarray],
    y: np.ndarray,
    model_type: str,
    task_type: str,
    combos: list[list[str]],
    test_ratio: float = 0.2,
) -> list[dict]:
    """
    요구사항 42: Feature Ablation Analysis.
    combos: [["news"], ["news", "price"], ["news", "price", "fundamental"], ...] 형태로
    비교할 Feature 그룹 조합을 지정한다. 시간 순서를 유지한 단순 Hold-out 분할을 사용한다.
    """
    n = len(y)
    split_idx = int(n * (1 - test_ratio))
    results = []

    for combo in combos:
        try:
            X = np.concatenate([feature_groups[g] for g in combo if g in feature_groups], axis=1)
        except ValueError:
            results.append({"feature_combo": "+".join(combo), "directional_accuracy": None})
            continue

        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        try:
            model = get_model(model_type, task_type=task_type)
            model.fit(X_train, y_train)
            metrics = model.evaluate(X_test, y_test)
            accuracy = metrics.get("directional_accuracy") or metrics.get("accuracy")
        except ProviderUnavailableError:
            accuracy = None

        results.append({"feature_combo": "+".join(combo), "directional_accuracy": accuracy})

    return results
