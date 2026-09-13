"""STL Decomposition (요구사항 32).

statsmodels.tsa.seasonal.STL 을 사용하여 Trend/Seasonal/Residual로 분해한다.
Residual은 이후 분석 Target 또는 Feature로 사용될 수 있다.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.core.errors import ProviderUnavailableError


@dataclass
class STLResult:
    trend: pd.Series
    seasonal: pd.Series
    residual: pd.Series


def decompose(series: pd.Series, period: int = 5) -> STLResult:
    """
    series: 시계열 (예: 종가 또는 로그수익률), DatetimeIndex 권장.
    period: 계절성 주기 (거래일 기준 기본값 5 = 주간 패턴 근사치)
    """
    try:
        from statsmodels.tsa.seasonal import STL
    except ImportError as exc:  # pragma: no cover
        raise ProviderUnavailableError("statsmodels_stl", "statsmodels 패키지가 설치되어 있지 않습니다.") from exc

    result = STL(series, period=period, robust=True).fit()
    return STLResult(trend=result.trend, seasonal=result.seasonal, residual=result.resid)
