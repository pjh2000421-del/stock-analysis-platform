"""
WICS(FnGuide Wise Industry Classification Standard) 기반 투자용 산업분류 Provider.

데이터 출처: wiseindex.com(FnGuide가 운영하는 WICS 지수 공식 사이트)의
GetIndexComponets 공개 JSON 엔드포인트.

    GET https://www.wiseindex.com/Index/GetIndexComponets
        ?ceil_yn=0&dt=YYYYMMDD&sec_cd={WICS 지수 코드}

이 엔드포인트는 "지수 구성종목 조회"라는 명확한 목적의 JSON API이며, 종목 상세
페이지 HTML을 무단으로 대량 수집하는 것이 아니다(요구사항 4). 이미 이 프로젝트가
FinanceDataReader를 통해 KRX/Naver의 공개 데이터를 API Key 없이 가져오는 것과
같은 성격의 "공개 데이터 조회"로 판단해 사용했다.

WICS 대분류(Sector) 10개는 FnGuide의 "WICS Sector Index Methodology" 문서에
명시된 대로 10개이며, GICS와 동일한 2자리 코드 체계(10/15/20/.../55)를 사용한다.
아래 SECTOR_CODES는 그중 G45(IT)를 실제로 호출해 SEC_NM_KOR="IT"임을 확인했고,
나머지 9개는 동일 체계의 표준 명칭을 사용한다.

WICS 소분류(79개) 전체 코드 목록은 공식적으로 공개된 표를 찾지 못해 절대
추측으로 채우지 않았다(요구사항 4, 17: "없는 데이터를 만들어내지 않는다").
KNOWN_SUB_INDUSTRY_CODES에는 실제로 위 API를 호출해 응답을 확인한 항목만
등록했으며, 각 항목에 확인 근거(포함된 종목)를 주석으로 남겼다. 여기에 없는
종목은 대분류(10개) 수준까지만 자동으로 채워지고, 소분류는 비워둔다. 새로운
소분류 코드를 추가할 때도 반드시 실제 API 응답으로 검증 후 추가해야 한다
(절대 ticker별 하드코딩으로 문제를 숨기지 않는다).
"""
from __future__ import annotations

import time
from datetime import date, datetime, timedelta

import httpx

from app.core.logging import get_logger
from app.providers.base import ClassificationProvider, ClassificationRecord, ProviderResult

logger = get_logger(__name__)

COMPONENTS_ENDPOINT = "https://www.wiseindex.com/Index/GetIndexComponets"

# WICS 대분류(Sector) 10개. G45=IT는 실제 호출로 SEC_NM_KOR="IT" 확인됨.
SECTOR_CODES: dict[str, str] = {
    "G10": "에너지",
    "G15": "소재",
    "G20": "산업재",
    "G25": "경기관련소비재",
    "G30": "필수소비재",
    "G35": "보건의료",
    "G40": "금융",
    "G45": "IT",
    "G50": "커뮤니케이션서비스",
    "G55": "유틸리티",
}

# 실제 API 호출로 검증된 WICS 소분류만 등록한다. {sec_cd: (대분류 코드, 소분류명)}.
KNOWN_SUB_INDUSTRY_CODES: dict[str, tuple[str, str]] = {
    "G4530": ("G45", "반도체와반도체장비"),  # 확인됨: 005930 삼성전자, 000660 SK하이닉스 포함
    "G2510": ("G25", "자동차와부품"),  # 확인됨: 005380 현대차 포함
    "G4010": ("G40", "은행"),  # 확인됨: 105560 KB금융 포함
    "G5020": ("G50", "미디어와엔터테인먼트"),  # 확인됨: 035420 NAVER 포함
    "G3520": ("G35", "제약과생물공학"),  # 확인됨: 068270 셀트리온 포함
}

_CACHE_TTL_SECONDS = 6 * 3600  # 프로세스 내 메모리 캐시(빈번한 재호출 방지)

# 거래일 탐색 시 사용할 probe용 대분류 코드(IT, 항상 종목 수가 많아 존재 여부 판단에 적합).
_PROBE_SEC_CD = "G45"
# 최대 며칠 전까지 거슬러 올라가며 실제 거래일(데이터가 있는 날)을 찾을지.
# 주말(최대 2일) + 연휴가 겹치는 경우(예: 추석 연휴)까지 감안해 여유 있게 잡는다.
_MAX_TRADING_DATE_LOOKBACK_DAYS = 10


class WicsClassificationProvider(ClassificationProvider):
    name = "wics_wiseindex"

    def __init__(self) -> None:
        self._sector_map: dict[str, str] | None = None
        self._sub_industry_map: dict[str, str] | None = None
        self._cached_at: float = 0.0
        self.last_error: str | None = None

    def _fetch_components(self, sec_cd: str, dt: str) -> list[dict] | None:
        try:
            resp = httpx.get(
                COMPONENTS_ENDPOINT,
                params={"ceil_yn": 0, "dt": dt, "sec_cd": sec_cd},
                timeout=10.0,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                    ),
                    "Referer": "https://www.wiseindex.com/Index/Index",
                    "Accept": "application/json, text/plain, */*",
                },
                follow_redirects=True,
            )
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:  # noqa: BLE001 - 지수 하나 실패해도 전체 분류 기능이 죽으면 안 됨
            self.last_error = f"{type(exc).__name__}: {exc}"
            logger.warning("WICS 지수 구성종목 조회 실패(sec_cd=%s): %s", sec_cd, self.last_error)
            return None
        return payload.get("list") or []

    def _resolve_trading_date(self) -> str | None:
        """실제 구성종목 데이터가 존재하는 가장 최근 거래일(YYYYMMDD)을 찾는다.

        wiseindex.com의 GetIndexComponets는 "지수 스냅샷" 조회 API라서, 주말/공휴일처럼
        실제로 지수가 산출되지 않은 날짜를 dt로 넘기면 list가 빈 배열([])로 돌아온다
        (요청 자체는 200 OK라 예외가 발생하지 않으므로, 이를 확인하지 않으면 "종목이
        전혀 없다"는 잘못된 empty 결과로 이어진다 - 실제로 이 버그 때문에 삼성전자/
        SK하이닉스가 WICS에서 조회되지 않는 문제가 발생했었다).
        오늘부터 최대 _MAX_TRADING_DATE_LOOKBACK_DAYS일 전까지 하루씩 거슬러 올라가며,
        토/일요일은 건너뛰고, 실제로 종목이 1개 이상 포함된 응답이 오는 첫 날짜를 사용한다.
        """
        candidate = date.today()
        checked = 0
        while checked < _MAX_TRADING_DATE_LOOKBACK_DAYS:
            if candidate.weekday() < 5:  # 0=월요일 ... 4=금요일만 시도(5,6=토,일 스킵)
                dt = candidate.strftime("%Y%m%d")
                items = self._fetch_components(_PROBE_SEC_CD, dt)
                if items:
                    return dt
                checked += 1
                if checked < _MAX_TRADING_DATE_LOOKBACK_DAYS:
                    time.sleep(0.6)
            candidate -= timedelta(days=1)

        self.last_error = (
            f"최근 {_MAX_TRADING_DATE_LOOKBACK_DAYS}일 이내에 구성종목 데이터가 있는 거래일을 찾지 못했습니다."
        )
        logger.warning("WICS(wiseindex.com) 거래일 탐색 실패: %s", self.last_error)
        return None

    def _ensure_maps(self) -> bool:
        now = time.time()
        if self._sector_map is not None and now - self._cached_at < _CACHE_TTL_SECONDS:
            return True

        dt = self._resolve_trading_date()
        if dt is None:
            return False

        sector_map: dict[str, str] = {}
        sector_fail_count = 0
        codes = list(SECTOR_CODES.items())
        for i, (sec_cd, sector_name) in enumerate(codes):
            items = self._fetch_components(sec_cd, dt)
            if items is None:
                sector_fail_count += 1
                continue
            for item in items:
                cmp_cd = item.get("CMP_CD")
                if cmp_cd:
                    sector_map[cmp_cd] = sector_name
            # wiseindex.com은 연속 요청 시 요청 간 약간의 간격을 두는 것이 권장된다
            # (과도한 연속 호출로 인한 일시적 차단/누락 방지).
            if i < len(codes) - 1:
                time.sleep(0.6)

        if sector_fail_count == len(codes):
            logger.warning("WICS(wiseindex.com) 대분류 조회가 전부 실패했습니다 - unavailable로 처리합니다.")
            return False
        if sector_fail_count:
            logger.warning(
                "WICS(wiseindex.com) 대분류 %d/%d개 조회 실패 - 일부만 반영됩니다.", sector_fail_count, len(codes)
            )

        sub_map: dict[str, str] = {}
        sub_items = list(KNOWN_SUB_INDUSTRY_CODES.items())
        for i, (sec_cd, (_, sub_name)) in enumerate(sub_items):
            items = self._fetch_components(sec_cd, dt)
            if items is None:
                continue
            for item in items:
                cmp_cd = item.get("CMP_CD")
                if cmp_cd:
                    sub_map[cmp_cd] = sub_name
            if i < len(sub_items) - 1:
                time.sleep(0.6)

        self._sector_map = sector_map
        self._sub_industry_map = sub_map
        self._cached_at = now
        return True

    def get_classification(self, ticker: str) -> ProviderResult:
        if not self._ensure_maps():
            return ProviderResult(
                status="unavailable",
                source_name=self.name,
                message=f"wiseindex.com(WICS) 응답을 가져오지 못했습니다: {self.last_error}",
            )

        sector = (self._sector_map or {}).get(ticker)
        if sector is None:
            return ProviderResult(
                status="empty",
                source_name=self.name,
                message=(
                    "해당 종목이 WICS 대분류 구성종목 목록에 없습니다. "
                    f"(현재까지 확보된 대분류 종목 수: {len(self._sector_map or {})}건, "
                    f"소분류 종목 수: {len(self._sub_industry_map or {})}건)"
                ),
            )

        sub_industry_name = (self._sub_industry_map or {}).get(ticker)
        record = ClassificationRecord(
            sector=sector,
            industry=sub_industry_name or sector,
            sub_industry=None,
            system="WICS",
            confidence=0.95 if sub_industry_name else 0.6,
        )
        return ProviderResult(
            status="ok",
            data=record,
            source_name=self.name,
            source_url="https://www.wiseindex.com/",
            retrieved_at=datetime.utcnow(),
        )


_singleton: WicsClassificationProvider | None = None


def get_wics_provider() -> WicsClassificationProvider:
    global _singleton
    if _singleton is None:
        _singleton = WicsClassificationProvider()
    return _singleton
