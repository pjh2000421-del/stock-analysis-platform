"""Persona Agent 정의 (요구사항 50, 51)."""
from __future__ import annotations

from dataclasses import dataclass

DEFAULT_PERSONAS: dict[str, dict] = {
    "Value Investor": {
        "risk_tolerance": 0.3,
        "investment_horizon": 0.9,
        "news_dependency": 0.3,
        "social_dependency": 0.1,
        "trend_dependency": 0.2,
        "fundamental_dependency": 0.9,
    },
    "Momentum Investor": {
        "risk_tolerance": 0.7,
        "investment_horizon": 0.2,
        "news_dependency": 0.6,
        "social_dependency": 0.4,
        "trend_dependency": 0.9,
        "fundamental_dependency": 0.2,
    },
    "Long-term Investor": {
        "risk_tolerance": 0.4,
        "investment_horizon": 1.0,
        "news_dependency": 0.2,
        "social_dependency": 0.1,
        "trend_dependency": 0.1,
        "fundamental_dependency": 0.8,
    },
    "Risk Averse Investor": {
        "risk_tolerance": 0.1,
        "investment_horizon": 0.7,
        "news_dependency": 0.4,
        "social_dependency": 0.2,
        "trend_dependency": 0.2,
        "fundamental_dependency": 0.6,
    },
    "News-driven Investor": {
        "risk_tolerance": 0.6,
        "investment_horizon": 0.3,
        "news_dependency": 0.9,
        "social_dependency": 0.3,
        "trend_dependency": 0.5,
        "fundamental_dependency": 0.3,
    },
    "SNS-driven Investor": {
        "risk_tolerance": 0.8,
        "investment_horizon": 0.1,
        "news_dependency": 0.5,
        "social_dependency": 0.9,
        "trend_dependency": 0.8,
        "fundamental_dependency": 0.1,
    },
}


@dataclass
class Persona:
    name: str
    risk_tolerance: float
    investment_horizon: float
    news_dependency: float
    social_dependency: float
    trend_dependency: float
    fundamental_dependency: float

    # TODO(Phase6): LLM 기반 뉴스 해석 - 동일 뉴스에 대해 Persona별 반응(매수/매도/관망)을
    # 생성하는 interpret_news(news_text: str) -> str 메서드를 LLM Provider와 연동하여 추가한다.
