"""알림 API (요구사항 47, 48, 55) - Phase4."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.watchlist import NotificationOut
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
def get_notifications(unread_only: bool = Query(False), db: Session = Depends(get_db)):
    return notification_service.list_notifications(db, unread_only=unread_only)


@router.post("/{notification_id}/read")
def mark_notification_read(notification_id: int, db: Session = Depends(get_db)):
    notification_service.mark_as_read(db, notification_id)
    return {"status": "ok"}
