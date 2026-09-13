"""Market Simulation Lab API (요구사항 50~52, 55) - Phase6."""
from __future__ import annotations

from fastapi import APIRouter

from app.schemas.simulation import MarketSimulationRequest, MarketSimulationResult
from app.services.simulation_service import run_mock_simulation

router = APIRouter(prefix="/simulation", tags=["simulation"])


@router.post("", response_model=MarketSimulationResult)
def run_simulation(request: MarketSimulationRequest):
    # TODO(Phase6): 실제 Agent-based Simulation(PAMS 등) 연동 전까지는 Mock Adapter 사용
    return run_mock_simulation(request)
