"""API 라우터 Aggregator (요구사항 55)."""
from fastapi import APIRouter

from app.api.routes import (
    analysis,
    backtest,
    companies,
    dcf,
    news,
    notifications,
    prediction,
    simulation,
    watchlist,
)

api_router = APIRouter()

api_router.include_router(companies.router)
api_router.include_router(prediction.router)
api_router.include_router(news.router)
api_router.include_router(analysis.router)
api_router.include_router(watchlist.router)
api_router.include_router(notifications.router)
api_router.include_router(dcf.router)
api_router.include_router(simulation.router)
api_router.include_router(backtest.router)
