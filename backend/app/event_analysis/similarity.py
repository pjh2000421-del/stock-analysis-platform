"""
과거 유사 뉴스 Similarity Score 계산 (요구사항 11).

가중치는 app/config/similarity_weights.json 에서 로드하며 하드코딩하지 않는다.
Semantic similarity는 Phase2에서 sentence-transformers 임베딩 코사인 유사도로 구현 예정이며,
현재는 인터페이스와 나머지(Event/규모/산업 등) 유사도 계산 로직을 우선 완성한다.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.config.loader import load_similarity_weights


@dataclass
class EventFeatureForSimilarity:
    """유사도 비교에 필요한 Event 특성 (현재/과거 공통 포맷)."""

    event_type: str
    event_subtype: str | None = None
    amount_real: float | None = None
    revenue_ratio: float | None = None
    market_cap_ratio: float | None = None
    industry: str | None = None
    product: str | None = None
    technology: str | None = None
    counterparty: str | None = None
    is_domestic: bool | None = None
    commercialization_stage: str | None = None
    sentiment: float | None = None
    semantic_embedding: list[float] | None = None
    # 당시 시장환경/산업사이클/Valuation 상태는 범주형 문자열로 단순화하여 비교 (Phase2 확장 예정)
    market_regime: str | None = None
    industry_cycle: str | None = None
    valuation_state: str | None = None


def _ratio_similarity(a: float | None, b: float | None) -> float | None:
    """두 스칼라 값의 상대적 유사도 (0~1). 값 차이가 클수록 0에 가까워진다."""
    if a is None or b is None:
        return None
    if a == 0 and b == 0:
        return 1.0
    denom = max(abs(a), abs(b), 1e-9)
    return max(0.0, 1.0 - abs(a - b) / denom)


def _categorical_similarity(a: str | None, b: str | None) -> float | None:
    if a is None or b is None:
        return None
    return 1.0 if a == b else 0.0


def _cosine_similarity(a: list[float] | None, b: list[float] | None) -> float | None:
    if not a or not b or len(a) != len(b):
        return None
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return None
    return dot / (norm_a * norm_b)


def compute_similarity_score(
    current: EventFeatureForSimilarity, historical: EventFeatureForSimilarity
) -> dict:
    """
    요구사항 11의 각 하위 유사도를 계산하고, config weight로 가중합하여
    0~100 스케일의 final_score를 반환한다.
    반환값에는 각 하위 점수도 포함하여 투명성을 확보한다.
    """
    weights = load_similarity_weights()["weights"]

    raw_scores: dict[str, float | None] = {
        "semantic_similarity": _cosine_similarity(
            current.semantic_embedding, historical.semantic_embedding
        ),
        "event_type_match": _categorical_similarity(current.event_type, historical.event_type),
        "event_subtype_match": _categorical_similarity(
            current.event_subtype, historical.event_subtype
        ),
        "amount_real_similarity": _ratio_similarity(current.amount_real, historical.amount_real),
        "revenue_ratio_similarity": _ratio_similarity(
            current.revenue_ratio, historical.revenue_ratio
        ),
        "market_cap_ratio_similarity": _ratio_similarity(
            current.market_cap_ratio, historical.market_cap_ratio
        ),
        "industry_match": _categorical_similarity(current.industry, historical.industry),
        "product_technology_similarity": _categorical_similarity(
            current.product or current.technology, historical.product or historical.technology
        ),
        "counterparty_similarity": _categorical_similarity(
            current.counterparty, historical.counterparty
        ),
        "domestic_overseas_match": (
            1.0
            if (current.is_domestic is not None and current.is_domestic == historical.is_domestic)
            else (0.0 if current.is_domestic is not None and historical.is_domestic is not None else None)
        ),
        "commercialization_stage_match": _categorical_similarity(
            current.commercialization_stage, historical.commercialization_stage
        ),
        "market_environment_similarity": _categorical_similarity(
            current.market_regime, historical.market_regime
        ),
        "valuation_state_similarity": _categorical_similarity(
            current.valuation_state, historical.valuation_state
        ),
        "sentiment_similarity": _ratio_similarity(current.sentiment, historical.sentiment),
    }

    weighted_sum = 0.0
    weight_total = 0.0
    for key, score in raw_scores.items():
        weight = weights.get(key, 0.0)
        if score is not None:
            weighted_sum += score * weight
            weight_total += weight

    final_score = (weighted_sum / weight_total * 100) if weight_total > 0 else 0.0

    return {
        "final_score": round(final_score, 1),
        "components": raw_scores,
        "semantic_score": raw_scores["semantic_similarity"],
        "event_score": raw_scores["event_type_match"],
        "scale_score": raw_scores["amount_real_similarity"],
        "market_score": raw_scores["market_environment_similarity"],
    }
