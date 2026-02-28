# feature-001-任务管线详情历史功能 - 实现细节

## 1. 端到端逻辑（现状）
1. Worker/Executor 在阶段执行时创建 `StageEventTracker`。
2. 进入一次 LLM chat 时写入 `agent_runner_chat_sent`（running）。
3. Runner 触发 turn/tool 事件：
   - turn_start -> `llm_turn_sent`
   - turn_end -> 更新 sent 状态并写入 `llm_turn_received`
   - before_tool_call -> `tool_call_executed`（running）
   - tool_execution_update -> WebSocket 流式 chunk
   - after_tool_result -> update 工具日志状态、耗时、结果、摘要
4. chat 完成后写入 `agent_runner_chat_received`，并回填 sent 的时长/状态。
5. 阶段异常/取消时，`finalize_unfinished` 对未闭合日志做收口（failed/cancelled）。
6. 所有 create/update 通过 `TaskLogEventPipeline` 入队，后台批量落库并 commit。

## 2. 事件类型清单（历史）

### 2.1 阶段执行明细类
- `agent_runner_chat_sent`
- `agent_runner_chat_received`
- `llm_turn_sent`
- `llm_turn_received`
- `tool_call_executed`
- `llm_retry_scheduled`
- `llm_fallback_text_only`

### 2.2 系统编排类
- `sandbox_create_started` / `sandbox_create_finished` / `sandbox_fallback`
- `worktree_create_started` / `worktree_create_finished`
- `worktree_commit_push_started` / `worktree_commit_push_finished`
- `worktree_pr_started` / `worktree_pr_finished`
- `worktree_cleanup_started` / `worktree_cleanup_finished`
- `memory_extract_started` / `memory_extract_finished`
- `compression_started` / `compression_finished`
- `gate_wait_started` / `gate_wait_timeout` / `gate_wait_approved` / `gate_wait_rejected` / `gate_wait_revised` / `gate_wait_cancelled`

## 3. 关键实现策略

### 3.1 顺序与一致性
- 每条日志在入队前分配 `event_seq`（按 task 维度递增）。
- 查询按 `event_seq ASC` + `created_at ASC` + 兜底键排序，保证同时刻可稳定排序。

### 3.2 回压与优先级
- 队列满时：
  - `low` 优先级日志可丢弃并告警；
  - `high/normal` 会阻塞等待，避免关键事件乱序或丢失。

### 3.3 安全与截断
- 对 `request_body/response_body/command_args/result/output_summary` 做统一 sanitize。
- key 包含 `api_key/apikey/authorization/password/secret/token` 时置为 `***`。
- Bearer token 文本按正则替换为 `***`。
- 超过 50KB 文本截断并追加 `...[truncated]`，同时标记 `output_truncated=true`。

### 3.4 工具结果摘要
- tool 运行中持续累积 `output_summary`（最多 50KB）。
- 结束时写入 `result` 与 `output_summary`，并广播 `finished=true`。

## 4. 关键文件与职责
- `app/worker/executor.py`: 阶段执行埋点与 tracker 收口。
- `app/worker/engine.py`: 系统级事件（sandbox/worktree/gate/compression/memory）。
- `app/services/task_log_pipeline.py`: 异步队列、批量刷盘、优先级策略。
- `app/services/task_log_service.py`: 脱敏、更新白名单、排序查询。
- `app/api/v1/task_logs.py`: 日志查询 API。
- `app/websocket/events.py`: 流式事件类型常量。

## 5. 测试覆盖证据
- `tests/test_task_logs_api.py`: 字段完整性、分页、只读性、排序、参数兼容。
- `tests/test_executor_stage_logs.py`: chat/turn/tool 生命周期、流式推送、异常收口。
- `tests/test_worker_stage_tracker.py`: tracker 事件映射与结束态更新。
- `tests/test_task_log_service.py`: 脱敏、截断、append alias、更新行为。

## 6. 后续维护建议（文档层）
1. 若新增事件类型，需同步更新本文件第 2 节清单与 mock。
2. 若新增日志字段，需同步更新 `02_interface.md` 数据结构与 API 示例。
3. 若更改排序策略，需同步更新第 3.1 节并补回归测试说明。
