"""
투자용 산업분류 Service (raw_industry / investment_industry 분리, 요구사항 2).

Lazy Loading 원칙: 기업 상세를 조회할 때, 분류가 없거나 오래되었으면(30일 이상)
그때 Classification Provider 체인으로 갱신한다. 전 종목을 미리 일괄 분류하지
않는다(요구사항 3의 Lazy Loading 원칙과 동일).
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.company import Company
from app.providers.classification.classifier import classify_company

logger = get_logger(__name__)

CLASSIFICATION_REFRESH_INTERVAL = timedelta(days=30)


def ensure_classification(db: Session, company: Company, force: bool = False) -> None:
    """investment_* 분류가 없거나 오래되었으면 Classification Provider 체인으로 갱신한다."""
    now = datetime.utcnow()

    # 과거 데이터 이전(migration): raw_industry가 비어있고 기존 industry 값이 있으면 복사해 보존한다.
    if not company.raw_industry and company.industry:
        company.raw_industry = company.industry

    if (
        not force
        and company.investment_industry
        and company.classification_updated_at
        and now - company.classification_updated_at < CLASSIFICATION_REFRESH_INTERVAL
    ):
        return

    try:
        outcome = classify_company(company.ticker, company.raw_industry)
    except Exception:  # noqa: BLE001 - 분류 실패가 기업 상세 조회 전체를 막으면 안 된다
        logger.exception("업종 분류 실패: %s", company.ticker)
        return

    company.investment_sector = outcome.sector
    company.investment_industry = outcome.industry
    company.investment_sub_industry = outcome.sub_industry
    company.classification_system = outcome.system
    company.classification_source = outcome.source
    company.classification_confidence = outcome.confidence
    company.classification_updated_at = outcome.updated_at
    db.add(company)
    db.commit()
