"""Lag Feature 생성 (요구사항 33)."""
from __future__ import annotations

import pandas as pd


def add_lag_features(df: pd.DataFrame, column: str, lags: list[int]) -> pd.DataFrame:
    """
    지정된 컬럼(예: 뉴스 감정 점수)에 대해 lag(t-1, t-2, ...) Feature를 추가한다.
    lags에 0이 포함되면 원본 값(t 시점)도 그대로 유지된다.
    """
    out = df.copy()
    for lag in lags:
        if lag == 0:
            continue
        out[f"{column}_lag{lag}"] = out[column].shift(lag)
    return out
