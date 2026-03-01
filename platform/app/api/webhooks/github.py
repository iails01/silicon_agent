import hashlib
import hmac
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.services.trigger_service import TriggerService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/github", tags=["webhooks"])

# (X-GitHub-Event header, action field) → 标准化 event_type
# action 为 None 表示不依赖 action 字段
_GITHUB_EVENT_MAP: dict[tuple[str, str | None], str] = {
    ("pull_request", "opened"):      "pr_opened",
    ("pull_request", "reopened"):    "pr_reopened",
    ("pull_request", "closed"):      "pr_merged",   # merged=True 时视为 merged，否则 pr_closed
    ("pull_request", "synchronize"): "pr_synchronized",
    ("pull_request", "labeled"):     "pr_labeled",
    ("issues", "opened"):            "issue_opened",
    ("issues", "closed"):            "issue_closed",
    ("issues", "labeled"):           "issue_labeled",
    ("issues", "reopened"):          "issue_reopened",
    ("issue_comment", "created"):    "issue_comment_created",
    ("push", None):                  "push",
    ("pull_request_review", "submitted"): "pr_review_submitted",
    ("create", None):                "branch_created",
    ("delete", None):                "branch_deleted",
}


def _verify_signature(body: bytes, signature: str | None) -> bool:
    """验证 GitHub webhook HMAC-SHA256 签名（X-Hub-Signature-256 头）。"""
    if not settings.GITHUB_WEBHOOK_SECRET:
        return True  # 未配置 secret，跳过验证
    if not signature:
        return False
    expected = "sha256=" + hmac.new(
        settings.GITHUB_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _resolve_event_type(gh_event: str, body: dict) -> str:
    """将 GitHub 事件头 + action 解析为标准化 event_type。"""
    action = body.get("action")

    # pull_request closed + merged=True → pr_merged
    if gh_event == "pull_request" and action == "closed":
        pr = body.get("pull_request", {})
        if pr.get("merged"):
            return "pr_merged"
        return "pr_closed"

    key = (gh_event, action)
    if key in _GITHUB_EVENT_MAP:
        return _GITHUB_EVENT_MAP[key]

    # 无需 action 的事件（push / create / delete）
    key_no_action = (gh_event, None)
    if key_no_action in _GITHUB_EVENT_MAP:
        return _GITHUB_EVENT_MAP[key_no_action]

    # 兜底：原样返回
    return f"{gh_event}_{action}" if action else gh_event


def _normalize_github_payload(gh_event: str, event_type: str, body: dict) -> dict:
    """将 GitHub webhook payload 规范化为触发器统一格式。"""
    repo = body.get("repository") or {}
    sender = body.get("sender") or {}

    base: dict = {
        "event_type": event_type,
        "repo_name": repo.get("name", ""),
        "repo_full_name": repo.get("full_name", ""),
        "author": sender.get("login", ""),
    }

    # Pull Request 事件
    if gh_event == "pull_request":
        pr = body.get("pull_request") or {}
        labels = [lb.get("name", "") for lb in (pr.get("labels") or [])]
        base.update({
            "pr_number": pr.get("number", ""),
            "pr_title": pr.get("title", ""),
            "pr_url": pr.get("html_url", ""),
            "pr_author": (pr.get("user") or {}).get("login", ""),
            "branch": (pr.get("head") or {}).get("ref", ""),
            "base_branch": (pr.get("base") or {}).get("ref", ""),
            "labels": labels,
            "title": pr.get("title", ""),
        })

    # Push 事件
    elif gh_event == "push":
        ref = body.get("ref", "")
        push_branch = ref.replace("refs/heads/", "").replace("refs/tags/", "")
        base.update({
            "push_branch": push_branch,
            "branch": push_branch,
            "commit_count": len(body.get("commits") or []),
            "after": body.get("after", ""),
            "pusher": (body.get("pusher") or {}).get("name", ""),
            "title": f"push to {push_branch}",
        })

    # Issues 事件
    elif gh_event == "issues":
        issue = body.get("issue") or {}
        labels = [lb.get("name", "") for lb in (issue.get("labels") or [])]
        base.update({
            "issue_number": issue.get("number", ""),
            "issue_title": issue.get("title", ""),
            "issue_url": issue.get("html_url", ""),
            "issue_author": (issue.get("user") or {}).get("login", ""),
            "labels": labels,
            "title": issue.get("title", ""),
        })

    # Issue Comment 事件
    elif gh_event == "issue_comment":
        issue = body.get("issue") or {}
        comment = body.get("comment") or {}
        base.update({
            "issue_number": issue.get("number", ""),
            "issue_title": issue.get("title", ""),
            "comment_body": comment.get("body", "")[:200],
            "title": issue.get("title", ""),
        })

    # 保留原始 body 供模板使用（顶层字段）
    for k, v in body.items():
        if k not in base and not isinstance(v, (dict, list)):
            base[k] = v

    return base


@router.post("")
async def github_webhook(request: Request, session: AsyncSession = Depends(get_db)):
    body_bytes = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")

    if not _verify_signature(body_bytes, signature):
        logger.warning("GitHub webhook 签名验证失败")
        raise HTTPException(status_code=403, detail="Invalid webhook signature")

    import json
    body = json.loads(body_bytes)

    gh_event = request.headers.get("X-GitHub-Event", "unknown")
    event_type = _resolve_event_type(gh_event, body)
    repo_name = (body.get("repository") or {}).get("full_name", "unknown")

    logger.info("GitHub webhook received: event=%s type=%s repo=%s", gh_event, event_type, repo_name)

    payload = _normalize_github_payload(gh_event, event_type, body)
    service = TriggerService(session)
    task_id = await service.process_event("github", event_type, payload)

    return {
        "status": "received",
        "event": event_type,
        "repo": repo_name,
        "task_id": task_id,
    }
