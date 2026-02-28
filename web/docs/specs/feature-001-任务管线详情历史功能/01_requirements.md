# Feature-001 任务管线详情历史功能

## 1. 文档定位
- 类型：历史功能梳理（As-Is）
- 范围：仅整理当前已上线能力，不新增业务逻辑
- 页面：`/tasks/:id`（任务详情页）

## 2. 背景与目标
任务管线详情页是任务执行可观测性的核心入口，承载以下目标：
- 展示任务在多阶段管线中的执行进度与状态。
- 展示阶段级产出、ReAct 推演过程、实时日志与错误信息。
- 在需要人工审批（Gate）时提供阻塞态提示与跳转能力。
- 支持任务取消与失败后重试。

## 3. 用户故事（历史能力）
1. 作为研发/运营人员，我希望看到任务整体阶段进度，以便快速判断任务卡在哪个阶段。
2. 作为审批人员，我希望在阶段被 Gate 阻塞时看到明确提示，并能一键跳转审批中心。
3. 作为排障人员，我希望查看阶段的 ReAct 过程与工具执行结果，以定位失败原因。
4. 作为执行人，我希望在任务失败后可从失败阶段触发重试，减少重复执行成本。
5. 作为观察者，我希望看到任务级统计信息（耗时、Token、成本、分支等）评估执行质量。

## 4. 功能范围（已实现）
- 任务基础信息展示：标题、状态、模板、项目、分支、创建/完成时间、总耗时、Token、成本、描述。
- 管线进度条展示：阶段名映射、状态映射、当前运行阶段定位。
- 阶段折叠面板：
  - 阶段状态、Token、耗时。
  - Gate 状态卡片（pending/approved/rejected/revised）与审批跳转。
  - 结构化产出徽章（status/confidence/tests/issues/artifacts）。
  - 失败分类、重试次数。
  - ReAct Track（历史日志 + 运行中轮询）。
  - 执行报告（Markdown 折叠/展开、错误提示、跳过提示、空态）。
- 实时能力：
  - `stage_log` WebSocket 事件进入阶段日志 store。
  - `task_log_stream` WebSocket 事件进入流式日志 store，用于 ReAct 运行态补全。
- 操作能力：
  - 运行中任务可取消。
  - 失败任务可重试。

## 5. 非目标
- 不包含任务创建流程（单任务/PRD 分解）的需求定义。
- 不包含审批中心页面（`/gates`）完整交互定义。
- 不包含后端 API 协议变更。

## 6. 文件路径
### 6.1 本次文档新增
- `docs/specs/feature-001-任务管线详情历史功能/01_requirements.md`
- `docs/specs/feature-001-任务管线详情历史功能/02_interface.md`
- `docs/specs/feature-001-任务管线详情历史功能/03_implementation.md`

### 6.2 现有实现涉及文件（只读梳理）
- `src/pages/Tasks/TaskDetail.tsx`
- `src/components/PipelineView.tsx`
- `src/components/ReActTimeline/index.tsx`
- `src/components/ReActTimeline/styles.css`
- `src/hooks/useTasks.ts`
- `src/hooks/useGates.ts`
- `src/hooks/useWebSocket.ts`
- `src/services/taskApi.ts`
- `src/services/taskLogApi.ts`
- `src/services/gateApi.ts`
- `src/stores/stageLogStore.ts`
- `src/stores/taskLogStreamStore.ts`
- `src/types/task.ts`
- `src/types/gate.ts`
- `src/types/websocket.ts`
- `src/utils/constants.ts`

## 7. 签名（历史能力，无新增）
本次为历史梳理，不新增/修改签名。现有关键签名见 `02_interface.md`。

## 8. 验收标准（文档）
- 覆盖任务管线详情当前核心能力与状态流转。
- 包含关键文件路径、关键签名、关键接口 Mock 数据。
- 可供后续新需求对比“现状（As-Is）/目标（To-Be）”。
