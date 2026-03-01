import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.services.trigger_service import TriggerService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/jira", tags=["webhooks"])

# Jira webhookEvent → 标准化 event_type 映射
_JIRA_EVENT_MAP = {
    "jira:issue_created": "issue_created",
    "jira:issue_updated": "issue_updated",
    "jira:issue_deleted": "issue_deleted",
    "comment_created": "comment_created",
    "comment_updated": "comment_updated",
}


def _verify_jira_signature(body: bytes, signature: str | None) -> bool:
    """Verify Jira webhook HMAC-SHA256 signature if secret is configured."""
    if not settings.JIRA_WEBHOOK_SECRET:
        return True  # no secret configured, skip verification
    if not signature:
        return False
    expected = hmac.new(
        settings.JIRA_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _normalize_jira_payload(data: dict) -> dict:
    """将 Jira webhook payload 规范化为触发器可用的扁平结构。"""
    issue = data.get("issue", {})
    fields = issue.get("fields", {})
    labels_raw = fields.get("labels", [])
    # Jira labels 可能是字符串列表或对象列表
    labels = [lb if isinstance(lb, str) else lb.get("name", "") for lb in labels_raw]

    return {
        "issue_key": issue.get("key", ""),
        "issue_title": fields.get("summary", ""),
        "issue_type": (fields.get("issuetype") or {}).get("name", ""),
        "issue_status": (fields.get("status") or {}).get("name", ""),
        "project_key": (fields.get("project") or {}).get("key", ""),
        "labels": labels,
        "author": (fields.get("reporter") or {}).get("name", ""),
        "event_type": _JIRA_EVENT_MAP.get(data.get("webhookEvent", ""), data.get("webhookEvent", "")),
        # 保留原始数据供模板使用
        **data,
    }


@router.post("")
async def jira_webhook(request: Request, session: AsyncSession = Depends(get_db)):
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature")

    if not _verify_jira_signature(body, signature):
        logger.warning("Jira webhook signature verification failed")
        raise HTTPException(status_code=403, detail="Invalid webhook signature")

    data = json.loads(body)
    raw_event = data.get("webhookEvent", "unknown")
    event_type = _JIRA_EVENT_MAP.get(raw_event, raw_event)
    issue_key = data.get("issue", {}).get("key", "unknown")

    logger.info("Jira webhook received: event=%s, issue=%s", raw_event, issue_key)

    payload = _normalize_jira_payload(data)
    service = TriggerService(session)
    task_id = await service.process_event("jira", event_type, payload)

    return {
        "status": "received",
        "event": event_type,
        "issue": issue_key,
        "task_id": task_id,
    }
