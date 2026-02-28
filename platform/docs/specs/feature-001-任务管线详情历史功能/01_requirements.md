# feature-001-任务管线详情历史功能

## 1. 背景与目标
将“任务管线详情”相关的**已上线能力**整理为历史功能文档，统一为项目 Spec 格式，便于后续迭代对照与回归。

## 2. 用户故事（历史能力视角）
1. 作为前端/运营人员，我希望按任务与阶段查看执行日志，理解当前卡点。
2. 作为研发人员，我希望看到 LLM 对话、turn、tool 调用的生命周期细节，定位失败原因。
3. 作为系统维护者，我希望系统事件（sandbox/worktree/gate/compression 等）被统一记录，便于审计。
4. 作为安全负责人，我希望日志中的敏感字段与 token 被脱敏，超长文本被截断。

## 3. 历史功能范围（已实现）
1. 任务日志异步落库管线（队列 + 批量 flush + 优先级）。
2. 阶段执行生命周期埋点（chat/turn/tool/system 事件）。
3. 工具调用流式回传（WebSocket `task:log_stream_update`）。
4. 日志查询接口（分页、阶段过滤、事件来源过滤、兼容 `task_id`）。
5. 事件顺序控制（`event_seq` + 时间排序）与运行时补偿（未完成事件 finalize）。
6. 脱敏/截断策略（敏感 key、Bearer token、50KB 截断标记）。

## 4. 验收标准（历史事实）
1. 可通过 `GET /api/v1/task-logs` 返回任务日志明细。
2. 返回日志包含：`event_type`、`event_source`、`status`、`duration_ms`、`result`、`output_summary` 等关键字段。
3. 工具执行中可收到流式 `chunk`，结束时可收到 `finished=true` 的收口事件。
4. 同任务日志按 `event_seq ASC` 保序返回。
5. 接口缺少 `task/task_id` 参数时返回 422。

## 5. 文件路径
### 5.1 历史实现文件（已存在）
- `app/services/task_log_pipeline.py`
- `app/services/task_log_service.py`
- `app/models/task_log.py`
- `app/schemas/task_log.py`
- `app/api/v1/task_logs.py`
- `app/worker/executor.py`
- `app/worker/engine.py`
- `app/websocket/events.py`
- `tests/test_task_logs_api.py`
- `tests/test_executor_stage_logs.py`
- `tests/test_worker_stage_tracker.py`
- `tests/test_task_log_service.py`

### 5.2 本次文档新增文件
- `docs/specs/feature-001-任务管线详情历史功能/01_requirements.md`
- `docs/specs/feature-001-任务管线详情历史功能/02_interface.md`
- `docs/specs/feature-001-任务管线详情历史功能/03_implementation.md`

## 6. 非目标
1. 本文不引入新接口、新字段或新事件类型。
2. 本文不改动运行时代码逻辑，仅做历史能力归档。
