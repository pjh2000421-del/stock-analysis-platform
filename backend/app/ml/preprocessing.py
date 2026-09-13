"""
ML 전처리 파이프라인 (요구사항 28~31).

핵심 원칙:
    - Log Return은 Scaling 전에 계산한다.
    - Min-Max Scaling은 종목별로 개별 적용한다.
    - Train/Test 분리 후 Train 기준으로만 scaler를 fit하고, Test에는 transform만 적용한다.
    - scaler는 저장 가능해야 하며 inverse_transform을 지원해야 한다 (joblib으로 저장, ml/registry.py 참고).
    - Data Leakage 방지 (요구사항 30, 63): 이 모듈은 순수 배열/DataFrame 연산만 수행하며,
      "어떤 시점까지의 데이터를 사용할지"는 호출자(Point-in-Time 필터링)의 책임이다.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler


def compute_log_return(close_prices: pd.Series) -> pd.Series:
    """종가 Series로부터 로그수익률 Series를 계산한다 (첫 값은 NaN)."""
    return np.log(close_prices / close_prices.shift(1))


@dataclass
class ScaledDataset:
    train_scaled: np.ndarray
    test_scaled: np.ndarray
    scaler: MinMaxScaler
    feature_columns: list[str]


def fit_scaler_on_train_only(
    train_df: pd.DataFrame, test_df: pd.DataFrame, feature_columns: list[str]
) -> ScaledDataset:
    """
    Train 데이터로만 MinMaxScaler를 fit하고, Test 데이터에는 transform만 적용한다.
    (요구사항 31: Data Leakage 방지의 핵심 - Test 정보가 Scaler에 반영되면 안 됨)
    """
    scaler = MinMaxScaler(feature_range=(0, 1))
    train_values = train_df[feature_columns].to_numpy()
    test_values = test_df[feature_columns].to_numpy()

    train_scaled = scaler.fit_transform(train_values)
    test_scaled = scaler.transform(test_values)

    return ScaledDataset(
        train_scaled=train_scaled, test_scaled=test_scaled, scaler=scaler, feature_columns=feature_columns
    )


def inverse_transform(scaler: MinMaxScaler, scaled_values: np.ndarray) -> np.ndarray:
    return scaler.inverse_transform(scaled_values)


def build_price_feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    """
    OHLCV DataFrame(columns: open, high, low, close, volume)으로부터
    log_return, 단순 이동평균(MA5/MA20), 변동성(20일 rolling std) 등 기본 Feature를 생성한다.
    개별 종목 단위로 호출되어야 한다 (종목마다 개별 정규화하기 위함, 요구사항 31).
    """
    out = df.copy()
    out["log_return"] = compute_log_return(out["close"])
    out["ma5"] = out["close"].rolling(window=5).mean()
    out["ma20"] = out["close"].rolling(window=20).mean()
    out["volatility_20d"] = out["log_return"].rolling(window=20).std()
    return out
