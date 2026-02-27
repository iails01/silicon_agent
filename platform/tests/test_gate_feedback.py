"""Tests for gate rejection feedback extraction and memory persistence."""
import pytest
import pytest_asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from app.db.session import async_session_factory
from app.models.gate import HumanGateModel
from app.models.skill_feedback import SkillFeedbackModel
from app.models.task import TaskModel
from app.models.project import ProjectModel


@pytest_asyncio.fixture
async def seed_gate_task():
    """Seed a project, task, and pending gate for feedback testing."""
    now = datetime.now(timezone.utc)
    async with async_session_factory() as session:
        project = ProjectModel(
            id="gf-proj-1",
            name="Gate Feedback Test Project",
            display_name="Gate Feedback Test Project",
        )
        session.add(project)

        task = TaskModel(
            id="gf-task-1",
            title="Gate Feedback Test Task",
            status="running",
            project_id="gf-proj-1",
            total_tokens=1000,
            total_cost_rmb=0.01,
            created_at=now,
        )
        session.add(task)

        gate = HumanGateModel(
            id="gf-gate-1",
            gate_type="review",
            task_id="gf-task-1",
            agent_role="review",
            status="pending",
            content={"stage": "review", "summary": "Code review output to approve"},
        )
        session.add(gate)

        await session.commit()

    yield

    # Cleanup
    async with async_session_factory() as session:
        for model_cls in [SkillFeedbackModel, HumanGateModel, TaskModel, ProjectModel]:
            result = await session.execute(select(model_cls))
            for obj in result.scalars().all():
                if hasattr(obj, "id") and str(obj.id).startswith("gf-"):
                    await session.delete(obj)
                elif hasattr(obj, "task_id") and str(getattr(obj, "task_id", "")) == "gf-task-1":
                    await session.delete(obj)
        await session.commit()


@pytest.mark.asyncio
async def test_gate_reject_creates_feedback(client, seed_gate_task):
    """Rejecting a gate creates a SkillFeedbackModel record."""
    # Mock the LLM call for lesson extraction
    with patch(
        "app.services.gate_service._llm_extract_gate_lesson",
        new_callable=AsyncMock,
        return_value="确保代码审查时检查边界条件",
    ):
        resp = await client.post(
            "/api/v1/gates/gf-gate-1/reject",
            json={"reviewer": "tester", "comment": "Missing edge case handling"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "rejected"
    assert data["reviewer"] == "tester"

    # Verify feedback record was created
    async with async_session_factory() as session:
        result = await session.execute(
            select(SkillFeedbackModel).where(
                SkillFeedbackModel.task_id == "gf-task-1",
                SkillFeedbackModel.feedback_type == "gate_reject",
            )
        )
        feedback = result.scalar_one_or_none()

    assert feedback is not None
    assert feedback.skill_name == "gate:review"
    assert feedback.agent_role == "review"
    assert feedback.content == "确保代码审查时检查边界条件"


@pytest.mark.asyncio
async def test_gate_reject_persists_to_memory(client, seed_gate_task):
    """Rejecting a gate persists the lesson to project memory."""
    with patch(
        "app.services.gate_service._llm_extract_gate_lesson",
        new_callable=AsyncMock,
        return_value="始终检查空指针",
    ), patch(
        "app.worker.memory.ProjectMemoryStore"
    ) as mock_store_cls:
        mock_store = AsyncMock()
        mock_store.add_entries = AsyncMock()
        mock_store_cls.return_value = mock_store

        resp = await client.post(
            "/api/v1/gates/gf-gate-1/reject",
            json={"reviewer": "tester", "comment": "Null pointer issue"},
        )

    assert resp.status_code == 200

    # Verify memory store was called
    mock_store_cls.assert_called_once_with("gf-proj-1")
    mock_store.add_entries.assert_called_once()
    call_args = mock_store.add_entries.call_args
    assert call_args[0][0] == "issues"
    entries = call_args[0][1]
    assert len(entries) == 1
    assert entries[0].content == "始终检查空指针"
    assert entries[0].confidence == 1.0
    assert "gate-reject" in entries[0].tags


@pytest.mark.asyncio
async def test_gate_reject_no_comment_no_feedback(seed_gate_task):
    """Gate rejection with empty comment and empty summary skips feedback."""
    async with async_session_factory() as session:
        # Update gate to have empty content summary
        result = await session.execute(
            select(HumanGateModel).where(HumanGateModel.id == "gf-gate-1")
        )
        gate = result.scalar_one()
        gate.content = {}
        await session.commit()

    from app.services.gate_service import _extract_gate_feedback

    async with async_session_factory() as session:
        result = await session.execute(
            select(HumanGateModel).where(HumanGateModel.id == "gf-gate-1")
        )
        gate = result.scalar_one()
        gate.review_comment = ""
        await _extract_gate_feedback(session, gate)

    # No feedback should be created
    async with async_session_factory() as session:
        result = await session.execute(
            select(SkillFeedbackModel).where(
                SkillFeedbackModel.task_id == "gf-task-1"
            )
        )
        feedback = result.scalar_one_or_none()

    assert feedback is None


@pytest.mark.asyncio
async def test_llm_extract_gate_lesson_fallback():
    """_llm_extract_gate_lesson falls back to raw comment when LLM fails."""
    from app.services.gate_service import _llm_extract_gate_lesson

    with patch(
        "app.integration.llm_client.get_llm_client",
        side_effect=Exception("LLM unavailable"),
    ):
        result = await _llm_extract_gate_lesson("My feedback comment", "Stage summary")

    assert result == "My feedback comment"


@pytest.mark.asyncio
async def test_llm_extract_gate_lesson_fallback_to_summary():
    """_llm_extract_gate_lesson falls back to summary when comment is empty."""
    from app.services.gate_service import _llm_extract_gate_lesson

    with patch(
        "app.integration.llm_client.get_llm_client",
        side_effect=Exception("LLM unavailable"),
    ):
        result = await _llm_extract_gate_lesson("", "Stage summary text")

    assert result == "Stage summary text"
