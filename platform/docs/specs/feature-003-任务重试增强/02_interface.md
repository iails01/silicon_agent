# feature-003-任务重试增强 - 接口与数据结构

## 1. API

### 1.1 从失败节点重试
```http
POST /api/v1/tasks/{task_id}/retry-from-stage
Content-Type: application/json

{
  "stage_id": "stage-2"
}
```

响应：`TaskDetailResponse`

### 1.2 批量重试
```http
POST /api/v1/tasks/retry-batch
Content-Type: application/json

{
  "task_ids": ["task-1", "task-2", "task-3"]
}
```

响应：`TaskBatchRetryResponse`
说明：每个任务仅从失败节点恢复，不执行“全部失败阶段重置”。

## 2. Schema
```python
class TaskRetryFromStageRequest(BaseModel):
    stage_id: str

class TaskBatchRetryRequest(BaseModel):
    task_ids: List[str]

class TaskBatchRetryItem(BaseModel):
    task_id: str
    success: bool
    reason: Optional[str] = None
    task: Optional[TaskDetailResponse] = None

class TaskBatchRetryResponse(BaseModel):
    total: int
    succeeded: int
    failed: int
    items: List[TaskBatchRetryItem]
```

## 3. 服务签名
```python
class TaskService:
    async def retry_from_stage(self, task_id: str, stage_id: str) -> Optional[TaskDetailResponse]: ...
    async def retry_batch(self, task_ids: List[str]) -> TaskBatchRetryResponse: ...
```

## 4. 规则
1. `retry_from_stage` 仅在 task.status=`failed` 且目标阶段 status=`failed` 时执行。
2. `retry_from_stage` 只重置目标失败阶段；其他阶段保持原状（已完成阶段不回滚）。
3. 阶段重置字段：`status/error_message/failure_category/started_at/completed_at/duration/tokens/output`。
4. `retry_batch` 对每个任务采用“失败节点重试”语义（仅重置一个失败节点，默认按模板顺序最早失败节点）。
5. 重试计数达到上限时返回失败原因，不执行重置。
