"""뉴스 API 테스트 (요구사항 68: News API). Naver Provider는 monkeypatch로 대체한다."""
from datetime import datetime

from app.models.company import Company
from app.providers.base import ProviderResult, RawNewsItem


def _seed_company(db_session) -> Company:
    company = Company(ticker="000660", company_name="SK하이닉스", market="KOSPI", sector="반도체")
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    return company


def test_get_company_news_provider_unavailable(client, db_session, monkeypatch):
    company = _seed_company(db_session)

    def fake_search_news(self, query, display=30):
        return ProviderResult(status="unavailable", message="NAVER_CLIENT_ID 없음")

    from app.providers.news_provider import NaverNewsProvider

    monkeypatch.setattr(NaverNewsProvider, "search_news", fake_search_news)

    resp = client.get(f"/api/companies/{company.ticker}/news")
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider_status"]["naver_news"] == "unavailable"
    assert body["news"] == []


def test_get_company_news_success_computes_sentiment_and_event(client, db_session, monkeypatch):
    company = _seed_company(db_session)

    def fake_search_news(self, query, display=30):
        items = [
            RawNewsItem(
                title="SK하이닉스, HBM 대규모 공급계약 체결",
                url="https://example.com/news/1",
                source="테스트뉴스",
                published_at=datetime(2026, 9, 1, 9, 0),
                summary="SK하이닉스가 대형 고객사와 HBM 공급계약을 체결했다고 밝혔다.",
            )
        ]
        return ProviderResult(status="ok", data=items, source_name="naver_news")

    from app.providers.news_provider import NaverNewsProvider

    monkeypatch.setattr(NaverNewsProvider, "search_news", fake_search_news)

    resp = client.get(f"/api/companies/{company.ticker}/news")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["news"]) == 1
    assert body["news"][0]["event_type"] == "SUPPLY_CONTRACT"
