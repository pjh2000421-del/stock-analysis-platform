"""
종목 베타(β) 계산 Service.

WACC 자동 추정(app/valuation/wacc.py)에 필요한 베타를 최근 종목 가격과 KOSPI(KS11)
지수의 일별 로그수익률로 직접 계산한다. app/services/dcf_service.py(DCF Calculator 제안
가정값)와 app/services/financial_service.py(재무지표 화면의 WACC)가 공통으로 사용한다.
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.company import Company
from app.providers.macro_provider import get_macro_provider
from app.services.price_service import get_prices_in_range
from app.valuation.wacc import compute_beta_from_returns

logger = get_logger(__name__)

# 최소 60거래일 이상 확보하기 위해 캘린더 기준 약 1.5년치를 조회한다.
BETA_LOOKBACK_DAYS = 540
MIN_BETA_OBSERVATIONS = 40


def compute_company_beta(db: Session, company: Company) -> float | None:
    """최근 종목 가격과 KOSPI(KS11) 지수의 일별 로그수익률로 베타를 계산한다.

    가격 이력이 부족하거나 지수 Provider가 실패하면(예: 배포 서버 IP에서 KRX 계열
    소스가 막히는 경우 - 이 프로젝트에서 실제로 겪은 문제) None을 반환해 호출부가
    시장 평균 베타(1.0)로 안전하게 대체하도록 한다 (요구사항 74: 숫자를 함부로 만들지 않음).
    """
    end = date.today()
    start = end - timedelta(days=BETA_LOOKBACK_DAYS)

    try:
        bars = get_prices_in_range(db, company, start, end)
    except Exception:  # noqa: BLE001 - 베타는 보조 지표이므로 실패해도 호출부 전체가 죽으면 안 됨
        logger.exception("베타 계산용 가격 조회 실패: %s", company.ticker)
        return None
    if len(bars) < MIN_BETA_OBSERVATIONS:
        return None

    closes = pd.Series({b.date: b.close for b in bars if b.close is not None}).sort_index()
    if len(closes) < MIN_BETA_OBSERVATIONS:
        return None
    stock_returns = np.log(closes / closes.shift(1)).dropna()

    macro = get_macro_provider()
    try:
        result = macro.get_market_index("KS11", start, end)
    except Exception:  # noqa: BLE001
        logger.exception("베타 계산용 KOSPI 지수 조회 실패")
        return None
    if result.status != "ok" or result.data is None or getattr(result.data, "empty", True):
        return None

    market_df = result.data
    close_col = "Close" if "Close" in market_df.columns else market_df.columns[0]
    market_returns = np.log(market_df[close_col] / market_df[close_col].shift(1)).dropna()

    aligned = pd.concat(
        [stock_returns.rename("stock"), market_returns.rename("market")], axis=1, join="inner"
    ).dropna()
    if len(aligned) < MIN_BETA_OBSERVATIONS:
        return None

    return compute_beta_from_returns(aligned["stock"].to_numpy(), aligned["market"].to_numpy())
