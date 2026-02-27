"""Tests for skill feedback aggregation and effectiveness API."""
import pytest
import pytest_asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.session import async_session_factory
from app.models.skill_feedback import SkillFeedbackModel
from app.models.task import TaskModel
from app.models.task_log import TaskStageLogModel


@pytest_asyncio.fixture
async def seed_skill_logs():
    """Seed a task with task_stage_logs containing skill invocations."""
    now = datetime.now(timezone.utc)
    async with async_session_factory() as session:
        task = TaskModel(
            id="sf-task-1",
            title="Skill Feedback Test Task",
            status="completed",
            total_tokens=5000,
            total_cost_rmb=0.05,
            created_at=now,
        )
        session.add(task)

        # Skill logs: 2 success + 1 failure for "code_review"
        for i, status in enumerate(["success", "success", "failed"]):
            log = TaskStageLogModel(
                id=f"sf-log-{i}",
                task_id="sf-task-1",
                stage_name="review",
                agent_role="review",
                event_type="tool_call",
                event_source="llm",
                status=status,
                command="skill:code_review",
                duration_ms=100.0 + i * 50,
            )
            session.add(log)

        # Skill logs: 1 success for "write_test"
        log2 = TaskStageLogModel(
            id="sf-log-3",
            task_id="sf-task-1",
            stage_name="test",
            agent_role="test",
            event_type="tool_call",
            event_source="llm",
            status="success",
            command="skill:write_test",
            duration_ms=200.0,
        )
        session.add(log2)

        await session.commit()

    yield

    # Cleanup
    async with async_session_factory() as session:
        for model_cls in [TaskStageLogModel, SkillFeedbackModel, TaskModel]:
            result = await session.execute(select(model_cls))
            for obj in result.scalars().all():
                if hasattr(obj, "id") and str(obj.id).startswith("sf-"):
                    await session.delete(obj)
                elif hasattr(obj, "task_id") and str(obj.task_id) == "sf-task-1":
                    await session.delete(obj)
        await session.commit()


@pytest.mark.asyncio
async def test_aggregate_skill_metrics(seed_skill_logs):
    """aggregate_skill_metrics creates feedback records from task logs."""
    from app.services.skill_feedback_service import aggregate_skill_metrics

    async with async_session_factory() as session:
        records = await aggregate_skill_metrics(session, "sf-task-1")

    assert len(records) == 2
    by_name = {r["skill_name"]: r for r in records}

    assert "code_review" in by_name
    cr = by_name["code_review"]
    assert cr["invocations"] == 3
    assert cr["success_count"] == 2
    assert cr["fail_count"] == 1

    assert "write_test" in by_name
    wt = by_name["write_test"]
    assert wt["invocations"] == 1
    assert wt["success_count"] == 1
    assert wt["fail_count"] == 0


@pytest.mark.asyncio
async def test_aggregate_empty_task():
    """aggregate_skill_metrics returns empty list for task with no skill logs."""
    from app.services.skill_feedback_service import aggregate_skill_metrics

    async with async_session_factory() as session:
        records = await aggregate_skill_metrics(session, "nonexistent-task-id")

    assert records == []


@pytest.mark.asyncio
async def test_get_skill_effectiveness(seed_skill_logs):
    """get_skill_effectiveness returns aggregated stats from feedback records."""
    from app.services.skill_feedback_service import (
        aggregate_skill_metrics,
        get_skill_effectiveness,
    )

    # First aggregate
    async with async_session_factory() as session:
        await aggregate_skill_metrics(session, "sf-task-1")

    # Then query
    async with async_session_factory() as session:
        items = await get_skill_effectiveness(session)

    assert len(items) >= 2
    by_name = {item["skill_name"]: item for item in items}
    assert "code_review" in by_name
    assert "write_test" in by_name


@pytest.mark.asyncio
async def test_get_skill_effectiveness_filter(seed_skill_logs):
    """get_skill_effectiveness can filter by skill_name."""
    from app.services.skill_feedback_service import (
        aggregate_skill_metrics,
        get_skill_effectiveness,
    )

    async with async_session_factory() as session:
        await aggregate_skill_metrics(session, "sf-task-1")

    async with async_session_factory() as session:
        items = await get_skill_effectiveness(session, skill_name="write_test")

    assert len(items) == 1
    assert items[0]["skill_name"] == "write_test"


@pytest.mark.asyncio
async def test_skill_stats_includes_effectiveness(client, seed_skill_logs):
    """GET /api/v1/skills/stats response includes effectiveness field."""
    from app.services.skill_feedback_service import aggregate_skill_metrics

    async with async_session_factory() as session:
        await aggregate_skill_metrics(session, "sf-task-1")

    resp = await client.get("/api/v1/skills/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "effectiveness" in data
    assert isinstance(data["effectiveness"], list)


@pytest.mark.asyncio
async def test_effectiveness_api_endpoint(client, seed_skill_logs):
    """GET /api/v1/skills/effectiveness returns effectiveness data."""
    from app.services.skill_feedback_service import aggregate_skill_metrics

    async with async_session_factory() as session:
        await aggregate_skill_metrics(session, "sf-task-1")

    resp = await client.get("/api/v1/skills/effectiveness")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 2


@pytest.mark.asyncio
async def test_effectiveness_api_filter(client, seed_skill_logs):
    """GET /api/v1/skills/effectiveness?skill_name=... filters results."""
    from app.services.skill_feedback_service import aggregate_skill_metrics

    async with async_session_factory() as session:
        await aggregate_skill_metrics(session, "sf-task-1")

    resp = await client.get(
        "/api/v1/skills/effectiveness", params={"skill_name": "code_review"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["skill_name"] == "code_review"
