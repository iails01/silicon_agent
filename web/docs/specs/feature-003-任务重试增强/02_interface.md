# Feature-003 任务重试增强（前端）- 接口与数据结构

## 1. 后端接口契约（对齐 platform Spec）

### 1.1 从失败节点重试
```http
POST /api/v1/tasks/{task_id}/retry-from-stage
Content-Type: application/json

{
  "stage_id": "stage-2"
}
```
响应：`Task`（前端当前使用的任务详情模型）

### 1.2 批量重试
```http
POST /api/v1/tasks/retry-batch
Content-Type: application/json

{
  "task_ids": ["task-1", "task-2", "task-3"]
}
```
响应：`TaskBatchRetryResponse`
说明：每个任务按“失败节点重试”处理，仅重置一个失败节点（默认模板顺序最早失败节点），不是整任务全量失败阶段重试。

## 2. 前端类型签名（新增）
文件：`src/types/task.ts`

```ts
export interface TaskRetryFromStageRequest {
  stage_id: string;
}

export interface TaskBatchRetryRequest {
  task_ids: string[];
}

export interface TaskBatchRetryItem {
  task_id: string;
  success: boolean;
  reason?: string | null;
  task?: Task | null;
}

export interface TaskBatchRetryResponse {
  total: number;
  succeeded: number;
  failed: number;
  items: TaskBatchRetryItem[];
}
```

## 3. Service 签名（新增）
文件：`src/services/taskApi.ts`

```ts
export async function retryTaskFromStage(
  id: string,
  req: TaskRetryFromStageRequest,
): Promise<Task>

export async function retryTasksBatch(
  req: TaskBatchRetryRequest,
): Promise<TaskBatchRetryResponse>
```

## 4. Hook 签名（新增）
文件：`src/hooks/useTasks.ts`

```ts
export function useRetryTaskFromStage()
export function useBatchRetryTasks()
```

### 4.1 缓存失效约束
- `useRetryTaskFromStage` 成功后至少失效：
  - `['task', id]`
  - `['tasks']`
  - `['cockpit']`
- `useBatchRetryTasks` 成功后至少失效：
  - `['tasks']`
  - `['cockpit']`

## 5. 页面交互接口

### 5.1 TaskDetail 页面调用
- 调用：`retryTaskFromStage(task.id, { stage_id: stage.id })`
- 触发点：失败阶段“执行报告”区域与阶段失败操作区。
- 语义约束：只允许 stage 级重试，不允许回退为 `POST /tasks/{task_id}/retry` 的整任务重试语义。

### 5.2 TaskList 页面调用
- 调用：`retryTasksBatch({ task_ids })`
- `task_ids` 来源：表格选中项中过滤 `status === 'failed'`。
- 语义约束：批量中的每个任务均按“失败节点重试”处理，不触发整任务全量重试。

## 6. Mock 数据

### 6.1 retry-from-stage 成功
请求：
```json
{
  "stage_id": "stg_code"
}
```
响应（节选）：
```json
{
  "id": "task_1001",
  "status": "pending",
  "stages": [
    { "id": "stg_code", "status": "pending", "retry_count": 2 }
  ]
}
```

### 6.2 retry-from-stage 失败
```json
{
  "detail": "Target stage status is not failed"
}
```

### 6.3 retry-batch 混合结果
请求：
```json
{
  "task_ids": ["task_1", "task_2", "task_3"]
}
```
说明：`success=true` 表示该任务已按“失败节点重试”提交，不代表全阶段重置。
响应：
```json
{
  "total": 3,
  "succeeded": 2,
  "failed": 1,
  "items": [
    { "task_id": "task_1", "success": true },
    { "task_id": "task_2", "success": false, "reason": "task status is running" },
    { "task_id": "task_3", "success": true }
  ]
}
```
