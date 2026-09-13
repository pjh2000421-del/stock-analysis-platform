"""
인공시장 시뮬레이션 엔진 인터페이스 (요구사항 52).

MarketSimulationEngine 인터페이스를 두어, 향후 PAMS(Agent-based Simulation) 등
실제 엔진으로 교체 가능하게 한다. 현재는 MockMarketSimulationEngine만 제공한다.

TODO(Phase6): PAMS(https://github.com/pams-project) 또는 자체 ABM 엔진 연동.
    - Persona -> Agent 초기화 로직
    - 뉴스 Shock을 Agent 의사결정에 반영하는 Market Environment 구현
    - Order Book / 가격 형성 메커니즘
"""
from __future__ import annotations

import math
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SimulationOutput:
    price_path: list[float]
    volume_path: list[float]
    volatility_path: list[float]
    bubble_indicator: float | None
    herding_indicator: float | None


class MarketSimulationEngine(ABC):
    @abstractmethod
    def run(self, news_id: int, persona_weights: dict[str, float], steps: int) -> SimulationOutput:
        ...


class MockMarketSimulationEngine(MarketSimulationEngine):
    """
    실제 Agent 상호작용 없이, Persona 구성비로부터 단순화된 drift/변동성 파라미터를 만들어
    Geometric Brownian Motion 형태로 가격 경로를 생성하는 Mock 구현체.
    """

    def run(self, news_id: int, persona_weights: dict[str, float], steps: int) -> SimulationOutput:
        total_weight = sum(persona_weights.values()) or 1.0
        momentum_weight = persona_weights.get("Momentum", persona_weights.get("Momentum Investor", 0.0)) / total_weight
        risk_averse_weight = (
            persona_weights.get("Risk Averse", persona_weights.get("Risk Averse Investor", 0.0)) / total_weight
        )

        drift = momentum_weight * 0.002 - risk_averse_weight * 0.001
        vol = 0.01 + risk_averse_weight * 0.01

        rng = random.Random(news_id)
        price = 100.0
        price_path, volume_path, volatility_path = [], [], []

        for _ in range(steps):
            shock = rng.gauss(0, vol)
            price *= math.exp(drift + shock)
            price_path.append(round(price, 2))
            volume_path.append(round(abs(rng.gauss(1000, 300)), 0))
            volatility_path.append(round(abs(shock), 4))

        bubble_indicator = round(max(0.0, (price / 100.0 - 1) - 0.2), 3)
        herding_indicator = round(momentum_weight, 3)

        return SimulationOutput(
            price_path=price_path,
            volume_path=volume_path,
            volatility_path=volatility_path,
            bubble_indicator=bubble_indicator,
            herding_indicator=herding_indicator,
        )


def get_simulation_engine() -> MarketSimulationEngine:
    # TODO(Phase6): 설정에 따라 실제 엔진(PAMS 등)으로 교체
    return MockMarketSimulationEngine()
