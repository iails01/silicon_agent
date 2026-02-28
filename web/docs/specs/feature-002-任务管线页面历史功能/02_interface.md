# Feature-002 任务管线页面历史功能 - 接口与数据结构

## 1. 技术栈（现状）
- React + TypeScript
- Ant Design + ProTable
- TanStack Query（页面请求通过 ProTable `request` + service）

## 2. 关键类型签名（原样）

## 2.1 任务类型
文件：`src/types/task.ts`

```ts
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

export interface TaskCreateRequest {
  title: string;
  description: string;
  template_id?: string;
  project_id?: string;
  target_branch: string;
  yunxiao_task_id?: string;
}

export interface TaskDecomposeRequest {
  prd_text: string;
  project_id?: string;
  template_id?: string;
}

export interface DecomposedTask {
  title: string;
  description: string;
  priority: string;
}

export interface TaskDecomposeResponse {
  tasks: DecomposedTask[];
  summary: string;
  tokens_used: number;
}

export interface BatchTaskItem {
  title: string;
  description?: string;
  template_id?: string;
  project_id?: string;
  target_branch: string;
  yunxiao_task_id?: string;
}

export interface TaskBatchCreateRequest {
  tasks: BatchTaskItem[];
}

export interface TaskBatchCreateResponse {
  created: number;
  tasks: Task[];
}
```

## 2.2 模板与项目类型
文件：`src/types/template.ts`, `src/types/project.ts`

```ts
export interface TaskTemplate {
  id: string;
  name: string;
  display_name: string;
  description: string | null;
  stages: StageDefinition[];
  gates: GateDefinition[];
  is_builtin: boolean;
  created_at: string;
  updated_at: string;
}

export interface Project {
  id: string;
  name: string;
  display_name: string;
  repo_url: string | null;
  branch: string;
  description: string | null;
  status: 'active' | 'archived';
  tech_stack: string[] | null;
  repo_tree: string | null;
  last_synced_at: string | null;
  created_at: string;
  updated_at: string;
}
```

## 3. 关键接口签名（原样）
文件：`src/services/taskApi.ts`

```ts
export async function listTasks(params?: {
  status?: string;
  page?: number;
  page_size?: number;
  start_date?: string;
  end_date?: string;
  project_id?: string;
  title?: string;
}): Promise<TaskListResponse>

export async function createTask(req: TaskCreateRequest): Promise<Task>

export async function decomposePrd(req: TaskDecomposeRequest): Promise<TaskDecomposeResponse>

export async function batchCreateTasks(req: TaskBatchCreateRequest): Promise<TaskBatchCreateResponse>
```

文件：`src/services/templateApi.ts`, `src/services/projectApi.ts`

```ts
export async function listTemplates(): Promise<TemplateListResponse>

export async function listProjects(params?: {
  page?: number;
  page_size?: number;
  status?: string;
  name?: string;
}): Promise<ProjectListResponse>
```

## 4. Mock 数据（关键接口）

### 4.1 `GET /tasks`
```json
{
  "items": [
    {
      "id": "task_1001",
      "title": "登录模块重构",
      "description": "补齐 OAuth2 与审计日志",
      "status": "running",
      "created_at": "2026-02-28T09:00:00Z",
      "completed_at": null,
      "total_tokens": 24800,
      "total_cost_rmb": 21.3,
      "template_name": "默认研发模板",
      "project_name": "web-console",
      "yunxiao_task_id": "silicon_agent"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

### 4.2 `POST /tasks`
请求：
```json
{
  "title": "新增任务列表筛选",
  "description": "支持按状态与项目过滤",
  "template_id": "tpl_default",
  "project_id": "proj_web",
  "target_branch": "feature/task-filter",
  "yunxiao_task_id": "silicon_agent"
}
```

响应（示例）：
```json
{
  "id": "task_2001",
  "title": "新增任务列表筛选",
  "status": "pending",
  "target_branch": "feature/task-filter",
  "created_at": "2026-02-28T09:30:00Z"
}
```

### 4.3 `POST /tasks/decompose`
请求：
```json
{
  "prd_text": "用户登录模块需求：支持邮箱登录、OAuth2、密码重置",
  "project_id": "proj_web",
  "template_id": "tpl_default"
}
```

响应：
```json
{
  "summary": "识别出 3 个子任务，建议并行 2 条实现线",
  "tokens_used": 1800,
  "tasks": [
    {
      "title": "实现邮箱密码登录",
      "description": "含输入校验、错误提示、登录态写入",
      "priority": "high"
    },
    {
      "title": "接入 OAuth2 登录",
      "description": "接入 Google/GitHub，统一回调处理",
      "priority": "medium"
    }
  ]
}
```

### 4.4 `POST /tasks/batch`
请求：
```json
{
  "tasks": [
    {
      "title": "实现邮箱密码登录",
      "description": "含输入校验、错误提示、登录态写入",
      "template_id": "tpl_default",
      "project_id": "proj_web",
      "target_branch": "feature/auth-upgrade",
      "yunxiao_task_id": "silicon_agent"
    }
  ]
}
```

响应：
```json
{
  "created": 1,
  "tasks": [
    {
      "id": "task_2101",
      "title": "实现邮箱密码登录",
      "status": "pending"
    }
  ]
}
```

### 4.5 `GET /templates`
```json
{
  "items": [
    {
      "id": "tpl_default",
      "name": "default",
      "display_name": "默认研发模板",
      "stages": [
        { "name": "parse", "agent_role": "orchestrator", "order": 1 },
        { "name": "code", "agent_role": "coding", "order": 2 }
      ],
      "gates": [],
      "is_builtin": true,
      "created_at": "2026-02-20T00:00:00Z",
      "updated_at": "2026-02-28T00:00:00Z"
    }
  ],
  "total": 1
}
```

### 4.6 `GET /projects`
```json
{
  "items": [
    {
      "id": "proj_web",
      "name": "web",
      "display_name": "Web Console",
      "repo_url": "git@github.com:org/web-console.git",
      "branch": "main",
      "status": "active",
      "created_at": "2026-02-01T00:00:00Z",
      "updated_at": "2026-02-28T00:00:00Z"
    }
  ],
  "total": 1
}
```
