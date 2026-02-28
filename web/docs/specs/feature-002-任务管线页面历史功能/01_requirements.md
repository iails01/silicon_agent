# Feature-002 任务管线页面历史功能

## 1. 文档定位
- 类型：历史功能梳理（As-Is）
- 页面：`/tasks`（任务管线列表页）
- 范围：列表展示、筛选查询、新建任务向导（单任务/PRD 拆解）

## 2. 背景与目标
任务管线页面用于承载任务全局管理入口，核心目标：
- 快速查看任务池状态（进度、成本、创建时间）。
- 支持按状态过滤任务并进入任务详情。
- 支持通过向导创建任务：单任务直建或 PRD 智能拆解后批量创建。

## 3. 用户故事（历史能力）
1. 作为项目成员，我希望查看所有任务列表并按状态筛选，便于追踪执行进展。
2. 作为执行人，我希望一键进入任务详情页，定位具体阶段信息。
3. 作为需求方，我希望从单任务表单快速创建任务并指定目标分支。
4. 作为产品/架构角色，我希望粘贴 PRD 自动拆解子任务，再人工编辑后批量创建。

## 4. 功能范围（已实现）
- `ProTable` 任务列表：
  - 字段：ID、Title、Yunxiao ID、Template、Project、Status、Tokens、Cost、Created。
  - ID 列可跳转详情页 `/tasks/:id`。
  - Status 提供 valueEnum 过滤。
  - Created 列配置 dateRange 检索类型（当前请求未透传时间范围）。
- 新建任务入口：右上角 `New Task` 打开向导弹窗。
- 创建向导：
  - Step 0：选择模式（Single Task / PRD Smart Decompose）。
  - Step 1（Single）：填写标题、描述、模板、项目、目标分支，创建单任务。
  - Step 1（PRD）：输入 PRD、可选项目和模板、目标分支，调用 AI 拆解。
  - Step 2（PRD）：展示拆解结果，可编辑/删除/新增子任务，批量创建。
- 创建后行为：成功提示、刷新任务列表、关闭并重置向导。

## 5. 非目标
- 不覆盖任务详情页 `/tasks/:id` 的阶段级展示逻辑。
- 不覆盖审批中心与日志中心的独立交互。
- 不定义后端拆解策略与调度策略。

## 6. 文件路径
### 6.1 本次文档新增
- `docs/specs/feature-002-任务管线页面历史功能/01_requirements.md`
- `docs/specs/feature-002-任务管线页面历史功能/02_interface.md`
- `docs/specs/feature-002-任务管线页面历史功能/03_implementation.md`

### 6.2 现有实现涉及文件（只读梳理）
- `src/pages/Tasks/index.tsx`
- `src/services/taskApi.ts`
- `src/types/task.ts`
- `src/hooks/useTemplates.ts`
- `src/services/templateApi.ts`
- `src/types/template.ts`
- `src/hooks/useProjects.ts`
- `src/services/projectApi.ts`
- `src/types/project.ts`
- `src/utils/constants.ts`
- `src/utils/formatters.ts`

## 7. 签名（历史能力，无新增）
本次仅梳理已有实现，不新增签名；关键签名见 `02_interface.md`。

## 8. 验收标准（文档）
- 准确覆盖 `/tasks` 页面现有能力。
- 包含规约要求的文件路径、方法签名、关键接口 Mock 数据。
- 明确历史行为与边界，便于后续 To-Be 设计对照。
