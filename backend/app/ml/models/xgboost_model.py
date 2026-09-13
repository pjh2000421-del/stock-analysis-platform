"""XGBoost 모델 (요구사항 34). xgboost 미설치 환경에서는 ProviderUnavailableError를 발생시킨다."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from app.core.errors import ProviderUnavailableError
from app.ml.base_model import BaseModel


class XGBoostRegressionModel(BaseModel):
    task_type = "regression"
    name = "xgboost"

    def __init__(self, **kwargs):
        try:
            from xgboost import XGBRegressor  # type: ignore
        except ImportError as exc:
            raise ProviderUnavailableError(self.name, "xgboost 패키지가 설치되어 있지 않습니다.") from exc
        self._model = XGBRegressor(n_estimators=300, max_depth=4, learning_rate=0.05, random_state=42, **kwargs)

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        self._model.fit(X, y)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self._model.predict(X)

    def feature_importance(self, feature_names: list[str]) -> dict[str, float]:
        return dict(zip(feature_names, self._model.feature_importances_.tolist()))

    def evaluate(self, X: np.ndarray, y: np.ndarray) -> dict:
        pred = self.predict(X)
        mae = mean_absolute_error(y, pred)
        rmse = mean_squared_error(y, pred) ** 0.5
        r2 = r2_score(y, pred) if len(y) > 1 else None
        directional_accuracy = float(np.mean(np.sign(pred) == np.sign(y))) if len(y) > 0 else None
        return {"mae": mae, "rmse": rmse, "r2": r2, "directional_accuracy": directional_accuracy}
