# Feature-001 任务管线详情历史功能 - 接口与数据结构

## 1. 技术栈（现状）
- 前端框架：React + TypeScript
- UI 组件：Ant Design / Pro Components
- 数据请求与缓存：TanStack Query
- 状态管理：Zustand
- 实时通道：WebSocket
- Markdown 渲染：react-markdown + remark-gfm

## 2. 关键类型签名（原样）

## 2.1 任务与阶段
文件：`src/types/task.ts`

```ts
export interface StageOutputStructured {
  summary: string;
  status: 'pass' | 'fail' | 'partial';
  confidence: number;
  artifacts: string[];
  metadata: Record<string, unknown>;
  [key: string]: unknown;
}

export interface TaskStage {
  id: string;
  task_id: string;
  stage_name: string;
  agent_role: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  tokens_used: number;
  turns_used: number;
  output_summary: string | null;
  error_message: string | null;
  output_structured: StageOutputStructured | null;
  failure_category: string | null;
  self_assessment_score: number | null;
  retry_count: number;
}

export interface Task {
  id: string;
  jira_id: string | null;
  title: string;
  description: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled' | 'planning';
  created_at: string;
  completed_at: string | null;
  stages: TaskStage[];
  total_tokens: number;
  total_cost_rmb: number;
  template_id: string | null;
  project_id: string | null;
  template_name: string | null;
  project_name: string | null;
  target_branch: string | null;
  yunxiao_task_id: string | null;
}
```

## 2.2 Gate
文件：`src/types/gate.ts`

```ts
export interface Gate {
  id: string;
  gate_type: string;
  task_id: string;
  agent_role: string;
  content: Record<string, string> | null;
  status: 'pending' | 'approved' | 'rejected' | 'revised';
  reviewer: string | null;
  review_comment: string | null;
  created_at: string;
  reviewed_at: string | null;
  retry_count?: number;
  is_dynamic?: boolean;
  revised_content?: string | null;
}
```

## 2.3 任务日志
文件：`src/services/taskLogApi.ts`

```ts
export interface TaskLogEvent {
  id: string;
  task_id: string;
  stage_id: string | null;
  stage_name: string;
  agent_role: string | null;
  correlation_id: string | null;
  event_seq: number;
  event_type: string;
  event_source: 'llm' | 'tool' | string;
  status: string;
  request_body: Record<string, unknown> | null;
  response_body: Record<string, unknown> | null;
  command: string | null;
  command_args: Record<string, unknown> | null;
  workspace: string | null;
  execution_mode: 'sandbox' | 'in_process' | null;
  duration_ms: number | null;
  result: string | null;
  output_summary: string | null;
  output_truncated: boolean;
  missing_fields: string[];
  created_at: string;
}
```

## 2.4 WebSocket
文件：`src/types/websocket.ts`

```ts
export type WSMessageType =
  | 'agent_status'
  | 'activity'
  | 'task_update'
  | 'stage_log'
  | 'gate_created'
  | 'gate_resolved'
  | 'task_log_stream'
  | 'pong';

export interface WSStageLogPayload {
  task_id: string;
  stage_id: string;
  stage_name: string;
  event_type: string;
  event_source: string;
  status: string;
  command?: string;
  duration_ms?: number;
  result_preview?: string;
  timestamp: string;
}

export interface WSTaskLogStreamPayload {
  task_id: string;
  stage_id: string;
  stage_name: string;
  log_id: string;
  tool_call_id: string;
  chunk: string;
  finished: boolean;
  status?: string;
}
```

## 3. 关键接口签名（原样）

### 3.1 Task API
文件：`src/services/taskApi.ts`

```ts
export async function getTask(id: string): Promise<Task>
export async function getTaskStages(id: string): Promise<TaskStage[]>
export async function cancelTask(id: string): Promise<void>
export async function retryTask(id: string): Promise<void>
```

### 3.2 Task Log API
文件：`src/services/taskLogApi.ts`

```ts
export async function listTaskLogs(params: {
  task: string;
  task_id?: string;
  stage?: string;
  event_source?: string;
  page?: number;
  page_size?: number;
}): Promise<TaskLogListResponse>
```

### 3.3 Gate API
文件：`src/services/gateApi.ts`

```ts
export async function listGates(params?: {
  status?: string;
  task_id?: string;
}): Promise<Gate[]>
```

## 4. Mock 数据（关键接口）

### 4.1 `GET /tasks/{id}`
```json
{
  "id": "task_01",
  "title": "实现任务管线详情页",
  "description": "展示阶段进度与推演日志",
  "status": "running",
  "created_at": "2026-02-28T10:00:00Z",
  "completed_at": null,
  "total_tokens": 15234,
  "total_cost_rmb": 12.8,
  "template_name": "默认研发模板",
  "project_name": "silicon_agent",
  "target_branch": "feature/task-detail",
  "stages": [
    {
      "id": "stg_parse",
      "task_id": "task_01",
      "stage_name": "parse",
      "agent_role": "orchestrator",
      "status": "completed",
      "started_at": "2026-02-28T10:00:10Z",
      "completed_at": "2026-02-28T10:00:30Z",
      "duration_seconds": 20,
      "tokens_used": 640,
      "turns_used": 2,
      "output_summary": "需求拆解完成",
      "error_message": null,
      "output_structured": { "summary": "ok", "status": "pass", "confidence": 0.92, "artifacts": [], "metadata": {} },
      "failure_category": null,
      "self_assessment_score": 0.9,
      "retry_count": 0
    }
  ]
}
```

### 4.2 `GET /task-logs?task=...&stage=...`
```json
{
  "items": [
    {
      "id": "log_01",
      "task_id": "task_01",
      "stage_id": "stg_code",
      "stage_name": "code",
      "agent_role": "coding",
      "correlation_id": "corr_01",
      "event_seq": 12,
      "event_type": "llm_turn_received",
      "event_source": "llm",
      "status": "success",
      "request_body": { "prompt": "实现接口" },
      "response_body": { "content": "<thought>先补齐类型</thought>" },
      "command": null,
      "command_args": null,
      "workspace": "/workspace",
      "execution_mode": "sandbox",
      "duration_ms": 2800,
      "result": null,
      "output_summary": null,
      "output_truncated": false,
      "missing_fields": [],
      "created_at": "2026-02-28T10:01:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 500
}
```

### 4.3 `GET /gates?task_id=...`
```json
{
  "items": [
    {
      "id": "gate_01",
      "gate_type": "plan_review",
      "task_id": "task_01",
      "agent_role": "spec",
      "content": { "stage": "spec" },
      "status": "pending",
      "reviewer": null,
      "review_comment": null,
      "created_at": "2026-02-28T10:02:00Z",
      "reviewed_at": null
    }
  ],
  "total": 1
}
```

### 4.4 WebSocket `stage_log`
```json
{
  "type": "stage_log",
  "payload": {
    "task_id": "task_01",
    "stage_id": "stg_code",
    "stage_name": "code",
    "event_type": "tool_call_executed",
    "event_source": "tool",
    "status": "running",
    "command": "npm test",
    "duration_ms": 1200,
    "result_preview": "Running tests...",
    "timestamp": "2026-02-28T10:03:00Z"
  },
  "timestamp": "2026-02-28T10:03:00Z"
}
```

### 4.5 WebSocket `task_log_stream`
```json
{
  "type": "task_log_stream",
  "payload": {
    "task_id": "task_01",
    "stage_id": "stg_code",
    "stage_name": "code",
    "log_id": "log_02",
    "tool_call_id": "tool_01",
    "chunk": "正在分析失败用例...",
    "finished": false,
    "status": "running"
  },
  "timestamp": "2026-02-28T10:03:02Z"
}
```
