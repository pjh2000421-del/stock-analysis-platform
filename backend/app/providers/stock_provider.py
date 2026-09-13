"""
주가/거래량 및 종목 마스터 Provider 구현체.

우선순위 (요구사항 5, Fallback 원칙):
    1) 한국투자증권 Open API (KOREA_INVESTMENT_APP_KEY 설정 시) - TODO: 실계좌 연동 필요, 인터페이스만 준비
    2) KRX Open API (KRX_OPEN_API_KEY 설정 시) - TODO: 인터페이스만 준비
    3) FinanceDataReader (API Key 불필요, KRX/네이버금융 기반 공개 데이터) - 기본 Provider

get_stock_provider() 팩토리가 설정된 Key 유무에 따라 적절한 Provider를 선택한다.
특정 Provider가 바뀌어도 Service Layer는 StockPriceProvider 인터페이스만 바라본다.
"""
from __future__ import annotations

from datetime import date, datetime

from app.core.config import get_settings
from app.core.errors import ProviderUnavailableError
from app.core.logging import get_logger
from app.providers.base import (
    CompanyMasterRecord,
    PriceBar,
    ProviderResult,
    StockPriceProvider,
)

logger = get_logger(__name__)


_INVALID_TEXT_VALUES = {"nan", "none", "null", "na", "n/a", "-"}


def _clean_str(value) -> str | None:
    """pandas 셀 값을 안전하게 문자열로 변환한다.

    비어있거나(None) NaN인 값을 그대로 str()하면 "nan" 문자열이 되어버려
    (NaN은 파이썬에서 truthy이므로 흔한 `if value:` 체크로 걸러지지 않는다),
    실제로는 없는 값인데 마치 "nan"이라는 업종/이름이 있는 것처럼 취급되는
    문제가 생긴다. `value != value`는 NaN 여부를 pandas/numpy 없이 판별하는
    표준적인 방법이다.

    일부 컬럼은 실제 float NaN이 아니라 이미 문자열 "nan"/"None" 등으로
    직렬화되어 들어오는 경우가 있어(라이브러리/소스에 따라 다름), 위 NaN 판별을
    통과해버린다. 그래서 문자열로 변환한 뒤에도 알려진 "빈 값" 표현들은
    한 번 더 걸러낸다.
    """
    if value is None:
        return None
    if value != value:  # NaN 판별
        return None
    text = str(value).strip()
    if not text or text.lower() in _INVALID_TEXT_VALUES:
        return None
    return text


class FinanceDataReaderStockProvider(StockPriceProvider):
    """FinanceDataReader 기반 (기본 Provider, API Key 불필요)."""

    name = "finance_datareader"

    def _import_fdr(self):
        try:
            import FinanceDataReader as fdr  # type: ignore

            return fdr
        except ImportError as exc:  # pragma: no cover - 환경에 미설치 시
            raise ProviderUnavailableError(
                self.name, "finance-datareader 패키지가 설치되어 있지 않습니다."
            ) from exc

    def _fetch_sector_industry_map(self, fdr) -> dict[str, tuple[str | None, str | None]]:
        """업종(Sector)/산업(Industry) 정보를 별도 목록(KRX-DESC)에서 가져와 티커 기준으로 매핑한다.

        `fdr.StockListing("KRX")`는 시세/시가총액 위주 목록이라 Sector/Industry 컬럼이
        없는 경우가 많다 (Peer Comparison 등 업종 기반 기능이 전부 비어보이는 원인이었음).
        이 목록은 실패해도 전체 부트스트랩을 막지 않고, 빈 매핑으로 조용히 넘어간다.
        """
        try:
            desc_df = fdr.StockListing("KRX-DESC")
        except Exception:  # noqa: BLE001
            logger.warning("KRX-DESC(업종 정보) 목록 조회 실패 - Sector/Industry 없이 진행합니다.")
            return {}

        desc_cols = {c.lower(): c for c in desc_df.columns}

        def dcol(*names: str) -> str | None:
            for n in names:
                if n.lower() in desc_cols:
                    return desc_cols[n.lower()]
            return None

        code_col = dcol("Code", "Symbol")
        sector_col = dcol("Sector")
        industry_col = dcol("Industry")
        if not code_col or (not sector_col and not industry_col):
            return {}

        mapping: dict[str, tuple[str | None, str | None]] = {}
        for _, row in desc_df.iterrows():
            ticker = str(row[code_col]).zfill(6)
            sector = _clean_str(row.get(sector_col)) if sector_col else None
            industry = _clean_str(row.get(industry_col)) if industry_col else None
            mapping[ticker] = (sector, industry)
        return mapping

    def get_company_master_list(self) -> ProviderResult:
        try:
            fdr = self._import_fdr()
        except ProviderUnavailableError as exc:
            return ProviderResult(status="unavailable", message=str(exc), source_name=self.name)

        try:
            df = fdr.StockListing("KRX")
        except Exception as exc:  # noqa: BLE001
            # "KRX"(시가총액 기준) 엔드포인트는 배포 환경(해외 리전 서버 등)에서 KRX 쪽
            # 응답을 못 받아오는 경우가 있다(빈 응답 -> JSON 파싱 실패). 이 경우 같은
            # FinanceDataReader 안의 다른 소스(KRX-DESC, 상장법인목록 - 일반 HTML 표
            # 크롤링이라 별도 세션/OTP가 필요 없어 더 안정적)로 한 번 더 시도해본다.
            logger.warning("KRX(시가총액) 종목 목록 조회 실패(%s) - KRX-DESC로 재시도합니다.", exc)
            try:
                df = fdr.StockListing("KRX-DESC")
            except Exception as exc2:  # noqa: BLE001
                logger.exception("KRX-DESC 종목 목록 조회도 실패")
                return ProviderResult(status="error", message=str(exc2), source_name=self.name)

        records: list[CompanyMasterRecord] = []
        cols = {c.lower(): c for c in df.columns}

        def col(*names: str) -> str | None:
            for n in names:
                if n.lower() in cols:
                    return cols[n.lower()]
            return None

        code_col = col("Code", "Symbol")
        name_col = col("Name")
        market_col = col("Market")
        sector_col = col("Sector")
        industry_col = col("Industry")
        marcap_col = col("Marcap", "MarketCap")

        if not code_col or not name_col:
            return ProviderResult(
                status="error", message="예상치 못한 응답 스키마입니다.", source_name=self.name
            )

        # 메인 목록에 Sector/Industry가 없으면 KRX-DESC(상장법인목록)에서 보강한다.
        sector_map: dict[str, tuple[str | None, str | None]] = {}
        if not sector_col and not industry_col:
            sector_map = self._fetch_sector_industry_map(fdr)

        for _, row in df.iterrows():
            ticker = str(row[code_col]).zfill(6)
            sector = _clean_str(row.get(sector_col)) if sector_col else None
            industry = _clean_str(row.get(industry_col)) if industry_col else None
            if not sector and not industry and ticker in sector_map:
                sector, industry = sector_map[ticker]

            records.append(
                CompanyMasterRecord(
                    ticker=ticker,
                    company_name=str(row[name_col]),
                    market=_clean_str(row.get(market_col)) if market_col else None,
                    sector=sector,
                    industry=industry,
                    market_cap=(
                        float(row[marcap_col])
                        if marcap_col and row.get(marcap_col) not in (None, "") and row[marcap_col] == row[marcap_col]
                        else None
                    ),
                )
            )

        return ProviderResult(
            status="ok",
            data=records,
            source_name=self.name,
            source_url="https://github.com/FinanceData/FinanceDataReader",
            retrieved_at=datetime.utcnow(),
        )

    def get_price_history(self, ticker: str, start: date, end: date) -> ProviderResult:
        try:
            fdr = self._import_fdr()
            df = fdr.DataReader(ticker, start, end)
        except ProviderUnavailableError as exc:
            return ProviderResult(status="unavailable", message=str(exc), source_name=self.name)
        except Exception as exc:  # noqa: BLE001
            logger.exception("주가 조회 실패: %s", ticker)
            return ProviderResult(status="error", message=str(exc), source_name=self.name)

        if df is None or df.empty:
            return ProviderResult(status="empty", source_name=self.name, data=[])

        bars: list[PriceBar] = []
        for idx, row in df.iterrows():
            d = idx.date() if hasattr(idx, "date") else idx
            bars.append(
                PriceBar(
                    date=d,
                    open=float(row.get("Open")) if row.get("Open") == row.get("Open") else None,
                    high=float(row.get("High")) if row.get("High") == row.get("High") else None,
                    low=float(row.get("Low")) if row.get("Low") == row.get("Low") else None,
                    close=float(row.get("Close")) if row.get("Close") == row.get("Close") else None,
                    volume=int(row.get("Volume"))
                    if row.get("Volume") == row.get("Volume") and row.get("Volume") is not None
                    else None,
                )
            )

        return ProviderResult(
            status="ok",
            data=bars,
            source_name=self.name,
            source_url=f"https://github.com/FinanceData/FinanceDataReader",
            retrieved_at=datetime.utcnow(),
        )

    def get_current_quote(self, ticker: str) -> ProviderResult:
        # 최근 2영업일 데이터를 조회하여 현재가/전일대비를 계산한다.
        today = date.today()
        result = self.get_price_history(ticker, date(today.year - 1, today.month, today.day), today)
        if result.status != "ok" or not result.data:
            return result

        bars: list[PriceBar] = result.data  # type: ignore
        if len(bars) < 1:
            return ProviderResult(status="empty", source_name=self.name)

        latest = bars[-1]
        prev = bars[-2] if len(bars) >= 2 else None
        change = (latest.close - prev.close) if (prev and prev.close and latest.close) else None
        change_pct = (change / prev.close * 100) if (change is not None and prev.close) else None

        return ProviderResult(
            status="ok",
            data={
                "date": latest.date,
                "close": latest.close,
                "change": change,
                "change_pct": change_pct,
                "volume": latest.volume,
            },
            source_name=self.name,
            retrieved_at=datetime.utcnow(),
        )


class KoreaInvestmentStockProvider(StockPriceProvider):
    """
    한국투자증권 Open API 어댑터.
    TODO(Phase1 이후): OAuth 토큰 발급 및 실시간 시세 연동 구현.
    현재는 인터페이스만 제공하며, Key 미설정/미구현 상태에서는 항상 unavailable을 반환한다.
    """

    name = "korea_investment"

    def __init__(self) -> None:
        settings = get_settings()
        self._app_key = settings.korea_investment_app_key
        self._app_secret = settings.korea_investment_app_secret

    def _unavailable(self, reason: str) -> ProviderResult:
        return ProviderResult(status="unavailable", message=reason, source_name=self.name)

    def get_company_master_list(self) -> ProviderResult:
        return self._unavailable("한국투자증권 API 연동은 TODO 상태입니다 (Adapter 준비됨).")

    def get_price_history(self, ticker: str, start: date, end: date) -> ProviderResult:
        return self._unavailable("한국투자증권 API 연동은 TODO 상태입니다 (Adapter 준비됨).")

    def get_current_quote(self, ticker: str) -> ProviderResult:
        return self._unavailable("한국투자증권 API 연동은 TODO 상태입니다 (Adapter 준비됨).")


def get_stock_provider() -> StockPriceProvider:
    """설정된 API Key 우선순위에 따라 실제 사용할 Provider를 선택한다."""
    settings = get_settings()
    if settings.korea_investment_app_key and settings.korea_investment_app_secret:
        # TODO: 실제 구현이 완료되면 이 Provider를 우선 사용하도록 활성화
        logger.info("한국투자증권 Key가 설정되었지만 어댑터가 아직 TODO 상태이므로 FDR로 대체합니다.")
    return FinanceDataReaderStockProvider()
