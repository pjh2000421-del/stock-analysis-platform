"""
뉴스 감정 분석 (요구사항 10).

기본 Provider는 한국어 금융 뉴스로 파인튜닝된 KR-FinBert-SC(서울대 NLP연구실,
snunlp/KR-FinBert-SC)이다. VADER는 영어 lexicon 기반이라 한국어 뉴스 제목/요약에
그대로 적용하면 대부분 중립(0)으로 판정되어 사실상 무용지물이었다 - 이 문제를 해결하기
위해 KR-FinBert-SC로 교체했다. KR-FinBert-SC는 한국어 금융 텍스트 5만 건으로
검증되었고(96%대 정확도), negative/neutral/positive 3-class를 직접 제공해 기존
SentimentScore(positive/neutral/negative/compound) 스키마와도 자연스럽게 맞는다.

VADER는 완전히 제거하지 않고, 1) KR-FinBert-SC를 아예 못 쓰는 환경의 전체 fallback,
2) KR-FinBert-SC를 쓸 수 있는 경우에도 "영문 등 한국어가 아닌 기사"의 전담 분석기,
이렇게 두 가지 역할로 남겨둔다. Naver(1차)는 항상 한국어지만, NewsData.io/GNews
(2·3차 보완 Provider)는 언어 필터(language=ko)를 걸어도 실제로는 영문 기사가 섞여
들어올 수 있다 - KR-FinBert-SC는 한국어 금융 텍스트로만 학습돼 영문에는 부정확하고,
반대로 VADER는 영문에 최적화돼 있으므로, 기사 본문 언어를 직접 감지해 둘 중 맞는
쪽으로 라우팅한다(RoutingSentimentProvider). Provider가 스스로 보고하는 language
메타데이터(예: GNews는 실제 언어와 무관하게 항상 "ko"로 고정 응답)는 신뢰할 수 없어
쓰지 않고, 실제 텍스트의 한글 비율로 직접 판별한다.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache

from app.core.errors import ProviderUnavailableError
from app.core.logging import get_logger

logger = get_logger(__name__)

KR_FINBERT_SC_MODEL_NAME = "snunlp/KR-FinBert-SC"

# 한글 음절(가-힣) + 자모 범위. 텍스트의 "언어가 한국어인지"를 판별하는 데는 이 정도
# 간단한 휴리스틱으로 충분하다 - 여기서 구분해야 하는 대상이 "한국어 vs 그 외(주로
# 영어)" 두 갈래뿐이라, langdetect 같은 별도 라이브러리를 추가로 의존성에 넣을 만큼의
# 가치가 없다.
_HANGUL_RANGES: tuple[tuple[int, int], ...] = ((0xAC00, 0xD7A3), (0x1100, 0x11FF), (0x3130, 0x318F))

# 알파벳 문자(한글 포함) 중 한글이 이 비율 이상이면 "한국어 텍스트"로 판단한다.
# 한국 기업 뉴스에는 "SK하이닉스", "DB금융투자" 처럼 영문 브랜드명이 섞이는 경우가
# 흔해서 "한글이 하나라도 있으면 한국어"는 오탐이 적당히 관대하고(원래 목적에 부합),
# 반대로 "전부 한글이어야 한국어"는 너무 엄격해 실제 한국어 기사를 놓치므로,
# 그 중간값인 30%를 임계값으로 둔다.
_KOREAN_TEXT_HANGUL_RATIO_THRESHOLD = 0.3


def _is_korean_text(text: str) -> bool:
    if not text:
        return False
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return False
    hangul_count = sum(1 for ch in letters if any(lo <= ord(ch) <= hi for lo, hi in _HANGUL_RANGES))
    return (hangul_count / len(letters)) >= _KOREAN_TEXT_HANGUL_RATIO_THRESHOLD


@dataclass
class SentimentScore:
    positive: float
    neutral: float
    negative: float
    compound: float  # -1 ~ 1


class SentimentProvider(ABC):
    name: str = "base_sentiment_provider"

    @abstractmethod
    def analyze(self, text: str) -> SentimentScore:
        ...


class KrFinBertSentimentProvider(SentimentProvider):
    """한국어 금융 뉴스 감정분석 (snunlp/KR-FinBert-SC, KR-BERT 기반 금융 도메인 파인튜닝).

    실제 HuggingFace config.json 기준 id2label = {0: negative, 1: neutral, 2: positive}
    (사전 확인 완료 - 일부 문서에는 이진분류로 잘못 소개되어 있으나 실제로는 3-class임).
    compound은 VADER와 동일한 관례(-1~1)를 따르도록 positive 확률 - negative 확률로
    계산한다(중립 확률이 클수록 자연히 0에 가까워짐).
    """

    name = "kr_finbert_sc"

    def __init__(self) -> None:
        try:
            import torch  # type: ignore
            from transformers import AutoModelForSequenceClassification, AutoTokenizer  # type: ignore
        except ImportError as exc:
            raise ProviderUnavailableError(
                self.name, "transformers/torch 패키지가 설치되어 있지 않습니다."
            ) from exc

        self._torch = torch
        try:
            self._tokenizer = AutoTokenizer.from_pretrained(KR_FINBERT_SC_MODEL_NAME)
            self._model = AutoModelForSequenceClassification.from_pretrained(KR_FINBERT_SC_MODEL_NAME)
        except Exception as exc:  # noqa: BLE001 - 최초 실행 시 HuggingFace 모델 다운로드가
            # 인터넷 차단/방화벽 등으로 실패할 수 있는데, 원인이 다양해(네트워크, 디스크,
            # 캐시 손상 등) 구체적인 예외 타입을 특정하기 어렵다. 어떤 이유든 이 Provider를
            # 못 쓰면 상위에서 VADER로 fallback해야 하므로 넓게 잡아 ProviderUnavailableError로
            # 변환한다.
            raise ProviderUnavailableError(
                self.name, f"KR-FinBert-SC 모델 로드 실패(최초 실행 시 인터넷 연결 필요): {exc}"
            ) from exc
        self._model.eval()
        id2label = {int(k): v for k, v in self._model.config.id2label.items()}
        self._label2idx = {label: idx for idx, label in id2label.items()}

    def analyze(self, text: str) -> SentimentScore:
        text = text or ""
        torch = self._torch
        inputs = self._tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
        with torch.no_grad():
            logits = self._model(**inputs).logits[0]
        probs = torch.softmax(logits, dim=-1).tolist()

        positive = probs[self._label2idx["positive"]]
        neutral = probs[self._label2idx["neutral"]]
        negative = probs[self._label2idx["negative"]]
        return SentimentScore(
            positive=positive,
            neutral=neutral,
            negative=negative,
            compound=positive - negative,
        )


class VaderSentimentProvider(SentimentProvider):
    """영어 lexicon 기반 fallback. KR-FinBert-SC를 쓸 수 없을 때만 사용한다(위 모듈
    docstring 참고) - 한국어 뉴스에는 대부분 중립(0)으로 판정되어 정확도가 낮다."""

    name = "vader"

    def __init__(self) -> None:
        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer  # type: ignore

            self._analyzer = SentimentIntensityAnalyzer()
        except ImportError as exc:
            raise ProviderUnavailableError(self.name, "vaderSentiment 패키지가 설치되어 있지 않습니다.") from exc

    def analyze(self, text: str) -> SentimentScore:
        scores = self._analyzer.polarity_scores(text or "")
        return SentimentScore(
            positive=scores["pos"],
            neutral=scores["neu"],
            negative=scores["neg"],
            compound=scores["compound"],
        )


class RoutingSentimentProvider(SentimentProvider):
    """텍스트의 실제 언어를 감지해 한국어는 KR-FinBert-SC, 그 외(주로 영어)는 VADER로
    라우팅한다. 두 Provider 모두 준비됐을 때만 이 클래스를 쓴다 - 하나만 있으면 그냥
    그 Provider를 그대로 쓰는 게 더 단순하다(_default_provider 참고)."""

    name = "kr_finbert_sc+vader(routed)"

    def __init__(self, korean_provider: SentimentProvider, other_provider: SentimentProvider) -> None:
        self._korean_provider = korean_provider
        self._other_provider = other_provider

    def analyze(self, text: str) -> SentimentScore:
        provider = self._korean_provider if _is_korean_text(text) else self._other_provider
        return provider.analyze(text)


@lru_cache(maxsize=1)
def _default_provider() -> SentimentProvider:
    """가능하면 KR-FinBert-SC(한국어) + VADER(그 외 언어)를 언어별로 라우팅해서 함께
    쓰고, 둘 중 하나만 쓸 수 있으면 그 Provider 하나로, 둘 다 안 되면 예외를 낸다.
    한 번 결정된 결과는 프로세스 수명 동안 캐시한다(BERT 모델 로드가 매 기사마다
    반복되면 너무 느리다 - 싱글턴으로 재사용).
    """
    try:
        vader: SentimentProvider | None = VaderSentimentProvider()
    except ProviderUnavailableError as exc:
        logger.warning("VADER 사용 불가(%s)", exc)
        vader = None

    try:
        kr_finbert: SentimentProvider | None = KrFinBertSentimentProvider()
        logger.info("감정분석 Provider: KR-FinBert-SC 로드 성공")
    except ProviderUnavailableError as exc:
        logger.warning("KR-FinBert-SC 사용 불가(%s)", exc)
        kr_finbert = None

    if kr_finbert is not None and vader is not None:
        logger.info("한국어 기사는 KR-FinBert-SC, 그 외 언어(영문 등) 기사는 VADER로 라우팅")
        return RoutingSentimentProvider(korean_provider=kr_finbert, other_provider=vader)
    if kr_finbert is not None:
        logger.warning("VADER를 못 써서 비한국어 기사도 KR-FinBert-SC로 처리(부정확할 수 있음)")
        return kr_finbert
    if vader is not None:
        logger.warning("KR-FinBert-SC를 못 써서 한국어 기사도 VADER로 처리(대부분 중립 판정)")
        return vader
    raise ProviderUnavailableError("sentiment", "KR-FinBert-SC와 VADER 둘 다 사용할 수 없습니다.")


def get_sentiment_provider() -> SentimentProvider:
    """
    기본 SentimentProvider를 반환한다: 한국어 기사는 KR-FinBert-SC, 영문 등 그 외
    언어는 VADER로 자동 라우팅한다(RoutingSentimentProvider). 둘 중 하나만 설치돼
    있으면 그 Provider 하나로 전체를 처리하고, 둘 다 사용 불가한 경우(둘 다 미설치)
    상위 서비스에서 ProviderUnavailableError를 잡아 sentiment_score = None 으로
    처리해야 한다(전체 뉴스 파이프라인이 깨지지 않도록).
    """
    return _default_provider()


def compute_daily_sentiment_summary(scores: list[float]) -> dict:
    """일 단위 mean/median/weighted/개수 계산 (요구사항 10).

    weighted는 단순 예시로 최근 뉴스에 더 큰 가중치를 부여하는 선형 가중 평균을 사용한다.
    """
    if not scores:
        return {"mean": None, "median": None, "weighted": None, "news_count": 0}

    n = len(scores)
    sorted_scores = sorted(scores)
    mean = sum(scores) / n
    mid = n // 2
    median = sorted_scores[mid] if n % 2 == 1 else (sorted_scores[mid - 1] + sorted_scores[mid]) / 2

    weights = list(range(1, n + 1))  # 뒤로 갈수록(최근일수록) 가중치가 크다고 가정한 입력 순서 기준
    weighted = sum(s * w for s, w in zip(scores, weights)) / sum(weights)

    return {"mean": mean, "median": median, "weighted": weighted, "news_count": n}
