"""Random Forest 모델 (요구사항 34)."""
from __future__ import annotations

import numpy as np
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from app.ml.base_model import BaseModel


class RandomForestRegressionModel(BaseModel):
    task_type = "regression"
    name = "random_forest"

    def __init__(self, **kwargs):
        self._model = RandomForestRegressor(n_estimators=200, random_state=42, **kwargs)

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


class RandomForestClassificationModel(BaseModel):
    task_type = "classification"
    name = "random_forest_classifier"

    def __init__(self, **kwargs):
        self._model = RandomForestClassifier(n_estimators=200, random_state=42, **kwargs)

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        self._model.fit(X, y)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self._model.predict(X)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        return self._model.predict_proba(X)

    def feature_importance(self, feature_names: list[str]) -> dict[str, float]:
        return dict(zip(feature_names, self._model.feature_importances_.tolist()))

    def evaluate(self, X: np.ndarray, y: np.ndarray) -> dict:
        from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score

        pred = self.predict(X)
        metrics = {
            "accuracy": accuracy_score(y, pred),
            "precision": precision_score(y, pred, zero_division=0),
            "recall": recall_score(y, pred, zero_division=0),
            "f1": f1_score(y, pred, zero_division=0),
        }
        try:
            proba = self.predict_proba(X)[:, 1]
            metrics["roc_auc"] = roc_auc_score(y, proba)
        except (ValueError, IndexError):
            metrics["roc_auc"] = None
        return metrics
