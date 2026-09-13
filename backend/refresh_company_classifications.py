"""
기존 DB에 저장된 기업들의 투자용 산업분류(investment_industry 등)를 일괄 재계산한다.

새 Classification Provider 구조(WICS 우선 -> FICS -> KRX 원본 -> DART 보조 ->
Unknown)를 도입한 뒤, 이미 저장되어 있던 기업들은 코드만 바꿔서는 자동으로
재분류되지 않는다(기업 상세 페이지를 실제로 열어봐야 Lazy Loading으로 갱신됨).
이 스크립트는 그 갱신을 한 번에(또는 오래된 것만) 수행한다.

사용법(backend 디렉터리에서):
    python refresh_company_classifications.py            # classification_updated_at이
                                                            # 없거나 30일 이상 지난 기업만 갱신
    python refresh_company_classifications.py --force     # 전체 기업 강제 재분류
    python refresh_company_classifications.py --ticker 005930 000660  # 특정 종목만

기존 raw_industry/industry 값은 건드리지 않고, investment_* 필드만 갱신한다.
"""
from __future__ import annotations

import argparse
import sys
import time

from sqlalchemy import select

from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.models.company import Company
from app.services.classification_service import ensure_classification

logger = get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="기업 투자용 산업분류 일괄 재계산")
    parser.add_argument("--force", action="store_true", help="이미 최신인 기업도 강제로 재분류한다")
    parser.add_argument("--ticker", nargs="*", help="특정 종목코드만 재분류 (미지정 시 전체)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        stmt = select(Company)
        if args.ticker:
            stmt = stmt.where(Company.ticker.in_(args.ticker))
        companies = list(db.execute(stmt).scalars().all())

        total = len(companies)
        print(f"대상 기업 수: {total}건 (force={args.force})")

        updated = 0
        for i, company in enumerate(companies, start=1):
            before = (company.investment_industry, company.classification_system)
            ensure_classification(db, company, force=args.force)
            after = (company.investment_industry, company.classification_system)
            changed = before != after
            if changed:
                updated += 1
            print(
                f"[{i}/{total}] {company.ticker} {company.company_name}: "
                f"raw={company.raw_industry!r} -> investment_industry={company.investment_industry!r} "
                f"(system={company.classification_system}, confidence={company.classification_confidence})"
            )
            # WICS Provider는 내부적으로 캐시되므로 대부분 즉시 처리되지만, 첫 호출이나
            # DART 호출 등 실제 네트워크 요청이 발생하는 경우를 위해 약간의 여유를 둔다.
            time.sleep(0.05)

        print(f"완료: {total}건 중 {updated}건 갱신됨")
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
