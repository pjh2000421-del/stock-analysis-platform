"""
Analysis Lab / ML AnalysisConfig 스키마 (요구사항 40, 41).

중요: 사용자가 임의 Python 코드를 서버에서 실행하도록 허용하지 않는다.
아래처럼 "선택 가능한 옵션 조합"만 스키마로 제한한다.
"""
from __future__ import annotations

from datetime import date as date_
from enum import Enum

from pydantic import BaseModel, Field


class AnalysisTarget(str, Enum):
    NEXT_DAY_RETURN = "next_day_return"
    RETURN_5D = "return_5d"
    RETURN_20D = "return_20d"
    UP_DOWN = "up_down"
    VOLATILITY = "volatility"
    RESIDUAL = "residual"
    EXCESS_RETURN = "excess_return"


class FeatureGroup(str, Enum):
    PRICE = "price"
    VOLUME = "volume"
    NEWS_SENTIMENT = "news_sentiment"
    NEWS_FREQUENCY = "news_frequency"
    EVENT_TYPE = "event_type"
    HISTORICAL_SIMILARITY = "historical_similarity"
    VALUATION = "valuation"
    FUNDAMENTAL = "fundamental"
    MARKET_INDEX = "market_index"
    FX_RATE = "fx_rate"
    INTEREST_RATE = "interest_rate"
    VOLATILITY = "volatility"


class ModelType(str, Enum):
    LINEAR_REGRESSION = "linear_regression"
    LOGISTIC_REGRESSION = "logistic_regression"
    RANDOM_FOREST = "random_forest"
    XGBOOST = "xgboost"
    ANN = "ann"
    LSTM = "lstm"
    AUTO_COMPARE = "auto_compare"


class ScalerType(str, Enum):
    MINMAX = "minmax"
    NONE = "none"


class ValidationMethod(str, Enum):
    TIME_SERIES_SPLIT = "time_series_split"
    WALK_FORWARD = "walk_forward"


class AnalysisConfig(BaseModel):
    ticker: str
    start_date: date_
    end_date: date_
    features: list[FeatureGroup] = Field(default_factory=lambda: [FeatureGroup.PRICE])
    lags: list[int] = Field(default_factory=lambda: [0])
    target: AnalysisTarget = AnalysisTarget.RETURN_5D
    model: ModelType = ModelType.RANDOM_FOREST
    scaler: ScalerType = ScalerType.MINMAX
    validation_method: ValidationMethod = ValidationMethod.TIME_SERIES_SPLIT
    hyperparameters: dict = Field(default_factory=dict)


class AnalysisJobCreated(BaseModel):
    job_id: int
    status: str


class ModelMetrics(BaseModel):
    directional_accuracy: float | None = None
    mae: float | None = None
    rmse: float | None = None
    r2: float | None = None
    accuracy: float | None = None
    precision: float | None = None
    recall: float | None = None
    f1: float | None = None
    roc_auc: float | None = None


class AnalysisResultOut(BaseModel):
    model: str
    target: str
    prediction: dict
    metrics: ModelMetrics | None = None
    feature_importance: dict[str, float] | None = None
    confidence: str | None = None
    prediction_interval: dict | None = None


class AnalysisJobResult(BaseModel):
    job_id: int
    status: str
    config: AnalysisConfig
    results: list[AnalysisResultOut] = []
    error_message: str | None = None


class FeatureAblationRow(BaseModel):
    """요구사항 42: Feature Ablation 결과 한 행."""

    feature_combo: str  # 예: "뉴스만", "뉴스 + 주가"
    directional_accuracy: float | None = None
