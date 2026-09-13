"""
백테스트 Service (요구사항 45) - Phase5.

TODO(Phase5): app/ml 예측 파이프라인이 완성된 후 아래 순서로 구현한다.
    1) 지정 기간 동안 매 시점 t에서 "그 시점까지의 정보만 사용한" 모델 예측을 재현
       (Point-in-Time 원칙 준수 - 미래 정보 사용 금지, 요구사항 63)
    2) buy_probability_threshold 이상일 때 매수, holding_period_days 이후 매도 가정
    3) transaction_cost_pct를 반영한 순수익률 계산
    4) 승률/누적수익률/Benchmark(KOSPI) 대비 수익률/Sharpe Ratio/MDD 계산

현재는 예측 파이프라인이 없으므로 임의의 신호로 "가짜 백테스트"를 만들지 않고
명확히 실행 불가 상태를 반환한다 (요구사항: 작동하지 않는 거대한 가짜 코드 생성 금지).
"""
from __future__ import annotations

from app.schemas.backtest import BacktestConfig, BacktestResult


def run_backtest(config: BacktestConfig) -> BacktestResult:
    return BacktestResult(ticker=config.ticker, is_available=False)
