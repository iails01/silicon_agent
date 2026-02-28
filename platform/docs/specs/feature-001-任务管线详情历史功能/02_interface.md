# feature-001-任务管线详情历史功能 - 接口与数据结构

## 1. 技术栈与边界
- API 框架：FastAPI
- ORM：SQLAlchemy (AsyncSession)
- Schema：Pydantic
- 异步日志管线：`asyncio.Queue` + 后台 worker 批量提交
- 实时通道：WebSocket 广播

## 2. 核心类与方法签名（现状）

### 2.1 日志管线服务
```python
class TaskLogEventPipeline:
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def ensure_started(self) -> None: ...
    async def wait_until_drained(self, timeout_seconds: float = 5.0) -> None: ...

    async def emit_create(
        self,
        *,
        task_id: str,
        stage_id: Optional[str],
        stage_name: str,
        agent_role: Optional[str],
        event_type: str,
        event_source: str,
        status: str,
        request_body: Optional[dict[str, Any]] = None,
        response_body: Optional[dict[str, Any]] = None,
        command: Optional[str] = None,
        command_args: Optional[dict[str, Any]] = None,
        workspace: Optional[str] = None,
        execution_mode: Optional[str] = None,
        duration_ms: Optional[float] = None,
        result: Optional[str] = None,
        output_summary: Optional[str] = None,
        missing_fields: Optional[list[str]] = None,
        correlation_id: Optional[str] = None,
        log_id: Optional[str] = None,
        priority: Literal["high", "normal", "low"] = "normal",
    ) -> str: ...

    async def emit_update(
        self,
        *,
        log_id: str,
        updates: dict[str, Any],
        priority: Literal["high", "normal", "low"] = "normal",
    ) -> bool: ...
```

### 2.2 日志查询服务
```python
class TaskLogService:
    async def create_log(self, raw: dict[str, Any]) -> None: ...
    async def create_logs(self, logs: list[dict[str, Any]]) -> None: ...
    async def append_logs(self, logs: list[dict[str, Any]]) -> None: ...
    async def update_log(self, log_id: str, updates: dict[str, Any]) -> bool: ...
    async def get_max_event_seq(self, task_id: str, stage_id: Optional[str] = None) -> int: ...
    async def list_logs(
        self,
        task_id: str,
        stage: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
        event_source: Optional[str] = None,
    ) -> TaskLogListResponse: ...
```

### 2.3 API 接口
```python
@router.get("", response_model=TaskLogListResponse)
async def list_task_logs(
    task: Optional[str] = None,
    task_id: Optional[str] = None,
    stage: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    event_source: Optional[str] = None,
)
```

## 3. 数据结构

### 3.1 `task_stage_logs` 主表字段（核心）
- 标识：`id`, `task_id`, `stage_id`, `event_seq`, `correlation_id`
- 维度：`stage_name`, `agent_role`, `event_type`, `event_source`, `status`
- 载荷：`request_body`, `response_body`, `command`, `command_args`, `workspace`, `execution_mode`
- 结果：`duration_ms`, `result`, `output_summary`, `output_truncated`, `missing_fields`
- 时间：`created_at`

### 3.2 WebSocket 事件类型
- `task:log_stream_update`

## 4. Mock Data（关键接口）

### 4.1 查询日志请求
```http
GET /api/v1/task-logs?task=tt-log-task&stage=coding&page=1&page_size=2&event_source=tool
```

### 4.2 查询日志响应（示例）
```json
{
  "items": [
    {
      "id": "tt-log-3",
      "task_id": "tt-log-task",
      "stage_id": "tt-log-stage",
      "stage_name": "coding",
      "agent_role": "coding",
      "correlation_id": "tool-1",
      "event_seq": 3,
      "event_type": "tool_call_executed",
      "event_source": "tool",
      "status": "success",
      "command": "npm test",
      "command_args": {
        "tool_name": "execute",
        "command": "npm test",
        "cwd": "/tmp/silicon_agent/tasks/tt-log-task"
      },
      "workspace": "/tmp/silicon_agent/tasks/tt-log-task",
      "execution_mode": "in_process",
      "duration_ms": 123.45,
      "result": "ok",
      "output_summary": "ok",
      "output_truncated": false,
      "missing_fields": [],
      "created_at": "2026-02-24T13:30:00"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 2
}
```

### 4.3 工具流式日志（WebSocket）
```json
{
  "task_id": "task-1",
  "stage_id": "stage-1",
  "stage_name": "coding",
  "log_id": "log-9",
  "tool_call_id": "tool-call-1",
  "chunk": "line-1\\n",
  "finished": false
}
```

```json
{
  "task_id": "task-1",
  "stage_id": "stage-1",
  "stage_name": "coding",
  "log_id": "log-9",
  "tool_call_id": "tool-call-1",
  "chunk": "",
  "finished": true,
  "status": "success"
}
```
