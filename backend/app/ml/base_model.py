"""
ML 모델 공통 인터페이스 (요구사항 34).

모든 모델(Linear/Logistic/RandomForest/XGBoost/ANN/LSTM)은 이 인터페이스를 구현하여
Auto Compare(ml/registry.py)에서 동일한 방식으로 다룰 수 있게 한다.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np


@dataclass
class ModelArtifact:
    """요구사항 64: 모델 저장 시 함께 보관해야 하는 메타데이터."""

    model_name: str
    feature_list: list[str]
    training_period: str
    metrics: dict
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class BaseModel(ABC):
    task_type: str = "regression"  # "regression" | "classification"
    name: str = "base_model"

    @abstractmethod
    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        ...

    @abstractmethod
    def predict(self, X: np.ndarray) -> np.ndarray:
        ...

    @abstractmethod
    def evaluate(self, X: np.ndarray, y: np.ndarray) -> dict:
        ...

    def save(self, path: str | Path, artifact_meta: ModelArtifact) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model": self, "meta": artifact_meta.__dict__}, path)

    @classmethod
    def load(cls, path: str | Path) -> tuple["BaseModel", dict]:
        payload = joblib.load(path)
        return payload["model"], payload["meta"]
