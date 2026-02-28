# Feature-001 任务管线详情历史功能 - 实现逻辑

## 1. 页面结构
文件：`src/pages/Tasks/TaskDetail.tsx`

1. 顶部操作区：返回、取消任务、重试任务。
2. 管线总览区：`<PipelineView stages={...} />`。
3. 阶段产出区：按阶段渲染 `Collapse.Panel`，每个阶段含两类 Tab：
   - 推演过程（ReAct Track）
   - 执行报告
4. 任务详情区：`Descriptions` 展示任务元信息。
5. 描述区：原始任务描述。

## 2. 核心流程

### 2.1 任务数据加载与刷新
- Hook：`useTask(id)`
- 行为：
  - 初次加载 `getTask(id)`。
  - 当任务状态为 `running` 时每 3 秒轮询。

### 2.2 管线步骤渲染
文件：`src/components/PipelineView.tsx`
- 状态映射：
  - `pending -> wait`
  - `running -> process`
  - `completed -> finish`
  - `failed -> error`
  - `skipped -> wait`
- 当前步骤定位：取首个 `running` 阶段索引作为 `current`。
- 回退逻辑：若 `stages` 为空，使用 `STAGE_NAMES` 渲染默认步骤。

### 2.3 Gate 关联与展示
- 数据来源：`useGateList({ task_id: id })`
- 匹配逻辑：按 `gate.content?.stage === stage.stage_name` 过滤并取最新 `created_at`。
- UI 规则：
  - `pending` 时阶段头部显示“等待审批”。
  - `approved/rejected/revised` 显示结果态与跳转链接。
  - 为避免重试后旧审批误导：当 gate 非 pending 且 stage 仍 pending 时不展示历史 gate 结果。

### 2.4 ReAct Track
- 组件：`src/components/ReActTimeline/index.tsx`
- 数据：`listTaskLogs({ task, stage, page_size: 500 })`
- 运行态：阶段运行中每 3 秒轮询日志。
- 解析策略：按 `correlation_id`/`id` 聚合 turn，识别 prompt/thought/action/observation。
- 流式补全：
  - 当 `thought_sent` 为 running 且无最终 thought 时，订阅 `task_log_stream`。
  - `taskLogStreamStore` 将 chunk 追加并维护状态。

### 2.5 执行报告区
- 有 `output_summary`：Markdown 展示，超高可折叠展开。
- 有 `error_message`：展示错误，并在任务失败时提供“从此阶段重试”。
- 阶段 `running`：展示 `StageLiveLog`（来自 stage log store）。
- 阶段 `skipped`：展示“条件不满足，阶段已跳过”。
- 其他：空态“暂无产出摘要”。

## 3. 实时链路

### 3.1 WebSocket 入口
文件：`src/hooks/useWebSocket.ts`
- `stage_log` -> `useStageLogStore.getState().addLog(sl)`
- `task_log_stream` -> `useTaskLogStreamStore.append(payload, timestamp)`
- `task_update` -> 失效 `['task', id]`、`['tasks']`、`['cockpit']`、`['kpi-summary']`

### 3.2 Store 约束
- `stageLogStore`
  - 每阶段最多保留 200 条。
- `taskLogStreamStore`
  - 仅对订阅日志接收 chunk。
  - chunk 缓存上限 2000 行。
  - 根据 `status/finished` 维护流式状态。

## 4. 关键签名（原样）

```ts
// src/hooks/useTasks.ts
export function useTask(id: string)
export function useCancelTask()
export function useRetryTask()

// src/components/PipelineView.tsx
const PipelineView: React.FC<{ stages: TaskStage[] }>

// src/pages/Tasks/TaskDetail.tsx
const StageLiveLog: React.FC<{ stageId: string }>
const StageReActDetails: React.FC<{ taskId: string; stageId: string; stageName: string; isRunning: boolean }>
const TaskDetail: React.FC
```

## 5. 已知边界（现状）
- ReAct 渲染优先依赖历史日志接口，WebSocket 阶段日志主要用于报告区“运行中”展示。
- Gate 与 Stage 的绑定依赖 `gate.content.stage` 字段，后端字段语义变化会直接影响匹配结果。
- 阶段展示名称依赖 `STAGE_NAMES` 常量，若后端新增阶段名且未同步常量，页面会回退展示原始 `stage_name`。

## 6. 后续维护建议（文档层）
- 若未来改动任务详情交互或日志协议，应同步更新本 Feature 文档三件套。
- 若引入新的日志事件模型或审批编排策略，建议新增 ADR 记录演进与架构图。
