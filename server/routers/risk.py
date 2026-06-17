from __future__ import annotations

from fastapi import APIRouter, HTTPException

from server.models.risk import (
    RiskEvaluationRequest,
    RiskEvaluationResult,
    RiskRule,
    RiskRuleDraft,
)
from server.services.risk_service import evaluate_risk, get_risk_rule_store

router = APIRouter(prefix="/api/risk", tags=["risk"])


@router.get("/rules", response_model=list[RiskRule])
def api_list_risk_rules():
    return get_risk_rule_store().list()


@router.post("/rules", response_model=RiskRule)
def api_create_risk_rule(draft: RiskRuleDraft):
    return get_risk_rule_store().save(draft)


@router.put("/rules/{rule_id}", response_model=RiskRule)
def api_update_risk_rule(rule_id: str, draft: RiskRuleDraft):
    if get_risk_rule_store().get(rule_id) is None:
        raise HTTPException(status_code=404, detail="risk rule not found")
    return get_risk_rule_store().save(draft, rule_id)


@router.delete("/rules/{rule_id}")
def api_delete_risk_rule(rule_id: str):
    if not get_risk_rule_store().delete(rule_id):
        raise HTTPException(status_code=404, detail="risk rule not found")
    return {"status": "deleted"}


@router.post("/evaluate", response_model=RiskEvaluationResult)
def api_evaluate_risk(req: RiskEvaluationRequest):
    try:
        return evaluate_risk(req)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
