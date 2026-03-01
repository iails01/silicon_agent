from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_trigger_service
from app.schemas.trigger import (
    TriggerEventResponse,
    TriggerRuleCreate,
    TriggerRuleResponse,
    TriggerRuleUpdate,
)
from app.services.trigger_service import TriggerService

router = APIRouter(prefix="/triggers", tags=["triggers"])


@router.get("", response_model=List[TriggerRuleResponse])
async def list_rules(service: TriggerService = Depends(get_trigger_service)):
    rules = await service.list_rules()
    return [TriggerRuleResponse.model_validate(r) for r in rules]


@router.post("", response_model=TriggerRuleResponse, status_code=201)
async def create_rule(
    request: TriggerRuleCreate,
    service: TriggerService = Depends(get_trigger_service),
):
    data = request.model_dump()
    data["dedup_window_hours"] = str(data["dedup_window_hours"])
    rule = await service.create_rule(data)
    return TriggerRuleResponse.model_validate(rule)


@router.get("/events", response_model=List[TriggerEventResponse])
async def list_events(
    limit: int = 50,
    service: TriggerService = Depends(get_trigger_service),
):
    events = await service.list_events(limit=limit)
    return [TriggerEventResponse.model_validate(e) for e in events]


@router.get("/{rule_id}", response_model=TriggerRuleResponse)
async def get_rule(
    rule_id: str,
    service: TriggerService = Depends(get_trigger_service),
):
    rule = await service.get_rule(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="触发规则不存在")
    return TriggerRuleResponse.model_validate(rule)


@router.put("/{rule_id}", response_model=TriggerRuleResponse)
async def update_rule(
    rule_id: str,
    request: TriggerRuleUpdate,
    service: TriggerService = Depends(get_trigger_service),
):
    data = {k: v for k, v in request.model_dump().items() if v is not None}
    if "dedup_window_hours" in data:
        data["dedup_window_hours"] = str(data["dedup_window_hours"])
    rule = await service.update_rule(rule_id, data)
    if rule is None:
        raise HTTPException(status_code=404, detail="触发规则不存在")
    return TriggerRuleResponse.model_validate(rule)


@router.delete("/{rule_id}", status_code=204)
async def delete_rule(
    rule_id: str,
    service: TriggerService = Depends(get_trigger_service),
):
    deleted = await service.delete_rule(rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="触发规则不存在")
