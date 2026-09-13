"""Watchlist API (요구사항 46, 55)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.errors import NotFoundError
from app.schemas.watchlist import WatchlistItemCreate, WatchlistItemOut
from app.services import watchlist_service

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


@router.get("", response_model=list[WatchlistItemOut])
def get_watchlist(db: Session = Depends(get_db)):
    return watchlist_service.list_watchlist(db)


@router.post("", status_code=201)
def add_watchlist_item(item: WatchlistItemCreate, db: Session = Depends(get_db)):
    try:
        watchlist_service.add_to_watchlist(
            db, item.ticker, item.notify_all_news, item.notify_event_types
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "added", "ticker": item.ticker}


@router.delete("/{ticker}")
def delete_watchlist_item(ticker: str, db: Session = Depends(get_db)):
    try:
        watchlist_service.remove_from_watchlist(db, ticker)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "removed", "ticker": ticker}
