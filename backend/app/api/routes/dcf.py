"""DCF 계산기 최상위 API (요구사항 55: /api/dcf)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.errors import NotFoundError
from app.schemas.dcf import DCFRequest, DCFResult
from app.services import company_service
from app.services.dcf_service import calculate_dcf

router = APIRouter(prefix="/dcf", tags=["dcf"])


@router.post("", response_model=DCFResult)
def calculate(request: DCFRequest, db: Session = Depends(get_db)):
    try:
        company = company_service.get_company_by_ticker(db, request.ticker)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return calculate_dcf(db, company, request.assumptions)
