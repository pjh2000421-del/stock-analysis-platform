"""
종목 상세 페이지 우측 패널의 AI 질의응답 Service (요구사항: AI QA).

byul.ai류 서비스의 "AI에게 무엇이든 물어보기"와 달리, 이 기능은 반드시 플랫폼이
이미 계산/수집해둔 해당 종목의 실제 데이터(가격/재무지표/뉴스)만을 Claude에게
함께 전달하고, 그 데이터에 근거해서만 답변하도록 강제한다 (요구사항 74: 숫자를
함부로 만들지 않는다 - LLM이 학습 지식만으로 재무 수치를 추측해 답하는 것을 방지).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.company import Company
from app.models.financial import FinancialMetric
from app.providers.llm_provider import get_llm_provider
from app.schemas.qa import AskQuestionRequest, AskQuestionResponse
from app.services.news_service import get_company_news
from app.services.price_service import get_latest_quote
from app.services.scoring_service import get_composite_score, get_latest_metric

logger = get_logger(__name__)


def _num(value: float | None, suffix: str = "") -> str:
    if value is None:
        return "데이터 없음"
    return f"{value:,.2f}{suffix}"


def _valuation_line(label: str, value: float | None, is_deficit: bool, deficit_label: str, is_estimated: bool = False) -> str:
    if is_deficit and value is None:
        return f"{label}: {deficit_label} (배수로 의미 없음)"
    if value is None:
        return f"{label}: 데이터 없음"
    estimated_note = " (추정치 - 감가상각비 단독 공시 없어 근사 계산)" if is_estimated else ""
    return f"{label}: {value:,.2f}{estimated_note}"


def _build_context(db: Session, company: Company) -> str:
    quote = get_latest_quote(db, company)
    metric: FinancialMetric = get_latest_metric(db, company)
    score = get_composite_score(db, company)
    news_rows, _related_counts, _provider_status = get_company_news(db, company, limit=5)

    lines: list[str] = []
    lines.append(f"기업명: {company.company_name} ({company.ticker})")
    lines.append(f"시장: {company.market or '데이터 없음'}")
    if company.investment_industry:
        lines.append(
            f"업종(투자분석 기준, {company.classification_system or 'WICS'}): {company.investment_industry}"
        )
    else:
        lines.append(f"업종: {company.raw_industry or company.industry or '데이터 없음'} (KRX 등록 기준 - 겸업 대기업은 실제 사업과 다를 수 있음)")
    lines.append(f"시가총액: {_num(company.market_cap, '원')}")

    if quote:
        lines.append(
            f"현재가: {_num(quote.get('close'), '원')} (전일대비 {_num(quote.get('change_pct'), '%')}, 기준일 {quote.get('date')})"
        )
    else:
        lines.append("현재가: 데이터 없음")

    lines.append("")
    lines.append("[Valuation]")
    lines.append(_valuation_line("PER", metric.per, metric.per_is_deficit, "적자"))
    lines.append(_valuation_line("PBR", metric.pbr, metric.pbr_is_deficit, "자본잠식"))
    lines.append(_valuation_line("PSR", metric.psr, False, ""))
    lines.append(
        _valuation_line(
            "EV/EBITDA", metric.ev_ebitda, metric.ev_ebitda_is_deficit, "적자", metric.ev_ebitda_is_estimated
        )
    )

    lines.append("")
    lines.append("[Profitability]")
    lines.append(f"ROE: {_num(metric.roe, '%')}")
    lines.append(f"ROA: {_num(metric.roa, '%')}")
    lines.append(f"영업이익률: {_num(metric.operating_margin, '%')}")
    lines.append(f"순이익률: {_num(metric.net_margin, '%')}")

    lines.append("")
    lines.append("[Growth]")
    lines.append(f"매출성장률(YoY): {_num(metric.revenue_growth_yoy, '%')}")

    lines.append("")
    lines.append("[Financial Health]")
    lines.append(f"부채비율: {_num(metric.debt_equity, '%')}")
    lines.append(f"유동비율: {_num(metric.current_ratio, '%')}")
    lines.append(f"이자보상배율: {_num(metric.interest_coverage)}")
    lines.append(
        _valuation_line(
            "순차입금/EBITDA",
            metric.net_debt_ebitda,
            metric.ev_ebitda_is_deficit,
            "적자",
            metric.ev_ebitda_is_estimated,
        )
    )

    lines.append("")
    lines.append(f"[종합점수] {score.total_score if score.total_score is not None else '데이터 없음'} / 100")
    for breakdown in score.scores:
        score_text = f"{breakdown.score:.1f}" if breakdown.score is not None else "N/A"
        lines.append(f"  - {breakdown.category}: {score_text}")

    lines.append("")
    lines.append("[최근 뉴스]")
    if news_rows:
        for n in news_rows:
            date_str = n.published_at.date().isoformat() if n.published_at else "날짜 미상"
            lines.append(f"  - ({date_str}) {n.title}")
    else:
        lines.append("  - 수집된 뉴스 없음")

    return "\n".join(lines)


SYSTEM_PROMPT_TEMPLATE = """당신은 한국 주식 분석 플랫폼에 내장된 AI 애널리스트입니다.
아래 [종목 데이터]는 이 플랫폼이 DART 공시/시세/뉴스 API로부터 직접 수집·계산한 실제 데이터입니다.

반드시 지켜야 할 규칙:
1. 답변은 오직 [종목 데이터]에 있는 내용에만 근거하세요. 데이터에 없는 수치나 사실을 추측하거나 지어내지 마세요.
2. [종목 데이터]에 답이 없으면 솔직히 "제공된 데이터에는 해당 정보가 없습니다"라고 답하세요.
3. "(추정치)"라고 표시된 값을 인용할 때는 반드시 근사치임을 함께 언급하세요.
4. 특정 종목을 매수/매도하라는 직접적인 투자 권유는 하지 말고, 데이터가 의미하는 바를 객관적으로 설명하세요.
5. 한국어로, 간결하고 이해하기 쉽게 답변하세요.

[종목 데이터]
{context}
"""


def ask_about_company(db: Session, company: Company, request: AskQuestionRequest) -> AskQuestionResponse:
    provider = get_llm_provider()
    context = _build_context(db, company)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(context=context)

    result = provider.ask(system_prompt, request.question)

    if result.status == "unavailable":
        return AskQuestionResponse(
            ticker=company.ticker,
            question=request.question,
            is_unavailable=True,
            message=result.message,
        )

    if result.status != "ok":
        return AskQuestionResponse(
            ticker=company.ticker,
            question=request.question,
            message=result.message or "AI 답변 생성에 실패했습니다.",
        )

    return AskQuestionResponse(
        ticker=company.ticker,
        question=request.question,
        answer=result.data,
        model=provider.model,
    )
