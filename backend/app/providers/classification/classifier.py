"""
투자용 산업분류 Fallback 오케스트레이터 (요구사항 6).

우선순위:
    1. WICS (wiseindex.com)
    2. FICS (TODO - 무료 데이터소스 미확인, 항상 unavailable)
    3. (신뢰 가능한 금융 데이터 Provider의 투자용 Industry - 현재는 WICS Provider가
       사실상 이 역할을 겸한다. 별도로 확보된 추가 Provider는 없다)
    4. KRX 원본(raw_industry) - Company.raw_industry(옛 Company.industry, KSIC 기반)를
       아주 낮은 신뢰도의 최후 보조 수단으로만 사용한다.
    5. DART 사업내용 기반 보조 분류
    6. Unknown - 위 모든 단계가 실패하면 값을 임의로 만들어내지 않고 비워둔다.

각 단계는 ProviderResult.status가 "ok"가 아니면 다음 단계로 넘어간다.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.providers.base import ClassificationRecord
from app.providers.classification.dart_classification_provider import get_dart_classification_provider
from app.providers.classification.fics_provider import get_fics_provider
from app.providers.classification.wics_provider import get_wics_provider


@dataclass
class ClassificationOutcome:
    sector: str | None
    industry: str | None
    sub_industry: str | None
    system: str
    source: str
    confidence: float
    updated_at: datetime


def _from_record(rec: ClassificationRecord, source: str, now: datetime) -> ClassificationOutcome:
    return ClassificationOutcome(
        sector=rec.sector,
        industry=rec.industry,
        sub_industry=rec.sub_industry,
        system=rec.system,
        source=source,
        confidence=rec.confidence,
        updated_at=now,
    )


def classify_company(ticker: str, raw_industry: str | None) -> ClassificationOutcome:
    now = datetime.utcnow()

    # 1. WICS, 2. FICS
    fallback_reasons: list[str] = []
    for provider in (get_wics_provider(), get_fics_provider()):
        result = provider.get_classification(ticker)
        if result.status == "ok" and isinstance(result.data, ClassificationRecord):
            return _from_record(result.data, result.source_name or provider.name, now)
        if result.message:
            fallback_reasons.append(f"{provider.name}: {result.message}")

    # 4. KRX 원본(raw_industry) - WICS/FICS가 모두 실패했을 때만, 낮은 신뢰도로 사용.
    # 실패 사유를 source에 남겨 디버깅(요구사항 15: 분류 출처 표시)에 활용한다.
    reason_suffix = f" [{' / '.join(fallback_reasons)}]" if fallback_reasons else ""
    if raw_industry:
        return ClassificationOutcome(
            sector=None,
            industry=raw_industry,
            sub_industry=None,
            system="KRX_RAW",
            source=(
                "finance_datareader(KRX 상장법인목록, KSIC 기반 - 투자분석용 아님, 최후 보조 수단)"
                + reason_suffix
            ),
            confidence=0.2,
            updated_at=now,
        )

    # 5. DART 사업내용 기반 보조 분류 (raw_industry조차 없는 극소수 케이스)
    dart_result = get_dart_classification_provider().get_classification(ticker)
    if dart_result.status == "ok" and isinstance(dart_result.data, ClassificationRecord):
        return _from_record(dart_result.data, dart_result.source_name or "dart_business_desc", now)

    # 6. Unknown
    return ClassificationOutcome(
        sector=None,
        industry=None,
        sub_industry=None,
        system="UNKNOWN",
        source="none",
        confidence=0.0,
        updated_at=now,
    )
