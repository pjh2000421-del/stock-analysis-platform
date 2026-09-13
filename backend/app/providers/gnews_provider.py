"""
GNews Provider Adapter — 3차 optional fallback Provider.

Naver + NewsData.io 결과가 모두 부족할 때만 Service Layer에서 명시적으로 호출한다.
API Key가 없으면 자동으로 unavailable 처리되어 파이프라인 전체가 이 Provider에
의존하지 않는다 (요구사항: BIGKinds 단일 의존 제거와 동일한 원칙을 모든 외부
뉴스 Provider에 적용).
"""
from __future__ import annotations

from datetime import date, datetime

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.providers.base import NewsProvider, ProviderResult, RawNewsItem

logger = get_logger(__name__)

GNEWS_SEARCH_ENDPOINT = "https://gnews.io/api/v4/search"


def _parse_published_at(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None


class GNewsProvider(NewsProvider):
    name = "gnews"

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.gnews_api_key

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def search_news(
        self, query: str, display: int = 30, start: date | None = None, end: date | None = None
    ) -> ProviderResult:
        if not self._api_key:
            return ProviderResult(
                status="unavailable", source_name=self.name, message="GNEWS_API_KEY 가 설정되어 있지 않습니다."
            )

        params: dict = {"q": query, "lang": "ko", "max": min(display, 10), "token": self._api_key}
        if start:
            params["from"] = f"{start.isoformat()}T00:00:00Z"
        if end:
            params["to"] = f"{end.isoformat()}T23:59:59Z"

        try:
            resp = httpx.get(GNEWS_SEARCH_ENDPOINT, params=params, timeout=15.0)
        except httpx.HTTPError as exc:
            logger.warning("GNews 연결 실패: %s", exc)
            return ProviderResult(status="error", source_name=self.name, message="GNews 연결에 실패했습니다.")

        if resp.status_code in (401, 403):
            return ProviderResult(
                status="unavailable", source_name=self.name, message="GNews API Key가 유효하지 않습니다."
            )
        if resp.status_code == 429:
            return ProviderResult(status="error", source_name=self.name, message="GNews 요청 한도를 초과했습니다.")
        if resp.status_code >= 400:
            logger.warning("GNews 오류(%s): %s", resp.status_code, resp.text[:300])
            return ProviderResult(status="error", source_name=self.name, message=f"GNews 오류: {resp.status_code}")

        try:
            payload = resp.json()
        except ValueError:
            return ProviderResult(status="error", source_name=self.name, message="GNews 응답 파싱 실패")

        articles = payload.get("articles") or []
        items: list[RawNewsItem] = []
        for a in articles:
            url = a.get("url")
            title = a.get("title")
            if not url or not title:
                continue
            source = a.get("source") or {}
            items.append(
                RawNewsItem(
                    title=title,
                    url=url,
                    source=source.get("name"),
                    published_at=_parse_published_at(a.get("publishedAt")),
                    summary=a.get("description"),
                    provider=self.name,
                    language="ko",
                )
            )

        return ProviderResult(
            status="ok" if items else "empty",
            data=items,
            source_name=self.name,
            source_url="https://gnews.io/",
            retrieved_at=datetime.utcnow(),
        )


def get_gnews_provider() -> GNewsProvider:
    return GNewsProvider()
