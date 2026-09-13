"""
Fundamental 지표 직접 계산 (요구사항 18, 74의 Fallback 원칙).

가능한 경우 외부 사이트의 계산된 숫자를 그대로 쓰지 않고,
공식 재무데이터(OpenDART) + 시장가(주가)로부터 원자료 기반 직접 계산을 우선한다.
각 함수는 (value, calculation_method) 튜플을 반환하며, 계산 불가 시 (None, 사유)를 반환한다.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CalculatedMetric:
    value: float | None
    calculation_method: str
    is_estimated: bool = False
    na_reason: str | None = None
    # 값이 없는 이유가 단순 데이터 부족이 아니라 "적자/자본잠식" 등 구조적인 상태라서
    # 원래 지표(배수) 자체가 의미를 갖지 못하는 경우 True. 화면에서는 "N/A" 대신
    # na_reason에 담긴 짧은 라벨("적자", "자본잠식" 등)을 그대로 보여주기 위한 플래그다.
    is_deficit: bool = False

    @staticmethod
    def na(method: str, reason: str) -> "CalculatedMetric":
        return CalculatedMetric(value=None, calculation_method=method, na_reason=reason)

    @staticmethod
    def deficit(method: str, label: str) -> "CalculatedMetric":
        return CalculatedMetric(value=None, calculation_method=method, na_reason=label, is_deficit=True)


def _safe_div(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def per(price: float | None, eps: float | None) -> CalculatedMetric:
    """PER = 주가 / EPS.

    EPS(주당순이익)가 음수, 즉 당기순손실(적자) 상태이면 PER을 음수 배수로
    그대로 계산하지 않는다. 음수 PER은 수학적으로는 계산되어도 "저평가/고평가"
    관점에서 아무 의미가 없고, 오히려 낮을수록 좋다는 정규화 규칙(app/valuation/scoring.py)에
    걸려 적자 기업이 "매우 저평가"로 왜곡 채점되는 문제가 있었다. 따라서 적자 구간은
    명확히 "적자"로 분리해 N/A 처리한다.
    """
    method = "Price / EPS"
    if price is None or eps is None:
        return CalculatedMetric.na(method, "주가 또는 EPS 데이터 없음")
    if eps < 0:
        return CalculatedMetric.deficit(method, "적자")
    if eps == 0:
        return CalculatedMetric.na(method, "당기순이익이 0이라 PER 산정 불가")
    return CalculatedMetric(_safe_div(price, eps), method)


def pbr(price: float | None, bps: float | None) -> CalculatedMetric:
    """PBR = 주가 / BPS. BPS가 음수(자본총계가 마이너스, 완전자본잠식)이면
    PER과 같은 이유로 "자본잠식"으로 명확히 표시하고 배수로 계산하지 않는다.
    """
    method = "Price / BPS(자본총계/발행주식수)"
    if price is None or bps is None:
        return CalculatedMetric.na(method, "주가 또는 BPS 데이터 없음")
    if bps < 0:
        return CalculatedMetric.deficit(method, "자본잠식")
    if bps == 0:
        return CalculatedMetric.na(method, "자본총계가 0이라 PBR 산정 불가")
    return CalculatedMetric(_safe_div(price, bps), method)


def psr(market_cap: float | None, revenue: float | None) -> CalculatedMetric:
    method = "시가총액 / 매출액"
    if market_cap is None or revenue in (None, 0):
        return CalculatedMetric.na(method, "시가총액 또는 매출액 데이터 없음")
    return CalculatedMetric(_safe_div(market_cap, revenue), method)


def eps(net_income: float | None, shares_outstanding: float | None) -> CalculatedMetric:
    method = "당기순이익 / 발행주식수"
    if net_income is None or shares_outstanding in (None, 0):
        return CalculatedMetric.na(method, "당기순이익 또는 발행주식수 데이터 없음")
    return CalculatedMetric(_safe_div(net_income, shares_outstanding), method)


def bps(equity: float | None, shares_outstanding: float | None) -> CalculatedMetric:
    method = "자본총계 / 발행주식수"
    if equity is None or shares_outstanding in (None, 0):
        return CalculatedMetric.na(method, "자본총계 또는 발행주식수 데이터 없음")
    return CalculatedMetric(_safe_div(equity, shares_outstanding), method)


def ebitda(
    operating_income: float | None,
    depreciation_amortization: float | None,
    non_cash_adjustments_total: float | None = None,
) -> CalculatedMetric:
    """EBITDA = 영업이익 + 감가상각비(D&A). OpenDART 현금흐름표의 '감가상각비' 계정을 사용한다.

    일부 대기업(예: 삼성전자)은 현금흐름표에서 감가상각비를 손상차손/이연법인세 등
    다른 비현금 항목들과 함께 "조정" 한 줄로만 합산 공시하여 감가상각비만 따로 뽑아낼 수
    없다. 이 경우 감가상각비 대신 그 "조정" 합계(non_cash_adjustments_total)를 근사치로
    사용하되, 감가상각비 외의 다른 항목도 섞여 있어 실제 EBITDA와 오차가 있을 수 있으므로
    반드시 is_estimated=True로 표시한다(요구사항 74: 추정치는 추정치로 명시).
    """
    method = "영업이익 + 감가상각비"
    if operating_income is not None and depreciation_amortization is not None:
        return CalculatedMetric(operating_income + depreciation_amortization, method)
    if operating_income is not None and non_cash_adjustments_total is not None:
        return CalculatedMetric(
            operating_income + non_cash_adjustments_total,
            "영업이익 + 현금흐름표 비현금성 조정 합계(감가상각비 단독 공시 없어 근사치)",
            is_estimated=True,
        )
    return CalculatedMetric.na(method, "영업이익 또는 감가상각비 데이터 없음")


def net_debt(total_borrowings: float | None, cash_and_equivalents: float | None) -> CalculatedMetric:
    """순차입금 = 총차입금(단기+유동성장기부채+사채+장기차입금) - 현금및현금성자산."""
    method = "총차입금 - 현금및현금성자산"
    if total_borrowings is None or cash_and_equivalents is None:
        return CalculatedMetric.na(method, "총차입금 또는 현금성자산 데이터 없음")
    return CalculatedMetric(total_borrowings - cash_and_equivalents, method)


def enterprise_value(market_cap: float | None, net_debt_value: float | None) -> CalculatedMetric:
    """EV(기업가치) = 시가총액 + 순차입금."""
    method = "시가총액 + 순차입금"
    if market_cap is None or net_debt_value is None:
        return CalculatedMetric.na(method, "시가총액 또는 순차입금 데이터 없음")
    return CalculatedMetric(market_cap + net_debt_value, method)


def ev_ebitda(
    enterprise_value: float | None, ebitda: float | None, ebitda_is_estimated: bool = False
) -> CalculatedMetric:
    """EV / EBITDA. PER/PBR과 같은 이유로 EBITDA가 0 이하(적자)면 배수로 계산하지 않고
    "적자"로 명확히 표시한다 (낮을수록 좋다는 정규화 규칙에서 음수 배수가 왜곡 채점되는 것을 방지).
    EBITDA 자체가 근사치(ebitda_is_estimated)면 이 배수도 추정치로 함께 표시한다.
    """
    method = "EV / EBITDA (EBITDA = 영업이익 + 감가상각비)"
    if enterprise_value is None or ebitda is None:
        return CalculatedMetric.na(method, "EV 또는 EBITDA 데이터 없음")
    if ebitda <= 0:
        return CalculatedMetric.deficit(method, "적자")
    return CalculatedMetric(_safe_div(enterprise_value, ebitda), method, is_estimated=ebitda_is_estimated)


def net_debt_ebitda(
    net_debt_value: float | None, ebitda: float | None, ebitda_is_estimated: bool = False
) -> CalculatedMetric:
    method = "순차입금 / EBITDA"
    if net_debt_value is None or ebitda is None:
        return CalculatedMetric.na(method, "순차입금 또는 EBITDA 데이터 없음")
    if ebitda <= 0:
        return CalculatedMetric.deficit(method, "적자")
    return CalculatedMetric(_safe_div(net_debt_value, ebitda), method, is_estimated=ebitda_is_estimated)


def roe(net_income: float | None, avg_equity: float | None) -> CalculatedMetric:
    method = "당기순이익 / 평균자본총계"
    if net_income is None or avg_equity in (None, 0):
        return CalculatedMetric.na(method, "당기순이익 또는 평균자본 데이터 없음")
    return CalculatedMetric(_safe_div(net_income, avg_equity) * 100, method)


def roa(net_income: float | None, avg_assets: float | None) -> CalculatedMetric:
    method = "당기순이익 / 평균자산총계"
    if net_income is None or avg_assets in (None, 0):
        return CalculatedMetric.na(method, "당기순이익 또는 평균자산 데이터 없음")
    return CalculatedMetric(_safe_div(net_income, avg_assets) * 100, method)


def roic(nopat: float | None, invested_capital: float | None) -> CalculatedMetric:
    method = "NOPAT(영업이익*(1-법인세율)) / 투하자본(자본총계+순차입금)"
    if nopat is None or invested_capital in (None, 0):
        return CalculatedMetric.na(method, "NOPAT 또는 투하자본 데이터 없음")
    return CalculatedMetric(_safe_div(nopat, invested_capital) * 100, method)


def operating_margin(operating_income: float | None, revenue: float | None) -> CalculatedMetric:
    method = "영업이익 / 매출액"
    if operating_income is None or revenue in (None, 0):
        return CalculatedMetric.na(method, "영업이익 또는 매출액 데이터 없음")
    return CalculatedMetric(_safe_div(operating_income, revenue) * 100, method)


def net_margin(net_income: float | None, revenue: float | None) -> CalculatedMetric:
    method = "당기순이익 / 매출액"
    if net_income is None or revenue in (None, 0):
        return CalculatedMetric.na(method, "당기순이익 또는 매출액 데이터 없음")
    return CalculatedMetric(_safe_div(net_income, revenue) * 100, method)


def fcf(operating_cash_flow: float | None, capex: float | None) -> CalculatedMetric:
    method = "영업활동현금흐름 - Capex"
    if operating_cash_flow is None:
        return CalculatedMetric.na(method, "영업활동현금흐름 데이터 없음")
    capex_v = capex or 0.0
    return CalculatedMetric(operating_cash_flow - capex_v, method, is_estimated=capex is None)


def fcf_margin(fcf_value: float | None, revenue: float | None) -> CalculatedMetric:
    method = "FCF / 매출액"
    if fcf_value is None or revenue in (None, 0):
        return CalculatedMetric.na(method, "FCF 또는 매출액 데이터 없음")
    return CalculatedMetric(_safe_div(fcf_value, revenue) * 100, method)


def debt_equity(liabilities: float | None, equity: float | None) -> CalculatedMetric:
    method = "부채총계 / 자본총계"
    if liabilities is None or equity in (None, 0):
        return CalculatedMetric.na(method, "부채 또는 자본 데이터 없음")
    return CalculatedMetric(_safe_div(liabilities, equity) * 100, method)


def current_ratio(current_assets: float | None, current_liabilities: float | None) -> CalculatedMetric:
    method = "유동자산 / 유동부채"
    if current_assets is None or current_liabilities in (None, 0):
        return CalculatedMetric.na(method, "유동자산 또는 유동부채 데이터 없음")
    return CalculatedMetric(_safe_div(current_assets, current_liabilities) * 100, method)


def quick_ratio(
    current_assets: float | None, inventory: float | None, current_liabilities: float | None
) -> CalculatedMetric:
    method = "(유동자산 - 재고자산) / 유동부채"
    if current_assets is None or current_liabilities in (None, 0):
        return CalculatedMetric.na(method, "유동자산 또는 유동부채 데이터 없음")
    inv = inventory or 0.0
    return CalculatedMetric(_safe_div(current_assets - inv, current_liabilities) * 100, method, is_estimated=inventory is None)


def interest_coverage(operating_income: float | None, interest_expense: float | None) -> CalculatedMetric:
    method = "영업이익 / 이자비용"
    if operating_income is None or interest_expense in (None, 0):
        return CalculatedMetric.na(method, "영업이익 또는 이자비용 데이터 없음")
    return CalculatedMetric(_safe_div(operating_income, interest_expense), method)


def revenue_growth_yoy(current_revenue: float | None, prev_revenue: float | None) -> CalculatedMetric:
    method = "(당기 매출액 - 전기 매출액) / 전기 매출액"
    if current_revenue is None or prev_revenue in (None, 0):
        return CalculatedMetric.na(method, "당기 또는 전기 매출액 데이터 없음")
    return CalculatedMetric(_safe_div(current_revenue - prev_revenue, prev_revenue) * 100, method)


def cagr(begin_value: float | None, end_value: float | None, years: int) -> CalculatedMetric:
    method = f"CAGR = (기말값/기초값)^(1/{years}) - 1"
    if begin_value in (None, 0) or end_value is None or years <= 0:
        return CalculatedMetric.na(method, "기초/기말 값 부족")
    if begin_value <= 0 or end_value <= 0:
        return CalculatedMetric.na(method, "음수 값으로 CAGR 계산 불가")
    value = ((end_value / begin_value) ** (1 / years) - 1) * 100
    return CalculatedMetric(value, method)
