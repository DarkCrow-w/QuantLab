from __future__ import annotations

from fastapi import APIRouter

from server.services.system_service import get_system_status

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/status")
def api_system_status():
    return get_system_status()
