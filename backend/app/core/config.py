"""
전역 설정 모듈.

모든 API Key와 환경 의존적인 값은 .env 파일에서 로드한다.
(요구사항 5, 65: API Key는 .env에서 관리, .env.example 제공)
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_name: str = "한국 주식 AI 분석 플랫폼"

    # DB
    database_url: str = "sqlite:///./stock_platform.db"

    # 주가 Provider
    krx_open_api_key: str | None = None
    korea_investment_app_key: str | None = None
    korea_investment_app_secret: str | None = None

    # 공시 (OpenDART)
    dart_api_key: str | None = None

    # 거시경제 CPI (한국은행 ECOS) - 물가조정(실질금액 환산, 요구사항 13)에 사용.
    # ecos.bok.or.kr 에서 발급. Provider 구현은 app/providers/macro_provider.py의
    # get_cpi() (ECOS StatisticSearch, 통계표코드 901Y009) 참고 - 라이브 검증 완료.
    ecos_api_key: str | None = None

    # 뉴스 (네이버) - 2026-07-31부로 신규 발급은 개발자센터가 아닌 NAVER API HUB
    # (ncloud.com, 네이버클라우드플랫폼)에서만 가능해졌다. 자세한 내용은
    # app/providers/news_provider.py 모듈 docstring 참고.
    naver_client_id: str | None = None
    naver_client_secret: str | None = None

    # 과거뉴스 (BIGKinds) - 선택적 Provider. 기본 뉴스 수집 파이프라인은 더 이상
    # BIGKinds에 의존하지 않으며(요구사항: Provider 다변화), 키가 있어도 기본 실행에서는
    # 호출하지 않는다. 향후 별도 기능에서 명시적으로만 사용한다.
    bigkinds_api_key: str | None = None

    # 뉴스 (NewsData.io) - 과거뉴스/보완 검색용 2차 Provider
    newsdata_api_key: str | None = None

    # 뉴스 (GNews) - 3차 optional fallback Provider (없으면 자동 skip)
    gnews_api_key: str | None = None

    # AI 질의응답 (Anthropic Claude API) - 종목 상세 페이지 우측 패널 (요구사항: AI QA)
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5"

    # 뉴스 모니터링
    news_polling_interval_seconds: int = 300

    # CORS
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
