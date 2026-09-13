"""
기업 검색 / 기업 마스터 정보 Service (요구사항 3, 4, 6).

Lazy Loading + Caching 원칙:
    1) DB(companies)에서 먼저 검색
    2) 결과가 없고 아직 종목 마스터 목록을 한 번도 캐시하지 않았다면
       Provider에서 전체 마스터 목록(티커/기업명/시장/업종 - 가벼운 메타데이터)을 1회 로드
    3) 이후에는 DB만으로 검색 (Provider 재호출 없음)
    4) 개별 기업의 "현재가/전일대비" 등 상세 시세는 기업 상세 조회 시에만 갱신
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.models.company import Company
from app.providers.base import ProviderResult
from app.providers.stock_provider import get_stock_provider

logger = get_logger(__name__)

QUOTE_REFRESH_INTERVAL = timedelta(minutes=15)

# 여러 요청(타이핑 중 매 글자마다 검색 요청)이 동시에 들어와도 종목 마스터 목록
# 부트스트랩(최초 1회 전체 로드)이 중복 실행되지 않도록 직렬화하는 락.
_bootstrap_lock = threading.Lock()


def _has_any_company(db: Session) -> bool:
    return db.execute(select(Company.id).limit(1)).first() is not None


def _bootstrap_company_master_list(db: Session) -> ProviderResult:
    """종목 마스터 목록을 최초 1회 Provider에서 가져와 DB에 채운다.

    동시 요청 경합(race condition) 방지: 락 획득 후 DB 상태를 다시 확인하고,
    그래도 경합으로 중복 삽입이 발생하면 IntegrityError를 흡수하고 정상 처리한다.
    """
    with _bootstrap_lock:
        # 락을 기다리는 동안 다른 요청이 이미 채워놨을 수 있으므로 재확인.
        if _has_any_company(db):
            return ProviderResult(status="ok", data=[], source_name="cache")

        provider = get_stock_provider()
        result = provider.get_company_master_list()
        if result.status != "ok":
            return result

        for record in result.data:
            existing = db.execute(
                select(Company).where(Company.ticker == record.ticker)
            ).scalar_one_or_none()
            if existing is None:
                db.add(
                    Company(
                        ticker=record.ticker,
                        company_name=record.company_name,
                        market=record.market,
                        sector=record.sector,
                        industry=record.industry,
                        # raw_industry: industry와 동일한 원본 값을 명시적인 이름으로도 저장한다
                        # (투자용 분류(investment_industry)는 별도로 Lazy Loading 시점에 채워진다).
                        raw_industry=record.industry,
                        market_cap=record.market_cap,
                    )
                )
        try:
            db.commit()
        except IntegrityError:
            # 극히 드문 잔여 경합(다른 프로세스 등)에 대한 안전망: 롤백 후 정상 처리.
            db.rollback()
            logger.info("종목 마스터 목록이 이미 다른 요청에 의해 채워져 있습니다.")
            return ProviderResult(status="ok", data=[], source_name="cache")

        logger.info("종목 마스터 목록 부트스트랩 완료 (%d건)", len(result.data))
        return result


def search_companies(db: Session, query: str, limit: int = 20) -> list[Company]:
    query = query.strip()
    if not query:
        return []

    stmt = (
        select(Company)
        .where(or_(Company.company_name.ilike(f"%{query}%"), Company.ticker == query))
        .limit(limit)
    )
    results = list(db.execute(stmt).scalars().all())

    if not results and not _has_any_company(db):
        # DB가 비어있으면(최초 실행) 마스터 목록을 부트스트랩 후 재검색
        bootstrap_result = _bootstrap_company_master_list(db)
        if bootstrap_result.status == "ok":
            results = list(db.execute(stmt).scalars().all())

    return results


def get_company_by_ticker(db: Session, ticker: str) -> Company:
    company = db.execute(select(Company).where(Company.ticker == ticker)).scalar_one_or_none()
    if company is None:
        # 마스터 목록에 없는 티커일 수 있으므로 한 번 더 부트스트랩 시도
        if not _has_any_company(db):
            _bootstrap_company_master_list(db)
        company = db.execute(select(Company).where(Company.ticker == ticker)).scalar_one_or_none()

    if company is None:
        raise NotFoundError(f"종목코드 {ticker}에 해당하는 기업을 찾을 수 없습니다.")
    return company


def refresh_current_quote(db: Session, company: Company) -> dict | None:
    """현재가/전일대비 스냅샷을 최신 상태로 유지 (일정 주기 이상 지났을 때만 갱신)."""
    now = datetime.utcnow()
    if company.last_updated and now - company.last_updated < QUOTE_REFRESH_INTERVAL:
        return None  # 최근에 갱신했으므로 재호출 생략 (불필요한 외부 호출 방지)

    provider = get_stock_provider()
    result = provider.get_current_quote(company.ticker)
    if result.status != "ok":
        logger.info("현재가 갱신 불가(%s): %s", company.ticker, result.message)
        return None

    company.last_updated = now
    db.add(company)
    db.commit()
    return result.data
