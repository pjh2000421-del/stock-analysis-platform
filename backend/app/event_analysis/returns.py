"""
수익률/변동성/초과수익률 계산 유틸 (요구사항 15, 43).

Event Study, Historical Similarity 결과 화면, 그리고 일반적인 주가 분석에서
공통으로 사용하는 순수 계산 함수 모음이다. (DB/외부 API에 의존하지 않아 테스트 용이)
"""
from __future__ import annotations

import math


def simple_return(begin_price: float | None, end_price: float | None) -> float | None:
    """단순 수익률(%) = (end - begin) / begin * 100"""
    if begin_price in (None, 0) or end_price is None:
        return None
    return (end_price - begin_price) / begin_price * 100


def log_return(begin_price: float | None, end_price: float | None) -> float | None:
    """로그수익률 = ln(end / begin)"""
    if begin_price in (None, 0) or end_price in (None,) or begin_price <= 0 or (end_price or 0) <= 0:
        return None
    return math.log(end_price / begin_price)


def log_returns_series(prices: list[float]) -> list[float]:
    """일별 종가 리스트로부터 로그수익률 시계열을 계산한다. 길이는 len(prices)-1."""
    returns = []
    for i in range(1, len(prices)):
        r = log_return(prices[i - 1], prices[i])
        if r is not None:
            returns.append(r)
    return returns


def volatility(returns: list[float]) -> float | None:
    """수익률 리스트의 표준편차(변동성). 연율화하지 않은 raw 표준편차를 반환한다."""
    if not returns or len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return math.sqrt(variance)


def max_upside(prices: list[float], base_price: float | None = None) -> float | None:
    """기준가(base_price, 기본값=prices[0]) 대비 구간 내 최대 상승폭(%)."""
    if not prices:
        return None
    base = base_price if base_price is not None else prices[0]
    if not base:
        return None
    return (max(prices) - base) / base * 100


def max_drawdown(prices: list[float]) -> float | None:
    """구간 내 최대 낙폭(%, 음수로 표현). 고점 대비 이후 저점까지의 최대 하락률."""
    if not prices:
        return None
    peak = prices[0]
    max_dd = 0.0
    for p in prices:
        if p > peak:
            peak = p
        if peak:
            dd = (p - peak) / peak * 100
            if dd < max_dd:
                max_dd = dd
    return max_dd


def excess_return(asset_return_pct: float | None, benchmark_return_pct: float | None) -> float | None:
    """초과수익률(Abnormal/Excess Return) = 자산 수익률 - 벤치마크 수익률"""
    if asset_return_pct is None or benchmark_return_pct is None:
        return None
    return asset_return_pct - benchmark_return_pct


def return_at_horizon(prices_by_offset: dict[int, float], horizon: int) -> float | None:
    """Day 0 가격 대비 특정 horizon(거래일) 시점의 수익률(%)."""
    base = prices_by_offset.get(0)
    target = prices_by_offset.get(horizon)
    return simple_return(base, target)
