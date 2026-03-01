from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trigger import TriggerEventModel, TriggerRuleModel
from app.schemas.task import TaskCreateRequest
from app.services.task_service import TaskService

logger = logging.getLogger(__name__)


class TriggerService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def process_event(
        self,
        source: str,
        event_type: str,
        payload: dict,
    ) -> Optional[str]:
        """处理外部事件，匹配规则并创建任务。

        Returns:
            创建的 task_id，或 None（未触发）。
        """
        # 查找匹配的启用规则
        result = await self.session.execute(
            select(TriggerRuleModel).where(
                TriggerRuleModel.source == source,
                TriggerRuleModel.enabled.is_(True),
            )
        )
        rules = result.scalars().all()

        # 过滤 event_type（支持通配符 "*"）
        matched_rules = [
            r for r in rules
            if r.event_type == "*" or r.event_type == event_type
        ]

        if not matched_rules:
            await self._log_event(source, event_type, payload, None, None, "skipped_no_rule")
            logger.info("触发器：无匹配规则 source=%s event=%s", source, event_type)
            return None

        for rule in matched_rules:
            # 1. 过滤器检查
            if not _passes_filters(rule.filters or {}, payload):
                await self._log_event(source, event_type, payload, rule.id, None, "skipped_filter")
                logger.info("触发器：过滤器未通过 rule=%s", rule.name)
                continue

            # 2. 去重检查
            dedup_key = _render_template(rule.dedup_key_template or "", payload) or None
            if dedup_key and await self._is_duplicate(rule, dedup_key):
                await self._log_event(source, event_type, payload, rule.id, dedup_key, "skipped_dedup")
                logger.info("触发器：去重跳过 rule=%s dedup_key=%s", rule.name, dedup_key)
                continue

            # 3. 创建任务
            title = _render_template(rule.title_template, payload)
            description = _render_template(rule.desc_template or "", payload) or None

            task_service = TaskService(self.session)
            task = await task_service.create_task(TaskCreateRequest(
                title=title,
                description=description,
                template_id=rule.template_id,
                project_id=rule.project_id,
            ))

            await self._log_event(source, event_type, payload, rule.id, dedup_key, "triggered", task.id)
            logger.info(
                "触发器：创建任务成功 rule=%s task_id=%s title=%s",
                rule.name, task.id, title,
            )
            return task.id

        return None

    async def _is_duplicate(self, rule: TriggerRuleModel, dedup_key: str) -> bool:
        """检查去重窗口内是否已有相同 dedup_key 的触发记录。"""
        try:
            window_hours = int(rule.dedup_window_hours)
        except (ValueError, TypeError):
            window_hours = 24
        cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)

        result = await self.session.execute(
            select(TriggerEventModel).where(
                TriggerEventModel.rule_id == rule.id,
                TriggerEventModel.dedup_key == dedup_key,
                TriggerEventModel.result == "triggered",
                TriggerEventModel.created_at >= cutoff,
            ).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def _log_event(
        self,
        source: str,
        event_type: str,
        payload: dict,
        rule_id: Optional[str],
        dedup_key: Optional[str],
        result: str,
        task_id: Optional[str] = None,
    ) -> None:
        event = TriggerEventModel(
            source=source,
            event_type=event_type,
            payload=payload,
            rule_id=rule_id,
            dedup_key=dedup_key,
            result=result,
            task_id=task_id,
        )
        self.session.add(event)
        await self.session.commit()

    # ── 规则 CRUD ────────────────────────────────────────────────────────────

    async def list_rules(self) -> list[TriggerRuleModel]:
        result = await self.session.execute(
            select(TriggerRuleModel).order_by(TriggerRuleModel.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_rule(self, rule_id: str) -> Optional[TriggerRuleModel]:
        return await self.session.get(TriggerRuleModel, rule_id)

    async def create_rule(self, data: dict) -> TriggerRuleModel:
        rule = TriggerRuleModel(**data)
        self.session.add(rule)
        await self.session.commit()
        await self.session.refresh(rule)
        return rule

    async def update_rule(self, rule_id: str, data: dict) -> Optional[TriggerRuleModel]:
        rule = await self.session.get(TriggerRuleModel, rule_id)
        if rule is None:
            return None
        for key, value in data.items():
            setattr(rule, key, value)
        await self.session.commit()
        await self.session.refresh(rule)
        return rule

    async def delete_rule(self, rule_id: str) -> bool:
        rule = await self.session.get(TriggerRuleModel, rule_id)
        if rule is None:
            return False
        await self.session.delete(rule)
        await self.session.commit()
        return True

    async def list_events(self, limit: int = 50) -> list[TriggerEventModel]:
        result = await self.session.execute(
            select(TriggerEventModel)
            .order_by(TriggerEventModel.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


# ── 工具函数 ──────────────────────────────────────────────────────────────────


class _SafeDict(dict):
    """format_map 安全字典：缺失的 key 原样保留 {key}。"""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _render_template(template: str, payload: dict) -> str:
    """将 payload 中的字段渲染到模板字符串。"""
    if not template:
        return ""
    flat = _flatten(payload)
    try:
        return template.format_map(_SafeDict(flat))
    except Exception:
        return template


def _flatten(d: dict, prefix: str = "") -> dict:
    """将嵌套 dict 展平为 dot-notation 键，同时保留顶层键。"""
    result: dict = {}
    for k, v in d.items():
        key = f"{prefix}{k}" if prefix else k
        result[key] = v
        if isinstance(v, dict):
            result.update(_flatten(v, f"{key}."))
    return result


def _passes_filters(filters: dict, payload: dict) -> bool:
    """
    支持的过滤规则：
    - labels: list[str]       payload 中至少包含一个指定标签
    - branch: str             分支精确匹配
    - title_contains: str     标题包含关键词（不区分大小写）
    - author_not: list[str]   排除指定作者
    """
    if not filters:
        return True

    flat = _flatten(payload)

    # labels 过滤：payload 中的 labels 列表需包含规则指定的至少一个标签
    if "labels" in filters:
        required_labels: list = filters["labels"]
        payload_labels: list = flat.get("labels") or flat.get("issue.fields.labels") or []
        if isinstance(payload_labels, list):
            # Jira labels 可能是 string list 或 object list
            payload_label_names = [
                lb if isinstance(lb, str) else lb.get("name", "") for lb in payload_labels
            ]
        else:
            payload_label_names = []
        if not any(lb in payload_label_names for lb in required_labels):
            return False

    # branch 过滤
    if "branch" in filters:
        branch = (
            flat.get("branch")
            or flat.get("object_attributes.target_branch")
            or flat.get("ref", "").replace("refs/heads/", "")
        )
        if branch != filters["branch"]:
            return False

    # title_contains 过滤
    if "title_contains" in filters:
        title = (
            flat.get("title")
            or flat.get("issue_title")
            or flat.get("object_attributes.title")
            or flat.get("issue.fields.summary", "")
        )
        if filters["title_contains"].lower() not in str(title).lower():
            return False

    # author_not 过滤
    if "author_not" in filters:
        author = (
            flat.get("author")
            or flat.get("user.username")
            or flat.get("object_attributes.author_id")
            or flat.get("issue.fields.reporter.name", "")
        )
        if str(author) in [str(a) for a in filters["author_not"]]:
            return False

    return True
