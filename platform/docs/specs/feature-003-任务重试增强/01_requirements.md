# feature-003-任务重试增强

## 1. 背景与目标
为任务管线提供更精细的人工恢复能力：
1. 在任务管线详情中支持从失败节点手动重试。
2. 在任务管线管理页面支持批量重试失败任务。

## 2. 用户故事
1. 作为研发/值班人员，我希望对指定失败阶段发起重试，而不是只能整任务重试。
2. 作为运营人员，我希望一次性重试多个失败任务，减少重复操作。

## 3. 功能范围
1. 新增单任务“从失败节点重试”接口（按 `stage_id` 指定）。
2. 新增任务批量重试接口（按 `task_ids` 指定），每个任务仅从其失败节点恢复，不做全量阶段重置。
3. 复用现有重试规则：仅对失败任务生效；遵守阶段最大重试次数限制。

## 4. 验收标准
1. `POST /api/v1/tasks/{task_id}/retry-from-stage`：
   - 任务不存在返回 404。
   - 目标阶段不存在或不属于该任务返回 404。
   - 任务非 failed 状态时返回 400。
   - 目标阶段状态非 failed 时返回 400。
   - 成功时任务状态变为 pending，目标失败阶段重置为 pending，`retry_count + 1`。
   - 非目标阶段（尤其历史成功阶段）不重置。
2. `POST /api/v1/tasks/retry-batch`：
   - 返回每个任务的重试结果（成功/失败及原因）。
   - 每个成功任务只重置失败节点，不重置已成功节点。
   - 批量结果包含统计字段（total/succeeded/failed）。

## 5. 文件路径
- `app/api/v1/tasks.py`
- `app/schemas/task.py`
- `app/services/task_service.py`
- `tests/test_tasks_api.py`

## 6. 签名约束
- `TaskService.retry_from_stage(task_id: str, stage_id: str) -> Optional[TaskDetailResponse]`
- `TaskService.retry_batch(task_ids: List[str]) -> TaskBatchRetryResponse`

## 7. Mock 数据
- `POST /api/v1/tasks/task-1/retry-from-stage` body: `{"stage_id":"stage-2"}`
- `POST /api/v1/tasks/retry-batch` body: `{"task_ids":["t1","t2"]}`
