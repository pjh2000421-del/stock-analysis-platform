"""기업 검색/상세/가격/재무/뉴스 API (요구사항 55)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.errors import NotFoundError
from app.schemas.company import (
    ClassificationOut,
    CompanyDetail,
    CompanySearchResponse,
    CompanySearchResult,
    RawClassificationOut,
)
from app.schemas.dcf import DCFAssumptions, DCFRequest, DCFResult
from app.schemas.financial import (
    CompanyMetricsResponse,
    FinancialHealthMetrics,
    FinancialStatementOut,
    GrowthMetrics,
    PeerComparisonResponse,
    ProfitabilityMetrics,
    ValuationMetrics,
    CapitalCostMetrics,
)
from app.schemas.common import ValueWithSource, DataSourceMeta
from app.schemas.news import NewsListResponse, NewsItem
from app.schemas.overview import CompositeScoreResponse, SimpleViewResponse
from app.schemas.price import EventMarker, PriceHistoryResponse, PricePoint
from app.schemas.qa import AskQuestionRequest, AskQuestionResponse
from app.services import company_service, financial_service, news_service, price_service
from app.services.classification_service import ensure_classification
from app.services.ai_qa_service import ask_about_company
from app.services.dcf_service import calculate_dcf
from app.services.overview_service import get_simple_view
from app.services.peer_service import get_peer_comparison
from app.services.scoring_service import get_composite_score

router = APIRouter(prefix="/companies", tags=["companies"])

VALID_PERIODS = {"1D", "5D", "1M", "3M", "6M", "1Y", "5Y", "MAX"}


@router.get("/search", response_model=CompanySearchResponse)
def search_companies(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    companies = company_service.search_companies(db, q)
    return CompanySearchResponse(
        query=q,
        results=[
            CompanySearchResult(
                ticker=c.ticker,
                company_name=c.company_name,
                market=c.market,
                sector=c.sector,
                industry=c.industry,
                # 검색 결과 단계에서는 분류를 새로 계산하지 않는다(Lazy Loading 원칙, 요구사항 3).
                # 이미 상세 조회 등으로 분류가 확보된 기업만 investment_industry가 채워진다.
                investment_industry=c.investment_industry,
            )
            for c in companies
        ],
    )


def _get_company_or_404(ticker: str, db: Session):
    try:
        return company_service.get_company_by_ticker(db, ticker)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{ticker}", response_model=CompanyDetail)
def get_company_detail(ticker: str, db: Session = Depends(get_db)):
    company = _get_company_or_404(ticker, db)
    quote = price_service.get_latest_quote(db, company)
    # 투자용 산업분류를 Lazy Loading으로 확보/갱신한다 (요구사항: WICS 우선, 없으면 낮은
    # 신뢰도로만 fallback, 절대 KSIC 원본을 투자용 분류로 그대로 쓰지 않는다).
    ensure_classification(db, company)

    current_price = quote.get("close") if quote else None
    price_change = quote.get("change") if quote else None
    price_change_pct = quote.get("change_pct") if quote else None
    price_date = quote.get("date") if quote else None

    classification = None
    if company.classification_system:
        classification = ClassificationOut(
            sector=company.investment_sector,
            industry=company.investment_industry,
            sub_industry=company.investment_sub_industry,
            system=company.classification_system,
            source=company.classification_source,
            confidence=company.classification_confidence,
            updated_at=company.classification_updated_at,
        )

    return CompanyDetail(
        ticker=company.ticker,
        company_name=company.company_name,
        company_name_en=company.company_name_en,
        market=company.market,
        sector=company.sector,
        industry=company.industry,
        market_cap=company.market_cap,
        classification=classification,
        raw_classification=RawClassificationOut(industry=company.raw_industry or company.industry),
        current_price=current_price,
        price_change=price_change,
        price_change_pct=price_change_pct,
        price_date=price_date,
        last_updated=company.last_updated,
    )


@router.get("/{ticker}/prices", response_model=PriceHistoryResponse)
def get_company_prices(ticker: str, period: str = Query("3M"), db: Session = Depends(get_db)):
    if period not in VALID_PERIODS:
        raise HTTPException(status_code=400, detail=f"유효하지 않은 기간입니다: {period}")

    company = _get_company_or_404(ticker, db)
    rows = price_service.get_price_history(db, company, period)

    # 뉴스 Event Marker (요구사항 7) - 이미 저장된 뉴스 중 이벤트가 있는 것만 매핑
    from sqlalchemy import select

    from app.models.news import News

    news_rows = db.execute(
        select(News).where(News.company_id == company.id, News.event_type.is_not(None)).limit(200)
    ).scalars().all()

    markers = [
        EventMarker(
            date=n.published_at.date(),
            news_id=n.id,
            title=n.title,
            event_type=n.event_type,
        )
        for n in news_rows
        if n.published_at
    ]

    return PriceHistoryResponse(
        ticker=ticker,
        period=period,
        prices=[
            PricePoint(date=r.date, open=r.open, high=r.high, low=r.low, close=r.close, volume=r.volume)
            for r in rows
        ],
        event_markers=markers,
    )


@router.get("/{ticker}/financials", response_model=list[FinancialStatementOut])
def get_company_financials(ticker: str, db: Session = Depends(get_db)):
    company = _get_company_or_404(ticker, db)
    statements = financial_service.get_financial_statements(db, company)
    return [
        FinancialStatementOut(
            period=s.period,
            reported_at=s.reported_at,
            available_at=s.available_at,
            revenue=s.revenue,
            operating_income=s.operating_income,
            net_income=s.net_income,
            assets=s.assets,
            liabilities=s.liabilities,
            equity=s.equity,
            operating_cash_flow=s.operating_cash_flow,
            free_cash_flow=s.free_cash_flow,
        )
        for s in statements
    ]


@router.get("/{ticker}/financials/debug-raw-accounts")
def debug_raw_dart_accounts(ticker: str, year: int | None = None, db: Session = Depends(get_db)):
    """[임시 진단용] DART가 실제로 반환하는 계정명(account_nm) 원본 목록을 그대로 노출한다.

    PER/EV-EBITDA가 다수 기업에서 N/A로 나오는 문제의 원인이 "계정명 후보 매핑이
    실제 공시 계정명과 다르다"인지 확인하기 위한 일회성 진단 엔드포인트. 원인 특정 후
    제거할 예정이므로 response_model을 별도로 정의하지 않는다.
    """
    from datetime import date as _date

    from app.providers.financial_provider import DartFinancialProvider

    _get_company_or_404(ticker, db)
    bsns_year = year or _date.today().year
    result = DartFinancialProvider().debug_raw_rows(ticker, bsns_year)
    return {"status": result.status, "message": result.message, "data": result.data}


def _vs(
    value: float | None,
    method: str,
    *,
    is_deficit: bool = False,
    deficit_label: str | None = None,
    is_estimated: bool = False,
) -> ValueWithSource:
    return ValueWithSource(
        value=value,
        meta=DataSourceMeta(
            calculation_method=method,
            source_name="직접 계산 (OpenDART + 시장가)",
            is_estimated=is_estimated,
        ),
        is_na=value is None,
        na_reason=(deficit_label if is_deficit else "관련 원자료 부족") if value is None else None,
        is_deficit=is_deficit and value is None,
    )


@router.get("/{ticker}/metrics", response_model=CompanyMetricsResponse)
def get_company_metrics(ticker: str, db: Session = Depends(get_db)):
    company = _get_company_or_404(ticker, db)
    metric = financial_service.compute_and_store_financial_metrics(db, company)

    return CompanyMetricsResponse(
        ticker=ticker,
        as_of=metric.date,
        valuation=ValuationMetrics(
            per=_vs(metric.per, "Price / EPS", is_deficit=metric.per_is_deficit, deficit_label="적자"),
            forward_per=_vs(metric.forward_per, "N/A (컨센서스 데이터 미연동)"),
            pbr=_vs(metric.pbr, "Price / BPS", is_deficit=metric.pbr_is_deficit, deficit_label="자본잠식"),
            psr=_vs(metric.psr, "시가총액 / 매출액"),
            ev_ebitda=_vs(
                metric.ev_ebitda,
                "EV / EBITDA",
                is_deficit=metric.ev_ebitda_is_deficit,
                deficit_label="적자",
                is_estimated=metric.ev_ebitda_is_estimated,
            ),
            peg=_vs(metric.peg, "PER / EPS성장률"),
            fcf_yield=_vs(metric.fcf_yield, "FCF / 시가총액"),
            earnings_yield=_vs(metric.earnings_yield, "1 / PER"),
        ),
        profitability=ProfitabilityMetrics(
            roe=_vs(metric.roe, "당기순이익 / 평균자본"),
            roa=_vs(metric.roa, "당기순이익 / 평균자산"),
            roic=_vs(metric.roic, "NOPAT / 투하자본"),
            gross_margin=_vs(metric.gross_margin, "매출총이익 / 매출액"),
            operating_margin=_vs(metric.operating_margin, "영업이익 / 매출액"),
            net_margin=_vs(metric.net_margin, "당기순이익 / 매출액"),
            fcf_margin=_vs(metric.fcf_margin, "FCF / 매출액"),
        ),
        growth=GrowthMetrics(
            revenue_growth_yoy=_vs(metric.revenue_growth_yoy, "YoY 매출액 성장률"),
            eps_growth_yoy=_vs(metric.eps_growth_yoy, "YoY EPS 성장률"),
            operating_income_growth_yoy=_vs(metric.operating_income_growth_yoy, "YoY 영업이익 성장률"),
            fcf_growth_yoy=_vs(metric.fcf_growth_yoy, "YoY FCF 성장률"),
            revenue_cagr_3y=_vs(metric.revenue_cagr_3y, "3Y CAGR"),
            revenue_cagr_5y=_vs(metric.revenue_cagr_5y, "5Y CAGR"),
        ),
        financial_health=FinancialHealthMetrics(
            debt_equity=_vs(metric.debt_equity, "부채총계 / 자본총계"),
            net_debt=_vs(metric.net_debt, "총차입금 - 현금성자산"),
            # EBITDA <= 0(적자)이면 ev_ebitda와 동일한 이유로 배수가 의미 없어지므로
            # 같은 플래그(ev_ebitda_is_deficit)를 재사용한다.
            net_debt_ebitda=_vs(
                metric.net_debt_ebitda,
                "순차입금 / EBITDA",
                is_deficit=metric.ev_ebitda_is_deficit,
                deficit_label="적자",
                is_estimated=metric.ev_ebitda_is_estimated,
            ),
            current_ratio=_vs(metric.current_ratio, "유동자산 / 유동부채"),
            quick_ratio=_vs(metric.quick_ratio, "(유동자산-재고자산) / 유동부채"),
            interest_coverage=_vs(metric.interest_coverage, "영업이익 / 이자비용"),
        ),
        capital_cost=CapitalCostMetrics(
            roic=_vs(metric.roic, "NOPAT / 투하자본"),
            wacc=_vs(metric.wacc, "TODO: WACC 산출 로직 미구현"),
            roic_minus_wacc=_vs(metric.roic_minus_wacc, "ROIC - WACC"),
        ),
    )


@router.get("/{ticker}/score", response_model=CompositeScoreResponse)
def get_company_score(ticker: str, db: Session = Depends(get_db)):
    company = _get_company_or_404(ticker, db)
    return get_composite_score(db, company)


@router.get("/{ticker}/peers", response_model=PeerComparisonResponse)
def get_company_peers(ticker: str, db: Session = Depends(get_db)):
    """업종 동종기업 비교 (Peer Comparison, 요구사항: 상대 밸류에이션)."""
    company = _get_company_or_404(ticker, db)
    return get_peer_comparison(db, company)


@router.get("/{ticker}/simple-view", response_model=SimpleViewResponse)
def get_company_simple_view(ticker: str, db: Session = Depends(get_db)):
    company = _get_company_or_404(ticker, db)
    return get_simple_view(db, company)


@router.get("/{ticker}/news", response_model=NewsListResponse)
def get_company_news(ticker: str, limit: int = Query(30, le=100), db: Session = Depends(get_db)):
    company = _get_company_or_404(ticker, db)
    # Provider 다변화(Naver -> NewsData.io -> GNews, BIGKinds 미사용): 각 Provider별
    # 상태와 Event Cluster 기반 관련기사 수(related_counts)를 함께 받는다.
    rows, related_counts, provider_status = news_service.get_company_news(db, company, limit=limit)

    return NewsListResponse(
        ticker=ticker,
        provider_status=provider_status,
        news=[
            NewsItem(
                id=n.id,
                title=n.title,
                summary=n.summary,
                source=n.source,
                published_at=n.published_at,
                url=n.url,
                sentiment_score=n.sentiment_score,
                importance_score=n.importance_score,
                event_type=n.event_type,
                event_subtype=n.event_subtype,
                is_mock=n.is_mock,
                provider=n.source_name,
                cluster_head_id=n.cluster_head_id,
                related_count=related_counts.get(n.id, 0),
            )
            for n in rows
        ],
    )


@router.post("/{ticker}/dcf", response_model=DCFResult)
def post_company_dcf(ticker: str, request: DCFRequest | None = None, db: Session = Depends(get_db)):
    company = _get_company_or_404(ticker, db)
    assumptions = request.assumptions if request else DCFAssumptions()
    return calculate_dcf(db, company, assumptions)


@router.post("/{ticker}/ask", response_model=AskQuestionResponse)
def post_company_ask(ticker: str, request: AskQuestionRequest, db: Session = Depends(get_db)):
    """종목 상세 페이지 우측 AI 질의응답 패널 (요구사항: AI QA).

    해당 종목의 실제 가격/재무/뉴스 데이터를 Claude에게 함께 전달하여,
    그 데이터에 근거한 답변만 생성하도록 한다 (요구사항 74).
    """
    company = _get_company_or_404(ticker, db)
    return ask_about_company(db, company, request)
