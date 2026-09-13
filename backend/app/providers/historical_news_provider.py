"""
BIGKinds 과거 뉴스 Provider Adapter — 선택적(optional) Provider.

BIGKinds는 승인/발급에 시간이 걸리고 접근 절차가 불확실해, 기본 뉴스 수집
파이프라인(news_service.py)은 더 이상 이 Provider에 의존하지 않는다. 대신
NewsData.io + GNews + 내부 DB 조합으로 과거/보완 뉴스를 확보한다
(Provider 다변화 요구사항).

이 파일은 삭제하지 않고 남겨두며, BIGKINDS_API_KEY가 설정되고 실제 연동이
완성되더라도 news_service.py가 명시적으로 호출하지 않는 한 기본 실행에는
영향을 주지 않는다. 향후 이 Provider를 다시 쓰고 싶다면 news_service.py의
Provider 체인에 선택적으로 추가하면 된다.
"""
from __future__ import annotations

from datetime import date

from app.core.config import get_settings
from app.core.logging import get_logger
from app.providers.base import HistoricalNewsProvider, ProviderResult

logger = get_logger(__name__)

BIGKINDS_ENDPOINT = "https://tools.kinds.or.kr/search/news"  # 참고용, 실제 계약사 문서 기준으로 조정 필요


class BigKindsHistoricalNewsProvider(HistoricalNewsProvider):
    name = "bigkinds"

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.bigkinds_api_key

    def search_historical_news(
        self, query: str, start: date, end: date, limit: int = 200
    ) -> ProviderResult:
        if not self._api_key:
            return ProviderResult(
                status="unavailable",
                source_name=self.name,
                message="BIGKinds API 인증정보(BIGKINDS_API_KEY)가 없어 사용할 수 없습니다. "
                "과거 유사 뉴스 탐색은 Naver 뉴스 검색 결과로 대체됩니다.",
            )

        # TODO: BIGKinds Open API 승인 후 실제 요청 구현.
        # 계약된 API 스펙(요청 파라미터/응답 스키마)에 맞춰 httpx 요청을 작성한다.
        logger.info("BIGKinds API Key가 설정되었지만 실제 연동은 TODO 상태입니다.")
        return ProviderResult(
            status="unavailable",
            source_name=self.name,
            message="BIGKinds 연동은 아직 구현되지 않았습니다 (TODO).",
        )


def get_historical_news_provider() -> HistoricalNewsProvider:
    return BigKindsHistoricalNewsProvider()
