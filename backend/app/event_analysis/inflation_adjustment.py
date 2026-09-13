"""
물가 조정 (요구사항 13).

CPI Provider(한국은행 ECOS)가 아직 연동되지 않은 경우, amount_real은 계산하지 않고
amount_nominal만 제공하며 is_estimated=False, na_reason을 명시한다 (억지로 값을 채우지 않음).
CPI 데이터가 준비되면 아래 adjust_for_inflation()의 cpi_lookup 콜백만 교체하면 된다.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class InflationAdjustmentResult:
    amount_nominal: float
    amount_real: float | None
    base_year: int | None
    is_available: bool
    reason: str | None = None


def adjust_for_inflation(
    amount_nominal: float,
    event_date: date,
    base_date: date,
    cpi_lookup: dict[int, float] | None = None,
) -> InflationAdjustmentResult:
    """
    cpi_lookup: {연도: CPI 지수} 형태. None이면 CPI Provider 미연동 상태로 간주한다.
    실질금액 = 명목금액 * (기준연도 CPI / 사건연도 CPI)
    """
    if not cpi_lookup:
        return InflationAdjustmentResult(
            amount_nominal=amount_nominal,
            amount_real=None,
            base_year=None,
            is_available=False,
            reason="CPI 데이터 Provider가 연동되지 않아 물가조정 금액을 계산할 수 없습니다 (TODO).",
        )

    event_cpi = cpi_lookup.get(event_date.year)
    base_cpi = cpi_lookup.get(base_date.year)
    if not event_cpi or not base_cpi:
        return InflationAdjustmentResult(
            amount_nominal=amount_nominal,
            amount_real=None,
            base_year=base_date.year,
            is_available=False,
            reason=f"{event_date.year}년 또는 {base_date.year}년 CPI 데이터가 없습니다.",
        )

    amount_real = amount_nominal * (base_cpi / event_cpi)
    return InflationAdjustmentResult(
        amount_nominal=amount_nominal,
        amount_real=amount_real,
        base_year=base_date.year,
        is_available=True,
    )
