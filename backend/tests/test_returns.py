"""수익률/변동성 계산 테스트 (요구사항 68: Return calculation)."""
import math

from app.event_analysis.returns import (
    excess_return,
    log_return,
    log_returns_series,
    max_drawdown,
    max_upside,
    return_at_horizon,
    simple_return,
    volatility,
)


def test_simple_return_basic():
    assert simple_return(100, 110) == 10.0
    assert simple_return(100, 90) == -10.0


def test_simple_return_none_handling():
    assert simple_return(None, 110) is None
    assert simple_return(0, 110) is None
    assert simple_return(100, None) is None


def test_log_return_matches_math_log():
    expected = math.log(110 / 100)
    assert math.isclose(log_return(100, 110), expected)


def test_log_returns_series_length():
    prices = [100, 101, 99, 105]
    series = log_returns_series(prices)
    assert len(series) == 3


def test_volatility_zero_for_constant_returns():
    assert volatility([0.01, 0.01, 0.01]) == 0.0


def test_volatility_none_for_insufficient_data():
    assert volatility([0.01]) is None
    assert volatility([]) is None


def test_max_upside_and_drawdown():
    prices = [100, 120, 90, 130]
    assert max_upside(prices) == 30.0  # (130-100)/100
    dd = max_drawdown(prices)
    # 고점 120 이후 90까지 하락 = -25%
    assert math.isclose(dd, -25.0)


def test_excess_return():
    assert excess_return(7.2, 1.5) == 5.7 or math.isclose(excess_return(7.2, 1.5), 5.7)
    assert excess_return(None, 1.5) is None


def test_return_at_horizon():
    prices_by_offset = {0: 100.0, 5: 107.2}
    assert math.isclose(return_at_horizon(prices_by_offset, 5), 7.2)
