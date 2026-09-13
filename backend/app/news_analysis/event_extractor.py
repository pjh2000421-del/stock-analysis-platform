"""
뉴스 Event 구조화 추출기 (요구사항 9).

Phase1에서는 정교한 NLP 모델 대신, 제목/요약의 키워드 기반 규칙(rule-based)으로
event_type을 1차 분류하는 가벼운 baseline을 제공한다.
Phase2 이후 실제 서비스 품질을 위해서는 한국어 금융 뉴스로 학습된 분류기 또는
LLM 기반 구조화 추출(company/product/amount 등 slot-filling)로 교체하는 것을 권장한다.

인터페이스(EventExtractor)를 통해 구현체를 자유롭게 교체할 수 있다.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.schemas.common import EventType

# event_type: 제목/요약에 포함되면 해당 유형으로 분류할 키워드 목록.
# 우선순위 순서대로 검사하며, 여러 키워드가 매치될 경우 리스트 앞쪽 유형을 우선한다.
_KEYWORD_RULES: list[tuple[EventType, list[str]]] = [
    (EventType.M_AND_A, ["인수", "합병", "M&A", "지분 인수", "매각"]),
    (EventType.SUPPLY_CONTRACT, ["공급계약", "공급 계약", "수주"]),
    (EventType.CAPITAL_INCREASE, ["유상증자", "무상증자", "증자"]),
    (EventType.BUYBACK, ["자사주 매입", "자사주매입", "자사주 소각"]),
    (EventType.DIVIDEND, ["배당"]),
    (EventType.CAPEX, ["설비투자", "증설", "공장 건설", "capex"]),
    (EventType.PATENT, ["특허"]),
    (EventType.RND, ["연구개발", "R&D"]),
    (EventType.NEW_TECHNOLOGY, ["신기술", "기술 개발"]),
    (EventType.NEW_PRODUCT, ["신제품", "출시"]),
    (EventType.PRODUCT_LAUNCH, ["양산", "출시"]),
    (EventType.PRODUCTION, ["생산", "양산"]),
    (EventType.REGULATION, ["규제", "제재"]),
    (EventType.LEGAL, ["소송", "고발", "기소"]),
    (EventType.MANAGEMENT, ["대표이사", "경영진", "인사"]),
    (EventType.EARNINGS, ["실적", "잠정실적", "영업이익"]),
    (EventType.GUIDANCE, ["가이던스", "전망치"]),
    (EventType.GEOPOLITICAL, ["관세", "지정학", "수출 규제"]),
    (EventType.SUPPLY_CHAIN, ["공급망"]),
    (EventType.PARTNERSHIP, ["업무협약", "MOU", "파트너십", "협력"]),
]


@dataclass
class ExtractedEvent:
    event_type: str
    event_subtype: str | None = None
    product: str | None = None
    technology: str | None = None
    counterparty: str | None = None
    country: str | None = None
    amount_nominal: float | None = None
    development_stage: str | None = None
    commercialization_stage: str | None = None
    confidence: float = 0.3  # rule-based baseline은 신뢰도를 낮게 표시


class EventExtractor(ABC):
    @abstractmethod
    def extract(self, title: str, summary: str | None) -> ExtractedEvent:
        ...


class KeywordRuleEventExtractor(EventExtractor):
    """제목+요약 키워드 매칭 기반 baseline 추출기."""

    def extract(self, title: str, summary: str | None) -> ExtractedEvent:
        text = f"{title} {summary or ''}"
        for event_type, keywords in _KEYWORD_RULES:
            if any(kw in text for kw in keywords):
                return ExtractedEvent(event_type=event_type.value)
        return ExtractedEvent(event_type=EventType.OTHER.value, confidence=0.1)


def get_event_extractor() -> EventExtractor:
    return KeywordRuleEventExtractor()
