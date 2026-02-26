import React, { useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Card, Collapse, Descriptions, Empty, Tag, Button, Spin, Typography, Space, message, Timeline, Tabs } from 'antd';
import { ArrowLeftOutlined, StopOutlined, ReloadOutlined, CodeOutlined, RobotOutlined, LoadingOutlined } from '@ant-design/icons';
import { useTask, useCancelTask, useRetryTask } from '@/hooks/useTasks';
import { useStageLogStore } from '@/stores/stageLogStore';
import { listTaskLogs } from '@/services/taskLogApi';
import PipelineView from '@/components/PipelineView';
import ReActTimeline from '@/components/ReActTimeline';
import { STAGE_NAMES } from '@/utils/constants';
import { formatTimestamp, formatTokens, formatCost, formatDuration } from '@/utils/formatters';

const { Title } = Typography;

const STATUS_COLOR: Record<string, string> = {
  pending: 'default',
  running: 'processing',
  completed: 'success',
  failed: 'error',
  cancelled: 'warning',
  skipped: 'default',
};

const STAGE_DISPLAY: Record<string, string> = Object.fromEntries(
  STAGE_NAMES.map((sn) => [sn.key, sn.name])
);

const EVENT_ICONS: Record<string, React.ReactNode> = {
  tool_call_executed: <CodeOutlined style={{ color: '#1890ff' }} />,
  llm_response_received: <RobotOutlined style={{ color: '#52c41a' }} />,
  llm_request_sent: <LoadingOutlined style={{ color: '#faad14' }} />,
};

const EMPTY_LOGS: import('@/types/websocket').WSStageLogPayload[] = [];

const StageLiveLog: React.FC<{ stageId: string }> = ({ stageId }) => {
  const logs = useStageLogStore((s) => s.logsByStage[stageId] ?? EMPTY_LOGS);
  const containerRef = useRef<HTMLDivElement>(null);
  const logCount = logs.length;

  useEffect(() => {
    const el = containerRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [logCount]);

  if (logCount === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '24px 0' }}>
        <LoadingOutlined style={{ fontSize: 24, marginBottom: 8 }} />
        <div style={{ color: '#999' }}>等待执行日志...</div>
      </div>
    );
  }

  return (
    <div ref={containerRef} style={{ maxHeight: 400, overflow: 'auto', padding: '0 8px' }}>
      <Timeline
        items={logs.map((log, i) => ({
          key: i,
          dot: EVENT_ICONS[log.event_type] || EVENT_ICONS.llm_request_sent,
          children: (
            <div style={{ fontSize: 13 }}>
              <div>
                <Tag color={log.status === 'success' ? 'green' : log.status === 'failed' ? 'red' : 'blue'} style={{ fontSize: 11 }}>
                  {log.event_source}
                </Tag>
                <span style={{ fontWeight: 500 }}>{log.command || log.event_type}</span>
                {log.duration_ms != null && (
                  <span style={{ color: '#999', marginLeft: 8 }}>{(log.duration_ms / 1000).toFixed(1)}s</span>
                )}
              </div>
              {log.result_preview && (
                <pre style={{ marginTop: 4, marginBottom: 0, fontSize: 12, color: '#666', whiteSpace: 'pre-wrap', maxHeight: 80, overflow: 'hidden' }}>
                  {log.result_preview}
                </pre>
              )}
            </div>
          ),
        }))}
      />
    </div>
  );
};

const StageReActDetails: React.FC<{ taskId: string; stageId: string; stageName: string; isRunning: boolean }> = ({ taskId, stageId, stageName, isRunning }) => {
  const liveLogs = useStageLogStore((s) => s.logsByStage[stageId] ?? EMPTY_LOGS);

  // Fetch historical logs for this stage
  const { data, isLoading } = useQuery({
    queryKey: ['taskLogs', taskId, stageName],
    queryFn: () => listTaskLogs({ task: taskId, stage: stageName, page_size: 500 }),
    enabled: !!taskId && !!stageName,
    refetchInterval: isRunning ? 3000 : false, // Poll if still running to get the latest DB state
  });

  const historicalLogs = data?.items || [];

  // Merge: Since our ReActTimeline handles all event types natively based on correlation mapping,
  // we mainly rely on historicalLogs (DB state) which is richer.
  // The 'liveLogs' from WebSocket are simpler StageLogPayloads. 
  // In a robust implementation, we'd map WS to TaskLogEvents, but since we poll when running,
  // passing historicalLogs covers most of the ReAct rendering nicely.

  return <ReActTimeline logs={historicalLogs} loading={isLoading} />;
};

const TaskDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: task, isLoading } = useTask(id!);
  const cancelTask = useCancelTask();
  const retryTask = useRetryTask();

  if (isLoading || !task) {
    return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  }

  const duration = task.created_at && task.completed_at
    ? (new Date(task.completed_at).getTime() - new Date(task.created_at).getTime()) / 1000
    : null;

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/tasks')}>
          Back
        </Button>
        {(task.status === 'running' || task.status === 'pending') && (
          <Button
            danger
            icon={<StopOutlined />}
            onClick={async () => {
              await cancelTask.mutateAsync(task.id);
              message.success('Task cancelled');
            }}
            loading={cancelTask.isPending}
          >
            Cancel Task
          </Button>
        )}
        {task.status === 'failed' && (
          <Button
            type="primary"
            icon={<ReloadOutlined />}
            onClick={async () => {
              await retryTask.mutateAsync(task.id);
              message.success('任务已重新提交，将从失败阶段继续执行');
            }}
            loading={retryTask.isPending}
          >
            重试任务
          </Button>
        )}
      </Space>

      <Title level={4}>{task.title}</Title>

      <Card style={{ marginBottom: 16 }}>
        <PipelineView stages={task.stages} />
      </Card>

      {task.stages.length > 0 && (
        <Card title="阶段产出" style={{ marginBottom: 16 }}>
          <Collapse accordion>
            {task.stages.map((stage) => (
              <Collapse.Panel
                key={stage.id}
                header={
                  <Space>
                    <Tag color={STATUS_COLOR[stage.status]}>{stage.status}</Tag>
                    <span>{STAGE_DISPLAY[stage.stage_name] || stage.stage_name}</span>
                    <span style={{ color: '#999' }}>
                      {stage.tokens_used > 0 && `${stage.tokens_used.toLocaleString()} tokens`}
                      {stage.duration_seconds != null && ` · ${stage.duration_seconds.toFixed(1)}s`}
                    </span>
                  </Space>
                }
              >
                <Tabs
                  defaultActiveKey="react"
                  items={[
                    {
                      key: 'react',
                      label: '推演过程 (ReAct Track)',
                      children: (
                        <StageReActDetails
                          taskId={task.id}
                          stageId={stage.id}
                          stageName={stage.stage_name}
                          isRunning={stage.status === 'running'}
                        />
                      ),
                    },
                    {
                      key: 'output',
                      label: '阶段产出结果',
                      children: stage.output_summary ? (
                        <Typography.Paragraph style={{ whiteSpace: 'pre-wrap', padding: 16 }}>
                          {stage.output_summary}
                        </Typography.Paragraph>
                      ) : stage.error_message ? (
                        <div style={{ padding: 16 }}>
                          <Typography.Text type="danger">{stage.error_message}</Typography.Text>
                          {task.status === 'failed' && (
                            <div style={{ marginTop: 12 }}>
                              <Button
                                type="primary"
                                size="small"
                                icon={<ReloadOutlined />}
                                onClick={async () => {
                                  await retryTask.mutateAsync(task.id);
                                  message.success('任务已重新提交，将从失败阶段继续执行');
                                }}
                                loading={retryTask.isPending}
                              >
                                从此阶段重试
                              </Button>
                            </div>
                          )}
                        </div>
                      ) : (
                        <Empty description="暂无产出摘要 (任务可能正在运行或未生成摘要)" style={{ marginTop: 32 }} />
                      ),
                    },
                  ]}
                />
              </Collapse.Panel>
            ))}
          </Collapse>
        </Card>
      )}

      <Card title="Task Details" style={{ marginBottom: 16 }}>
        <Descriptions column={2}>
          <Descriptions.Item label="ID">{task.id}</Descriptions.Item>
          <Descriptions.Item label="Status">
            <Tag color={STATUS_COLOR[task.status]}>{task.status}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Template">{task.template_name || '-'}</Descriptions.Item>
          <Descriptions.Item label="Project">{task.project_name || '-'}</Descriptions.Item>
          <Descriptions.Item label="Created At">{formatTimestamp(task.created_at)}</Descriptions.Item>
          <Descriptions.Item label="Completed At">{task.completed_at ? formatTimestamp(task.completed_at) : '-'}</Descriptions.Item>
          <Descriptions.Item label="Duration">{duration != null ? formatDuration(duration) : '-'}</Descriptions.Item>
          <Descriptions.Item label="Total Tokens">{formatTokens(task.total_tokens)}</Descriptions.Item>
          <Descriptions.Item label="Total Cost">{formatCost(task.total_cost_rmb)}</Descriptions.Item>
        </Descriptions>
      </Card>

      <Card title="Description">
        <Typography.Paragraph>{task.description}</Typography.Paragraph>
      </Card>
    </div>
  );
};

export default TaskDetail;
