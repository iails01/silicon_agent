import React, { useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, Collapse, Descriptions, Empty, Tag, Button, Spin, Typography, Space, message, Timeline } from 'antd';
import { ArrowLeftOutlined, StopOutlined, ReloadOutlined, CodeOutlined, RobotOutlined, LoadingOutlined } from '@ant-design/icons';
import { useTask, useCancelTask, useRetryTask } from '@/hooks/useTasks';
import { useStageLogStore } from '@/stores/stageLogStore';
import PipelineView from '@/components/PipelineView';
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
  planning: 'warning',
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
                {/* Phase 1.1: Structured output badges */}
                {stage.output_structured && (
                  <div style={{ marginBottom: 12 }}>
                    <Space wrap>
                      <Tag color={stage.output_structured.status === 'pass' ? 'green' : stage.output_structured.status === 'fail' ? 'red' : 'orange'}>
                        {stage.output_structured.status}
                      </Tag>
                      {stage.output_structured.confidence != null && (
                        <Tag color={stage.output_structured.confidence >= 0.7 ? 'green' : stage.output_structured.confidence >= 0.5 ? 'orange' : 'red'}>
                          信心: {Math.round(stage.output_structured.confidence * 100)}%
                        </Tag>
                      )}
                      {/* Stage-specific badges */}
                      {(stage.output_structured as Record<string, unknown>).tests_passed != null && (
                        <Tag color="green">通过: {String((stage.output_structured as Record<string, unknown>).tests_passed)}</Tag>
                      )}
                      {(stage.output_structured as Record<string, unknown>).tests_failed != null && Number((stage.output_structured as Record<string, unknown>).tests_failed) > 0 && (
                        <Tag color="red">失败: {String((stage.output_structured as Record<string, unknown>).tests_failed)}</Tag>
                      )}
                      {(stage.output_structured as Record<string, unknown>).issues_critical != null && Number((stage.output_structured as Record<string, unknown>).issues_critical) > 0 && (
                        <Tag color="red">Critical: {String((stage.output_structured as Record<string, unknown>).issues_critical)}</Tag>
                      )}
                      {(stage.output_structured as Record<string, unknown>).issues_major != null && Number((stage.output_structured as Record<string, unknown>).issues_major) > 0 && (
                        <Tag color="orange">Major: {String((stage.output_structured as Record<string, unknown>).issues_major)}</Tag>
                      )}
                      {stage.output_structured.artifacts && stage.output_structured.artifacts.length > 0 && (
                        <Tag>{stage.output_structured.artifacts.length} 文件</Tag>
                      )}
                    </Space>
                    {stage.output_structured.summary && (
                      <div style={{ marginTop: 4, color: '#666', fontSize: 13 }}>
                        {stage.output_structured.summary}
                      </div>
                    )}
                  </div>
                )}
                {/* Phase 1.2: Failure category badge */}
                {stage.failure_category && (
                  <Tag color="volcano" style={{ marginBottom: 8 }}>{stage.failure_category}</Tag>
                )}
                {/* Phase 2.5: Retry count */}
                {stage.retry_count > 0 && (
                  <Tag style={{ marginBottom: 8 }}>重试 {stage.retry_count}</Tag>
                )}
                {stage.output_summary ? (
                  <Typography.Paragraph style={{ whiteSpace: 'pre-wrap' }}>
                    {stage.output_summary}
                  </Typography.Paragraph>
                ) : stage.error_message ? (
                  <div>
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
                ) : stage.status === 'running' ? (
                  <StageLiveLog stageId={stage.id} />
                ) : stage.status === 'skipped' ? (
                  <div style={{ color: '#999', fontStyle: 'italic', textDecoration: 'line-through' }}>
                    条件不满足，阶段已跳过
                  </div>
                ) : (
                  <Empty description="暂无产出" />
                )}
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
