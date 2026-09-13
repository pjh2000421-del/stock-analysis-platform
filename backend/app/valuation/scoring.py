"""
종합 기업 분석 점수 계산 (요구사항 25).

- 점수 계산식을 투명하게 공개한다 (black-box 금지).
- weight는 app/config/scoring_weights.json 에서 로드한다.
- 정규화 방식: 각 지표를 업종 관행상 "우수~취약" 구간으로 매핑하는 단순 선형/구간 정규화를
  사용하며, 그 구간 기준 자체도 이 파일에 상수로 명시하여 추적 가능하게 한다.
"""
from __future__ import annotations

from app.config.loader import load_scoring_weights


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _normalize_lower_is_better(value: float | None, good: float, bad: float) -> float | None:
    """값이 낮을수록 좋은 지표(PER, PBR, Debt/Equity 등) 정규화. good <= bad 가정."""
    if value is None:
        return None
    if value <= good:
        return 100.0
    if value >= bad:
        return 0.0
    return _clip((bad - value) / (bad - good) * 100, 0, 100)


def _normalize_higher_is_better(value: float | None, bad: float, good: float) -> float | None:
    """값이 높을수록 좋은 지표(ROE, 성장률 등) 정규화. bad <= good 가정."""
    if value is None:
        return None
    if value <= bad:
        return 0.0
    if value >= good:
        return 100.0
    return _clip((value - bad) / (good - bad) * 100, 0, 100)


# 정규화 기준값 (업종 평균적 관행에 기반한 근사치 - 필요 시 조정 가능)
NORMALIZATION_RULES = {
    "per": {"type": "lower_is_better", "good": 8.0, "bad": 40.0},
    "pbr": {"type": "lower_is_better", "good": 0.7, "bad": 4.0},
    "ev_ebitda": {"type": "lower_is_better", "good": 4.0, "bad": 20.0},
    "revenue_growth_yoy": {"type": "higher_is_better", "bad": -10.0, "good": 30.0},
    "eps_growth_yoy": {"type": "higher_is_better", "bad": -20.0, "good": 40.0},
    "operating_income_growth_yoy": {"type": "higher_is_better", "bad": -20.0, "good": 40.0},
    "roe": {"type": "higher_is_better", "bad": 0.0, "good": 20.0},
    "operating_margin": {"type": "higher_is_better", "bad": 0.0, "good": 20.0},
    "net_margin": {"type": "higher_is_better", "bad": 0.0, "good": 15.0},
    "debt_equity": {"type": "lower_is_better", "good": 50.0, "bad": 200.0},
    "current_ratio": {"type": "higher_is_better", "bad": 80.0, "good": 200.0},
    "interest_coverage": {"type": "higher_is_better", "bad": 1.0, "good": 10.0},
}


def _normalize(metric_name: str, value: float | None) -> float | None:
    rule = NORMALIZATION_RULES.get(metric_name)
    if rule is None or value is None:
        return None
    if rule["type"] == "lower_is_better":
        return _normalize_lower_is_better(value, rule["good"], rule["bad"])
    return _normalize_higher_is_better(value, rule["bad"], rule["good"])


def compute_category_score(category: str, raw_metrics: dict[str, float | None]) -> tuple[float | None, dict]:
    """
    category: "valuation" | "growth" | "profitability" | "financial_health"
    raw_metrics: {"per": 18.2, "pbr": 1.4, ...} 형태의 원본 지표 값
    반환: (0~100 점수 또는 None, 세부 정규화 점수 dict)
    """
    weights_config = load_scoring_weights()
    component_weights: dict[str, float] = weights_config[f"{category}_component_weights"]

    components: dict[str, float | None] = {}
    weighted_sum = 0.0
    weight_total = 0.0

    for metric_name, weight in component_weights.items():
        norm_score = _normalize(metric_name, raw_metrics.get(metric_name))
        components[metric_name] = norm_score
        if norm_score is not None:
            weighted_sum += norm_score * weight
            weight_total += weight

    if weight_total == 0:
        return None, components

    # 사용 가능한 지표만으로 재정규화 (일부 지표 N/A 시에도 점수 산출 가능하도록)
    score = weighted_sum / weight_total
    return round(score, 1), components


def compute_total_score(category_scores: dict[str, float | None]) -> float | None:
    weights_config = load_scoring_weights()
    category_weights: dict[str, float] = weights_config["category_weights"]

    weighted_sum = 0.0
    weight_total = 0.0
    for category, weight in category_weights.items():
        score = category_scores.get(category)
        if score is not None:
            weighted_sum += score * weight
            weight_total += weight

    if weight_total == 0:
        return None
    return round(weighted_sum / weight_total, 1)
