"""
Analysis Lab Feature Matrix 빌더 (Phase3 MVP).

AnalysisConfig(요구사항 40, 41)에서 사용자가 고른 기업/기간/Feature 그룹/Lag/예측대상을
실제 학습 가능한 (X, y) 배열로 조립하는 핵심 연결부. ml/preprocessing.py, ml/lag_features.py
등 이미 있던 "부품"들을 여기서 조합한다.

MVP 범위(요구사항 74 - 숫자를 함부로 만들지 않는다는 원칙에 따라, 아직 제대로 만들 수
없는 Feature는 조용히 0으로 채우지 않고 명시적으로 건너뛰고 알려준다):
    지원: price, volume, news_sentiment, news_frequency, event_type
    미지원(다음 단계): historical_similarity, valuation, fundamental, market_index,
        fx_rate, interest_rate, volatility
    - valuation/fundamental은 "그 시점에 실제로 알 수 있었던 값"만 써야 하는
      Point-in-Time 정합성(요구사항 30, 63) 검증이 필요해 MVP에서는 제외한다.
    - market_index/fx_rate는 macro_provider.py에 이미 있지만, interest_rate는
      Provider 자체가 아직 없어 함께 다음 단계로 미룬다.
    - historical_similarity는 계산 비용이 커서(이벤트별 유사도 검색) 이 Feature Matrix
      빌더에 바로 붙이기보다 별도 캐싱 전략이 필요해 다음 단계로 미룬다.

예측 대상(AnalysisTarget) 중 EXCESS_RETURN/RESIDUAL은 시장 벤치마크/팩터 데이터 연동이
필요해 아직 지원하지 않는다(AnalysisDataError로 명확히 알림).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_
from datetime import datetime, time

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AnalysisDataError
from app.core.logging import get_logger
from app.ml.lag_features import add_lag_features
from app.ml.preprocessing import build_price_feature_frame
from app.models.company import Company
from app.models.event import NewsEvent
from app.models.news import News
from app.schemas.analysis import AnalysisConfig, AnalysisTarget, FeatureGroup
from app.schemas.common import EventType
from app.services.price_service import get_prices_in_range

logger = get_logger(__name__)

# 이 Feature Matrix 빌더가 실제로 조립할 수 있는 Feature 그룹 (MVP 범위).
SUPPORTED_FEATURE_GROUPS: set[FeatureGroup] = {
    FeatureGroup.PRICE,
    FeatureGroup.VOLUME,
    FeatureGroup.NEWS_SENTIMENT,
    FeatureGroup.NEWS_FREQUENCY,
    FeatureGroup.EVENT_TYPE,
}

# 예측 대상별 "며칠 앞을 볼 것인가" (거래일 기준). UP_DOWN은 다음 거래일 방향을,
# VOLATILITY는 향후 5거래일 실현 변동성을 예측하도록 정의한다 (스키마에 명시돼 있지
# 않아 여기서 정한 설계 결정 - 필요하면 나중에 조정 가능).
_REGRESSION_HORIZON_DAYS: dict[AnalysisTarget, int] = {
    AnalysisTarget.NEXT_DAY_RETURN: 1,
    AnalysisTarget.RETURN_5D: 5,
    AnalysisTarget.RETURN_20D: 20,
}
_UP_DOWN_HORIZON_DAYS = 1
_VOLATILITY_HORIZON_DAYS = 5

MIN_TRAINING_ROWS = 30


@dataclass
class FeatureMatrixResult:
    X_train_df: pd.DataFrame  # 학습에 실제로 쓰이는 (target이 존재하는) 구간의 Feature
    y: pd.Series  # X_train_df와 같은 index를 갖는 target
    latest_features: pd.Series  # 가장 최근 거래일의 Feature (실시간 예측용, target은 모름)
    latest_date: date_
    feature_columns: list[str]
    task_type: str  # "regression" | "classification"
    skipped_feature_groups: list[str]


def _price_dataframe(db: Session, company: Company, config: AnalysisConfig) -> pd.DataFrame:
    bars = get_prices_in_range(db, company, config.start_date, config.end_date)
    rows = [
        {"date": b.date, "open": b.open, "high": b.high, "low": b.low, "close": b.close, "volume": b.volume}
        for b in bars
        if b.close is not None
    ]
    if not rows:
        raise AnalysisDataError(
            f"{config.ticker}의 {config.start_date}~{config.end_date} 구간 주가 데이터를 확보하지 못했습니다."
        )
    df = pd.DataFrame(rows).set_index("date").sort_index()
    df.index = pd.to_datetime(df.index)
    return df


def _news_daily_aggregates(db: Session, company: Company, config: AnalysisConfig) -> pd.DataFrame:
    """일자별 (평균 감정점수, 기사 수)를 반환한다. 뉴스가 없는 날은 포함되지 않는다(호출부에서 reindex)."""
    start_dt = datetime.combine(config.start_date, time.min)
    end_dt = datetime.combine(config.end_date, time.max)
    rows = db.execute(
        select(News.published_at, News.sentiment_score).where(
            News.company_id == company.id,
            News.published_at.is_not(None),
            News.published_at >= start_dt,
            News.published_at <= end_dt,
        )
    ).all()
    if not rows:
        return pd.DataFrame(columns=["news_sentiment", "news_frequency"])

    df = pd.DataFrame([{"published_at": r.published_at, "sentiment_score": r.sentiment_score} for r in rows])
    df["date"] = pd.to_datetime(df["published_at"]).dt.normalize()
    grouped = df.groupby("date").agg(
        news_sentiment=("sentiment_score", "mean"), news_frequency=("sentiment_score", "size")
    )
    return grouped


def _event_type_daily_counts(db: Session, company: Company, config: AnalysisConfig) -> pd.DataFrame:
    """일자별 event_type 발생 건수(one-hot count) 행렬을 반환한다. 알려진 모든 EventType
    컬럼을 항상 포함시켜, 기간에 따라 컬럼 구성이 달라져 Scaler/모델 재사용이 꼬이는 일을 막는다."""
    start_dt = datetime.combine(config.start_date, time.min)
    end_dt = datetime.combine(config.end_date, time.max)
    rows = db.execute(
        select(NewsEvent.event_date, NewsEvent.event_type).where(
            NewsEvent.company_id == company.id,
            NewsEvent.event_date.is_not(None),
            NewsEvent.event_date >= start_dt,
            NewsEvent.event_date <= end_dt,
        )
    ).all()

    all_columns = [f"event_{t.value}" for t in EventType]
    if not rows:
        return pd.DataFrame(columns=all_columns)

    df = pd.DataFrame([{"event_date": r.event_date, "event_type": r.event_type} for r in rows])
    df["date"] = pd.to_datetime(df["event_date"]).dt.normalize()
    counts = df.groupby(["date", "event_type"]).size().unstack(fill_value=0)
    counts = counts.rename(columns={t: f"event_{t}" for t in counts.columns})
    # 관측되지 않은 event_type 컬럼도 0으로 채워서 항상 같은 컬럼 구성을 유지한다.
    for col in all_columns:
        if col not in counts.columns:
            counts[col] = 0
    return counts[all_columns]


def _compute_target(price_df: pd.DataFrame, target: AnalysisTarget) -> tuple[pd.Series, str]:
    """price_df(다음: close, log_return 컬럼 포함)로부터 target Series와 task_type을 계산한다."""
    if target in _REGRESSION_HORIZON_DAYS:
        horizon = _REGRESSION_HORIZON_DAYS[target]
        y = np.log(price_df["close"].shift(-horizon) / price_df["close"])
        return y, "regression"

    if target == AnalysisTarget.UP_DOWN:
        forward_return = np.log(price_df["close"].shift(-_UP_DOWN_HORIZON_DAYS) / price_df["close"])
        y = (forward_return > 0).astype(float)
        y[forward_return.isna()] = np.nan
        return y, "classification"

    if target == AnalysisTarget.VOLATILITY:
        # 오늘 이후 5거래일 구간의 일일수익률 표준편차 = "향후 실현 변동성"에 대한 근사.
        y = price_df["log_return"].rolling(window=_VOLATILITY_HORIZON_DAYS).std().shift(-_VOLATILITY_HORIZON_DAYS)
        return y, "regression"

    raise AnalysisDataError(
        f"'{target.value}' 예측 대상은 아직 지원하지 않습니다 "
        "(시장 벤치마크/펀더멘털 팩터 데이터 연동이 더 필요합니다 - 다음 단계에서 제공 예정)."
    )


def build_feature_matrix(db: Session, company: Company, config: AnalysisConfig) -> FeatureMatrixResult:
    price_df = _price_dataframe(db, company, config)
    price_df = build_price_feature_frame(price_df)  # log_return, ma5, ma20, volatility_20d 추가

    requested = set(config.features)
    skipped = sorted(g.value for g in (requested - SUPPORTED_FEATURE_GROUPS))
    supported_requested = requested & SUPPORTED_FEATURE_GROUPS
    if not supported_requested:
        raise AnalysisDataError(
            "선택한 Feature 그룹 중 현재 지원되는 것이 없습니다 "
            f"(선택: {sorted(g.value for g in requested)}). "
            "price/volume/news_sentiment/news_frequency/event_type 중 하나 이상을 선택해주세요."
        )

    pieces: list[pd.DataFrame] = []
    base_columns: list[str] = []

    if FeatureGroup.PRICE in supported_requested:
        cols = ["close", "log_return", "ma5", "ma20"]
        pieces.append(price_df[cols])
        base_columns.extend(cols)
    if FeatureGroup.VOLUME in supported_requested:
        pieces.append(price_df[["volume"]])
        base_columns.append("volume")
    if FeatureGroup.NEWS_SENTIMENT in supported_requested or FeatureGroup.NEWS_FREQUENCY in supported_requested:
        news_df = _news_daily_aggregates(db, company, config)
        news_df = news_df.reindex(price_df.index)
        want_cols = []
        if FeatureGroup.NEWS_SENTIMENT in supported_requested:
            want_cols.append("news_sentiment")
        if FeatureGroup.NEWS_FREQUENCY in supported_requested:
            want_cols.append("news_frequency")
        selected = news_df[want_cols].fillna(0.0)
        pieces.append(selected)
        base_columns.extend(want_cols)
    if FeatureGroup.EVENT_TYPE in supported_requested:
        event_df = _event_type_daily_counts(db, company, config)
        event_df = event_df.reindex(price_df.index).fillna(0.0)
        pieces.append(event_df)
        base_columns.extend(list(event_df.columns))

    raw_features = pd.concat(pieces, axis=1)

    # 요청된 Lag(요구사항 33)을 base_columns 각각에 적용한다 (lag 0은 원본 그대로 유지).
    lags = [lag for lag in config.lags if lag != 0]
    if lags:
        for col in base_columns:
            raw_features = add_lag_features(raw_features, col, lags)

    y_full, task_type = _compute_target(price_df, config.target)

    feature_df = raw_features.dropna()
    if feature_df.empty:
        raise AnalysisDataError(
            "Feature를 계산할 수 있는 거래일이 없습니다 (이동평균/Lag 계산에 필요한 "
            "기간보다 조회 기간이 짧을 수 있습니다). 조회 기간을 늘려주세요."
        )

    latest_date = feature_df.index[-1].date()
    latest_features = feature_df.iloc[-1]

    y_aligned = y_full.reindex(feature_df.index)
    training_df = feature_df.assign(__target__=y_aligned).dropna(subset=["__target__"])

    if len(training_df) < MIN_TRAINING_ROWS:
        raise AnalysisDataError(
            f"학습 가능한 거래일이 부족합니다 (사용 가능 {len(training_df)}개, 최소 "
            f"{MIN_TRAINING_ROWS}개 필요). 조회 기간을 늘리거나 데이터가 더 쌓인 뒤 다시 시도해주세요."
        )

    X_train_df = training_df.drop(columns=["__target__"])
    y = training_df["__target__"]
    if task_type == "classification":
        y = y.astype(int)

    return FeatureMatrixResult(
        X_train_df=X_train_df,
        y=y,
        latest_features=latest_features,
        latest_date=latest_date,
        feature_columns=list(X_train_df.columns),
        task_type=task_type,
        skipped_feature_groups=skipped,
    )
