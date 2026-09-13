"""백테스트 스키마 (요구사항 45) - Phase5."""
from __future__ import annotations

from pydantic import BaseModel, Field


class BacktestConfig(BaseModel):
    ticker: str
    start_date: str
    end_date: str
    buy_probability_threshold: float = Field(0.65, description="이 확률 이상일 때 매수한다고 가정")
    holding_period_days: int = 5
    transaction_cost_pct: float = Field(0.02, description="왕복 거래비용(%) 가정치")


class BacktestResult(BaseModel):
    ticker: str
    total_trades: int | None = None
    win_rate: float | None = None
    cumulative_return_pct: float | None = None
    benchmark_return_pct: float | None = None
    sharpe_ratio: float | None = None
    max_drawdown_pct: float | None = None
    is_available: bool = False
    message: str = (
        "백테스트는 AI 예측 파이프라인(Phase3)이 준비된 이후 제공됩니다. "
        "Look-ahead Bias 방지를 위해 실제 예측 신호 없이는 백테스트를 실행하지 않습니다."
    )
