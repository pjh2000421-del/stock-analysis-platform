"""
Event Study Service — 이벤트 전후 주가반응 계산 오케스트레이션 (요구사항 15, 43).

event_analysis/event_study.py(순수 계산 함수)와 event_analysis/returns.py를
DB(NewsEvent/DailyPrice)와 연결한다:
    1) 뉴스에서 추출된 NewsEvent + event_date 확인
    2) 해당 기업의 event_date 전후(-20 ~ +60 거래일) 가격을 확보(부족하면 Provider로 보충)
    3) KOSPI/KOSDAQ 벤치마크 지수도 같은 구간으로 조회해 초과수익률 계산
    4) 결과를 EventMarketReaction에 저장(캐싱) - 이후 조회는 재계산하지 않는다.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.event_analysis.event_study import compute_event_market_reaction
from app.models.company import Company
from app.models.event import EventMarketReaction, NewsEvent
from app.models.news import News
from app.providers.macro_provider import get_macro_provider
from app.schemas.event import EventStudyPoint, EventStudyResponse, MarketReactionOut
from app.services.price_service import get_prices_in_range

logger = get_logger(__name__)

# 휴장일(주말/공휴일)을 감안해 거래일 -20~+60을 안전하게 담을 수 있도록 여유를 둔 캘린더일 범위.
_LOOKBACK_CALENDAR_DAYS = 40
_LOOKAHEAD_CALENDAR_DAYS = 100

_MARKET_TO_INDEX_CODE = {"KOSPI": "KS11", "KOSDAQ": "KQ11", "KONEX": "KQ11"}


def _get_benchmark_closes(market: str | None, start: date, end: date) -> dict[date, float]:
    index_code = _MARKET_TO_INDEX_CODE.get((market or "").upper())
    if not index_code:
        return {}

    provider = get_macro_provider()
    result = provider.get_market_index(index_code, start, end)
    if result.status != "ok" or result.data is None:
        return {}

    df = result.data
    closes: dict[date, float] = {}
    close_col = "Close" if "Close" in df.columns else None
    if close_col is None:
        return {}
    for idx, row in df.iterrows():
        d = idx.date() if hasattr(idx, "date") else idx
        value = row.get(close_col)
        if value is not None:
            closes[d] = float(value)
    return closes


def _get_event_for_news(db: Session, news_id: int) -> NewsEvent | None:
    return db.execute(select(NewsEvent).where(NewsEvent.news_id == news_id)).scalar_one_or_none()


def compute_and_store_market_reaction(
    db: Session, event: NewsEvent
) -> tuple[EventMarketReaction | None, dict[int, float] | None, str, str | None]:
    """주가 반응을 계산해 저장하고 (row, offset별 종가 시계열, status, message)를 반환한다.

    status: "ok" | "insufficient_data" | "no_price_data"
    """
    if event.event_date is None:
        return None, None, "insufficient_data", "이벤트 발생일 정보가 없어 주가 반응을 계산할 수 없습니다."

    company = db.get(Company, event.company_id)
    if company is None:
        return None, None, "insufficient_data", "기업 정보를 찾을 수 없습니다."

    event_date = event.event_date.date() if hasattr(event.event_date, "date") else event.event_date
    range_start = event_date - timedelta(days=_LOOKBACK_CALENDAR_DAYS)
    range_end = event_date + timedelta(days=_LOOKAHEAD_CALENDAR_DAYS)

    rows = get_prices_in_range(db, company, range_start, range_end)
    if not rows:
        return None, None, "no_price_data", "해당 기간의 주가 데이터를 확보하지 못했습니다."

    dates = [r.date for r in rows]
    day0_idx = next((i for i, d in enumerate(dates) if d >= event_date), None)
    if day0_idx is None:
        return None, None, "no_price_data", "이벤트 발생일 이후의 주가 데이터가 아직 없습니다."

    # 최소 Day+1 데이터는 있어야 "반응"을 논할 수 있다 (너무 최근 이벤트면 아직 계산 불가).
    if day0_idx + 1 >= len(rows):
        return None, None, "insufficient_data", "이벤트 발생 이후 경과일이 짧아 아직 주가 반응 데이터가 부족합니다."

    prices_by_offset: dict[int, float] = {}
    for offset in range(-20, 61):
        idx = day0_idx + offset
        if 0 <= idx < len(rows) and rows[idx].close is not None:
            prices_by_offset[offset] = rows[idx].close

    benchmark_closes = _get_benchmark_closes(company.market, range_start, range_end)
    benchmark_index_code = _MARKET_TO_INDEX_CODE.get((company.market or "").upper())
    benchmark_prices_by_offset: dict[int, float] | None = None
    if benchmark_closes:
        benchmark_prices_by_offset = {}
        for offset, idx_pos in ((o, day0_idx + o) for o in prices_by_offset):
            if 0 <= idx_pos < len(rows):
                bench_close = benchmark_closes.get(rows[idx_pos].date)
                if bench_close is not None:
                    benchmark_prices_by_offset[offset] = bench_close

    reaction = compute_event_market_reaction(prices_by_offset, benchmark_prices_by_offset)

    existing = db.execute(
        select(EventMarketReaction).where(EventMarketReaction.event_id == event.id)
    ).scalar_one_or_none()
    row = existing or EventMarketReaction(event_id=event.id)

    row.return_0d = reaction.get("return_0d")
    row.return_1d = reaction.get("return_1d")
    row.return_5d = reaction.get("return_5d")
    row.return_20d = reaction.get("return_20d")
    row.return_60d = reaction.get("return_60d")
    row.excess_return_1d = reaction.get("excess_return_1d")
    row.excess_return_5d = reaction.get("excess_return_5d")
    row.excess_return_20d = reaction.get("excess_return_20d")
    row.volatility_before = reaction.get("volatility_before")
    row.volatility_after = reaction.get("volatility_after")
    row.max_upside = reaction.get("max_upside")
    row.max_drawdown = reaction.get("max_drawdown")
    row.benchmark_index = benchmark_index_code if benchmark_prices_by_offset else None

    db.add(row)
    db.commit()
    db.refresh(row)

    # 시계열 포인트(차트용)는 DB에 저장하지 않고 매 요청마다 가격 원자료로부터 다시 만든다
    # (요구사항 74: 파생 시계열을 별도로 캐싱하면 원자료와 어긋날 위험이 있어, 항상 원천 가격에서 재계산).
    return row, prices_by_offset, "ok", None


def get_event_study(db: Session, news_id: int) -> EventStudyResponse:
    news = db.get(News, news_id)
    if news is None:
        return EventStudyResponse(news_id=news_id, status="no_event", message="뉴스를 찾을 수 없습니다.")

    event = _get_event_for_news(db, news_id)
    if event is None:
        return EventStudyResponse(
            news_id=news_id, status="no_event", message="이 뉴스에서 추출된 Event 정보가 없습니다."
        )

    reaction, series, status, message = compute_and_store_market_reaction(db, event)
    if reaction is None or series is None:
        return EventStudyResponse(news_id=news_id, status=status, message=message)

    base_price = series.get(0)
    points: list[EventStudyPoint] = []
    for offset in sorted(series):
        price = series[offset]
        return_pct = ((price - base_price) / base_price * 100) if base_price else None
        points.append(EventStudyPoint(offset_days=offset, return_pct=return_pct, volume=None, volatility=None))

    summary = MarketReactionOut(
        return_0d=reaction.return_0d,
        return_1d=reaction.return_1d,
        return_5d=reaction.return_5d,
        return_20d=reaction.return_20d,
        return_60d=reaction.return_60d,
        excess_return_1d=reaction.excess_return_1d,
        excess_return_5d=reaction.excess_return_5d,
        excess_return_20d=reaction.excess_return_20d,
        volatility_before=reaction.volatility_before,
        volatility_after=reaction.volatility_after,
        max_upside=reaction.max_upside,
        max_drawdown=reaction.max_drawdown,
        benchmark_index=reaction.benchmark_index,
    )

    return EventStudyResponse(news_id=news_id, status="ok", current_event=points, summary=summary, overlay_historical={})
