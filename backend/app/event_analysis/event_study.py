"""
Event Study 오케스트레이션 (요구사항 15, 43) - Phase2.

현재 news_events / prices 테이블에 데이터가 충분히 축적되면 이 모듈에서
DB 조회 -> returns.py 계산 -> EventMarketReaction 저장까지 연결한다.
Phase1에서는 계산 함수(returns.py)와 DB 모델까지 완성해 두고,
실제 배치/트리거 오케스트레이션은 TODO로 남긴다.

TODO(Phase2):
    1) news_events 테이블에서 아직 market_reaction이 계산되지 않은 Event 조회
    2) 해당 기업의 prices 테이블에서 event_date 전후 거래일 가격 조회
    3) returns.py 함수들로 return_1d/5d/20d/60d, volatility, drawdown 등 계산
    4) KOSPI/업종지수 대비 excess_return 계산 (market_reaction 테이블 저장)
    5) Event Overlay Chart용 -20D~+60D 정규화 시계열 생성
"""
from __future__ import annotations

from app.event_analysis.returns import (
    max_drawdown,
    max_upside,
    return_at_horizon,
    simple_return as simple_return_between,
    volatility,
)


def compute_event_market_reaction(
    prices_by_offset: dict[int, float],
    benchmark_prices_by_offset: dict[int, float] | None = None,
) -> dict:
    """
    prices_by_offset: {-20: close가격, -1: ..., 0: Day0 종가, 1: ..., 5: ..., 20: ..., 60: ...}
    이미 조회된 가격 데이터를 받아 반환/변동성/초과수익률을 계산하는 순수 함수.
    (DB/외부 조회는 이 함수 밖에서 수행하여 테스트 용이성을 확보한다.)
    """
    result: dict = {}
    # Day 0 자체의 반응(이벤트 전일 종가 -> 이벤트일 종가)
    result["return_0d"] = simple_return_between(prices_by_offset.get(-1), prices_by_offset.get(0))
    for horizon in (1, 5, 20, 60):
        result[f"return_{horizon}d"] = return_at_horizon(prices_by_offset, horizon)

    before_series = [
        prices_by_offset[k] for k in sorted(prices_by_offset) if -20 <= k <= 0 and k in prices_by_offset
    ]
    after_series = [
        prices_by_offset[k] for k in sorted(prices_by_offset) if 0 <= k <= 20 and k in prices_by_offset
    ]

    from app.event_analysis.returns import log_returns_series

    result["volatility_before"] = volatility(log_returns_series(before_series))
    result["volatility_after"] = volatility(log_returns_series(after_series))

    full_series = [prices_by_offset[k] for k in sorted(prices_by_offset) if k >= 0]
    result["max_upside"] = max_upside(full_series)
    result["max_drawdown"] = max_drawdown(full_series)

    if benchmark_prices_by_offset:
        for horizon in (1, 5, 20):
            asset_r = result.get(f"return_{horizon}d")
            bench_r = return_at_horizon(benchmark_prices_by_offset, horizon)
            if asset_r is not None and bench_r is not None:
                result[f"excess_return_{horizon}d"] = asset_r - bench_r
            else:
                result[f"excess_return_{horizon}d"] = None

    return result
