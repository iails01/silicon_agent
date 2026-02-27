"""Skill feedback aggregation and effectiveness query service."""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill_feedback import SkillFeedbackModel
from app.models.task_log import TaskStageLogModel

logger = logging.getLogger(__name__)


async def aggregate_skill_metrics(session: AsyncSession, task_id: str) -> List[dict]:
    """Aggregate skill invocation data from task_stage_logs after task completion.

    Queries logs where command LIKE 'skill:%', groups by skill_name,
    and writes aggregated SkillFeedbackModel records.
    """
    # Query skill-related logs for this task
    result = await session.execute(
        select(TaskStageLogModel).where(
            TaskStageLogModel.task_id == task_id,
            TaskStageLogModel.command.like("skill:%"),
        )
    )
    logs = result.scalars().all()
    if not logs:
        return []

    # Group by skill name
    skill_groups: Dict[str, list] = {}
    for log in logs:
        # command format: "skill:{name}"
        skill_name = log.command.split(":", 1)[1] if ":" in log.command else log.command
        skill_groups.setdefault(skill_name, []).append(log)

    records = []
    for skill_name, group_logs in skill_groups.items():
        success_count = sum(1 for lg in group_logs if lg.status == "success")
        fail_count = sum(1 for lg in group_logs if lg.status != "success")
        total_duration = sum(lg.duration_ms or 0.0 for lg in group_logs)
        avg_duration = total_duration / len(group_logs) if group_logs else 0.0

        # Use the first log's stage_name and agent_role as representative
        first_log = group_logs[0]
        feedback_type = "success" if fail_count == 0 else "failure"

        record = SkillFeedbackModel(
            skill_name=skill_name,
            task_id=task_id,
            stage_name=first_log.stage_name,
            agent_role=first_log.agent_role or "unknown",
            feedback_type=feedback_type,
            content=f"invocations={len(group_logs)}, success={success_count}, fail={fail_count}",
            tokens_used=0,
            duration_ms=avg_duration,
        )
        session.add(record)
        records.append({
            "skill_name": skill_name,
            "invocations": len(group_logs),
            "success_count": success_count,
            "fail_count": fail_count,
            "avg_duration_ms": round(avg_duration, 2),
        })

    await session.commit()
    logger.info(
        "Aggregated skill metrics for task %s: %d skills", task_id, len(records)
    )
    return records


async def get_skill_effectiveness(
    session: AsyncSession, skill_name: Optional[str] = None
) -> List[dict]:
    """Query skill effectiveness statistics from aggregated feedback records.

    Returns per-skill: invocations, success_rate, avg_duration, avg_tokens.
    """
    query = select(
        SkillFeedbackModel.skill_name,
        func.count(SkillFeedbackModel.id).label("invocations"),
        func.sum(
            case(
                (SkillFeedbackModel.feedback_type == "success", 1),
                else_=0,
            )
        ).label("success_count"),
        func.sum(
            case(
                (SkillFeedbackModel.feedback_type == "failure", 1),
                else_=0,
            )
        ).label("failure_count"),
        func.sum(
            case(
                (SkillFeedbackModel.feedback_type == "gate_reject", 1),
                else_=0,
            )
        ).label("gate_reject_count"),
        func.avg(SkillFeedbackModel.duration_ms).label("avg_duration_ms"),
        func.avg(SkillFeedbackModel.tokens_used).label("avg_tokens"),
    ).group_by(SkillFeedbackModel.skill_name)

    if skill_name:
        query = query.where(SkillFeedbackModel.skill_name == skill_name)

    result = await session.execute(query)
    rows = result.all()

    items = []
    for row in rows:
        invocations = row.invocations or 0
        success_count = row.success_count or 0
        failure_count = row.failure_count or 0
        gate_reject_count = row.gate_reject_count or 0
        success_rate = success_count / invocations if invocations > 0 else 0.0
        items.append({
            "skill_name": row.skill_name,
            "invocations": invocations,
            "success_count": success_count,
            "failure_count": failure_count,
            "gate_reject_count": gate_reject_count,
            "success_rate": round(success_rate, 4),
            "avg_duration_ms": round(row.avg_duration_ms or 0.0, 2),
            "avg_tokens": round(row.avg_tokens or 0.0, 2),
        })

    return items
