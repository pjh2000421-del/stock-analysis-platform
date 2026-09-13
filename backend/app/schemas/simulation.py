"""Persona Agent / 인공시장 시뮬레이션 스키마 (Phase6, 확장 구조).

요구사항 52: PAMS 등 실제 Agent-based Simulation 연동이 과도하게 큰 작업이면
Simulation Interface / Persona Schema / UI / Mock Adapter까지만 구현하고 TODO를 남긴다.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class PersonaDefinition(BaseModel):
    name: str  # 예: "Value Investor"
    risk_tolerance: float = Field(0.5, ge=0, le=1)
    investment_horizon: float = Field(0.5, ge=0, le=1)  # 0=단기, 1=장기
    news_dependency: float = Field(0.5, ge=0, le=1)
    social_dependency: float = Field(0.5, ge=0, le=1)
    trend_dependency: float = Field(0.5, ge=0, le=1)
    fundamental_dependency: float = Field(0.5, ge=0, le=1)


class PersonaMixConfig(BaseModel):
    """요구사항 51: Persona 구성비 (합계 100%)."""

    persona_weights: dict[str, float]  # {"Value": 0.3, "Momentum": 0.2, ...}


class MarketSimulationRequest(BaseModel):
    news_id: int
    personas: list[PersonaDefinition]
    persona_mix: PersonaMixConfig
    steps: int = 60


class MarketSimulationResult(BaseModel):
    price_path: list[float]
    volume_path: list[float]
    volatility_path: list[float]
    bubble_indicator: float | None = None
    herding_indicator: float | None = None
    is_mock: bool = True
    note: str = (
        "TODO: 실제 Agent-based Simulation(PAMS 등) 엔진과 연동 예정. "
        "현재는 Mock Adapter를 통해 인터페이스만 제공합니다."
    )
