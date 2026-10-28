"""
다국어 표시용 코드, 영문 회사명, 시가총액 계산, WICS 조회 속도 개선 테스트.
외부 API는 호출하지 않는다.
"""
from datetime import date, timedelta

import app.providers.classification.wics_provider as wics
from app.models.company import Company
from app.models.financial import FinancialStatement
from app.models.price import DailyPrice
from app.services import company_service, financial_service
from app.services.company_service import tidy_english_company_name


def _seed_company(db_session, **kwargs) -> Company:
    values = {"ticker": "005930", "company_name": "삼성전자", "market": "KOSPI"}
    values.update(kwargs)
    company = Company(**values)
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    return company


# --- 영문 회사명 -------------------------------------------------------------------


def test_tidy_english_company_name_handles_dart_formats():
    assert tidy_english_company_name("SAMSUNG ELECTRONICS CO,.LTD") == "Samsung Electronics Co., Ltd."
    assert tidy_english_company_name("SK HYNIX INC.") == "SK Hynix Inc."
    assert tidy_english_company_name("KB FINANCIAL GROUP INC.") == "KB Financial Group Inc."
    # 회사가 직접 정한 대소문자 표기는 그대로 둔다.
    assert tidy_english_company_name("NAVER Corporation") == "NAVER Corporation"
    assert tidy_english_company_name(None) == ""


def test_ensure_english_name_saves_once(db_session, monkeypatch):
    company = _seed_company(db_session)
    calls = []

    def fake_overview(ticker, api_key, timeout=5.0):
        calls.append(ticker)
        return {"status": "000", "corp_name_eng": "SAMSUNG ELECTRONICS CO,.LTD"}

    monkeypatch.setattr(company_service, "fetch_company_overview", fake_overview)
    monkeypatch.setattr(company_service.get_settings(), "dart_api_key", "test-key", raising=False)
    monkeypatch.setattr(company_service, "_english_name_failed_at", None)

    company_service.ensure_english_name(db_session, company)
    company_service.ensure_english_name(db_session, company)

    assert company.company_name_en == "Samsung Electronics Co., Ltd."
    assert calls == ["005930"]  # 두 번째 호출은 DART를 다시 부르지 않는다


def test_ensure_english_name_skips_retries_after_failure(db_session, monkeypatch):
    company = _seed_company(db_session)
    calls = []

    def failing_overview(ticker, api_key, timeout=5.0):
        calls.append(ticker)
        return None

    monkeypatch.setattr(company_service, "fetch_company_overview", failing_overview)
    monkeypatch.setattr(company_service.get_settings(), "dart_api_key", "test-key", raising=False)
    monkeypatch.setattr(company_service, "_english_name_failed_at", None)

    company_service.ensure_english_name(db_session, company)
    company_service.ensure_english_name(db_session, company)

    assert company.company_name_en is None  # 실패하면 빈 값으로 확정하지 않고 나중에 다시 시도
    assert calls == ["005930"]  # 재시도 금지 시간 동안은 다시 부르지 않는다


# --- 시가총액 ------------------------------------------------------------------------


def test_refresh_market_cap_uses_latest_price_and_shares(db_session):
    company = _seed_company(db_session)
    db_session.add(DailyPrice(company_id=company.id, date=date.today() - timedelta(days=1), close=243500))
    db_session.add(FinancialStatement(company_id=company.id, period="2025FY", shares_outstanding=5_000_000_000))
    db_session.commit()

    assert financial_service.refresh_market_cap(db_session, company) == 243500 * 5_000_000_000
    assert company.market_cap == 243500 * 5_000_000_000


def test_refresh_market_cap_keeps_existing_value_without_inputs(db_session):
    company = _seed_company(db_session, market_cap=123.0)
    assert financial_service.refresh_market_cap(db_session, company) == 123.0


# --- Simple View 번역 코드 -------------------------------------------------------------


def test_simple_view_returns_translation_codes(client, db_session):
    _seed_company(db_session)
    resp = client.get("/api/companies/005930/simple-view")
    assert resp.status_code == 200
    body = resp.json()
    # 점수 데이터가 없는 테스트 DB에서는 '데이터 부족' 코드가 나와야 한다.
    assert body["price_level"]["code"] == "insufficient_data"
    assert body["price_level"]["detail_code"] == "price_level"
    assert body["news_sentiment_level"]["detail_code"] == "news_none"
    assert body["historical_similarity_level"]["code"] == "no_data"
    assert len(body["risk_factor_codes"]) == len(body["risk_factors"])


# --- WICS 조회 -----------------------------------------------------------------------


def _fake_wics(monkeypatch, data, down=False):
    calls = []

    def fake_fetch(self, sec_cd, dt):
        calls.append(sec_cd)
        if down:
            return None
        return [{"CMP_CD": code} for code in data.get(sec_cd, [])]

    monkeypatch.setattr(wics.WicsClassificationProvider, "_fetch_components", fake_fetch)
    monkeypatch.setattr(wics.time, "sleep", lambda seconds: None)
    return calls


def test_wics_stops_as_soon_as_ticker_is_found(monkeypatch):
    calls = _fake_wics(monkeypatch, {"G45": ["005930"], "G4530": ["005930"]})
    provider = wics.WicsClassificationProvider()

    result = provider.get_classification("005930")

    assert result.status == "ok"
    assert result.data.industry == "반도체와반도체장비"
    # 예전에는 대분류 10개 + 소분류 전부(15회 이상)를 받았다. 이제 IT 대분류와 그 소분류만 받는다.
    assert calls == ["G45", "G4530"]


def test_wics_fails_fast_and_backs_off_when_site_unreachable(monkeypatch):
    calls = _fake_wics(monkeypatch, {}, down=True)
    provider = wics.WicsClassificationProvider()

    assert provider.get_classification("005930").status == "unavailable"
    assert calls == ["G45"]  # 연결 실패 시 날짜를 거슬러 올라가며 재시도하지 않는다

    assert provider.get_classification("000660").status == "unavailable"
    assert calls == ["G45"]  # 재시도 금지 시간 동안은 요청 자체를 보내지 않는다
