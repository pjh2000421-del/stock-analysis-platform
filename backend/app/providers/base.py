"""
Provider 공통 인터페이스 (Adapter 패턴).

특정 데이터 공급자가 바뀌어도 Service Layer를 다시 작성하지 않도록,
모든 외부 데이터 접근은 아래 추상 인터페이스를 구현한 Adapter를 통해서만 이루어진다.
(요구사항 2)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class ProviderResult:
    """모든 Provider 호출 결과를 감싸는 공통 Envelope.

    status:
        "ok"           - 정상 데이터
        "unavailable"  - API Key 없음/미승인 등으로 사용 불가 (정상적인 상태로 처리)
        "error"        - 예기치 못한 오류
        "empty"        - 정상 호출되었으나 데이터 없음
    """

    status: str
    data: object = None
    source_name: str | None = None
    source_url: str | None = None
    retrieved_at: datetime | None = None
    message: str | None = None
    is_mock: bool = False


@dataclass
class CompanyMasterRecord:
    ticker: str
    company_name: str
    market: str | None = None
    sector: str | None = None
    industry: str | None = None
    market_cap: float | None = None


@dataclass
class PriceBar:
    date: date
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: int | None


@dataclass
class RawFinancialStatement:
    period: str
    reported_at: date | None
    available_at: date | None
    revenue: float | None = None
    operating_income: float | None = None
    net_income: float | None = None
    assets: float | None = None
    liabilities: float | None = None
    equity: float | None = None
    operating_cash_flow: float | None = None
    free_cash_flow: float | None = None
    capital_expenditure: float | None = None
    shares_outstanding: float | None = None
    current_assets: float | None = None
    current_liabilities: float | None = None
    inventory: float | None = None
    interest_expense: float | None = None
    depreciation_amortization: float | None = None
    # EV(기업가치)/순차입금 계산에 필요 (요구사항: EV/EBITDA, Net Debt/EBITDA)
    cash_and_equivalents: float | None = None
    total_borrowings: float | None = None
    # 감가상각비를 별도 계정으로 공시하지 않는 대기업(예: 삼성전자)을 위한 EBITDA 추정 fallback.
    # 현금흐름표의 "조정"(당기순이익 대비 비현금성 조정 합계, 감가상각비 포함)을 담아두고,
    # 감가상각비 자체를 못 찾았을 때만 근사치로 사용한다(반드시 추정치임을 표시).
    non_cash_adjustments_total: float | None = None


@dataclass
class ClassificationRecord:
    """투자분석용 산업분류 결과 (요구사항: WICS/FICS 등 투자용 분류를 KSIC/법정업종과 분리).

    sector: 대분류(예: "IT"), industry: 화면 표시/Peer Comparison에 사용할 세부 분류
    (예: "반도체와반도체장비"), sub_industry: industry보다 더 세분화된 체계가 확보되면
    사용할 필드(현재 확인된 데이터소스에서는 채우지 않는다 - 없는 데이터를 만들지 않는다).
    """

    sector: str | None = None
    industry: str | None = None
    sub_industry: str | None = None
    system: str = "UNKNOWN"  # "WICS" | "FICS" | "KRX_RAW" | "DART_BUSINESS" | "UNKNOWN"
    confidence: float = 0.0


class ClassificationProvider(ABC):
    """기업 투자분석용 산업분류 Provider 인터페이스."""

    name: str = "base_classification_provider"

    @abstractmethod
    def get_classification(self, ticker: str) -> ProviderResult:
        """ClassificationRecord를 ProviderResult.data에 담아 반환한다."""


@dataclass
class RawNewsItem:
    title: str
    url: str
    source: str | None
    published_at: datetime | None
    summary: str | None = None
    # 이 기사를 실제로 가져온 Provider 이름 (예: "naver_news", "newsdata_io", "gnews").
    # Service Layer에서 여러 Provider 결과를 병합할 때 어디서 왔는지 추적하기 위함.
    provider: str | None = None
    language: str | None = None


class StockPriceProvider(ABC):
    """주가/거래량 Provider 인터페이스."""

    name: str = "base_stock_provider"

    @abstractmethod
    def get_company_master_list(self) -> ProviderResult:
        """검색용 전체 종목 마스터 목록(티커/기업명/시장/업종)을 반환한다."""

    @abstractmethod
    def get_price_history(self, ticker: str, start: date, end: date) -> ProviderResult:
        """기간별 일봉 데이터(list[PriceBar])를 반환한다."""

    @abstractmethod
    def get_current_quote(self, ticker: str) -> ProviderResult:
        """현재가/전일대비/시가총액 등 실시간에 가까운 스냅샷을 반환한다."""


class NewsProvider(ABC):
    """뉴스 검색 Provider 인터페이스."""

    name: str = "base_news_provider"

    @abstractmethod
    def search_news(self, query: str, display: int = 30) -> ProviderResult:
        """기업명/키워드로 최신 뉴스를 검색한다. (list[RawNewsItem])"""


class HistoricalNewsProvider(ABC):
    """과거 뉴스 검색 Provider 인터페이스 (예: BIGKinds)."""

    name: str = "base_historical_news_provider"

    @abstractmethod
    def search_historical_news(
        self, query: str, start: date, end: date, limit: int = 200
    ) -> ProviderResult:
        """과거 기간의 뉴스 후보(100~500건)를 검색한다."""


class FinancialStatementProvider(ABC):
    """재무제표 Provider 인터페이스 (예: OpenDART)."""

    name: str = "base_financial_provider"

    @abstractmethod
    def get_financial_statements(self, ticker: str, years: int = 5) -> ProviderResult:
        """list[RawFinancialStatement] 반환."""


class DisclosureProvider(ABC):
    """공시 Provider 인터페이스 (OpenDART 공시 목록/원문)."""

    name: str = "base_disclosure_provider"

    @abstractmethod
    def search_disclosures(
        self, ticker: str, keyword: str | None, start: date, end: date
    ) -> ProviderResult:
        """공시 목록 검색 (M&A/공급계약/증자 등 Anchor로 활용, 요구사항 12)."""


class MacroDataProvider(ABC):
    """거시경제/시장 지수 Provider 인터페이스."""

    name: str = "base_macro_provider"

    @abstractmethod
    def get_market_index(self, index_code: str, start: date, end: date) -> ProviderResult:
        """KOSPI/KOSDAQ 등 지수 데이터."""

    @abstractmethod
    def get_fx_rate(self, pair: str, start: date, end: date) -> ProviderResult:
        """USD/KRW 등 환율 데이터."""

    @abstractmethod
    def get_cpi(self, start: date, end: date) -> ProviderResult:
        """물가 조정(요구사항 13)에 사용할 CPI 데이터."""
