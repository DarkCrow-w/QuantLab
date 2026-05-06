from __future__ import annotations

from fastapi import APIRouter, HTTPException

from server.models.screening import ScreenRequest, ScreenResult
from server.services.screening_service import run_screening

router = APIRouter(prefix="/api/screening", tags=["screening"])


@router.post("/scan", response_model=ScreenResult)
def api_scan(req: ScreenRequest):
    try:
        return run_screening(req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
