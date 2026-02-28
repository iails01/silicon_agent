# feature-002-任务管线页面历史功能 - 实现细节

## 1. 页面侧能力链路（现状）
1. 进入页面后按任务 ID 拉取 `GET /tasks/{task_id}` 和 `GET /tasks/{task_id}/stages`。
2. 日志面板按当前阶段或全阶段请求 `GET /task-logs`。
3. 页面通过 `/ws` 订阅实时消息，接收 `task_update`、`gate_created/gate_resolved`、`task_log_stream`。
4. 遇到人工关卡时，通过 `GET /gates?task_id=...&status=pending` 获取待处理 Gate。
5. 操作 Gate（approve/reject/revise）后，后端写库并广播 Gate 状态事件。
6. 任务失败后可触发 `POST /tasks/{task_id}/retry` 进入重试；运行中可 `cancel`。

## 2. 后端实现要点

### 2.1 任务/阶段
- `TaskService.get_task` 返回任务详情与阶段列表。
- `TaskService.get_stages` 按 `started_at` 排序返回阶段。
- `cancel_task` 将任务设为 `cancelled`；`retry_task` 会重置可重试失败阶段并增加 `retry_count`。

### 2.2 日志
- `TaskLogService.list_logs` 支持 `stage`、`event_source`、分页。
- 返回按 `event_seq ASC` 保序；同序补充按 `created_at` 与主键排序。
- 如果日志缺失 `command`，会根据 `command_args.tool_name` 推导命令摘要。

### 2.3 Gate
- `GateService.list_gates` 支持 `status/task_id` 过滤。
- `approve/reject/revise` 更新 Gate 状态、审批人、评论、审批时间。
- `reject` 在配置启用时可触发经验提取（写入反馈/记忆）。

### 2.4 实时推送
- Worker 在阶段执行中广播 `task:stage_update`。
- tool 执行过程中广播 `task:log_stream_update` 的 chunk；结束时 `finished=true` 收口。
- Gate 创建与处理通过 `gate:created|approved|rejected` 广播。
- `ws_manager` 将后端事件映射成前端消费类型（如 `task_update`, `task_log_stream`）。

## 3. 页面可见状态与行为
1. 任务状态：`pending/running/completed/failed/cancelled`（由任务接口返回）。
2. 阶段状态：`pending/running/completed/failed/...`（由阶段与 stage update 驱动）。
3. Gate 状态：`pending/approved/rejected/revised`。
4. 日志来源：`llm/tool/system`。
5. 工具日志支持“进行中增量输出 + 结束态结果摘要”。

## 4. 测试证据（历史能力依据）
- `tests/test_tasks_api.py`：任务详情、阶段、过滤、重试/取消。
- `tests/test_task_logs_api.py`：日志字段、分页、排序、参数兼容与校验。
- `tests/test_gates_api.py`：Gate 列表、详情、审批/驳回、历史。
- `tests/test_executor_stage_logs.py`：tool 流式日志与生命周期事件。
- `tests/test_engine_system_logs.py`：系统事件（如 gate/compression）日志行为。

## 5. 维护约束（文档层）
1. 页面新增按钮动作时，需同步补充 `02_interface.md` 的 API 与请求体示例。
2. 页面新增状态标签时，需同步补充本文件第 3 节状态清单。
3. 若修改 WebSocket 事件映射，需同步更新 `02_interface.md` 第 4 节。
