"""네이버 뉴스 검색 API Adapter (요구사항 5).

주의(2026-09 갱신): 네이버는 검색 API(뉴스/블로그/카페글 등)를 기존 개발자센터
(developers.naver.com)에서 네이버클라우드플랫폼의 "NAVER API HUB"로 이관했다.
2026-07-31부로 개발자센터에서는 검색 API 신규 발급 자체가 막혔고(그래서 애플리케이션
등록 화면 "사용 API" 목록에 "검색"이 더 이상 뜨지 않는다), 신규로는 반드시
NAVER API HUB(ncloud.com)에서 Application을 만들어 키를 받아야 한다. 기존 개발자센터
키를 이미 갖고 있던 사용자는 2027-06-30까지 구버전 엔드포인트를 계속 쓸 수 있다고
안내되지만, 신규 사용자는 처음부터 새 방식으로만 발급 가능하다.

바뀐 것: 엔드포인트 도메인과 인증 헤더 이름뿐이고(아래 참고), 요청 파라미터
(query/display/start/sort)와 응답 JSON 필드 구조(items[].title/link/originallink/
description/pubDate 등)는 공식 문서(ncloud-docs.com) 기준으로 기존과 동일하게
유지된다 - 그래서 아래 파싱 로직은 그대로 두고 엔드포인트/헤더만 교체했다.
    기존: https://openapi.naver.com/v1/search/news.json
          X-Naver-Client-Id / X-Naver-Client-Secret
    신규: https://naverapihub.apigw.ntruss.com/search/v1/news
          X-NCP-APIGW-API-KEY-ID / X-NCP-APIGW-API-KEY
설정값 이름(NAVER_CLIENT_ID/NAVER_CLIENT_SECRET, settings.naver_client_id/secret)은
혼선을 줄이기 위해 그대로 유지하고, 실제로는 NAVER API HUB에서 발급받은
Client ID/Secret을 넣으면 된다.
"""
from __future__ import annotations

from datetime import date, datetime
from email.utils import parsedate_to_datetime

import httpx

from app.core.config import get_settings
from app.core.errors import ProviderUnavailableError
from app.core.logging import get_logger
from app.providers.base import NewsProvider, ProviderResult, RawNewsItem

logger = get_logger(__name__)

NAVER_NEWS_ENDPOINT = "https://naverapihub.apigw.ntruss.com/search/v1/news"


def _strip_html(text: str) -> str:
    return text.replace("<b>", "").replace("</b>", "").replace("&quot;", '"').replace("&amp;", "&")


class NaverNewsProvider(NewsProvider):
    name = "naver_news"

    def __init__(self) -> None:
        settings = get_settings()
        self._client_id = settings.naver_client_id
        self._client_secret = settings.naver_client_secret

    def search_news(self, query: str, display: int = 30) -> ProviderResult:
        if not self._client_id or not self._client_secret:
            return ProviderResult(
                status="unavailable",
                source_name=self.name,
                message=(
                    "NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 이 설정되어 있지 않습니다. "
                    "(2026-07-31부로 신규 발급은 개발자센터가 아닌 NAVER API HUB에서만 가능 - "
                    "위 모듈 docstring 참고)"
                ),
            )

        headers = {
            "X-NCP-APIGW-API-KEY-ID": self._client_id,
            "X-NCP-APIGW-API-KEY": self._client_secret,
        }
        params = {"query": query, "display": min(display, 100), "sort": "date"}

        try:
            resp = httpx.get(NAVER_NEWS_ENDPOINT, headers=headers, params=params, timeout=10.0)
            resp.raise_for_status()
            payload = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.warning("네이버 뉴스 API 오류: %s", exc)
            return ProviderResult(status="error", source_name=self.name, message=str(exc))
        except httpx.HTTPError as exc:
            logger.warning("네이버 뉴스 API 연결 실패: %s", exc)
            return ProviderResult(status="error", source_name=self.name, message="Naver News API 연결 실패")

        items: list[RawNewsItem] = []
        for item in payload.get("items", []):
            published_at = None
            try:
                published_at = parsedate_to_datetime(item.get("pubDate", ""))
            except (TypeError, ValueError):
                published_at = None

            items.append(
                RawNewsItem(
                    title=_strip_html(item.get("title", "")),
                    url=item.get("originallink") or item.get("link"),
                    source=None,  # 네이버 뉴스 검색 API는 언론사명을 별도로 제공하지 않음
                    published_at=published_at,
                    summary=_strip_html(item.get("description", "")),
                    provider=self.name,
                    language="ko",
                )
            )

        return ProviderResult(
            status="ok" if items else "empty",
            data=items,
            source_name=self.name,
            source_url="https://api.ncloud-docs.com/docs/naver-api-hub-search-news",
            retrieved_at=datetime.utcnow(),
        )


def get_news_provider() -> NewsProvider:
    return NaverNewsProvider()
