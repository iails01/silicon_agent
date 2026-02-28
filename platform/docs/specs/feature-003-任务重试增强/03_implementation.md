# feature-003-任务重试增强 - 实现细节

## 1. 实现步骤
1. 在 `task` schema 中新增 `retry-from-stage` 与 `retry-batch` 请求/响应模型。
2. 在 `TaskService` 中抽取失败阶段重置逻辑为可复用内部方法。
3. 新增 `retry_from_stage`：定位目标阶段并做合法性检查后重置。
4. 新增 `retry_batch`：遍历 `task_ids`，对每个任务定位失败节点并执行“单节点重试”，汇总结果。
5. 在 `tasks` 路由新增两个 endpoint 并返回标准状态码。
6. 新增测试覆盖成功、参数非法、非 failed 任务、批量混合结果。

## 2. 关键逻辑
- 仅重置目标失败节点；历史成功节点和非目标节点保持不变。
- 阶段重置后，任务状态置为 `pending`，`completed_at=None`。
- 任务 token/cost 重算：仅累计已 completed 阶段。
- 目标阶段重置时遵守模板中的 `max_retries`，否则使用 `STAGE_DEFAULT_MAX_RETRIES`。

## 3. 回归影响
- 不修改现有 `POST /tasks/{task_id}/retry` 行为。
- 批量接口只做编排聚合，且与“失败节点重试”语义一致。
