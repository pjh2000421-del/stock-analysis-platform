"""재무지표 직접 계산 테스트 (요구사항 68: Financial metric calculation)."""
from app.valuation import metrics as calc


def test_per_calculation():
    result = calc.per(price=100, eps=10)
    assert result.value == 10.0
    assert "EPS" in result.calculation_method


def test_per_na_when_eps_zero():
    result = calc.per(price=100, eps=0)
    assert result.value is None
    assert result.na_reason is not None


def test_pbr_calculation():
    result = calc.pbr(price=50, bps=25)
    assert result.value == 2.0


def test_roe_percentage():
    result = calc.roe(net_income=1000, avg_equity=10000)
    assert result.value == 10.0  # %


def test_operating_margin():
    result = calc.operating_margin(operating_income=200, revenue=1000)
    assert result.value == 20.0


def test_fcf_uses_zero_capex_when_missing_and_marks_estimated():
    result = calc.fcf(operating_cash_flow=500, capex=None)
    assert result.value == 500
    assert result.is_estimated is True


def test_debt_equity_ratio():
    result = calc.debt_equity(liabilities=2000, equity=1000)
    assert result.value == 200.0


def test_revenue_growth_yoy():
    result = calc.revenue_growth_yoy(current_revenue=120, prev_revenue=100)
    assert result.value == 20.0


def test_cagr_calculation():
    # 100 -> 133.1 over 3 years = 10% CAGR
    result = calc.cagr(begin_value=100, end_value=133.1, years=3)
    assert abs(result.value - 10.0) < 0.1


def test_cagr_na_for_negative_values():
    result = calc.cagr(begin_value=-100, end_value=50, years=3)
    assert result.value is None
