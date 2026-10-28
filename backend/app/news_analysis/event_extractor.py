"""
뉴스 Event 구조화 추출기 (요구사항 9).

Phase1에서는 정교한 NLP 모델 대신, 제목/요약의 키워드 기반 규칙(rule-based)으로
event_type을 1차 분류하는 가벼운 baseline을 제공한다.
Phase2 이후 실제 서비스 품질을 위해서는 한국어 금융 뉴스로 학습된 분류기 또는
LLM 기반 구조화 추출(company/product/amount 등 slot-filling)로 교체하는 것을 권장한다.

인터페이스(EventExtractor)를 통해 구현체를 자유롭게 교체할 수 있다.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.schemas.common import EventType

# --- 금액(원화) 추출 (요구사항 49 - 뉴스 중요도 판단에 "실제 영향 규모"를 반영하기 위함) ---
#
# "1조 2000억원", "500억원", "12억 3000만원" 처럼 조/억/만 단위가 이어지는 한국어 금액
# 표현을 최선노력(best-effort)으로 파싱한다. 표/각주식 표기나 "약 1조원대", 달러 등
# 외화 표기는 다루지 않는다 - 이 경우는 그냥 못 찾은 것으로 처리하고 절대 숫자를
# 추측하지 않는다(요구사항 74: 근거 없는 숫자를 만들지 않는다).
_AMOUNT_UNIT_MULTIPLIERS: dict[str, float] = {
    "조": 1_0000_0000_0000.0,  # 10^12
    "억": 1_0000_0000.0,  # 10^8
    "만": 1_0000.0,  # 10^4
}
_AMOUNT_BLOCK_RE = re.compile(r"(?:\d[\d,]*(?:\.\d+)?\s*(?:조|억|만)\s*)+원")
_AMOUNT_PART_RE = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(조|억|만)")


def _extract_amount_krw(text: str) -> float | None:
    """제목/요약 텍스트에서 원화 금액을 파싱한다. 매치되는 표현이 없으면 None."""
    match = _AMOUNT_BLOCK_RE.search(text)
    if not match:
        return None
    total = 0.0
    found = False
    for number_str, unit in _AMOUNT_PART_RE.findall(match.group(0)):
        try:
            number = float(number_str.replace(",", ""))
        except ValueError:
            continue
        total += number * _AMOUNT_UNIT_MULTIPLIERS[unit]
        found = True
    return total if found else None

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
        amount = _extract_amount_krw(text)
        for event_type, keywords in _KEYWORD_RULES:
            if any(kw in text for kw in keywords):
                return ExtractedEvent(event_type=event_type.value, amount_nominal=amount)
        return ExtractedEvent(event_type=EventType.OTHER.value, confidence=0.1, amount_nominal=amount)


def get_event_extractor() -> EventExtractor:
    return KeywordRuleEventExtractor()
