"""백테스트 API (요구사항 45, 55) - Phase5."""
from __future__ import annotations

from fastapi import APIRouter

from app.schemas.backtest import BacktestConfig, BacktestResult
from app.services.backtest_service import run_backtest

router = APIRouter(prefix="/backtest", tags=["backtest"])


@router.post("", response_model=BacktestResult)
def post_backtest(config: BacktestConfig):
    return run_backtest(config)
