"""과거 유사 뉴스 Similarity 계산 테스트 (요구사항 68: Similarity logic)."""
from app.event_analysis.similarity import EventFeatureForSimilarity, compute_similarity_score


def test_identical_events_score_high():
    a = EventFeatureForSimilarity(
        event_type="SUPPLY_CONTRACT",
        event_subtype="contract_signed",
        amount_real=1000.0,
        revenue_ratio=0.05,
        market_cap_ratio=0.03,
        industry="반도체",
        is_domestic=True,
    )
    b = EventFeatureForSimilarity(
        event_type="SUPPLY_CONTRACT",
        event_subtype="contract_signed",
        amount_real=1000.0,
        revenue_ratio=0.05,
        market_cap_ratio=0.03,
        industry="반도체",
        is_domestic=True,
    )
    result = compute_similarity_score(a, b)
    assert result["final_score"] > 50  # 동일 조건이면 높은 점수가 나와야 함


def test_completely_different_events_score_low():
    a = EventFeatureForSimilarity(event_type="SUPPLY_CONTRACT", industry="반도체")
    b = EventFeatureForSimilarity(event_type="LEGAL", industry="화학")
    result = compute_similarity_score(a, b)
    assert result["final_score"] < 50


def test_final_score_within_0_100():
    a = EventFeatureForSimilarity(event_type="M_AND_A")
    b = EventFeatureForSimilarity(event_type="M_AND_A")
    result = compute_similarity_score(a, b)
    assert 0 <= result["final_score"] <= 100
