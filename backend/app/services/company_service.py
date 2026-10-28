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

import json
import re
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.models.company import Company
from app.core.config import get_settings
from app.providers.base import CompanyMasterRecord, ProviderResult
from app.providers.dart_common import fetch_company_overview
from app.providers.stock_provider import get_stock_provider

logger = get_logger(__name__)

QUOTE_REFRESH_INTERVAL = timedelta(minutes=15)

# 여러 요청(타이핑 중 매 글자마다 검색 요청)이 동시에 들어와도 종목 마스터 목록
# 부트스트랩(최초 1회 전체 로드)이 중복 실행되지 않도록 직렬화하는 락.
_bootstrap_lock = threading.Lock()

_FALLBACK_MASTER_LIST_PATH = Path(__file__).resolve().parent.parent / "data" / "krx_fallback_companies.json"


def _has_any_company(db: Session) -> bool:
    return db.execute(select(Company.id).limit(1)).first() is not None


def _load_fallback_master_list() -> ProviderResult:
    """실 Provider(FinanceDataReader 등)가 배포 환경(예: 해외 리전 서버)에서 KRX 응답을
    정상적으로 못 받아오는 경우를 대비한 최소한의 비상 목록.

    시가총액 상위 대형주 위주로 직접 작성한 정적(static) 목록이라 전체 상장사를
    커버하지는 못하지만, 검색/분석 기능 자체가 완전히 막히는 것은 막아준다.
    (요구사항: Provider Fallback 원칙 - 외부 실패 시에도 서비스는 계속 동작해야 함)
    """
    try:
        raw = json.loads(_FALLBACK_MASTER_LIST_PATH.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.exception("정적 fallback 종목 목록 로드 실패")
        return ProviderResult(status="error", message=str(exc), source_name="static_fallback")

    records = [
        CompanyMasterRecord(
            ticker=row["ticker"],
            company_name=row["company_name"],
            market=row.get("market"),
            sector=row.get("sector"),
            industry=row.get("industry"),
            market_cap=row.get("market_cap"),
        )
        for row in raw
    ]
    return ProviderResult(status="ok", data=records, source_name="static_fallback")


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
            logger.warning(
                "실 Provider(%s) 종목 목록 조회 실패(%s) - 정적 fallback 목록으로 대체합니다.",
                provider.name,
                result.message,
            )
            result = _load_fallback_master_list()
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


# --- 영문 회사명 (English / 日本語 화면용) ----------------------------------------------

# 이 단어들은 전부 대문자여도 약어가 아니라 일반 단어이므로 첫 글자만 대문자로 바꾼다.
_COMMON_WORDS = {"AND", "OF", "THE", "CO", "INC", "LTD", "CORP", "NEW", "ONE", "BIO", "CAR", "OIL", "GAS"}
_ENGLISH_NAME_RETRY_SECONDS = 10 * 60
_english_name_failed_at: float | None = None


def tidy_english_company_name(raw: str | None) -> str:
    """DART의 영문 회사명을 화면에 쓰기 좋게 정리한다.

    DART는 "SAMSUNG ELECTRONICS CO,.LTD"처럼 전부 대문자이거나 구두점이 어긋난 값을 주는 경우가
    많다. 전부 대문자인 이름만 단어별로 첫 글자만 대문자로 바꾸고, 3글자 이하 약어(SK, LG, KB 등)는
    그대로 둔다. 원래 대소문자가 섞인 이름(예: "NAVER Corporation")은 회사가 정한 표기라서 손대지 않는다.
    """
    name = re.sub(r"\s+", " ", (raw or "").strip())
    if not name:
        return ""
    name = re.sub(r"\s*CO\s*[,.]+\s*,?\s*LTD\.?$", " CO., LTD.", name, flags=re.IGNORECASE)
    if name != name.upper():
        return name

    def fix(word: str) -> str:
        letters = re.sub(r"[^A-Z]", "", word)
        if 0 < len(letters) <= 3 and letters not in _COMMON_WORDS:
            return word
        return word[:1] + word[1:].lower()

    return " ".join(fix(w) for w in name.split(" "))


def ensure_english_name(db: Session, company: Company) -> None:
    """영문 회사명이 없으면 OpenDART 기업개황에서 한 번 가져와 저장한다.

    - 이미 조회한 적이 있으면(빈 문자열 포함) 다시 부르지 않는다. 빈 문자열 = DART에 영문명이 없음.
    - DART_API_KEY가 없으면 아무것도 하지 않는다(나중에 키를 넣으면 그때 채워진다).
    - DART에 연결하지 못하면 10분 동안은 재시도하지 않아, 상세 페이지가 매번 기다리지 않게 한다.
    """
    global _english_name_failed_at
    if company.company_name_en is not None:
        return
    api_key = get_settings().dart_api_key
    if not api_key:
        return
    if _english_name_failed_at is not None and time.time() - _english_name_failed_at < _ENGLISH_NAME_RETRY_SECONDS:
        return

    payload = fetch_company_overview(company.ticker, api_key)
    if payload is None:
        _english_name_failed_at = time.time()
        return
    _english_name_failed_at = None
    company.company_name_en = tidy_english_company_name(payload.get("corp_name_eng"))
    db.add(company)
    db.commit()
