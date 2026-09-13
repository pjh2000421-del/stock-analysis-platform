"""
뉴스 제목 정규화 / 유사도 비교 (여러 Provider 결과 병합용).

Naver/NewsData/GNews 등 여러 Provider에서 동일한 사건에 대한 기사를 각자 다른
문구의 제목으로 보도하는 경우가 많다. 완전 일치(URL 동일)만 중복 처리하면
같은 기사가 Provider별로 중복 저장되고, 반대로 유사도를 전혀 보지 않으면
"같은 사건, 다른 언론사"인 기사들이 서로 무관한 것처럼 흩어진다.

여기서는 무거운 임베딩 모델 없이(요구사항: Provider/Service 레이어만 수정,
큰 의존성 추가 지양) difflib 기반 경량 유사도로 "같은 사건일 가능성이 높은"
기사를 판단한다. 나중에 Historical Similarity 단계에서 의미 기반(semantic)
임베딩을 도입하면 이 함수를 교체하거나 보완할 수 있도록 인터페이스를 분리해둔다.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

# 언론사 표기 방식 차이로 인한 잡음을 줄이기 위해 정규화 시 제거하는 패턴들.
_BRACKET_PATTERN = re.compile(r"[\[\(].*?[\]\)]")  # "[단독]", "(종합)" 등
_PUNCT_PATTERN = re.compile(r"[^\w\s가-힣]")
_WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_title(title: str) -> str:
    """비교를 위해 제목에서 대괄호 태그/구두점/공백 차이를 제거한 정규화 문자열을 만든다."""
    text = _BRACKET_PATTERN.sub(" ", title)
    text = _PUNCT_PATTERN.sub(" ", text)
    text = _WHITESPACE_PATTERN.sub(" ", text).strip().lower()
    return text


def title_similarity(a: str, b: str) -> float:
    """정규화된 제목 간 유사도 (0~1). difflib SequenceMatcher 기반 경량 구현."""
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


# 이 값 이상이면 "같은 사건을 다른 언론사가 보도한 기사"로 간주해 클러스터로 묶는다.
# 지나치게 낮추면 무관한 기사가 잘못 묶이고, 너무 높이면 실제 중복도 못 묶으므로
# 경험적으로 보수적인(오탐지보다 미탐지를 선호하는) 값을 사용한다.
SIMILAR_EVENT_TITLE_THRESHOLD = 0.55
