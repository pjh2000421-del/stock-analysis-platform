"""
ANN / LSTM 모델 (요구사항 34) - TODO.

TensorFlow/Keras 또는 PyTorch 중 하나를 사용하도록 요구되어 있으며,
이 프로젝트는 TensorFlow/Keras를 기본으로 채택한다 (요구사항 62의 기존 연구 코드와의 호환성 고려).
무거운 딥러닝 의존성은 기본 requirements.txt에서 선택 설치 항목으로 분리되어 있으므로,
미설치 환경에서는 ProviderUnavailableError로 명확히 안내한다.
"""
from __future__ import annotations

import numpy as np

from app.core.errors import ProviderUnavailableError
from app.ml.base_model import BaseModel


class ANNModel(BaseModel):
    task_type = "regression"
    name = "ann"

    def __init__(self, input_dim: int, **kwargs):
        try:
            import tensorflow as tf  # type: ignore
        except ImportError as exc:
            raise ProviderUnavailableError(self.name, "tensorflow 패키지가 설치되어 있지 않습니다 (TODO).") from exc

        self._tf = tf
        self._model = tf.keras.Sequential(
            [
                tf.keras.layers.Input(shape=(input_dim,)),
                tf.keras.layers.Dense(32, activation="relu"),
                tf.keras.layers.Dense(16, activation="relu"),
                tf.keras.layers.Dense(1),
            ]
        )
        self._model.compile(optimizer="adam", loss="mse")

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        self._model.fit(X, y, epochs=50, verbose=0)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self._model.predict(X, verbose=0).flatten()

    def evaluate(self, X: np.ndarray, y: np.ndarray) -> dict:
        from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

        pred = self.predict(X)
        return {
            "mae": mean_absolute_error(y, pred),
            "rmse": mean_squared_error(y, pred) ** 0.5,
            "r2": r2_score(y, pred) if len(y) > 1 else None,
        }


class LSTMModel(BaseModel):
    """
    TODO: 시계열 3D 입력(samples, timesteps, features) 형태로 재구성하는
    시퀀스 생성 유틸을 ml/preprocessing.py에 추가한 뒤 연결 필요.
    """

    task_type = "regression"
    name = "lstm"

    def __init__(self, timesteps: int, n_features: int, **kwargs):
        try:
            import tensorflow as tf  # type: ignore
        except ImportError as exc:
            raise ProviderUnavailableError(self.name, "tensorflow 패키지가 설치되어 있지 않습니다 (TODO).") from exc

        self._tf = tf
        self._model = tf.keras.Sequential(
            [
                tf.keras.layers.Input(shape=(timesteps, n_features)),
                tf.keras.layers.LSTM(32),
                tf.keras.layers.Dense(1),
            ]
        )
        self._model.compile(optimizer="adam", loss="mse")

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        self._model.fit(X, y, epochs=50, verbose=0)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self._model.predict(X, verbose=0).flatten()

    def evaluate(self, X: np.ndarray, y: np.ndarray) -> dict:
        from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

        pred = self.predict(X)
        return {
            "mae": mean_absolute_error(y, pred),
            "rmse": mean_squared_error(y, pred) ** 0.5,
            "r2": r2_score(y, pred) if len(y) > 1 else None,
        }
