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

# 요청 하나당 최대 대기 시간. 예전에는 10초였는데, 사이트가 느리거나 막힌 환경(예: 해외 서버)에서
# 10초 x 재시도 횟수만큼 기업 상세 페이지 전체가 멈췄다. 정상 응답은 보통 1초 안에 온다.
_REQUEST_TIMEOUT_SECONDS = 5.0
# 사이트에 연결하지 못했을 때, 이 시간 동안은 다시 시도하지 않고 바로 unavailable을 돌려준다.
# (실패할 때마다 매 요청이 다시 몇십 초씩 기다리는 것을 막기 위함)
_FAILURE_BACKOFF_SECONDS = 30 * 60
# wiseindex.com은 연속 요청 시 요청 간 약간의 간격을 두는 것이 권장된다.
_REQUEST_INTERVAL_SECONDS = 0.6


class WicsClassificationProvider(ClassificationProvider):
    """WICS 분류 조회.

    예전에는 첫 조회 때 대분류 10개 + 소분류 전부를 한 번에 내려받아 지도를 만들었다.
    그래서 서버가 막 켜진 직후의 첫 기업 상세 조회가 수십 초씩 걸렸다. 지금은 필요한 만큼만
    가져온다: 이미 받아둔 대분류부터 확인하고, 없으면 남은 대분류를 하나씩 받다가 종목을
    찾는 즉시 멈춘다. 소분류도 찾은 대분류에 속한 코드만 확인한다. 받아둔 목록은 코드별로
    캐시해 다음 종목 조회에 재사용한다.
    """

    name = "wics_wiseindex"

    def __init__(self) -> None:
        self._trading_date: str | None = None
        self._trading_date_at: float = 0.0
        # {지수 코드: (구성종목 코드 집합, 받아온 시각)}
        self._members: dict[str, tuple[set[str], float]] = {}
        self._failed_at: float | None = None
        self.last_error: str | None = None

    def _fetch_components(self, sec_cd: str, dt: str) -> list[dict] | None:
        """지수 구성종목을 가져온다. 네트워크/HTTP 오류면 None, 정상 응답이면 리스트(빈 리스트 가능)."""
        try:
            resp = httpx.get(
                COMPONENTS_ENDPOINT,
                params={"ceil_yn": 0, "dt": dt, "sec_cd": sec_cd},
                timeout=_REQUEST_TIMEOUT_SECONDS,
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

    def _remember(self, sec_cd: str, items: list[dict]) -> set[str]:
        members = {item["CMP_CD"] for item in items if item.get("CMP_CD")}
        self._members[sec_cd] = (members, time.time())
        return members

    def _cached_members(self, sec_cd: str) -> set[str] | None:
        cached = self._members.get(sec_cd)
        if cached and time.time() - cached[1] < _CACHE_TTL_SECONDS:
            return cached[0]
        return None

    def _resolve_trading_date(self) -> str | None:
        """실제 구성종목 데이터가 존재하는 가장 최근 거래일(YYYYMMDD)을 찾는다.

        wiseindex.com의 GetIndexComponets는 "지수 스냅샷" 조회 API라서, 주말/공휴일처럼
        실제로 지수가 산출되지 않은 날짜를 dt로 넘기면 list가 빈 배열([])로 돌아온다
        (요청 자체는 200 OK라 예외가 발생하지 않으므로, 이를 확인하지 않으면 "종목이
        전혀 없다"는 잘못된 empty 결과로 이어진다 - 실제로 이 버그 때문에 삼성전자/
        SK하이닉스가 WICS에서 조회되지 않는 문제가 발생했었다).
        오늘부터 최대 _MAX_TRADING_DATE_LOOKBACK_DAYS일 전까지 하루씩 거슬러 올라가며,
        토/일요일은 건너뛰고, 실제로 종목이 1개 이상 포함된 응답이 오는 첫 날짜를 사용한다.

        빈 응답(휴장일)일 때만 전날로 넘어간다. 연결 자체가 실패하면(None) 사이트에 닿지
        못하는 상황이므로 더 거슬러 올라가 봐야 같은 실패만 반복되니 바로 포기한다.
        probe로 받은 IT(G45) 구성종목은 버리지 않고 캐시해 재사용한다.
        """
        if self._trading_date and time.time() - self._trading_date_at < _CACHE_TTL_SECONDS:
            return self._trading_date

        candidate = date.today()
        checked = 0
        while checked < _MAX_TRADING_DATE_LOOKBACK_DAYS:
            if candidate.weekday() < 5:  # 0=월요일 ... 4=금요일만 시도(5,6=토,일 스킵)
                dt = candidate.strftime("%Y%m%d")
                items = self._fetch_components(_PROBE_SEC_CD, dt)
                if items is None:
                    return None
                if items:
                    self._trading_date = dt
                    self._trading_date_at = time.time()
                    self._remember(_PROBE_SEC_CD, items)
                    return dt
                checked += 1
                if checked < _MAX_TRADING_DATE_LOOKBACK_DAYS:
                    time.sleep(_REQUEST_INTERVAL_SECONDS)
            candidate -= timedelta(days=1)

        self.last_error = (
            f"최근 {_MAX_TRADING_DATE_LOOKBACK_DAYS}일 이내에 구성종목 데이터가 있는 거래일을 찾지 못했습니다."
        )
        logger.warning("WICS(wiseindex.com) 거래일 탐색 실패: %s", self.last_error)
        return None

    def _unavailable(self) -> ProviderResult:
        return ProviderResult(
            status="unavailable",
            source_name=self.name,
            message=f"wiseindex.com(WICS) 응답을 가져오지 못했습니다: {self.last_error}",
        )

    def _mark_failed(self) -> ProviderResult:
        self._failed_at = time.time()
        return self._unavailable()

    def _find_sector(self, ticker: str, dt: str) -> tuple[str | None, int, int]:
        """(찾은 대분류 코드, 새로 받으려던 대분류 수, 그중 실패한 수).

        캐시된 대분류부터 확인한 뒤, 나머지를 하나씩 받다가 종목을 찾으면 바로 멈춘다.
        """
        uncached: list[str] = []
        for sec_cd in SECTOR_CODES:
            members = self._cached_members(sec_cd)
            if members is None:
                uncached.append(sec_cd)
            elif ticker in members:
                return sec_cd, 0, 0

        fail_count = 0
        for i, sec_cd in enumerate(uncached):
            if i > 0:
                time.sleep(_REQUEST_INTERVAL_SECONDS)
            items = self._fetch_components(sec_cd, dt)
            if items is None:
                fail_count += 1
                continue
            if ticker in self._remember(sec_cd, items):
                return sec_cd, len(uncached), fail_count
        return None, len(uncached), fail_count

    def _find_sub_industry(self, ticker: str, sector_cd: str, dt: str) -> str | None:
        for sub_cd, (parent_cd, sub_name) in KNOWN_SUB_INDUSTRY_CODES.items():
            if parent_cd != sector_cd:
                continue
            members = self._cached_members(sub_cd)
            if members is None:
                items = self._fetch_components(sub_cd, dt)
                if items is None:
                    continue
                members = self._remember(sub_cd, items)
            if ticker in members:
                return sub_name
        return None

    def get_classification(self, ticker: str) -> ProviderResult:
        if self._failed_at is not None and time.time() - self._failed_at < _FAILURE_BACKOFF_SECONDS:
            return self._unavailable()

        dt = self._resolve_trading_date()
        if dt is None:
            return self._mark_failed()

        sector_cd, tried, failed = self._find_sector(ticker, dt)
        if sector_cd is None and tried and failed == tried:
            logger.warning("WICS(wiseindex.com) 대분류 조회가 전부 실패했습니다 - unavailable로 처리합니다.")
            return self._mark_failed()
        if sector_cd is None and failed:
            # 일부 대분류를 못 받아서 "목록에 없다"고 단정할 수 없는 경우. 재시도 금지 시간은 두지 않는다.
            return self._unavailable()
        self._failed_at = None

        if sector_cd is None:
            cached_sectors = sum(1 for c in SECTOR_CODES if self._cached_members(c) is not None)
            return ProviderResult(
                status="empty",
                source_name=self.name,
                message=(
                    "해당 종목이 WICS 대분류 구성종목 목록에 없습니다. "
                    f"(확인한 대분류: {cached_sectors}/{len(SECTOR_CODES)}개)"
                ),
            )

        sector = SECTOR_CODES[sector_cd]
        sub_industry_name = self._find_sub_industry(ticker, sector_cd, dt)
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
