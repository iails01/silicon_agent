# Feature-002 任务管线页面历史功能 - 实现逻辑

## 1. 页面入口与结构
文件：`src/pages/Tasks/index.tsx`

1. 主体：`ProTable<Task>` 渲染任务列表。
2. 工具栏：`New Task` 按钮打开创建向导 `Modal`。
3. 向导：按 `step` 渲染不同内容，支持单任务创建与 PRD 拆解批量创建。

## 2. 列表查询逻辑

### 2.1 表格字段
- ID：显示短 ID，点击跳转 `/tasks/:id`。
- Title
- Yunxiao ID
- Template
- Project
- Status（颜色标签 + 筛选）
- Tokens
- Cost
- Created（显示创建时间）

### 2.2 请求逻辑
- `ProTable.request` 内调用 `listTasks`。
- 当前透传参数：
  - `status -> params.status`
  - `page -> params.current`
  - `page_size -> params.pageSize`
- 返回格式：`{ data, total, success: true }`。

## 3. 新建任务向导逻辑

### 3.1 状态机
- `wizardOpen`：弹窗开关。
- `step`：
  - `0` 选择模式
  - `1` 填写输入
  - `2` 仅 PRD 模式下的“预览与编辑”
- `createMode`：`single | prd`

### 3.2 Single 模式
- 输入项：`title`、`description`、`template_id`、`project_id`、`target_branch`。
- 校验：`target_branch` 必填。
- 提交：`createTask({...})`。
- 成功：提示 + 刷新列表 + 关闭向导。

### 3.3 PRD 模式
- 输入项：`prd_text`、`project_id`、`template_id`、`target_branch`。
- Step 1：调用 `decomposePrd`，返回 `summary + tasks`。
- Step 2：
  - 支持对子任务 `title/description` 编辑。
  - 支持删除与新增子任务。
  - 提交时调用 `batchCreateTasks`。
- 批量创建前校验：
  - 子任务数量 > 0。
  - `target_branch` 必填。

### 3.4 重置机制
- `resetWizard()` 在打开和关闭弹窗时都会执行：
  - 重置步骤、模式、所有表单字段、拆解结果、loading 状态。

## 4. 依赖数据加载
- 模板数据：`useTemplateList()` -> `listTemplates()`。
- 项目数据：`useProjectList()` -> `listProjects()`。
- 页面将模板/项目转换为 `<select>` options。
- 当选择模板时展示阶段预览：`Stages: ...`（通过 `STAGE_NAMES` 映射中文名）。

## 5. 关键签名（原样）

```ts
// src/pages/Tasks/index.tsx
const TaskList: React.FC

// src/services/taskApi.ts
export async function listTasks(...): Promise<TaskListResponse>
export async function createTask(req: TaskCreateRequest): Promise<Task>
export async function decomposePrd(req: TaskDecomposeRequest): Promise<TaskDecomposeResponse>
export async function batchCreateTasks(req: TaskBatchCreateRequest): Promise<TaskBatchCreateResponse>

// src/hooks/useTemplates.ts
export function useTemplateList()

// src/hooks/useProjects.ts
export function useProjectList(params?: { page?: number; page_size?: number; status?: string; name?: string })
```

## 6. 已知边界（现状）
- `Created` 列定义为 `dateRange`，但请求层当前仅透传 `status/page/page_size`，时间区间暂未真正参与后端过滤。
- `title/description` 在 single 模式 UI 标注为必填，但当前仅对 `target_branch` 做前端校验。
- `yunxiao_task_id` 在 UI 中固定为 `silicon_agent`，未暴露编辑入口。
- PRD 拆解后的 `priority` 仅展示，不支持页面内修改。

## 7. 后续维护建议（文档层）
- 若补齐任务检索字段透传（title/project/date range），需更新本 Feature 的接口与实现文档。
- 若向导改为统一 Form 校验或增加模板规则校验，需在 `01_requirements.md` 同步验收标准。
