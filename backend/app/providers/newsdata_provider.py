"""
NewsData.io Provider Adapter.

BIGKinds에 대한 의존을 없애기 위한 2차 뉴스 Provider. Naver 검색 결과가 부족할 때
보완용으로 쓰이며, 특히 날짜 범위 지정 검색(archive endpoint)을 지원해 과거 유사
사례 검색의 후보군 확보에도 사용한다.

NewsData.io의 archive(과거 기사) 엔드포인트는 유료 플랜에서만 제공되므로, 무료
플랜 키로 호출하면 401/403이 반환될 수 있다. 이 경우 전체 기능을 실패시키지 않고
"unavailable"로 정상 처리한다 (요구사항 5와 동일한 원칙).
"""
from __future__ import annotations

from datetime import date, datetime

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.providers.base import HistoricalNewsProvider, NewsProvider, ProviderResult, RawNewsItem

logger = get_logger(__name__)

NEWSDATA_LATEST_ENDPOINT = "https://newsdata.io/api/1/news"
NEWSDATA_ARCHIVE_ENDPOINT = "https://newsdata.io/api/1/archive"


def _parse_published_at(raw: str | None) -> datetime | None:
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


# 무료 플랜에서는 description/content 필드에 실제 본문 대신 이 고정 문구가 그대로
# 온다. 걸러내지 않으면 감정분석(sentiment.py)과 이벤트 추출(event_extractor.py)
# 입력에 영어 잡음이 섞여 들어가 title만 있을 때보다 오히려 정확도를 해친다.
_PAID_PLAN_PLACEHOLDER = "ONLY AVAILABLE IN PAID PLANS"


def _clean_summary(text: str | None) -> str | None:
    if text is None:
        return None
    stripped = text.strip()
    if not stripped or stripped.upper() == _PAID_PLAN_PLACEHOLDER:
        return None
    return stripped


def _to_raw_items(results: list[dict], provider_name: str) -> list[RawNewsItem]:
    items: list[RawNewsItem] = []
    for r in results:
        url = r.get("link")
        title = r.get("title")
        if not url or not title:
            continue
        items.append(
            RawNewsItem(
                title=title,
                url=url,
                source=r.get("source_id") or r.get("source_name"),
                published_at=_parse_published_at(r.get("pubDate")),
                summary=_clean_summary(r.get("description")) or _clean_summary(r.get("content")),
                provider=provider_name,
                language=r.get("language"),
            )
        )
    return items


class NewsDataProvider(NewsProvider, HistoricalNewsProvider):
    """NewsData.io: 최신 뉴스(NewsProvider) + 날짜범위 과거 뉴스(HistoricalNewsProvider) 겸용."""

    name = "newsdata_io"

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.newsdata_api_key

    def _request(self, endpoint: str, params: dict) -> ProviderResult:
        if not self._api_key:
            return ProviderResult(
                status="unavailable", source_name=self.name, message="NEWSDATA_API_KEY 가 설정되어 있지 않습니다."
            )

        params = {"apikey": self._api_key, **params}
        try:
            resp = httpx.get(endpoint, params=params, timeout=15.0)
        except httpx.HTTPError as exc:
            logger.warning("NewsData.io 연결 실패: %s", exc)
            return ProviderResult(status="error", source_name=self.name, message="NewsData.io 연결에 실패했습니다.")

        if resp.status_code in (401, 403):
            # 무료 플랜에서 archive 등 일부 기능이 막혀있는 경우가 대표적. 정상적으로 unavailable 처리.
            return ProviderResult(
                status="unavailable",
                source_name=self.name,
                message="NewsData.io API Key가 유효하지 않거나, 현재 요금제에서 지원하지 않는 기능입니다.",
            )
        if resp.status_code == 429:
            return ProviderResult(
                status="error", source_name=self.name, message="NewsData.io 요청 한도를 초과했습니다."
            )
        if resp.status_code >= 400:
            logger.warning("NewsData.io 오류(%s): %s", resp.status_code, resp.text[:300])
            return ProviderResult(status="error", source_name=self.name, message=f"NewsData.io 오류: {resp.status_code}")

        try:
            payload = resp.json()
        except ValueError:
            return ProviderResult(status="error", source_name=self.name, message="NewsData.io 응답 파싱 실패")

        if payload.get("status") != "success":
            return ProviderResult(
                status="error", source_name=self.name, message=payload.get("results", {}).get("message") if isinstance(payload.get("results"), dict) else "NewsData.io 오류"
            )

        results = payload.get("results") or []
        items = _to_raw_items(results, self.name)

        return ProviderResult(
            status="ok" if items else "empty",
            data=items,
            source_name=self.name,
            source_url="https://newsdata.io/",
            retrieved_at=datetime.utcnow(),
        )

    def search_news(self, query: str, display: int = 30) -> ProviderResult:
        return self._request(
            NEWSDATA_LATEST_ENDPOINT, {"q": query, "language": "ko", "size": min(display, 10)}
        )

    def search_historical_news(
        self, query: str, start: date, end: date, limit: int = 200
    ) -> ProviderResult:
        return self._request(
            NEWSDATA_ARCHIVE_ENDPOINT,
            {
                "q": query,
                "language": "ko",
                "from_date": start.isoformat(),
                "to_date": end.isoformat(),
            },
        )


def get_newsdata_provider() -> NewsDataProvider:
    return NewsDataProvider()
