"""
뉴스 상세 / 과거 유사사례 / Event Study API (요구사항 55).

Phase2: Event Study(이벤트 전후 주가반응)는 event_study_service를 통해 실제로
계산/캐싱된다. /api/news/{news_id}/similar (과거 유사사례 검색)는 다음 단계
(Historical Similarity, BIGKinds/임베딩 연동)에서 구현 예정이라 아직
status="not_implemented_yet"을 반환한다.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.news import News
from app.schemas.event import EventStudyResponse, SimilarEventGroupStats, SimilarNewsResponse
from app.schemas.news import NewsDetail
from app.services.event_study_service import get_event_study

router = APIRouter(prefix="/news", tags=["news"])


@router.get("/debug/sentiment")
def debug_sentiment(text: str):
    """[임시 진단용] 감정분석 Provider를 실제 뉴스 API 없이 임의 텍스트로 바로 테스트한다.

    VADER -> KR-FinBert-SC 교체가 실제로 반영/동작하는지 확인하기 위한 용도. 뉴스 수집
    API 키(Naver 등)가 아직 없어 실제 뉴스로는 감정분석 파이프라인을 테스트할 수 없어서
    추가함. 확인 후 제거 예정. /{news_id}보다 먼저 등록해야 "debug"가 news_id로
    잘못 매칭되지 않는다.
    """
    from app.news_analysis.sentiment import _is_korean_text, get_sentiment_provider

    provider = get_sentiment_provider()
    score = provider.analyze(text)
    return {
        "provider_name": provider.name,
        "detected_as_korean": _is_korean_text(text),  # 라우팅 결과 확인용(한국어/그 외 판별)
        "positive": score.positive,
        "neutral": score.neutral,
        "negative": score.negative,
        "compound": score.compound,
    }


@router.get("/{news_id}", response_model=NewsDetail)
def get_news_detail(news_id: int, db: Session = Depends(get_db)):
    news = db.get(News, news_id)
    if news is None:
        raise HTTPException(status_code=404, detail="뉴스를 찾을 수 없습니다.")

    return NewsDetail(
        id=news.id,
        title=news.title,
        summary=news.summary,
        source=news.source,
        published_at=news.published_at,
        url=news.url,
        sentiment_score=news.sentiment_score,
        importance_score=news.importance_score,
        event_type=news.event_type,
        event_subtype=news.event_subtype,
        is_mock=news.is_mock,
        events=[],
    )


@router.get("/{news_id}/similar", response_model=SimilarNewsResponse)
def get_similar_news(news_id: int, db: Session = Depends(get_db)):
    news = db.get(News, news_id)
    if news is None:
        raise HTTPException(status_code=404, detail="뉴스를 찾을 수 없습니다.")

    # TODO(Phase2): DART Anchor + 과거뉴스 Provider 후보 검색 -> similarity.py 계산 -> DB 저장
    return SimilarNewsResponse(
        news_id=news_id,
        top_similar=[],
        group_stats=SimilarEventGroupStats(
            total_count=0, up_count_1d=0, up_count_5d=0, up_count_20d=0
        ),
        similarity_config_version="not_implemented_yet",
    )


@router.get("/{news_id}/event-study", response_model=EventStudyResponse)
def get_news_event_study(news_id: int, db: Session = Depends(get_db)):
    news = db.get(News, news_id)
    if news is None:
        raise HTTPException(status_code=404, detail="뉴스를 찾을 수 없습니다.")

    return get_event_study(db, news_id)
