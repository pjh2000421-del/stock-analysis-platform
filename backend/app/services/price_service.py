"""
주가 데이터 Service (요구사항 3, 7): Lazy Loading + Caching.

사용자가 특정 기간을 조회하면:
    1) DB(prices)에 캐시된 데이터 범위를 확인
    2) 캐시가 없으면 Provider에서 전체 기간을 가져와 저장
    3) 캐시는 있지만 최신 데이터가 부족하면(last_updated 이후) 증분만 추가 조회
    4) 이후 동일 기업 조회는 DB 데이터를 재사용
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.company import Company
from app.models.price import DailyPrice
from app.providers.base import PriceBar
from app.providers.stock_provider import get_stock_provider

logger = get_logger(__name__)

PERIOD_TO_DAYS = {
    "1D": 5,  # 휴장일 등을 감안해 여유있게 조회 후 마지막 값만 사용
    "5D": 10,
    "1M": 31,
    "3M": 93,
    "6M": 186,
    "1Y": 366,
    "5Y": 366 * 5,
    "MAX": 366 * 20,
}


def _save_bars(db: Session, company: Company, bars: list[PriceBar]) -> None:
    existing_dates = {
        d
        for (d,) in db.execute(
            select(DailyPrice.date).where(DailyPrice.company_id == company.id)
        ).all()
    }
    for bar in bars:
        if bar.date in existing_dates:
            continue
        db.add(
            DailyPrice(
                company_id=company.id,
                date=bar.date,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
            )
        )
    company.prices_last_updated = datetime.utcnow()
    db.add(company)
    db.commit()


def ensure_price_history(db: Session, company: Company, period: str) -> str:
    """요청된 기간을 커버할 만큼 DB에 데이터가 있는지 확인하고, 부족하면 Provider로 보충한다.

    반환값: provider 상태 메시지 ("ok" | "unavailable" | "error" | "cached")
    """
    days_needed = PERIOD_TO_DAYS.get(period, 366)
    needed_start = date.today() - timedelta(days=days_needed)

    earliest = db.execute(
        select(DailyPrice.date).where(DailyPrice.company_id == company.id).order_by(DailyPrice.date.asc())
    ).first()
    latest = db.execute(
        select(DailyPrice.date).where(DailyPrice.company_id == company.id).order_by(DailyPrice.date.desc())
    ).first()

    provider = get_stock_provider()

    if earliest is None:
        # 캐시 없음 -> 전체 기간 최초 조회
        result = provider.get_price_history(company.ticker, needed_start, date.today())
        if result.status == "ok":
            _save_bars(db, company, result.data)
        return result.status

    earliest_date = earliest[0]
    latest_date = latest[0]

    status = "cached"
    if earliest_date > needed_start:
        # 더 과거 데이터가 필요한 경우 (예: 5Y 요청인데 1Y치만 캐시되어 있음)
        result = provider.get_price_history(company.ticker, needed_start, earliest_date - timedelta(days=1))
        if result.status == "ok":
            _save_bars(db, company, result.data)
            status = result.status

    if latest_date < date.today() - timedelta(days=1):
        # 최신 데이터 증분 갱신
        result = provider.get_price_history(company.ticker, latest_date + timedelta(days=1), date.today())
        if result.status == "ok":
            _save_bars(db, company, result.data)
            status = result.status

    return status


def ensure_price_range(db: Session, company: Company, start: date, end: date) -> str:
    """[start, end] 특정 과거 구간을 커버할 만큼 DB에 데이터가 있는지 확인하고 보충한다.

    ensure_price_history()는 "오늘로부터 N일 전"만 지원해 Event Study처럼 임의의
    과거 시점(예: 3년 전 이벤트) 주변 구간을 채우는 데는 맞지 않아 별도로 둔다.
    """
    end = min(end, date.today())
    if start > end:
        return "cached"

    earliest = db.execute(
        select(DailyPrice.date).where(DailyPrice.company_id == company.id).order_by(DailyPrice.date.asc())
    ).first()
    latest = db.execute(
        select(DailyPrice.date).where(DailyPrice.company_id == company.id).order_by(DailyPrice.date.desc())
    ).first()

    provider = get_stock_provider()
    status = "cached"

    if earliest is None:
        result = provider.get_price_history(company.ticker, start, end)
        if result.status == "ok":
            _save_bars(db, company, result.data)
        return result.status

    earliest_date, latest_date = earliest[0], latest[0]

    if start < earliest_date:
        result = provider.get_price_history(company.ticker, start, earliest_date - timedelta(days=1))
        if result.status == "ok":
            _save_bars(db, company, result.data)
            status = result.status

    if end > latest_date:
        result = provider.get_price_history(company.ticker, latest_date + timedelta(days=1), end)
        if result.status == "ok":
            _save_bars(db, company, result.data)
            status = result.status

    return status


def get_prices_in_range(db: Session, company: Company, start: date, end: date) -> list[DailyPrice]:
    """[start, end] 구간의 실제 거래일 종가 데이터를 날짜 오름차순으로 반환한다."""
    ensure_price_range(db, company, start, end)
    return list(
        db.execute(
            select(DailyPrice)
            .where(DailyPrice.company_id == company.id, DailyPrice.date >= start, DailyPrice.date <= end)
            .order_by(DailyPrice.date.asc())
        )
        .scalars()
        .all()
    )


def get_price_history(db: Session, company: Company, period: str) -> list[DailyPrice]:
    status = ensure_price_history(db, company, period)
    days_needed = PERIOD_TO_DAYS.get(period, 366)
    start = date.today() - timedelta(days=days_needed)

    rows = list(
        db.execute(
            select(DailyPrice)
            .where(DailyPrice.company_id == company.id, DailyPrice.date >= start)
            .order_by(DailyPrice.date.asc())
        )
        .scalars()
        .all()
    )

    if period == "1D" and rows:
        rows = rows[-1:]

    logger.debug("가격 조회 상태(%s, %s): %s, %d건", company.ticker, period, status, len(rows))
    return rows


def get_latest_quote(db: Session, company: Company) -> dict | None:
    """현재가/전일대비 스냅샷을 DB에 캐시된 최근 시세로부터 계산한다.

    기업 상세 조회 시마다 외부 API를 호출하지 않도록, 이미 캐싱된 DailyPrice
    데이터(최근 며칠치)를 우선 확보한 뒤 최신 2개 값으로 계산한다. 이렇게 하면
    "최근에 이미 갱신했으므로 재호출 생략" 판단이 나더라도 항상 마지막으로
    캐시된 값을 그대로 반환할 수 있어, N/A가 나오는 것을 방지한다.
    """
    ensure_price_history(db, company, "5D")

    rows = list(
        db.execute(
            select(DailyPrice)
            .where(DailyPrice.company_id == company.id)
            .order_by(DailyPrice.date.desc())
            .limit(2)
        )
        .scalars()
        .all()
    )
    if not rows:
        return None

    latest = rows[0]
    prev = rows[1] if len(rows) > 1 else None
    change = (
        (latest.close - prev.close) if (prev and prev.close is not None and latest.close is not None) else None
    )
    change_pct = (change / prev.close * 100) if (change is not None and prev.close) else None

    return {
        "date": latest.date,
        "close": latest.close,
        "change": change,
        "change_pct": change_pct,
        "volume": latest.volume,
    }
