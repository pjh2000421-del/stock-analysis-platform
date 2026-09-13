"""종합 점수 계산 테스트 (요구사항 25: 투명한 weight 기반 점수)."""
from app.valuation.scoring import compute_category_score, compute_total_score


def test_valuation_score_low_per_is_good():
    score, components = compute_category_score("valuation", {"per": 8.0, "pbr": 0.7, "ev_ebitda": 4.0})
    assert score == 100.0
    assert components["per"] == 100.0


def test_valuation_score_high_per_is_bad():
    score, _ = compute_category_score("valuation", {"per": 40.0, "pbr": 4.0, "ev_ebitda": 20.0})
    assert score == 0.0


def test_score_none_when_no_data():
    score, components = compute_category_score("valuation", {"per": None, "pbr": None, "ev_ebitda": None})
    assert score is None
    assert all(v is None for v in components.values())


def test_total_score_weighted_average():
    total = compute_total_score(
        {"valuation": 80.0, "growth": 60.0, "profitability": 70.0, "financial_health": 90.0}
    )
    assert total == 75.0  # 균등 weight(0.25씩) 가정 시 평균
