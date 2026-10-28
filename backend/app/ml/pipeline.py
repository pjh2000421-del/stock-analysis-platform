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
from app.ml.preprocessing import build_sequences
from app.ml.registry import get_model
from app.ml.validation import time_series_split, walk_forward_split
from app.schemas.analysis import ModelType, ScalerType, ValidationMethod

logger = get_logger(__name__)

_REGRESSION_METRIC_KEYS = ("mae", "rmse", "r2", "directional_accuracy")
_CLASSIFICATION_METRIC_KEYS = ("accuracy", "precision", "recall", "f1", "roc_auc")

# Auto Compare에서 task_type별로 시도할 후보 모델. xgboost는 회귀만 지원해 분류 후보에서 제외.
# ANN도 회귀만 지원(아래 run_one_model의 ANN+분류 차단 참고)하므로 회귀 후보에만 추가한다.
# tensorflow가 설치되어 있지 않은 환경(기본값)에서는 ANNModel 생성 시 바로
# ProviderUnavailableError가 나서 status="unavailable"로 조용히 건너뛴다.
# LSTM은 시퀀스 데이터가 필요해 별도 경로(_run_lstm_model)로 처리하며, 실행 비용도 상대적으로
# 커서 Auto Compare 기본 후보에는 포함하지 않는다(사용자가 명시적으로 선택했을 때만 실행).
_REGRESSION_CANDIDATES = [
    ModelType.LINEAR_REGRESSION.value,
    ModelType.RANDOM_FOREST.value,
    ModelType.XGBOOST.value,
    ModelType.ANN.value,
]
_CLASSIFICATION_CANDIDATES = [ModelType.LOGISTIC_REGRESSION.value, ModelType.RANDOM_FOREST.value]

# LSTM 시퀀스 윈도우 길이(거래일). ml/preprocessing.py의 build_sequences() 참고.
LSTM_TIMESTEPS = 10
MIN_LSTM_SEQUENCES = 30


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


def _run_lstm_model(
    task_type: str,
    X: np.ndarray,
    y: np.ndarray,
    latest_features: np.ndarray,
    validation_method: ValidationMethod,
    scaler_type: ScalerType,
) -> dict:
    """LSTM 전용 경로 (요구사항 34 - 기존 "TODO: 시계열 3D 입력 재구성 필요" 해소).

    다른 모델들과 달리 LSTM은 2D Feature 행렬을 그대로 쓸 수 없어(3D 시퀀스 입력 필요)
    별도 경로로 처리한다. 분류(UP_DOWN 등)는 시퀀스 분류 특유의 클래스 불균형/평가 이슈를
    이번 범위에서 검증하지 못해 아직 지원하지 않는다 - xgboost+분류를 막은 것과 같은 원칙.

    주의(Data Leakage 원칙의 의도적 예외, 요구사항 31): 다른 모델은 fold마다 Train
    구간으로만 Scaler를 fit한다. LSTM은 시퀀스 윈도우가 fold 경계를 넘나들며 원본 시간
    순서를 유지해야 해서 fold별로 따로 스케일링하면 윈도우 자체를 구성할 수 없다. 그래서
    LSTM만 전체 X로 Scaler를 한 번 fit한 뒤 시퀀스를 만든다 - MinMax 스케일링 범위 정보가
    Test 구간에도 약하게 새어 들어가는 것을 감수한 것으로, 다른 모델과 다른 방식임을
    여기 명시한다.
    """
    if task_type != "regression":
        return {
            "model": ModelType.LSTM.value,
            "status": "error",
            "message": "LSTM은 현재 회귀 예측 대상에서만 지원됩니다(UP_DOWN 등 분류 대상은 아직 미지원).",
        }

    X_scaled, latest_scaled = _scale_fit_transform(X, latest_features.reshape(1, -1), scaler_type)
    X_seq, y_seq = build_sequences(X_scaled, y, LSTM_TIMESTEPS)
    if len(X_seq) < MIN_LSTM_SEQUENCES:
        return {
            "model": ModelType.LSTM.value,
            "status": "error",
            "message": (
                f"LSTM은 시퀀스 길이({LSTM_TIMESTEPS}거래일)를 고려하면 최소 {MIN_LSTM_SEQUENCES}개 "
                f"시퀀스가 필요한데 {len(X_seq)}개만 확보되었습니다. 조회 기간을 늘려주세요."
            ),
        }

    folds = _make_folds(len(y_seq), validation_method)
    if not folds:
        return {"model": ModelType.LSTM.value, "status": "error", "message": "교차검증에 필요한 데이터가 부족합니다."}

    n_features = X_scaled.shape[1]
    fold_metrics: list[dict] = []
    residuals: list[float] = []

    try:
        for fold in folds:
            model = get_model(ModelType.LSTM.value, task_type=task_type, timesteps=LSTM_TIMESTEPS, n_features=n_features)
            model.fit(X_seq[fold.train_idx], y_seq[fold.train_idx])
            fold_metrics.append(model.evaluate(X_seq[fold.test_idx], y_seq[fold.test_idx]))
            pred = model.predict(X_seq[fold.test_idx])
            residuals.extend((y_seq[fold.test_idx] - pred).tolist())

        if not fold_metrics:
            return {
                "model": ModelType.LSTM.value,
                "status": "error",
                "message": "모든 교차검증 fold가 실패했습니다.",
            }

        final_model = get_model(ModelType.LSTM.value, task_type=task_type, timesteps=LSTM_TIMESTEPS, n_features=n_features)
        final_model.fit(X_seq, y_seq)
    except ProviderUnavailableError as exc:
        return {"model": ModelType.LSTM.value, "status": "unavailable", "message": str(exc)}
    except Exception as exc:  # noqa: BLE001 - 모델 하나의 예기치 못한 실패가 Job 전체를 죽이면 안 됨
        logger.exception("LSTM 모델 학습 실패")
        return {"model": ModelType.LSTM.value, "status": "error", "message": f"모델 학습 중 오류: {exc}"}

    avg_metrics = _average_metrics(fold_metrics, _REGRESSION_METRIC_KEYS)

    # 실시간 예측: 마지막 (timesteps-1)개 학습 구간 + 현재 시점(latest_scaled)을 이어붙인
    # 길이 timesteps짜리 윈도우로 "지금 시점" 예측을 만든다.
    prediction: dict = {"value": None}
    prediction_interval = None
    if len(X_scaled) >= LSTM_TIMESTEPS - 1:
        tail = X_scaled[-(LSTM_TIMESTEPS - 1):] if LSTM_TIMESTEPS > 1 else np.empty((0, n_features))
        latest_window = np.vstack([tail, latest_scaled]).reshape(1, LSTM_TIMESTEPS, n_features)
        pred_value = float(final_model.predict(latest_window)[0])
        prediction = {"value": pred_value}
        if residuals:
            std = float(np.std(residuals))
            prediction_interval = {"lower": pred_value - 1.96 * std, "upper": pred_value + 1.96 * std}

    return {
        "model": ModelType.LSTM.value,
        "status": "ok",
        "metrics": avg_metrics,
        "prediction": prediction,
        "prediction_interval": prediction_interval,
        "feature_importance": None,  # LSTM은 트리 계열처럼 feature_importance를 직접 제공하지 않음
        "confidence": _confidence_from_metrics(task_type, avg_metrics),
        "n_folds": len(folds),
    }


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
    if model_type == ModelType.LSTM.value:
        return _run_lstm_model(task_type, X, y, latest_features, validation_method, scaler_type)

    if model_type == ModelType.ANN.value and task_type == "classification":
        # ml/models/deep_learning_model.py의 ANNModel은 회귀 전용(Dense(1), MSE Loss)으로만
        # 구현되어 있다. 분류에 그대로 쓰면 회귀 출력을 억지로 클래스 라벨처럼 취급하게 되어
        # 조용히 의미 없는 결과가 나온다 - xgboost+분류를 막은 것과 같은 원칙으로 차단한다.
        return {
            "model": model_type,
            "status": "error",
            "message": "ANN은 현재 회귀 예측 대상에서만 지원됩니다(UP_DOWN 등 분류 대상은 아직 미지원).",
        }

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
                # ANN(ml/models/deep_learning_model.py)만 생성 시 input_dim(Feature 개수)이
                # 필요하다 - 다른 모델은 sklearn 관례대로 fit() 시점에 자동으로 차원을 인식한다.
                extra_kwargs = {"input_dim": X_train_fold.shape[1]} if model_type == ModelType.ANN.value else {}
                model = get_model(model_type, task_type=task_type, **extra_kwargs)
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
        final_extra_kwargs = {"input_dim": X_all_scaled.shape[1]} if model_type == ModelType.ANN.value else {}
        final_model = get_model(model_type, task_type=task_type, **final_extra_kwargs)
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
