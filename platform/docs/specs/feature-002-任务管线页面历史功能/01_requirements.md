# feature-002-任务管线页面历史功能

## 1. 背景与目标
对“任务管线页面”当前可见功能进行历史归档，统一为项目 Spec 结构，便于后续功能扩展时做差异比对与回归验证。

## 2. 用户故事（历史能力）
1. 作为用户，我可以查看任务详情和阶段状态，了解任务当前进度。
2. 作为用户，我可以查看任务阶段日志，定位 LLM/tool/system 执行细节。
3. 作为审批人，我可以在管线卡点时处理 Gate（approve/reject/revise）。
4. 作为操作者，我可以对任务执行取消或失败后重试。
5. 作为页面订阅方，我可以实时接收任务状态、阶段更新和日志流式输出。

## 3. 历史功能范围（已实现）
1. 任务详情读取：`GET /api/v1/tasks/{task_id}`。
2. 阶段列表读取：`GET /api/v1/tasks/{task_id}/stages`。
3. 任务日志读取：`GET /api/v1/task-logs`（支持任务、阶段、来源过滤与分页）。
4. Gate 列表/详情/历史：`GET /api/v1/gates`、`GET /api/v1/gates/{gate_id}`、`GET /api/v1/gates/history`。
5. Gate 操作：`POST /api/v1/gates/{gate_id}/approve|reject|revise`。
6. 任务操作：`POST /api/v1/tasks/{task_id}/cancel`、`POST /api/v1/tasks/{task_id}/retry`。
7. WebSocket 实时事件：任务更新、Gate 创建/处理、日志流式片段推送。

## 4. 验收标准（历史事实）
1. 页面可基于任务 ID 获取任务与阶段信息。
2. 页面可按阶段查询日志，且同任务日志按 `event_seq` 升序稳定返回。
3. 页面可完成 Gate 审批、驳回、修订继续三种动作。
4. 页面可收到 `task_update`、`gate_created/gate_resolved`、`task_log_stream` 实时消息。
5. 日志查询在缺少 `task/task_id` 时返回 422。

## 5. 文件路径
### 5.1 历史实现文件（已存在）
- `app/api/v1/tasks.py`
- `app/api/v1/task_logs.py`
- `app/api/v1/gates.py`
- `app/schemas/task.py`
- `app/schemas/task_log.py`
- `app/schemas/gate.py`
- `app/services/task_service.py`
- `app/services/task_log_service.py`
- `app/services/gate_service.py`
- `app/websocket/events.py`
- `app/websocket/manager.py`
- `app/worker/executor.py`
- `app/worker/engine.py`
- `tests/test_tasks_api.py`
- `tests/test_task_logs_api.py`
- `tests/test_gates_api.py`

### 5.2 本次文档新增文件
- `docs/specs/feature-002-任务管线页面历史功能/01_requirements.md`
- `docs/specs/feature-002-任务管线页面历史功能/02_interface.md`
- `docs/specs/feature-002-任务管线页面历史功能/03_implementation.md`

## 6. 非目标
1. 本文不新增页面交互能力或后端接口。
2. 本文不调整任务编排逻辑与执行策略，仅记录现状。
