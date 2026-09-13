"""
DART 사업내용 기반 보조 분류 Provider (우선순위 최하위, 요구사항 4의 5번).

OpenDART의 company.json은 기업의 업종코드(induty_code, 표준산업분류 KSIC 5자리)를
제공한다. 이 역시 KSIC 기반이라 WICS만큼 투자분석에 적합하지 않지만, WICS/FICS/
KRX 원본 데이터로도 분류를 확보하지 못한 경우를 위한 최후의 보조 수단으로만
사용한다. KSIC 앞 2자리만으로 아주 broad하게 묶은 결과이므로 confidence를
낮게(0.3) 설정해, 화면/Peer Comparison에서 이 값이 WICS 값보다 신뢰도가 낮다는
것을 구분할 수 있게 한다.
"""
from __future__ import annotations

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.providers.base import ClassificationProvider, ClassificationRecord, ProviderResult
from app.providers.dart_common import get_corp_code

logger = get_logger(__name__)

COMPANY_ENDPOINT = "https://opendart.fss.or.kr/api/company.json"

# KSIC 대분류 앞 2자리 -> broad 투자 참고용 카테고리 (최후 보조 수단으로만 사용됨).
# 실제 데이터가 없을 때 임의 추측으로 채우지 않기 위해, 매핑에 없는 코드는
# 그대로 status="empty" 처리되어 다음 단계(Unknown)로 넘어간다.
_KSIC_PREFIX_MAP: dict[str, str] = {
    "26": "전자·반도체 관련",
    "27": "의료·정밀기기 관련",
    "28": "전기장비 관련",
    "29": "기계 관련",
    "30": "자동차 관련",
    "31": "기타운송장비 관련",
    "20": "화학 관련",
    "21": "의약품 관련",
    "24": "1차금속 관련",
    "64": "금융업 관련",
    "65": "보험 관련",
    "66": "금융지원서비스 관련",
    "58": "출판·소프트웨어 관련",
    "62": "정보서비스·인터넷 관련",
    "63": "정보서비스 관련",
}


class DartClassificationProvider(ClassificationProvider):
    name = "dart_business_desc"

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.dart_api_key

    def get_classification(self, ticker: str) -> ProviderResult:
        if not self._api_key:
            return ProviderResult(
                status="unavailable", source_name=self.name, message="DART_API_KEY가 설정되어 있지 않습니다."
            )

        corp_code = get_corp_code(ticker, self._api_key)
        if not corp_code:
            return ProviderResult(
                status="unavailable", source_name=self.name, message=f"corp_code를 찾을 수 없습니다: {ticker}"
            )

        try:
            resp = httpx.get(
                COMPANY_ENDPOINT, params={"crtfc_key": self._api_key, "corp_code": corp_code}, timeout=10.0
            )
            resp.raise_for_status()
            payload = resp.json()
        except httpx.HTTPError as exc:
            logger.warning("DART 기업개황 조회 실패: %s", exc)
            return ProviderResult(status="error", source_name=self.name, message=str(exc))

        if payload.get("status") != "000":
            return ProviderResult(status="empty", source_name=self.name, message=payload.get("message"))

        induty_code = (payload.get("induty_code") or "").strip()
        if not induty_code:
            return ProviderResult(status="empty", source_name=self.name, message="induty_code 없음")

        broad = _KSIC_PREFIX_MAP.get(induty_code[:2])
        if not broad:
            return ProviderResult(
                status="empty", source_name=self.name, message=f"매핑되지 않은 KSIC 코드: {induty_code}"
            )

        record = ClassificationRecord(
            sector=None, industry=broad, sub_industry=None, system="DART_BUSINESS", confidence=0.3
        )
        return ProviderResult(status="ok", data=record, source_name=self.name, source_url="https://opendart.fss.or.kr/")


def get_dart_classification_provider() -> DartClassificationProvider:
    return DartClassificationProvider()
