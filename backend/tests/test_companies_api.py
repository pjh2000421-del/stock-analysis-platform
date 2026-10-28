"""
기업 검색 / 기업 상세 API 테스트 (요구사항 68).
외부 Provider는 monkeypatch로 대체하여 네트워크 없이 검증한다.
"""
from datetime import date, timedelta

from app.models.company import Company
from app.providers.base import PriceBar, ProviderResult


def _seed_company(db_session) -> Company:
    company = Company(ticker="005930", company_name="삼성전자", market="KOSPI", sector="반도체")
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    return company


def test_search_companies_returns_db_match(client, db_session):
    _seed_company(db_session)
    resp = client.get("/api/companies/search", params={"q": "삼성전자"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["results"][0]["ticker"] == "005930"


def test_get_company_detail_not_found(client, db_session):
    resp = client.get("/api/companies/999999")
    assert resp.status_code == 404


def test_get_company_detail_success(client, db_session, monkeypatch):
    _seed_company(db_session)

    # 기업 상세의 현재가는 외부 현재가 API가 아니라 DB에 캐시된 최근 일봉 2개로 계산한다
    # (price_service.get_latest_quote). 그래서 일봉 조회를 대체한다.
    def fake_get_price_history(self, ticker, start, end):
        today = date.today()
        bars = [
            PriceBar(date=today - timedelta(days=2), open=71000, high=71500, low=70800, close=71200, volume=900000),
            PriceBar(date=today - timedelta(days=1), open=71300, high=72500, low=71100, close=72300, volume=1000000),
        ]
        return ProviderResult(status="ok", data=[b for b in bars if start <= b.date <= end])

    from app.providers.stock_provider import FinanceDataReaderStockProvider

    monkeypatch.setattr(FinanceDataReaderStockProvider, "get_price_history", fake_get_price_history)

    resp = client.get("/api/companies/005930")
    assert resp.status_code == 200
    body = resp.json()
    assert body["company_name"] == "삼성전자"
    assert body["current_price"] == 72300


def test_get_company_prices(client, db_session, monkeypatch):
    company = _seed_company(db_session)

    def fake_get_price_history(self, ticker, start, end):
        # 고정 날짜를 쓰면 시간이 지나 "최근 1개월" 범위를 벗어나 실패하므로 오늘 기준 날짜를 쓴다.
        bars = [PriceBar(date=date.today() - timedelta(days=3), open=70000, high=71000, low=69500, close=70500, volume=100000)]
        return ProviderResult(status="ok", data=bars)

    from app.providers.stock_provider import FinanceDataReaderStockProvider

    monkeypatch.setattr(FinanceDataReaderStockProvider, "get_price_history", fake_get_price_history)

    resp = client.get(f"/api/companies/{company.ticker}/prices", params={"period": "1M"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["prices"]) >= 1
    assert body["prices"][0]["close"] == 70500
