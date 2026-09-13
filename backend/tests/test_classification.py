"""
투자용 업종 분류(Investment Industry Classification) 테스트.

배경: 기존에는 Company.industry(KRX 상장법인목록의 KSIC 기반 원본 값, 예: 삼성전자의
"방송장비 및 전자기기")를 그대로 화면/Peer Comparison에 사용해, 투자분석 관점에서
부적절한 업종으로 기업이 묶이는 문제가 있었다. 이를 해결하기 위해 WICS -> FICS ->
KRX 원본 -> DART 사업내용 -> Unknown 순으로 fallback하는 Classification Provider
체인(app/providers/classification/)을 도입했고, raw_industry(원본 보존)와
investment_industry(투자분석용, 화면/Peer Comparison에서 실제로 사용)를 분리했다.

외부 WICS/FICS/DART API는 이 테스트에서 실제 네트워크를 호출하지 않고 monkeypatch로
대체해 결정적으로 검증한다(다른 API 테스트들과 동일한 컨벤션, test_companies_api.py 참고).
wiseindex.com(WICS) 실제 연동 자체는 개발 중 라이브 브라우저 세션으로 직접 확인했으며
(삼성전자/SK하이닉스/현대차/KB금융/NAVER/셀트리온 6종목 모두 실제 API 응답 기준으로
올바르게 분류됨), 그 결과는 별도 완료 보고서에 요약되어 있다.

주의: 이 파일은 fastapi/sqlalchemy 등 requirements.txt 의존성이 설치된 환경에서
실행해야 한다(conftest.py의 기존 안내와 동일).
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.models.company import Company
from app.providers.base import ClassificationRecord, ProviderResult
from app.providers.classification.classifier import classify_company
from app.providers.classification.dart_classification_provider import DartClassificationProvider
from app.providers.classification.fics_provider import FicsClassificationProvider
from app.providers.classification.wics_provider import WicsClassificationProvider
from app.services.classification_service import ensure_classification
from app.services.peer_service import _find_peer_companies


def _seed(db_session, **kwargs) -> Company:
    defaults = {"market": "KOSPI"}
    defaults.update(kwargs)
    company = Company(**defaults)
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    return company


# --- 1. Classification Provider fallback 체인 테스트 -------------------------------


def test_classify_company_falls_back_to_raw_industry_when_wics_unavailable(monkeypatch):
    """WICS/FICS가 모두 실패하면, raw_industry를 낮은 신뢰도(KRX_RAW)로만 사용해야 한다."""
    monkeypatch.setattr(
        WicsClassificationProvider,
        "get_classification",
        lambda self, ticker: ProviderResult(status="empty", source_name=self.name, message="구성종목 목록에 없음"),
    )

    outcome = classify_company("005930", raw_industry="통신 및 방송 장비 제조업")

    assert outcome.system == "KRX_RAW"
    assert outcome.industry == "통신 및 방송 장비 제조업"
    assert outcome.confidence < 0.5
    # 실패 사유가 source에 남아야 나중에 원인 추적이 가능하다 (분류 출처 투명성 요구사항).
    assert "wics_wiseindex" in outcome.source
    assert "fics" in outcome.source


def test_classify_company_prefers_wics_when_available(monkeypatch):
    record = ClassificationRecord(sector="IT", industry="반도체와반도체장비", system="WICS", confidence=0.95)
    monkeypatch.setattr(
        WicsClassificationProvider,
        "get_classification",
        lambda self, ticker: ProviderResult(status="ok", data=record, source_name=self.name),
    )

    outcome = classify_company("005930", raw_industry="통신 및 방송 장비 제조업")

    assert outcome.system == "WICS"
    assert outcome.sector == "IT"
    assert outcome.industry == "반도체와반도체장비"
    assert outcome.confidence == 0.95


def test_classify_company_returns_unknown_without_fabricating_data(monkeypatch):
    """WICS/FICS/DART가 모두 실패하고 raw_industry조차 없으면, 값을 지어내지 않고 Unknown이어야 한다."""
    monkeypatch.setattr(
        WicsClassificationProvider,
        "get_classification",
        lambda self, ticker: ProviderResult(status="unavailable", source_name=self.name, message="네트워크 실패"),
    )
    monkeypatch.setattr(
        DartClassificationProvider,
        "get_classification",
        lambda self, ticker: ProviderResult(status="unavailable", source_name=self.name, message="DART_API_KEY 없음"),
    )

    outcome = classify_company("999999", raw_industry=None)

    assert outcome.system == "UNKNOWN"
    assert outcome.industry is None
    assert outcome.sector is None
    assert outcome.confidence == 0.0


# --- 2. raw_industry / investment_industry 분리 저장 테스트 -------------------------


def test_ensure_classification_preserves_raw_industry_separately(db_session, monkeypatch):
    company = _seed(db_session, ticker="005930", company_name="삼성전자", industry="통신 및 방송 장비 제조업")

    record = ClassificationRecord(sector="IT", industry="반도체와반도체장비", system="WICS", confidence=0.95)
    monkeypatch.setattr(
        WicsClassificationProvider,
        "get_classification",
        lambda self, ticker: ProviderResult(status="ok", data=record, source_name=self.name),
    )

    ensure_classification(db_session, company)

    assert company.raw_industry == "통신 및 방송 장비 제조업"  # 기존 값 보존(삭제되지 않음)
    assert company.investment_industry == "반도체와반도체장비"  # 신규 필드에 별도 저장
    assert company.raw_industry != company.investment_industry
    assert company.classification_system == "WICS"


# --- 3~6. 검증 대상 기업(삼성전자/SK하이닉스/현대차/KB금융) 분류 테스트 -----------------


@pytest.mark.parametrize(
    "ticker,name,raw_industry,sector,industry",
    [
        ("005930", "삼성전자", "통신 및 방송 장비 제조업", "IT", "반도체와반도체장비"),
        ("000660", "SK하이닉스", "반도체 제조업", "IT", "반도체와반도체장비"),
        ("005380", "현대차", "자동차용 엔진 및 자동차 제조업", "경기관련소비재", "자동차와부품"),
        ("105560", "KB금융", "기타 금융업", "금융", "은행"),
    ],
)
def test_wics_classification_for_key_companies(db_session, monkeypatch, ticker, name, raw_industry, sector, industry):
    company = _seed(db_session, ticker=ticker, company_name=name, industry=raw_industry)

    record = ClassificationRecord(sector=sector, industry=industry, system="WICS", confidence=0.95)
    monkeypatch.setattr(
        WicsClassificationProvider,
        "get_classification",
        lambda self, t, _record=record: ProviderResult(status="ok", data=_record, source_name=self.name),
    )

    ensure_classification(db_session, company)

    assert company.classification_system == "WICS"
    assert company.investment_sector == sector
    assert company.investment_industry == industry
    assert company.raw_industry == raw_industry  # 원본은 그대로 보존


def test_samsung_and_sk_hynix_share_investment_industry_despite_different_raw_industry(db_session, monkeypatch):
    """삼성전자/SK하이닉스는 raw_industry(KSIC)는 다르지만, investment_industry(WICS)로는
    같은 반도체 업종으로 묶여야 한다 - 이번 수정의 핵심 목표."""
    samsung = _seed(db_session, ticker="005930", company_name="삼성전자", industry="통신 및 방송 장비 제조업")
    hynix = _seed(db_session, ticker="000660", company_name="SK하이닉스", industry="반도체 제조업")

    def fake_get(self, ticker):
        mapping = {
            "005930": ClassificationRecord(sector="IT", industry="반도체와반도체장비", system="WICS", confidence=0.95),
            "000660": ClassificationRecord(sector="IT", industry="반도체와반도체장비", system="WICS", confidence=0.95),
        }
        return ProviderResult(status="ok", data=mapping[ticker], source_name=self.name)

    monkeypatch.setattr(WicsClassificationProvider, "get_classification", fake_get)

    ensure_classification(db_session, samsung)
    ensure_classification(db_session, hynix)

    assert samsung.raw_industry != hynix.raw_industry
    assert samsung.investment_industry == hynix.investment_industry == "반도체와반도체장비"


# --- 7. investment_industry 기반 Peer 탐색 테스트 -----------------------------------


def test_find_peer_companies_matches_by_investment_industry_not_raw_industry(db_session):
    """예전 로직(raw_industry/KSIC 매칭)이었다면 묶였을 '가짜 동종업체'가 investment_industry
    기준으로는 제외되고, raw_industry는 달라도 investment_industry가 같은 '진짜 동종업체'만
    Peer로 포함되어야 한다."""
    target = _seed(
        db_session,
        ticker="005930",
        company_name="삼성전자",
        industry="통신 및 방송 장비 제조업",
        raw_industry="통신 및 방송 장비 제조업",
        investment_industry="반도체와반도체장비",
        market_cap=5_000_000_000_000_00.0,
    )
    real_peer = _seed(
        db_session,
        ticker="000660",
        company_name="SK하이닉스",
        industry="반도체 제조업",
        raw_industry="반도체 제조업",
        investment_industry="반도체와반도체장비",
        market_cap=3_000_000_000_000_00.0,
    )
    # raw_industry(KSIC)는 target과 완전히 동일하지만 investment_industry는 다르다.
    fake_peer = _seed(
        db_session,
        ticker="999001",
        company_name="가짜동종업체",
        industry="통신 및 방송 장비 제조업",
        raw_industry="통신 및 방송 장비 제조업",
        investment_industry="통신서비스",
        classification_updated_at=datetime.utcnow(),  # 이미 최신 분류 - 재계산 없이 그대로 판정에 사용됨
        market_cap=1_000_000_000_000_00.0,
    )

    peers = _find_peer_companies(db_session, target)
    peer_tickers = {p.ticker for p in peers}

    assert real_peer.ticker in peer_tickers
    assert fake_peer.ticker not in peer_tickers


# --- 8. 기존 DB 데이터 재분류(refresh_company_classifications.py와 동일 경로) 테스트 -----


def test_ensure_classification_force_refresh_overwrites_stale_data(db_session, monkeypatch):
    """구버전 로직이 저장해둔 잘못된 investment_industry(raw_industry와 동일한 값)를
    refresh_company_classifications.py --force 와 동일한 경로(force=True)로 재분류하면
    올바른 WICS 값으로 덮어써야 한다."""
    company = _seed(
        db_session,
        ticker="005930",
        company_name="삼성전자",
        industry="통신 및 방송 장비 제조업",
        investment_industry="통신 및 방송 장비 제조업",  # 구버전 버그로 raw와 동일하게 저장된 값
        classification_system="KRX_RAW",
        classification_updated_at=datetime.utcnow() - timedelta(days=1),  # 아직 30일 이내
    )

    record = ClassificationRecord(sector="IT", industry="반도체와반도체장비", system="WICS", confidence=0.95)
    monkeypatch.setattr(
        WicsClassificationProvider,
        "get_classification",
        lambda self, ticker: ProviderResult(status="ok", data=record, source_name=self.name),
    )

    # force=False면 아직 최신(30일 이내)이라고 판단해 재분류하지 않아야 한다.
    ensure_classification(db_session, company, force=False)
    assert company.investment_industry == "통신 및 방송 장비 제조업"

    # refresh_company_classifications.py --force 와 동일한 경로.
    ensure_classification(db_session, company, force=True)
    assert company.investment_industry == "반도체와반도체장비"
    assert company.classification_system == "WICS"


# --- 9. Provider가 완전히 죽어도 기업 상세 페이지 자체는 죽지 않아야 한다 ----------------


def test_company_detail_endpoint_survives_classification_provider_crash(client, db_session, monkeypatch):
    _seed(db_session, ticker="005930", company_name="삼성전자", industry="통신 및 방송 장비 제조업")

    def boom(self, ticker):
        raise RuntimeError("wiseindex.com 연결 실패 시뮬레이션")

    monkeypatch.setattr(WicsClassificationProvider, "get_classification", boom)
    monkeypatch.setattr(FicsClassificationProvider, "get_classification", boom)

    # 이 테스트의 목적은 분류 Provider 장애 상황만 검증하는 것이므로, 시세 Provider는
    # 실제 네트워크를 타지 않도록 명시적으로 unavailable 처리한다(test_companies_api.py와
    # 동일한 monkeypatch 컨벤션).
    from app.providers.stock_provider import FinanceDataReaderStockProvider

    monkeypatch.setattr(
        FinanceDataReaderStockProvider,
        "get_price_history",
        lambda self, ticker, start, end: ProviderResult(status="unavailable", source_name=self.name),
    )

    resp = client.get("/api/companies/005930")

    assert resp.status_code == 200
    body = resp.json()
    assert body["ticker"] == "005930"
    # 분류 자체는 실패했지만(=classification이 null), raw_classification은 정상적으로 내려가야 한다.
    assert body["classification"] is None
    assert body["raw_classification"]["industry"] == "통신 및 방송 장비 제조업"
