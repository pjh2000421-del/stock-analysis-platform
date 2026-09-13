"""
Persona Agent / Market Simulation Lab Service (요구사항 50~52) - Phase6.

실제 엔진 연동은 app/simulation/market_simulation.py 의 MarketSimulationEngine을
교체하는 것으로 처리하며, 이 Service는 Schema <-> 엔진 사이의 변환만 담당한다.
"""
from __future__ import annotations

from app.schemas.simulation import MarketSimulationRequest, MarketSimulationResult
from app.simulation.market_simulation import get_simulation_engine


def run_mock_simulation(request: MarketSimulationRequest) -> MarketSimulationResult:
    engine = get_simulation_engine()
    output = engine.run(
        news_id=request.news_id,
        persona_weights=request.persona_mix.persona_weights,
        steps=request.steps,
    )
    return MarketSimulationResult(
        price_path=output.price_path,
        volume_path=output.volume_path,
        volatility_path=output.volatility_path,
        bubble_indicator=output.bubble_indicator,
        herding_indicator=output.herding_indicator,
        is_mock=True,
    )
