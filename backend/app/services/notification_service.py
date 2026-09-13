"""
뉴스 실시간 모니터링 / 알림 Service (요구사항 47, 48) - Phase4.

Phase1에서는 Notification 테이블 조회/읽음처리 기본 기능만 제공하고,
실제 백그라운드 폴링(Watchlist -> News Provider -> 신규기사 탐지)은 TODO로 남긴다.

TODO(Phase4):
    - APScheduler로 NEWS_POLLING_INTERVAL_SECONDS 주기 작업 등록
    - Watchlist에 등록된 기업들에 대해 news_service.refresh_company_news() 호출
    - 새로 저장된 News 중 Watchlist의 notify_all_news/notify_event_types 필터에 맞는 것만
      Notification row로 생성
    - Push Provider는 추상화만 해두고(WebNotificationProvider, PushProvider 인터페이스),
      Phase1~3에서는 Web/DB 알림까지만 구현
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.news import News
from app.models.notification import Notification
from app.schemas.watchlist import NotificationOut


def list_notifications(db: Session, unread_only: bool = False, limit: int = 50) -> list[NotificationOut]:
    stmt = select(Notification).order_by(Notification.created_at.desc()).limit(limit)
    if unread_only:
        stmt = stmt.where(Notification.read.is_(False))

    rows = list(db.execute(stmt).scalars().all())
    results: list[NotificationOut] = []
    for row in rows:
        company = db.get(Company, row.company_id)
        news = db.get(News, row.news_id)
        if not company or not news:
            continue
        results.append(
            NotificationOut(
                id=row.id,
                ticker=company.ticker,
                company_name=company.company_name,
                news_id=news.id,
                news_title=news.title,
                importance=row.importance,
                read=row.read,
                created_at=row.created_at,
            )
        )
    return results


def mark_as_read(db: Session, notification_id: int) -> None:
    notification = db.get(Notification, notification_id)
    if notification:
        notification.read = True
        db.add(notification)
        db.commit()


def poll_watchlist_news(db: Session) -> None:
    """TODO(Phase4): APScheduler 등에서 주기적으로 호출할 폴링 함수."""
    raise NotImplementedError("뉴스 실시간 모니터링(Phase4)은 아직 구현되지 않았습니다.")
