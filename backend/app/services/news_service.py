"""
뉴스 Service (요구사항 3, 8, 9, 10, Provider 다변화): Lazy Loading + Caching +
멀티 Provider Fallback + 감정분석 + Event 구조화.

기업 뉴스 조회 흐름 (BIGKinds 단일 의존 제거):
    1) DB(news)에서 최근 뉴스 확인
    2) 마지막 갱신(news_last_updated)이 오래됐으면 Provider 체인 호출:
       Naver(1차) -> 결과 부족 시 NewsData.io(2차) -> 그래도 부족하고 키가 있으면 GNews(3차)
       하나의 Provider가 없거나 실패해도 나머지 결과만으로 계속 진행한다 (Provider Fallback).
    3) 여러 Provider 결과를 URL 기준으로 우선 중복 제거하고, 신규 기사만 필터링
    4) VADER 감정분석 + 규칙기반 Event 추출
    5) 제목이 매우 유사한 최근 기사가 있으면(다른 언론사의 동일 사건 보도) 완전히 별개로
       두지 않고 대표 기사(cluster_head_id)에 연결한다 (Event Cluster)
    6) 공급계약/M&A/유상증자 등 공식 이벤트 성격이면 OpenDART 공시를 조회해 근거(anchor) 연결
    7) DB에 저장, company.news_last_updated 갱신
    8) 이후 조회는 DB 재사용
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ProviderUnavailableError
from app.core.logging import get_logger
from app.event_analysis.inflation_adjustment import adjust_for_inflation
from app.models.company import Company
from app.models.event import NewsEvent
from app.models.news import News
from app.news_analysis.dedup import SIMILAR_EVENT_TITLE_THRESHOLD, title_similarity
from app.news_analysis.event_extractor import get_event_extractor
from app.news_analysis.sentiment import get_sentiment_provider
from app.providers.base import RawNewsItem
from app.providers.disclosure_provider import get_disclosure_provider
from app.providers.gnews_provider import get_gnews_provider
from app.providers.macro_provider import get_macro_provider
from app.providers.news_provider import get_news_provider
from app.providers.newsdata_provider import get_newsdata_provider

logger = get_logger(__name__)

NEWS_REFRESH_INTERVAL = timedelta(minutes=10)

# 1차 Provider(Naver) 결과가 이 개수 미만이면 "부족하다"고 보고 다음 Provider로 보완한다.
MIN_RESULTS_BEFORE_FALLBACK = 5

# 이 event_type이 추출되면 실제 공시가 있는지 OpenDART에서 확인해 근거를 연결한다.
_DART_ANCHOR_EVENT_TYPES = {
    "SUPPLY_CONTRACT",
    "M_AND_A",
    "CAPITAL_INCREASE",
    "DIVIDEND",
    "BUYBACK",
    "EARNINGS",
    "CAPEX",
}


def _analyze_and_extract(title: str, summary: str | None) -> dict:
    sentiment_result = {"compound": None, "positive": None, "neutral": None, "negative": None}
    try:
        provider = get_sentiment_provider()
        score = provider.analyze(f"{title} {summary or ''}")
        sentiment_result = {
            "compound": score.compound,
            "positive": score.positive,
            "neutral": score.neutral,
            "negative": score.negative,
        }
    except ProviderUnavailableError as exc:
        logger.info("감정분석 Provider 사용 불가: %s", exc)
    except Exception:  # noqa: BLE001 - KR-FinBert-SC(BERT 모델) 추론 중 예기치 못한 오류가
        # 나더라도 뉴스 기사 하나 때문에 전체 뉴스 수집 배치가 죽으면 안 된다(동종업체 하나
        # 실패해도 전체 Peer Comparison이 안 죽는 것과 같은 원칙 - peer_service.py 참고).
        # sentiment_result는 위 기본값(None)을 그대로 사용한다.
        logger.exception("감정분석 중 예기치 못한 오류 - 이 기사는 sentiment 없이 진행")

    extractor = get_event_extractor()
    extracted = extractor.extract(title, summary)

    return {"sentiment": sentiment_result, "event": extracted}


def _compute_importance(sentiment_compound: float | None, event_type: str) -> float:
    """
    뉴스 중요도(0~100) 1차 근사치 (요구사항 49).
    Phase1에서는 |sentiment| 강도와 Event Type 가중치만 반영하는 단순 baseline이며,
    Phase2 이후 기업규모 대비 Event 규모/공시 여부/보도량/Market Reaction 등을 반영해 고도화한다.
    """
    base = 30.0
    if sentiment_compound is not None:
        base += min(abs(sentiment_compound) * 30, 30)
    high_importance_types = {"M_AND_A", "EARNINGS", "SUPPLY_CONTRACT", "REGULATION", "CAPITAL_INCREASE"}
    if event_type in high_importance_types:
        base += 20
    return min(base, 100.0)


def _fetch_cpi_lookup() -> dict[int, float] | None:
    """물가조정(명목->실질금액, 요구사항 13)에 쓸 {연도: CPI} 조회.

    이번에 새로 fetch된 뉴스는 항상 "최신 뉴스" 검색 결과라 published_at이 최근 1~2년
    범위를 벗어날 일이 거의 없으므로, 작년 1월부터 오늘까지만 조회해도 충분하다(과거
    기사 아카이브 검색 기능이 나중에 추가되면 그때 범위를 넓히면 된다). ECOS_API_KEY가
    없거나 조회에 실패하면 None을 반환하고, 호출부는 amount_real 계산을 건너뛰어
    amount_nominal만 남긴다(요구사항 74 - 숫자를 함부로 만들지 않는다).
    """
    today = date.today()
    result = get_macro_provider().get_cpi(date(today.year - 1, 1, 1), today)
    if result.status != "ok" or not result.data:
        if result.status not in ("unavailable", "ok"):
            logger.info("CPI 조회 실패(%s): %s", result.status, result.message)
        return None
    return result.data


def _fetch_from_providers(company: Company, display: int) -> tuple[list[RawNewsItem], dict[str, str]]:
    """Naver -> (부족 시) NewsData.io -> (그래도 부족하고 키가 있으면) GNews 순으로 조회/병합한다.

    어느 한 Provider가 unavailable/error여도 전체를 실패시키지 않고, 확보된 결과만으로
    계속 진행한다 (Provider Fallback 원칙). BIGKinds는 기본 파이프라인에서 호출하지 않는다.
    """
    provider_status: dict[str, str] = {}
    collected: list[RawNewsItem] = []
    seen_urls: set[str] = set()

    def _merge(items: list[RawNewsItem]) -> None:
        for item in items:
            if not item.url or item.url in seen_urls:
                continue
            seen_urls.add(item.url)
            collected.append(item)

    naver_result = get_news_provider().search_news(company.company_name, display=display)
    provider_status["naver_news"] = naver_result.status
    if naver_result.status == "ok":
        _merge(naver_result.data or [])

    if len(collected) < MIN_RESULTS_BEFORE_FALLBACK:
        newsdata_result = get_newsdata_provider().search_news(company.company_name, display=display)
        provider_status["newsdata_io"] = newsdata_result.status
        if newsdata_result.status == "ok":
            _merge(newsdata_result.data or [])
    else:
        provider_status["newsdata_io"] = "skipped"

    gnews_provider = get_gnews_provider()
    if len(collected) < MIN_RESULTS_BEFORE_FALLBACK and gnews_provider.is_configured():
        gnews_result = gnews_provider.search_news(company.company_name, display=display)
        provider_status["gnews"] = gnews_result.status
        if gnews_result.status == "ok":
            _merge(gnews_result.data or [])
    else:
        provider_status["gnews"] = "skipped" if gnews_provider.is_configured() else "unavailable"

    # 기본 파이프라인은 BIGKinds에 의존하지 않는다 (Provider 다변화).
    provider_status["bigkinds"] = "not_used_by_default"

    return collected, provider_status


def _find_dart_anchor(company: Company, event_type: str, published_at: datetime | None) -> str | None:
    """공식 공시 성격의 Event이면 OpenDART 공시 목록에서 근거를 찾아 rcept_no를 반환한다.

    실패/미설정 시에는 조용히 None을 반환한다(뉴스 저장 자체를 막지 않음).
    """
    if event_type not in _DART_ANCHOR_EVENT_TYPES or published_at is None:
        return None
    try:
        provider = get_disclosure_provider()
        window_start = (published_at - timedelta(days=3)).date()
        window_end = (published_at + timedelta(days=3)).date()
        result = provider.search_disclosures(company.ticker, None, window_start, window_end)
        if result.status == "ok" and result.data:
            return result.data[0].get("rcept_no")
    except Exception:  # noqa: BLE001 - DART anchor는 부가 정보이므로 실패해도 뉴스 저장은 계속
        logger.exception("DART anchor 조회 실패: %s", company.ticker)
    return None


def _find_cluster_head(db: Session, company: Company, title: str, published_at: datetime | None) -> int | None:
    """같은 기업의 최근(±5일) 기사 중 제목이 매우 유사한 것이 있으면 그 대표 기사 id를 반환한다.

    완전 삭제/병합하지 않고 서로 연결만 하여, 여러 언론사의 동일 사건 보도를
    Event Cluster로 묶을 수 있게 한다.
    """
    if published_at is None:
        return None
    window_start = published_at - timedelta(days=5)
    window_end = published_at + timedelta(days=5)
    candidates = list(
        db.execute(
            select(News).where(
                News.company_id == company.id,
                News.published_at.is_not(None),
                News.published_at >= window_start,
                News.published_at <= window_end,
            )
        )
        .scalars()
        .all()
    )
    for candidate in candidates:
        if title_similarity(title, candidate.title) >= SIMILAR_EVENT_TITLE_THRESHOLD:
            return candidate.cluster_head_id or candidate.id
    return None


def refresh_company_news(db: Session, company: Company, display: int = 30) -> dict[str, str]:
    """여러 Provider를 조합해 신규 기사를 수집/저장한다. 반환값은 Provider별 상태 dict."""
    now = datetime.utcnow()
    if company.news_last_updated and now - company.news_last_updated < NEWS_REFRESH_INTERVAL:
        return {
            "naver_news": "cached",
            "newsdata_io": "cached",
            "gnews": "cached",
            "bigkinds": "not_used_by_default",
        }

    items, provider_status = _fetch_from_providers(company, display)

    existing_urls = {
        u for (u,) in db.execute(select(News.url).where(News.company_id == company.id)).all()
    }

    # CPI는 이 배치에 물가조정이 필요한 기사(금액이 추출된 기사)가 실제로 있을 때만,
    # 그것도 배치당 한 번만 조회한다 - 기사마다 매번 ECOS를 호출하면 낭비다.
    cpi_lookup: dict[int, float] | None = None
    cpi_lookup_attempted = False

    for item in items:
        if item.url in existing_urls:
            continue
        existing_urls.add(item.url)  # 이번 배치 내 Provider 간 URL 중복도 방지

        analysis = _analyze_and_extract(item.title, item.summary)
        sentiment = analysis["sentiment"]
        extracted = analysis["event"]
        importance = _compute_importance(sentiment["compound"], extracted.event_type)

        cluster_head_id = _find_cluster_head(db, company, item.title, item.published_at)

        news_row = News(
            company_id=company.id,
            title=item.title,
            summary=item.summary,
            source=item.source,
            published_at=item.published_at,
            url=item.url,
            sentiment_score=sentiment["compound"],
            sentiment_positive=sentiment["positive"],
            sentiment_neutral=sentiment["neutral"],
            sentiment_negative=sentiment["negative"],
            importance_score=importance,
            event_type=extracted.event_type,
            event_subtype=extracted.event_subtype,
            cluster_head_id=cluster_head_id,
            source_name=item.provider,
            retrieved_at=datetime.utcnow(),
            is_mock=False,
        )
        db.add(news_row)
        db.flush()  # news_row.id 확보 (이후 같은 배치의 유사도 비교 대상에도 포함시키기 위함)

        dart_anchor_rcept_no = _find_dart_anchor(company, extracted.event_type, item.published_at)

        # 물가조정 금액(amount_real, 요구사항 13): 기사에서 금액이 추출됐고 발행일을 알 때만
        # 계산한다. "오늘 기준 실질금액"으로 환산한다(base_date=오늘) - 몇 년 전 계약 금액이
        # 지금 돈으로 얼마인지 비교하는 게 목적이라 가장 직관적인 기준점이다. CPI를 못 구하면
        # (ECOS_API_KEY 미설정 등) amount_real은 None으로 남고 amount_nominal만 저장된다
        # (요구사항 74 - 숫자를 함부로 만들지 않는다).
        amount_real: float | None = None
        if extracted.amount_nominal is not None and item.published_at is not None:
            if not cpi_lookup_attempted:
                cpi_lookup_attempted = True
                cpi_lookup = _fetch_cpi_lookup()
            if cpi_lookup:
                event_date = item.published_at.date() if hasattr(item.published_at, "date") else item.published_at
                adjustment = adjust_for_inflation(
                    amount_nominal=extracted.amount_nominal,
                    event_date=event_date,
                    base_date=date.today(),
                    cpi_lookup=cpi_lookup,
                )
                amount_real = adjustment.amount_real

        db.add(
            NewsEvent(
                news_id=news_row.id,
                company_id=company.id,
                event_type=extracted.event_type,
                event_subtype=extracted.event_subtype,
                product=extracted.product,
                technology=extracted.technology,
                counterparty=extracted.counterparty,
                country=extracted.country,
                amount_nominal=extracted.amount_nominal,
                amount_real=amount_real,
                development_stage=extracted.development_stage,
                commercialization_stage=extracted.commercialization_stage,
                sentiment=sentiment["compound"],
                importance=importance,
                event_date=item.published_at,
                dart_anchor_rcept_no=dart_anchor_rcept_no,
            )
        )

    company.news_last_updated = now
    db.add(company)
    db.commit()
    return provider_status


def get_company_news(
    db: Session, company: Company, limit: int = 30
) -> tuple[list[News], dict[int, int], dict[str, str]]:
    """최근 뉴스 목록, {news_id: 같은 사건의 다른 기사 수}, Provider별 상태를 반환한다."""
    provider_status = refresh_company_news(db, company)
    rows = list(
        db.execute(
            select(News)
            .where(News.company_id == company.id)
            .order_by(News.published_at.desc().nullslast())
            .limit(limit)
        )
        .scalars()
        .all()
    )

    # related_count는 이번에 조회된 rows 범위 내에서만 계산하는 근사치다(요구사항 3의
    # Lazy Loading 원칙상 전체 기사를 항상 스캔하지 않음 - 화면 표시용 참고 정보이므로
    # 정확한 전수 집계가 아니어도 무방하다).
    head_counts: dict[int, int] = {}
    for r in rows:
        head_id = r.cluster_head_id or r.id
        head_counts[head_id] = head_counts.get(head_id, 0) + 1

    related_counts: dict[int, int] = {}
    for r in rows:
        head_id = r.cluster_head_id or r.id
        related_counts[r.id] = max(0, head_counts.get(head_id, 1) - 1)

    return rows, related_counts, provider_status


def search_historical_candidates(
    db: Session, company: Company, query: str, start: date, end: date, limit: int = 50
) -> list[RawNewsItem]:
    """과거 유사사례(Historical Similarity) 후보 뉴스를 모은다 (요구사항: Provider 다변화).

    특정 기간 전체를 무작정 다운로드하지 않고, 이미 추출된 현재 Event의 키워드로
    구성된 query에 대해서만 검색한다. 우선순위: 내부 DB(이미 수집된 기사, 비용 없음)
    -> NewsData.io archive(유료 플랜에서만 가능, 없으면 자동 unavailable)
    -> GNews(키가 있을 때만). BIGKinds는 기본적으로 사용하지 않는다.

    실제 유사도 순위 재계산(semantic/event/scale 등 종합 스코어링)은 이 함수의
    역할이 아니라 event_analysis/similarity.py의 몫이며, 여기서는 후보군만 모은다.
    """
    seen_urls: set[str] = set()
    candidates: list[RawNewsItem] = []

    def _merge(items: list[RawNewsItem]) -> None:
        for item in items:
            if not item.url or item.url in seen_urls:
                continue
            seen_urls.add(item.url)
            candidates.append(item)

    # 1) 내부 DB: 이미 수집해둔 기사 중 기간 내 & 제목/요약에 키워드가 포함된 것.
    #    LIKE 검색은 형태소 분석이 아니라 단순 부분일치이므로, query는 호출부에서
    #    핵심 키워드(회사명/제품명/이벤트유형 한글 표기 등) 위주로 짧게 구성해야 효과적이다.
    keyword = query.strip()
    internal_rows: list[News] = []
    if keyword:
        like_pattern = f"%{keyword}%"
        internal_rows = list(
            db.execute(
                select(News)
                .where(
                    News.published_at.is_not(None),
                    News.published_at >= datetime.combine(start, datetime.min.time()),
                    News.published_at <= datetime.combine(end, datetime.max.time()),
                    News.title.like(like_pattern),
                )
                .order_by(News.published_at.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
    _merge(
        [
            RawNewsItem(
                title=r.title,
                url=r.url,
                source=r.source,
                published_at=r.published_at,
                summary=r.summary,
                provider="internal_db",
                language="ko",
            )
            for r in internal_rows
        ]
    )

    # 2) NewsData.io archive (유료 플랜 전용 - 없으면 unavailable로 정상 처리됨)
    if len(candidates) < limit:
        newsdata_result = get_newsdata_provider().search_historical_news(keyword, start, end, limit=limit)
        if newsdata_result.status == "ok":
            _merge(newsdata_result.data or [])

    # 3) GNews (키가 있을 때만, optional)
    gnews_provider = get_gnews_provider()
    if len(candidates) < limit and gnews_provider.is_configured():
        gnews_result = gnews_provider.search_news(keyword, display=limit, start=start, end=end)
        if gnews_result.status == "ok":
            _merge(gnews_result.data or [])

    return candidates[:limit]
