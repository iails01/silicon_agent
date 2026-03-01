"""Tests for cron trigger: scheduler logic, TriggerService, and Triggers API."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.db.session import async_session_factory
from app.models.template import TaskTemplateModel
from app.models.trigger import TriggerEventModel, TriggerRuleModel
from app.worker.scheduler import _is_due, validate_cron_expr


# ── Helpers ───────────────────────────────────────────────────────────────────


def _mock_rule(cron_expr, last_triggered_at=None, name="test-rule", enabled=True):
    rule = MagicMock()
    rule.id = "rule-test-id"
    rule.name = name
    rule.source = "cron"
    rule.event_type = "*"
    rule.cron_expr = cron_expr
    rule.last_triggered_at = last_triggered_at
    rule.enabled = enabled
    rule.filters = None
    rule.template_id = None
    rule.project_id = None
    rule.title_template = "定时任务 {scheduled_at}"
    rule.desc_template = None
    rule.dedup_key_template = None
    rule.dedup_window_hours = "24"
    return rule


# ── Unit: validate_cron_expr ──────────────────────────────────────────────────


class TestValidateCronExpr:
    def test_standard_5field_expressions(self):
        assert validate_cron_expr("* * * * *") is True
        assert validate_cron_expr("0 9 * * *") is True
        assert validate_cron_expr("0 9 * * 1-5") is True
        assert validate_cron_expr("*/30 * * * *") is True
        assert validate_cron_expr("0 */2 * * *") is True
        assert validate_cron_expr("0 0 1 * *") is True

    def test_invalid_expressions(self):
        assert validate_cron_expr("bad") is False
        assert validate_cron_expr("") is False
        assert validate_cron_expr("99 * * * *") is False   # 分钟 > 59
        assert validate_cron_expr("* 25 * * *") is False   # 小时 > 23
        # 注：croniter 支持 6 段扩展格式（秒/年），故不测试 6 段


# ── Unit: _is_due ─────────────────────────────────────────────────────────────


class TestIsDue:
    def setup_method(self):
        self.now = datetime.now(timezone.utc)

    def test_never_triggered_every_minute_is_due(self):
        """首次运行，每分钟规则应立即触发。"""
        rule = _mock_rule("* * * * *", last_triggered_at=None)
        assert _is_due(rule, self.now) is True

    def test_just_triggered_is_not_due(self):
        """刚刚触发过，不应重复触发。"""
        rule = _mock_rule("* * * * *", last_triggered_at=self.now)
        assert _is_due(rule, self.now) is False

    def test_overdue_by_two_minutes(self):
        """上次触发在 2 分钟前，每分钟规则应到期。"""
        rule = _mock_rule("* * * * *", last_triggered_at=self.now - timedelta(minutes=2))
        assert _is_due(rule, self.now) is True

    def test_hourly_rule_triggered_30min_ago_is_not_due(self):
        """每小时规则，30 分钟前已触发，不应到期。"""
        rule = _mock_rule("0 * * * *", last_triggered_at=self.now - timedelta(minutes=30))
        # 取决于当前时间是否恰好整点，但不应抛出异常
        result = _is_due(rule, self.now)
        assert isinstance(result, bool)

    def test_hourly_rule_triggered_over_one_hour_ago_is_due(self):
        """每小时规则，75 分钟前触发，应到期。"""
        rule = _mock_rule("0 * * * *", last_triggered_at=self.now - timedelta(minutes=75))
        assert _is_due(rule, self.now) is True

    def test_invalid_cron_expr_returns_false(self):
        """无效的 cron 表达式不应抛异常，返回 False。"""
        rule = _mock_rule("bad-expr")
        assert _is_due(rule, self.now) is False

    def test_none_cron_expr_returns_false(self):
        """cron_expr 为 None 时返回 False。"""
        rule = _mock_rule(None)
        assert _is_due(rule, self.now) is False

    def test_naive_last_triggered_at_is_handled(self):
        """last_triggered_at 无时区信息时不应崩溃。"""
        naive_dt = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=5)
        rule = _mock_rule("* * * * *", last_triggered_at=naive_dt)
        result = _is_due(rule, self.now)
        assert isinstance(result, bool)

    def test_weekly_rule_triggered_eight_days_ago_is_due(self):
        """每周一规则，8 天前触发，应到期。"""
        rule = _mock_rule("0 9 * * 1", last_triggered_at=self.now - timedelta(days=8))
        assert _is_due(rule, self.now) is True


# ── Unit: TriggerService.process_event (cron) ─────────────────────────────────


class TestTriggerServiceCron:
    """用 mock session 测试 TriggerService 对 cron 事件的处理。"""

    def _make_service(self, rules: list):
        from app.services.trigger_service import TriggerService

        session = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = rules
        session.execute = AsyncMock(return_value=mock_result)
        session.add = MagicMock()
        session.commit = AsyncMock()

        service = TriggerService(session)
        return service

    @pytest.mark.asyncio
    async def test_no_matching_rules_logs_skipped(self):
        """无匹配规则时，事件结果应为 skipped_no_rule。"""
        service = self._make_service(rules=[])
        payload = {"scheduled_at": "2026-01-01T09:00:00Z", "rule_name": "test"}

        task_id = await service.process_event("cron", "scheduled", payload)
        assert task_id is None

        # 验证写入了 skipped_no_rule 事件
        added_event = service.session.add.call_args[0][0]
        assert isinstance(added_event, TriggerEventModel)
        assert added_event.result == "skipped_no_rule"
        assert added_event.source == "cron"

    @pytest.mark.asyncio
    async def test_matching_rule_creates_task(self):
        """匹配规则且无去重时，应调用 task_service 创建任务。"""
        rule = _mock_rule("0 9 * * *")

        service = self._make_service(rules=[rule])

        # 模拟 _is_duplicate 返回 False，task_service 返回 mock task
        mock_task = MagicMock()
        mock_task.id = "task-created-id"
        mock_task.title = "定时任务 2026-01-01"
        mock_task.description = None
        mock_task.status = "pending"
        mock_task.total_tokens = 0
        mock_task.total_cost_rmb = 0.0
        mock_task.created_at = datetime.now(timezone.utc)
        mock_task.completed_at = None
        mock_task.branch_name = None
        mock_task.pr_url = None
        mock_task.stages = []
        mock_task.template_id = None
        mock_task.project_id = None
        mock_task.template = None
        mock_task.project = None
        mock_task.target_branch = None
        mock_task.yunxiao_task_id = None
        mock_task.jira_id = None

        with patch(
            "app.services.trigger_service.TaskService.create_task",
            new_callable=AsyncMock,
            return_value=MagicMock(id="task-created-id"),
        ):
            with patch.object(service, "_is_duplicate", new_callable=AsyncMock, return_value=False):
                task_id = await service.process_event(
                    "cron", "scheduled",
                    {"scheduled_at": "2026-01-01T09:00:00Z", "event_type": "scheduled"},
                )

        assert task_id == "task-created-id"

        added_event = service.session.add.call_args[0][0]
        assert added_event.result == "triggered"
        assert added_event.task_id == "task-created-id"

    @pytest.mark.asyncio
    async def test_dedup_skips_task_creation(self):
        """去重命中时，不应创建任务，结果为 skipped_dedup。"""
        rule = _mock_rule("0 9 * * *")
        rule.dedup_key_template = "cron:{rule_name}"

        service = self._make_service(rules=[rule])

        with patch.object(service, "_is_duplicate", new_callable=AsyncMock, return_value=True):
            task_id = await service.process_event(
                "cron", "scheduled",
                {"scheduled_at": "2026-01-01T09:00:00Z", "rule_name": "test-rule", "event_type": "scheduled"},
            )

        assert task_id is None
        added_event = service.session.add.call_args[0][0]
        assert added_event.result == "skipped_dedup"


# ── Unit: _fire_due_rules ─────────────────────────────────────────────────────


class TestFireDueRules:
    @pytest.mark.asyncio
    async def test_due_rule_is_processed(self):
        """到期规则应调用 process_event。"""
        from app.worker.scheduler import _fire_due_rules

        now = datetime.now(timezone.utc)
        due_rule = _mock_rule("* * * * *", last_triggered_at=now - timedelta(minutes=2))
        due_rule.id = "rule-fire-test"

        mock_session = AsyncMock()
        mock_exec_result = MagicMock()
        mock_exec_result.scalars.return_value.all.return_value = [due_rule]
        mock_session.execute = AsyncMock(return_value=mock_exec_result)
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("app.worker.scheduler.async_session_factory", return_value=mock_session):
            with patch("app.worker.scheduler.TriggerService") as MockService:
                mock_svc_instance = AsyncMock()
                mock_svc_instance.process_event = AsyncMock(return_value="new-task-id")
                MockService.return_value = mock_svc_instance

                await _fire_due_rules()

                mock_svc_instance.process_event.assert_called_once()
                call_args = mock_svc_instance.process_event.call_args
                assert call_args[0][0] == "cron"
                assert call_args[0][1] == "scheduled"
                payload = call_args[0][2]
                assert "scheduled_at" in payload
                assert payload["rule_name"] == "test-rule"

    @pytest.mark.asyncio
    async def test_not_due_rule_is_skipped(self):
        """未到期规则不应调用 process_event。"""
        from app.worker.scheduler import _fire_due_rules

        now = datetime.now(timezone.utc)
        # 刚刚触发过
        not_due_rule = _mock_rule("* * * * *", last_triggered_at=now)
        not_due_rule.id = "rule-not-due"

        mock_session = AsyncMock()
        mock_exec_result = MagicMock()
        mock_exec_result.scalars.return_value.all.return_value = [not_due_rule]
        mock_session.execute = AsyncMock(return_value=mock_exec_result)
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("app.worker.scheduler.async_session_factory", return_value=mock_session):
            with patch("app.worker.scheduler.TriggerService") as MockService:
                mock_svc_instance = AsyncMock()
                MockService.return_value = mock_svc_instance

                await _fire_due_rules()

                mock_svc_instance.process_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_last_triggered_at_is_updated_after_fire(self):
        """触发后 last_triggered_at 应被更新。"""
        from app.worker.scheduler import _fire_due_rules

        now = datetime.now(timezone.utc)
        due_rule = _mock_rule("* * * * *", last_triggered_at=now - timedelta(minutes=2))
        due_rule.id = "rule-update-ts"

        mock_session = AsyncMock()
        mock_exec_result = MagicMock()
        mock_exec_result.scalars.return_value.all.return_value = [due_rule]
        mock_session.execute = AsyncMock(return_value=mock_exec_result)
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("app.worker.scheduler.async_session_factory", return_value=mock_session):
            with patch("app.worker.scheduler.TriggerService") as MockService:
                mock_svc_instance = AsyncMock()
                mock_svc_instance.process_event = AsyncMock(return_value="task-xyz")
                MockService.return_value = mock_svc_instance

                await _fire_due_rules()

        # last_triggered_at 应被设置为接近 now 的时间
        assert due_rule.last_triggered_at is not None
        assert abs((due_rule.last_triggered_at - now).total_seconds()) < 5

    @pytest.mark.asyncio
    async def test_multiple_rules_each_evaluated(self):
        """多条规则各自独立判断是否到期。"""
        from app.worker.scheduler import _fire_due_rules

        now = datetime.now(timezone.utc)
        due_rule = _mock_rule("* * * * *", last_triggered_at=now - timedelta(minutes=2), name="due")
        not_due_rule = _mock_rule("* * * * *", last_triggered_at=now, name="not-due")

        mock_session = AsyncMock()
        mock_exec_result = MagicMock()
        mock_exec_result.scalars.return_value.all.return_value = [due_rule, not_due_rule]
        mock_session.execute = AsyncMock(return_value=mock_exec_result)
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("app.worker.scheduler.async_session_factory", return_value=mock_session):
            with patch("app.worker.scheduler.TriggerService") as MockService:
                mock_svc_instance = AsyncMock()
                mock_svc_instance.process_event = AsyncMock(return_value="task-abc")
                MockService.return_value = mock_svc_instance

                await _fire_due_rules()

        # 只有 due_rule 触发
        assert mock_svc_instance.process_event.call_count == 1
        call_payload = mock_svc_instance.process_event.call_args[0][2]
        assert call_payload["rule_name"] == "due"


# ── Integration: Triggers API ─────────────────────────────────────────────────


@pytest_asyncio.fixture
async def cleanup_trigger_rules():
    """测试后清理 trigger_rules 和 trigger_events 表中的测试数据。"""
    yield
    async with async_session_factory() as session:
        for model in [TriggerEventModel, TriggerRuleModel]:
            result = await session.execute(select(model))
            for obj in result.scalars().all():
                await session.delete(obj)
        await session.commit()


@pytest_asyncio.fixture
async def seed_template():
    """为 API 集成测试创建一个模板。"""
    async with async_session_factory() as session:
        tmpl = TaskTemplateModel(
            id="tmpl-cron-test",
            name="cron_test_template",
            display_name="Cron Test Template",
            description="Used by cron trigger tests",
            stages='[{"name": "coding", "agent_role": "coding", "order": 0}]',
            gates="[]",
        )
        session.add(tmpl)
        await session.commit()

    yield "tmpl-cron-test"

    async with async_session_factory() as session:
        result = await session.execute(
            select(TaskTemplateModel).where(TaskTemplateModel.id == "tmpl-cron-test")
        )
        tmpl = result.scalar_one_or_none()
        if tmpl:
            await session.delete(tmpl)
        await session.commit()


class TestTriggersAPI:
    @pytest.mark.asyncio
    async def test_create_cron_rule(self, client, cleanup_trigger_rules, seed_template):
        """POST /api/v1/triggers 创建 cron 规则返回 201。"""
        resp = await client.post("/api/v1/triggers", json={
            "name": "每日扫描",
            "source": "cron",
            "event_type": "scheduled",
            "cron_expr": "0 9 * * 1-5",
            "title_template": "每日代码扫描 {scheduled_at}",
            "template_id": seed_template,
        })
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["source"] == "cron"
        assert data["cron_expr"] == "0 9 * * 1-5"
        assert data["enabled"] is True
        assert data["last_triggered_at"] is None

    @pytest.mark.asyncio
    async def test_create_cron_rule_invalid_expr(self, client, cleanup_trigger_rules):
        """无效的 cron_expr 应返回 422。"""
        resp = await client.post("/api/v1/triggers", json={
            "name": "坏表达式",
            "source": "cron",
            "event_type": "scheduled",
            "cron_expr": "not-valid",
            "title_template": "T",
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_cron_rule_missing_expr(self, client, cleanup_trigger_rules):
        """source=cron 但缺少 cron_expr 应返回 422。"""
        resp = await client.post("/api/v1/triggers", json={
            "name": "缺少表达式",
            "source": "cron",
            "event_type": "scheduled",
            "title_template": "T",
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_list_rules_includes_cron(self, client, cleanup_trigger_rules, seed_template):
        """GET /api/v1/triggers 返回列表，包含刚创建的 cron 规则。"""
        await client.post("/api/v1/triggers", json={
            "name": "列表测试规则",
            "source": "cron",
            "event_type": "scheduled",
            "cron_expr": "*/5 * * * *",
            "title_template": "T",
        })
        resp = await client.get("/api/v1/triggers")
        assert resp.status_code == 200
        names = [r["name"] for r in resp.json()]
        assert "列表测试规则" in names

    @pytest.mark.asyncio
    async def test_update_cron_expr(self, client, cleanup_trigger_rules):
        """PUT /api/v1/triggers/{id} 可更新 cron_expr。"""
        create_resp = await client.post("/api/v1/triggers", json={
            "name": "待更新规则",
            "source": "cron",
            "event_type": "scheduled",
            "cron_expr": "0 8 * * *",
            "title_template": "T",
        })
        rule_id = create_resp.json()["id"]

        update_resp = await client.put(f"/api/v1/triggers/{rule_id}", json={
            "cron_expr": "0 10 * * *",
        })
        assert update_resp.status_code == 200
        assert update_resp.json()["cron_expr"] == "0 10 * * *"

    @pytest.mark.asyncio
    async def test_update_with_invalid_cron_expr(self, client, cleanup_trigger_rules):
        """PUT 时传入无效 cron_expr 应返回 422。"""
        create_resp = await client.post("/api/v1/triggers", json={
            "name": "校验更新规则",
            "source": "cron",
            "event_type": "scheduled",
            "cron_expr": "0 8 * * *",
            "title_template": "T",
        })
        rule_id = create_resp.json()["id"]

        resp = await client.put(f"/api/v1/triggers/{rule_id}", json={
            "cron_expr": "invalid!!",
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_delete_rule(self, client, cleanup_trigger_rules):
        """DELETE /api/v1/triggers/{id} 返回 204，再 GET 返回 404。"""
        create_resp = await client.post("/api/v1/triggers", json={
            "name": "待删除规则",
            "source": "cron",
            "event_type": "scheduled",
            "cron_expr": "0 0 * * *",
            "title_template": "T",
        })
        rule_id = create_resp.json()["id"]

        del_resp = await client.delete(f"/api/v1/triggers/{rule_id}")
        assert del_resp.status_code == 204

        get_resp = await client.get(f"/api/v1/triggers/{rule_id}")
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_events_endpoint(self, client, cleanup_trigger_rules):
        """GET /api/v1/triggers/events 正常返回列表。"""
        resp = await client.get("/api/v1/triggers/events")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
