"""
WACC(가중평균자본비용) 자동 추정 (DCF Calculator 기본 가정값 제안용).

기존 문제: app/valuation/dcf.py의 run_dcf()는 WACC을 DCFAssumptions.wacc로 사용자에게서
그대로 받기만 했고, 그 기본값(9%)이 모든 종목에 동일하게 적용되었다 - 실제로는 종목마다
위험(베타)과 자본구조(자기자본/타인자본 비중)가 크게 다르므로 이는 "임시 placeholder"에
가까웠다. 이 모듈은 종목별 특성을 반영한 "제안 WACC"을 계산해 DCF Calculator를 열 때
초기값으로 미리 채워준다 - 사용자는 여전히 이 값을 자유롭게 수정할 수 있다(요구사항 22의
"사용자가 가정을 직접 조정" 원칙은 그대로 유지).

계산식 (표준 CAPM 기반 WACC):
    자기자본비용(Re) = 무위험이자율(Rf) + 베타(β) * 시장위험프리미엄(ERP)
    타인자본비용(Rd) = 이자비용 / 총차입금 (최근 재무제표 기준 실효 이자율)
    WACC = E/(E+D) * Re + D/(E+D) * Rd * (1 - 법인세율)

베타는 최근 가격 데이터(종목)와 KOSPI 지수의 일별 로그수익률로 직접 계산한 실제값이다.
무위험이자율/시장위험프리미엄은 app/core/config.py의 설정값(risk_free_rate,
equity_risk_premium)을 사용한다 - 실시간 국채금리 API 연동은 통계표코드를 신뢰성 있게
검증하지 못해 다음 단계로 미뤘다(요구사항 74, config.py 주석 참고).

데이터가 부족한 경우(가격 이력 부족, 차입금/이자비용 데이터 없음 등) 조용히 이상한 값을
만들지 않고, 업계 평균적인 가정(베타=1.0, 신용스프레드 가정)으로 대체하되 반드시
is_estimated 계열 플래그와 notes로 그 사실을 알린다(요구사항 74).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

logger_name = __name__

DEFAULT_BETA = 1.0
DEFAULT_CREDIT_SPREAD = 0.015  # 이자비용/총차입금 데이터가 없을 때만 사용하는 가정치


@dataclass
class WaccEstimate:
    wacc: float
    cost_of_equity: float
    cost_of_debt: float
    beta: float
    beta_is_estimated: bool
    cost_of_debt_is_estimated: bool
    equity_weight: float
    debt_weight: float
    risk_free_rate: float
    equity_risk_premium: float
    calculation_method: str
    notes: list[str] = field(default_factory=list)


def compute_beta_from_returns(stock_returns: np.ndarray, market_returns: np.ndarray) -> float | None:
    """두 로그수익률 배열(길이가 다르면 뒤쪽 min(len)개만 사용)로부터 베타를 계산한다.

    market_returns의 분산이 0이거나 표본이 너무 적으면(20개 미만) None을 반환해
    호출부가 기본 베타(1.0)로 대체하도록 한다.
    """
    n = min(len(stock_returns), len(market_returns))
    if n < 20:
        return None
    s = np.asarray(stock_returns[-n:], dtype=float)
    m = np.asarray(market_returns[-n:], dtype=float)
    if np.std(m) == 0:
        return None
    cov_matrix = np.cov(s, m)
    var_m = cov_matrix[1][1]
    if var_m == 0:
        return None
    return float(cov_matrix[0][1] / var_m)


def estimate_wacc(
    *,
    market_cap: float | None,
    total_borrowings: float | None,
    interest_expense: float | None,
    tax_rate: float,
    beta: float | None,
    risk_free_rate: float,
    equity_risk_premium: float,
) -> WaccEstimate:
    notes: list[str] = []

    beta_is_estimated = beta is None
    beta_value = beta if beta is not None else DEFAULT_BETA
    if beta_is_estimated:
        notes.append(
            "최근 가격 데이터가 부족하거나 KOSPI 지수 데이터를 가져오지 못해 베타를 직접 "
            "계산하지 못했습니다. 시장 평균 베타(1.0)로 대체했습니다."
        )

    cost_of_equity = risk_free_rate + beta_value * equity_risk_premium

    cost_of_debt_is_estimated = not (total_borrowings and interest_expense and total_borrowings > 0)
    if not cost_of_debt_is_estimated:
        cost_of_debt = interest_expense / total_borrowings  # type: ignore[operator]
    else:
        cost_of_debt = risk_free_rate + DEFAULT_CREDIT_SPREAD
        notes.append(
            "최근 재무제표에 이자비용 또는 총차입금 데이터가 없어 타인자본비용을 "
            f"무위험이자율 + 가정 신용스프레드({DEFAULT_CREDIT_SPREAD * 100:.1f}%p)로 근사했습니다."
        )

    market_cap_v = market_cap or 0.0
    debt_v = total_borrowings or 0.0
    total_capital = market_cap_v + debt_v
    if total_capital <= 0:
        equity_weight, debt_weight = 1.0, 0.0
        notes.append("시가총액/차입금 데이터가 없어 자기자본 100% 구조로 가정했습니다.")
    else:
        equity_weight = market_cap_v / total_capital
        debt_weight = debt_v / total_capital

    wacc = equity_weight * cost_of_equity + debt_weight * cost_of_debt * (1 - tax_rate)

    return WaccEstimate(
        wacc=round(wacc, 4),
        cost_of_equity=round(cost_of_equity, 4),
        cost_of_debt=round(cost_of_debt, 4),
        beta=round(beta_value, 3),
        beta_is_estimated=beta_is_estimated,
        cost_of_debt_is_estimated=cost_of_debt_is_estimated,
        equity_weight=round(equity_weight, 4),
        debt_weight=round(debt_weight, 4),
        risk_free_rate=risk_free_rate,
        equity_risk_premium=equity_risk_premium,
        calculation_method=(
            "WACC = E/(E+D)*Re + D/(E+D)*Rd*(1-법인세율), "
            "Re(자기자본비용) = 무위험이자율 + 베타*시장위험프리미엄(CAPM), "
            "Rd(타인자본비용) = 이자비용/총차입금(최근 재무제표), "
            "베타 = 최근 종목 일별수익률과 KOSPI 일별수익률의 공분산/KOSPI 분산"
        ),
        notes=notes,
    )
