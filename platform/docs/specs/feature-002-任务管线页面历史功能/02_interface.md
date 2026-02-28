# feature-002-任务管线页面历史功能 - 接口与数据结构

## 1. 页面核心接口（现状）

### 1.1 任务与阶段
```http
GET /api/v1/tasks/{task_id}
GET /api/v1/tasks/{task_id}/stages
POST /api/v1/tasks/{task_id}/cancel
POST /api/v1/tasks/{task_id}/retry
```

### 1.2 日志
```http
GET /api/v1/task-logs?task=<task_id>&stage=<stage_name>&page=1&page_size=50&event_source=<llm|tool|system>
```

### 1.3 Gate
```http
GET /api/v1/gates?task_id=<task_id>&status=<pending|approved|rejected|revised>
GET /api/v1/gates/{gate_id}
GET /api/v1/gates/history
POST /api/v1/gates/{gate_id}/approve
POST /api/v1/gates/{gate_id}/reject
POST /api/v1/gates/{gate_id}/revise
```

## 2. 核心签名（现状）

### 2.1 TaskService
```python
class TaskService:
    async def get_task(self, task_id: str) -> Optional[TaskDetailResponse]: ...
    async def get_stages(self, task_id: str) -> List[TaskStageResponse]: ...
    async def cancel_task(self, task_id: str) -> Optional[TaskDetailResponse]: ...
    async def retry_task(self, task_id: str) -> Optional[TaskDetailResponse]: ...
```

### 2.2 TaskLogService
```python
class TaskLogService:
    async def list_logs(
        self,
        task_id: str,
        stage: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
        event_source: Optional[str] = None,
    ) -> TaskLogListResponse: ...
```

### 2.3 GateService
```python
class GateService:
    async def list_gates(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> GateListResponse: ...
    async def get_gate(self, gate_id: str) -> Optional[GateDetailResponse]: ...
    async def approve(self, gate_id: str, request: GateApproveRequest) -> Optional[GateDetailResponse]: ...
    async def reject(self, gate_id: str, request: GateRejectRequest) -> Optional[GateDetailResponse]: ...
    async def revise(self, gate_id: str, request: GateReviseRequest) -> Optional[GateDetailResponse]: ...
    async def get_history(self, page: int = 1, page_size: int = 20) -> GateListResponse: ...
```

## 3. 页面关键数据结构

### 3.1 任务详情（`TaskDetailResponse`）
- `id`, `title`, `description`, `status`
- `total_tokens`, `total_cost_rmb`
- `created_at`, `completed_at`
- `stages[]`

### 3.2 阶段（`TaskStageResponse`）
- `id`, `task_id`, `stage_name`, `agent_role`, `status`
- `started_at`, `completed_at`, `duration_seconds`
- `tokens_used`, `turns_used`, `self_fix_count`
- `output_summary`, `error_message`, `output_structured`
- `failure_category`, `self_assessment_score`, `retry_count`

### 3.3 Gate（`GateDetailResponse`）
- `id`, `gate_type`, `task_id`, `agent_role`, `status`
- `content`, `reviewer`, `review_comment`, `reviewed_at`
- `retry_count`, `is_dynamic`, `revised_content`

### 3.4 日志项（`TaskLogResponse`）
- `id`, `task_id`, `stage_id`, `stage_name`, `event_seq`
- `event_type`, `event_source`, `status`, `correlation_id`
- `request_body`, `response_body`, `command`, `command_args`
- `workspace`, `execution_mode`, `duration_ms`, `result`, `output_summary`
- `output_truncated`, `missing_fields`, `created_at`

## 4. WebSocket 事件（页面消费）
- 后端事件：`task:stage_update` / `task:status_changed` / `gate:created` / `gate:approved` / `gate:rejected` / `task:log_stream_update`
- 前端映射类型（`ws_manager`）：`task_update` / `gate_created` / `gate_resolved` / `task_log_stream`
- 消息包装：
```json
{
  "type": "task_update",
  "payload": {"task_id": "..."},
  "timestamp": "2026-02-28T07:00:00+00:00"
}
```

## 5. Mock Data（关键请求/响应）

### 5.1 任务详情
```http
GET /api/v1/tasks/tt-staged
```

```json
{
  "id": "tt-staged",
  "title": "Staged Task",
  "status": "running",
  "total_tokens": 0,
  "total_cost_rmb": 0.0,
  "stages": [
    {"id": "tt-stage-0", "stage_name": "design", "agent_role": "design", "status": "pending"},
    {"id": "tt-stage-1", "stage_name": "coding", "agent_role": "coding", "status": "pending"}
  ]
}
```

### 5.2 Gate 审批
```http
POST /api/v1/gates/gt-gate-pending/approve
Content-Type: application/json

{"reviewer": "tester", "comment": "looks good"}
```

```json
{
  "id": "gt-gate-pending",
  "status": "approved",
  "reviewer": "tester",
  "review_comment": "looks good"
}
```

### 5.3 日志查询
```http
GET /api/v1/task-logs?task=tt-log-task&stage=coding&page=1&page_size=20
```

```json
{
  "items": [
    {
      "event_seq": 1,
      "event_type": "agent_runner_chat_sent",
      "event_source": "llm",
      "status": "running"
    },
    {
      "event_seq": 2,
      "event_type": "agent_runner_chat_received",
      "event_source": "llm",
      "status": "success"
    }
  ],
  "total": 2,
  "page": 1,
  "page_size": 20
}
```
