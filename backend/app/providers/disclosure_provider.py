"""OpenDART 공시 목록 Provider Adapter (요구사항 12: DART Anchor로 활용)."""
from __future__ import annotations

from datetime import date, datetime

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.providers.base import DisclosureProvider, ProviderResult
from app.providers.dart_common import get_corp_code

logger = get_logger(__name__)

DART_LIST_ENDPOINT = "https://opendart.fss.or.kr/api/list.json"


class DartDisclosureProvider(DisclosureProvider):
    name = "opendart_disclosure"

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.dart_api_key

    def search_disclosures(
        self, ticker: str, keyword: str | None, start: date, end: date
    ) -> ProviderResult:
        if not self._api_key:
            return ProviderResult(
                status="unavailable", source_name=self.name, message="DART_API_KEY 가 설정되어 있지 않습니다."
            )

        corp_code = get_corp_code(ticker, self._api_key)
        if not corp_code:
            return ProviderResult(
                status="unavailable", source_name=self.name, message=f"corp_code를 찾을 수 없습니다: {ticker}"
            )

        params = {
            "crtfc_key": self._api_key,
            "corp_code": corp_code,
            "bgn_de": start.strftime("%Y%m%d"),
            "end_de": end.strftime("%Y%m%d"),
            "page_count": 100,
        }
        try:
            resp = httpx.get(DART_LIST_ENDPOINT, params=params, timeout=15.0)
            resp.raise_for_status()
            payload = resp.json()
        except httpx.HTTPError as exc:
            logger.warning("DART 공시 목록 조회 실패: %s", exc)
            return ProviderResult(status="error", source_name=self.name, message=str(exc))

        if payload.get("status") not in ("000", "013"):  # 013: 조회된 데이터 없음
            return ProviderResult(status="error", source_name=self.name, message=payload.get("message"))

        items = payload.get("list", []) or []
        if keyword:
            items = [i for i in items if keyword in (i.get("report_nm") or "")]

        return ProviderResult(
            status="ok" if items else "empty",
            data=items,
            source_name=self.name,
            source_url="https://opendart.fss.or.kr/",
            retrieved_at=datetime.utcnow(),
        )


def get_disclosure_provider() -> DisclosureProvider:
    return DartDisclosureProvider()
