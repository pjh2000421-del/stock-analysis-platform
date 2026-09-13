"""AI 미래 주가 반응 예측 스키마 (요구사항 37, 38, 39)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ConfidenceLevel


class HorizonPrediction(BaseModel):
    horizon: str  # "1d" | "5d" | "20d"
    up_probability: float | None = None  # 0~1
    expected_return_pct: float | None = None
    prediction_interval_low: float | None = None
    prediction_interval_high: float | None = None
    expected_volatility_change_pct: float | None = None
    confidence: ConfidenceLevel | None = None


class FeatureContribution(BaseModel):
    feature_name: str
    feature_name_simple: str | None = None  # Simple View용 쉬운 한국어 라벨
    contribution_pct: float  # SHAP value 등 기반, 양수=긍정 기여
    direction: str  # "positive" | "negative"


class PredictionResponse(BaseModel):
    ticker: str
    predicted_at: datetime
    data_period_start: str
    data_period_end: str
    model_used: str
    last_trained_at: datetime | None = None
    horizons: list[HorizonPrediction]
    positive_factors: list[FeatureContribution] = []
    negative_factors: list[FeatureContribution] = []
    is_mock: bool = False
    disclaimer: str = "본 예측은 통계적 추정치이며 투자 결과를 보장하지 않습니다."
