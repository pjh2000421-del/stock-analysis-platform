"""Watchlist Service (요구사항 46)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.company import Company
from app.models.news import News
from app.models.watchlist import DEMO_USER_ID, Watchlist
from app.schemas.watchlist import WatchlistItemOut


def add_to_watchlist(
    db: Session, ticker: str, notify_all_news: bool = False, notify_event_types: list[str] | None = None
) -> Watchlist:
    company = db.execute(select(Company).where(Company.ticker == ticker)).scalar_one_or_none()
    if company is None:
        raise NotFoundError(f"종목코드 {ticker}에 해당하는 기업을 찾을 수 없습니다.")

    existing = db.execute(
        select(Watchlist).where(Watchlist.user_id == DEMO_USER_ID, Watchlist.company_id == company.id)
    ).scalar_one_or_none()
    if existing:
        return existing

    item = Watchlist(
        user_id=DEMO_USER_ID,
        company_id=company.id,
        notify_all_news=notify_all_news,
        notify_event_types=",".join(notify_event_types) if notify_event_types else None,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def remove_from_watchlist(db: Session, ticker: str) -> None:
    company = db.execute(select(Company).where(Company.ticker == ticker)).scalar_one_or_none()
    if company is None:
        raise NotFoundError(f"종목코드 {ticker}에 해당하는 기업을 찾을 수 없습니다.")

    item = db.execute(
        select(Watchlist).where(Watchlist.user_id == DEMO_USER_ID, Watchlist.company_id == company.id)
    ).scalar_one_or_none()
    if item:
        db.delete(item)
        db.commit()


def list_watchlist(db: Session) -> list[WatchlistItemOut]:
    items = list(
        db.execute(select(Watchlist).where(Watchlist.user_id == DEMO_USER_ID)).scalars().all()
    )
    results: list[WatchlistItemOut] = []
    for item in items:
        company = item.company
        latest_news = db.execute(
            select(News.title)
            .where(News.company_id == company.id)
            .order_by(News.importance_score.desc().nullslast())
            .limit(1)
        ).first()

        results.append(
            WatchlistItemOut(
                id=item.id,
                ticker=company.ticker,
                company_name=company.company_name,
                current_price=None,  # 상세 시세는 기업 상세 조회 시 갱신 (불필요한 외부호출 방지)
                price_change_pct=None,
                latest_important_news_title=latest_news[0] if latest_news else None,
                notify_all_news=item.notify_all_news,
                notify_event_types=item.notify_event_types.split(",") if item.notify_event_types else None,
            )
        )
    return results
