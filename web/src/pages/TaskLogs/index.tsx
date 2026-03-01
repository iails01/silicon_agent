import React, { useCallback, useEffect, useMemo, useState, useRef } from 'react';
import { Alert, Button, Card, Drawer, Form, Select, Space, Table, Tag, Typography, Tabs, Descriptions, Switch } from 'antd';
import { SyncOutlined } from '@ant-design/icons';
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table';
import { listTaskLogs, type TaskLogEvent } from '@/services/taskLogApi';
import { getTaskStages, listTasks } from '@/services/taskApi';
import { listProjects } from '@/services/projectApi';
import { useTaskLogStreamStore } from '@/stores/taskLogStreamStore';
import { formatTimestamp } from '@/utils/formatters';

const { Text } = Typography;

type QueryState = {
  project?: string;
  task: string;
  stage?: string;
  event_source?: string;
};

type SelectOption = {
  label: string;
  value: string;
};

const EVENT_SOURCE_OPTIONS = [
  { label: '全部', value: '' },
  { label: 'LLM', value: 'llm' },
  { label: 'Tool', value: 'tool' },
  { label: '系统', value: 'system' },
];

const AUTO_REFRESH_OPTIONS = [
  { label: '自动刷新: 关', value: 0 },
  { label: '3秒刷新', value: 3000 },
  { label: '5秒刷新', value: 5000 },
  { label: '10秒刷新', value: 10000 },
];

const STATUS_COLOR: Record<string, string> = {
  sent: 'processing',
  running: 'processing',
  success: 'green',
  failed: 'red',
  cancelled: 'orange',
};

const SOURCE_COLOR: Record<string, string> = {
  llm: 'blue',
  tool: 'purple',
  system: 'gold',
};

const TERMINAL_STREAM_STATUS = new Set(['success', 'failed', 'cancelled']);

// 辅助组件：带复制功能的代码/JSON展示块
const CodeBlock: React.FC<{ content: string; maxHeight?: number }> = ({ content, maxHeight = 400 }) => (
  <div style={{ position: 'relative', border: '1px solid #f0f0f0', borderRadius: 6, background: '#fafafa' }}>
    <div style={{ position: 'absolute', top: 8, right: 8, zIndex: 10 }}>
      <Typography.Text copyable={{ text: content }} />
    </div>
    <pre style={{ margin: 0, padding: '12px 36px 12px 12px', maxHeight, overflow: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontSize: 13 }}>
      {content}
    </pre>
  </div>
);

const TaskLogsPage: React.FC = () => {
  const [form] = Form.useForm<QueryState>();
  const [query, setQuery] = useState<QueryState | null>(null);
  const [rows, setRows] = useState<TaskLogEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [autoRefreshInterval, setAutoRefreshInterval] = useState<number>(0);

  const [projectOptions, setProjectOptions] = useState<SelectOption[]>([]);
  const [taskOptions, setTaskOptions] = useState<SelectOption[]>([]);
  const [projectLoading, setProjectLoading] = useState(false);
  const [taskLoading, setTaskLoading] = useState(false);
  const [stageOptions, setStageOptions] = useState<SelectOption[]>([]);
  const [stageLoading, setStageLoading] = useState(false);
  
  const [streamingLog, setStreamingLog] = useState<TaskLogEvent | null>(null);
  const streamPreRef = useRef<HTMLPreElement>(null);

  const taskValue = Form.useWatch('task', form);
  const projectValue = Form.useWatch('project', form);
  
  const linesByLog = useTaskLogStreamStore((s) => s.linesByLog);
  const statusByLog = useTaskLogStreamStore((s) => s.statusByLog);
  const subscribeStream = useTaskLogStreamStore((s) => s.subscribe);
  const unsubscribeStream = useTaskLogStreamStore((s) => s.unsubscribe);
  const clearStream = useTaskLogStreamStore((s) => s.clear);
  const setStreamStatus = useTaskLogStreamStore((s) => s.setStatus);

  const fetchLogs = useCallback(async (q: QueryState, nextPage: number, nextPageSize: number, hideLoading = false) => {
    if (!hideLoading) setLoading(true);
    setError('');
    try {
      const result = await listTaskLogs({
        task: q.task,
        stage: q.stage || undefined,
        event_source: q.event_source || undefined,
        page: nextPage,
        page_size: nextPageSize,
      });
      setRows(result.items);
      setTotal(result.total);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || '加载日志失败';
      setError(String(detail));
      if (!hideLoading) {
        setRows([]);
        setTotal(0);
      }
    } finally {
      if (!hideLoading) setLoading(false);
    }
  }, []);

  const loadProjectOptions = useCallback(async (keyword: string) => {
    setProjectLoading(true);
    try {
      const result = await listProjects({
        page: 1,
        page_size: 20,
        name: keyword.trim() || undefined,
      });
      const nextOptions = result.items.map((item) => ({
        value: item.id,
        label: item.display_name,
      }));
      setProjectOptions(nextOptions);
    } catch {
      setProjectOptions([]);
    } finally {
      setProjectLoading(false);
    }
  }, []);

  const loadTaskOptions = useCallback(async (keyword: string, projectId?: string) => {
    setTaskLoading(true);
    try {
      const result = await listTasks({
        page: 1,
        page_size: 20,
        project_id: projectId?.trim() || undefined,
        title: keyword.trim() || undefined,
      });
      const nextOptions = result.tasks.map((item) => ({
        value: item.id,
        label: `${item.title} (${item.id.slice(0, 8)})`,
      }));
      setTaskOptions(nextOptions);
    } catch {
      setTaskOptions([]);
    } finally {
      setTaskLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!query) return;
    void fetchLogs(query, page, pageSize);
  }, [fetchLogs, page, pageSize, query]);

  // 自动刷新逻辑
  useEffect(() => {
    if (!query || autoRefreshInterval === 0) return;
    const timer = setInterval(() => {
      void fetchLogs(query, page, pageSize, true);
    }, autoRefreshInterval);
    return () => clearInterval(timer);
  }, [autoRefreshInterval, fetchLogs, page, pageSize, query]);

  useEffect(() => {
    void loadProjectOptions('');
  }, [loadProjectOptions]);

  useEffect(() => {
    form.setFieldValue('task', undefined);
    form.setFieldValue('stage', undefined);
    setTaskOptions([]);
    setStageOptions([]);
    void loadTaskOptions('', projectValue);
  }, [form, loadTaskOptions, projectValue]);

  useEffect(() => {
    const taskId = (taskValue || '').trim();
    if (!taskId) {
      setStageOptions([]);
      form.setFieldValue('stage', undefined);
      return;
    }

    let canceled = false;
    const timer = window.setTimeout(async () => {
      setStageLoading(true);
      try {
        const stages = await getTaskStages(taskId);
        if (canceled) return;

        const uniqueStageNames = Array.from(
          new Set(stages.map((item) => item.stage_name).filter(Boolean)),
        );
        setStageOptions(uniqueStageNames.map((name) => ({ label: name, value: name })));

        const selected = form.getFieldValue('stage');
        if (selected && !uniqueStageNames.includes(selected)) {
          form.setFieldValue('stage', undefined);
        }
      } catch {
        if (!canceled) setStageOptions([]);
      } finally {
        if (!canceled) setStageLoading(false);
      }
    }, 300);

    return () => {
      canceled = true;
      window.clearTimeout(timer);
    };
  }, [form, taskValue]);

  useEffect(() => {
    if (!streamingLog) return;
    return () => {
      unsubscribeStream(streamingLog.id);
    };
  }, [streamingLog, unsubscribeStream]);

  const streamLines = streamingLog ? linesByLog[streamingLog.id] || [] : [];
  const streamStatus = streamingLog
    ? statusByLog[streamingLog.id] || streamingLog.status
    : undefined;

  // Drawer 自动滚动到底部
  useEffect(() => {
    if (streamPreRef.current) {
      streamPreRef.current.scrollTop = streamPreRef.current.scrollHeight;
    }
  }, [streamLines]);

  useEffect(() => {
    if (!streamingLog || !streamStatus || !query) return;
    if (!TERMINAL_STREAM_STATUS.has(streamStatus)) return;
    void fetchLogs(query, page, pageSize, true);
  }, [fetchLogs, page, pageSize, query, streamStatus, streamingLog]);

  useEffect(() => {
    if (!streamingLog) return;
    const matched = rows.find((item) => item.id === streamingLog.id);
    if (!matched || !matched.status) return;
    setStreamStatus(streamingLog.id, matched.status);
  }, [rows, setStreamStatus, streamingLog]);

  useEffect(() => {
    if (!streamingLog || !query) return;
    if (TERMINAL_STREAM_STATUS.has(streamStatus || '')) return;
    const timer = window.setInterval(() => {
      void fetchLogs(query, page, pageSize, true);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [fetchLogs, page, pageSize, query, streamStatus, streamingLog]);

  const openStream = useCallback(
    (record: TaskLogEvent) => {
      if (streamingLog && streamingLog.id !== record.id) {
        unsubscribeStream(streamingLog.id);
      }
      clearStream(record.id);
      subscribeStream(record.id);
      setStreamingLog(record);
    },
    [clearStream, streamingLog, subscribeStream, unsubscribeStream],
  );

  const closeStream = useCallback(() => {
    if (streamingLog) {
      unsubscribeStream(streamingLog.id);
    }
    setStreamingLog(null);
  }, [streamingLog, unsubscribeStream]);

  const columns: ColumnsType<TaskLogEvent> = useMemo(
    () => [
      {
        title: '序号',
        dataIndex: 'event_seq',
        width: 70,
        align: 'center',
      },
      {
        title: '时间',
        dataIndex: 'created_at',
        width: 170,
        render: (_, record) => formatTimestamp(record.created_at),
      },
      {
        title: '阶段',
        dataIndex: 'stage_name',
        width: 140,
        ellipsis: true,
        render: (_, record) => record.stage_name || '-',
      },
      {
        title: '来源',
        dataIndex: 'event_source',
        width: 90,
        align: 'center',
        render: (_, record) => (
          <Tag color={SOURCE_COLOR[record.event_source] || 'default'} style={{ margin: 0 }}>
            {record.event_source.toUpperCase()}
          </Tag>
        ),
      },
      {
        title: '类型',
        dataIndex: 'event_type',
        width: 180,
        ellipsis: true,
      },
      {
        title: '状态',
        dataIndex: 'status',
        width: 90,
        align: 'center',
        render: (_, record) => (
          <Tag color={STATUS_COLOR[record.status] || 'default'} style={{ margin: 0 }}>
            {record.status}
          </Tag>
        ),
      },
      {
        title: '命令',
        dataIndex: 'command',
        ellipsis: true,
        render: (val) => val ? <Text code>{val}</Text> : '-',
      },
      {
        title: '耗时',
        dataIndex: 'duration_ms',
        width: 100,
        align: 'right',
        render: (_, record) => {
          if (typeof record.duration_ms !== 'number') return '-';
          return record.duration_ms >= 1000 
            ? `${(record.duration_ms / 1000).toFixed(2)}s` 
            : `${record.duration_ms.toFixed(0)}ms`;
        },
      },
      {
        title: '实时输出',
        width: 100,
        align: 'center',
        fixed: 'right',
        render: (_, record) => {
          if (record.event_source !== 'tool') return '-';
          return (
            <Button
              type="link"
              size="small"
              disabled={record.status !== 'running'}
              onClick={() => openStream(record)}
            >
              查看
            </Button>
          );
        },
      },
    ],
    [openStream],
  );

  const onSearch = async () => {
    const values = await form.validateFields();
    const nextQuery: QueryState = {
      project: values.project ? values.project.trim() : undefined,
      task: values.task.trim(),
      stage: values.stage ? values.stage.trim() : undefined,
      event_source: values.event_source,
    };
    setQuery(nextQuery);
    setPage(1);
    await fetchLogs(nextQuery, 1, pageSize);
  };

  const handleManualRefresh = () => {
    if (query) {
      void fetchLogs(query, page, pageSize);
    }
  };

  const onTableChange = (pagination: TablePaginationConfig) => {
    setPage(pagination.current || 1);
    setPageSize(pagination.pageSize || 20);
  };

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card title="任务日志查询" bordered={false}>
        <Form form={form} layout="inline" initialValues={{ event_source: '' }}>
          <Form.Item label="项目" name="project">
            <Select
              allowClear
              showSearch
              filterOption={false}
              loading={projectLoading}
              options={projectOptions}
              placeholder="可选，按项目搜索"
              onSearch={(value) => void loadProjectOptions(value)}
              onFocus={() => { if (projectOptions.length === 0) void loadProjectOptions(''); }}
              style={{ width: 180 }}
            />
          </Form.Item>
          <Form.Item label="任务" name="task" rules={[{ required: true, message: '请选择任务' }]}>
            <Select
              allowClear
              showSearch
              filterOption={false}
              loading={taskLoading}
              options={taskOptions}
              placeholder="必填，按任务标题搜索"
              onSearch={(value) => void loadTaskOptions(value, projectValue)}
              onFocus={() => { if (taskOptions.length === 0) void loadTaskOptions('', projectValue); }}
              style={{ width: 280 }}
            />
          </Form.Item>
          <Form.Item label="阶段" name="stage">
            <Select
              allowClear
              showSearch
              loading={stageLoading}
              options={stageOptions}
              placeholder="可选"
              style={{ width: 160 }}
            />
          </Form.Item>
          <Form.Item label="来源" name="event_source">
            <Select style={{ width: 100 }} options={EVENT_SOURCE_OPTIONS} />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" onClick={() => void onSearch()}>查询</Button>
              <Button icon={<SyncOutlined />} onClick={handleManualRefresh} disabled={!query || loading}>刷新</Button>
              <Select 
                value={autoRefreshInterval} 
                onChange={setAutoRefreshInterval} 
                options={AUTO_REFRESH_OPTIONS} 
                style={{ width: 120 }} 
              />
            </Space>
          </Form.Item>
        </Form>
      </Card>

      {error ? <Alert type="error" showIcon message={error} /> : null}

      <Card bordered={false} bodyStyle={{ padding: '0 24px 24px' }}>
        <Table<TaskLogEvent>
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={rows}
          pagination={{ current: page, pageSize, total, showSizeChanger: true, showTotal: (t) => `共 ${t} 条记录` }}
          onChange={onTableChange}
          scroll={{ x: 1200 }}
          size="middle"
          locale={{ emptyText: query ? '没有匹配的日志记录' : '请先选择任务进行查询' }}
          expandable={{
            expandedRowRender: (record) => {
              const tabItems = [];

              if (record.request_body && Object.keys(record.request_body).length > 0) {
                tabItems.push({
                  key: 'req',
                  label: 'Request',
                  children: <CodeBlock content={JSON.stringify(record.request_body, null, 2)} />
                });
              }
              if (record.response_body && Object.keys(record.response_body).length > 0) {
                tabItems.push({
                  key: 'res',
                  label: 'Response',
                  children: <CodeBlock content={JSON.stringify(record.response_body, null, 2)} />
                });
              }
              if (record.command_args && Object.keys(record.command_args).length > 0) {
                tabItems.push({
                  key: 'args',
                  label: 'Command Args',
                  children: <CodeBlock content={JSON.stringify(record.command_args, null, 2)} />
                });
              }
              if (record.result) {
                tabItems.push({
                  key: 'resRaw',
                  label: 'Execution Result',
                  children: <CodeBlock content={record.result} />
                });
              }
              if (record.output_summary) {
                tabItems.push({
                  key: 'summary',
                  label: 'Output Summary',
                  children: (
                    <Space direction="vertical" style={{ width: '100%' }}>
                      {record.output_truncated && (
                        <Alert type="warning" showIcon message="输出过长，已自动截断（最大50KB）。" style={{ marginBottom: 8 }} />
                      )}
                      <CodeBlock content={record.output_summary} />
                    </Space>
                  )
                });
              }

              return (
                <div style={{ padding: '16px', background: '#fcfcfc', border: '1px solid #f0f0f0', borderRadius: 6 }}>
                  <Descriptions size="small" column={{ xxl: 3, xl: 3, lg: 3, md: 2, sm: 1, xs: 1 }} style={{ marginBottom: tabItems.length > 0 ? 16 : 0 }}>
                    <Descriptions.Item label="日志ID"><Text copyable>{record.id}</Text></Descriptions.Item>
                    <Descriptions.Item label="关联ID">{record.correlation_id ? <Text copyable>{record.correlation_id}</Text> : '-'}</Descriptions.Item>
                    <Descriptions.Item label="运行模式">{record.execution_mode || '-'}</Descriptions.Item>
                    <Descriptions.Item label="工作空间">
                      {record.workspace ? <Text code copyable>{record.workspace}</Text> : '-'}
                    </Descriptions.Item>
                    <Descriptions.Item label="Agent角色">{record.agent_role || '-'}</Descriptions.Item>
                    {record.missing_fields && record.missing_fields.length > 0 && (
                      <Descriptions.Item label="缺失字段">
                        <Text type="danger">{record.missing_fields.join(', ')}</Text>
                      </Descriptions.Item>
                    )}
                  </Descriptions>
                  
                  {tabItems.length > 0 && (
                    <Tabs size="small" items={tabItems} type="card" />
                  )}
                </div>
              );
            },
          }}
        />
      </Card>

      <Drawer
        title={
          <Space>
            {streamingLog ? `实时输出 - ${streamingLog.command || streamingLog.event_type}` : '实时输出'}
            {streamStatus && (
              <Tag color={STATUS_COLOR[streamStatus] || 'default'} style={{ margin: 0 }}>
                {streamStatus}
              </Tag>
            )}
          </Space>
        }
        width={720}
        open={Boolean(streamingLog)}
        onClose={closeStream}
        styles={{ body: { paddingBottom: 24 } }}
      >
        {streamingLog ? (
          <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <Space direction="vertical" size={4}>
                <Text type="secondary" style={{ fontSize: 13 }}>日志ID: {streamingLog.id}</Text>
                {TERMINAL_STREAM_STATUS.has(streamStatus || '') ? (
                  <Text type="secondary" style={{ fontSize: 13 }}>执行已结束，列表会显示最终状态和摘要。</Text>
                ) : (
                  <Text type="secondary" style={{ fontSize: 13 }}>仅显示你打开该面板后的新增输出，不回放历史内容。</Text>
                )}
              </Space>
            </div>
            <div style={{ position: 'relative', flex: 1, minHeight: 0 }}>
              <pre
                ref={streamPreRef}
                style={{
                  margin: 0,
                  height: '100%',
                  overflow: 'auto',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  background: '#1e1e1e',
                  color: '#d4d4d4',
                  border: '1px solid #333',
                  borderRadius: 6,
                  padding: 12,
                  fontFamily: 'SFMono-Regular, Consolas, "Liberation Mono", Menlo, Courier, monospace',
                  fontSize: 13,
                  lineHeight: 1.5,
                }}
              >
                {streamLines.length > 0 ? streamLines.join('') : '等待运行中输出...'}
              </pre>
            </div>
          </div>
        ) : null}
      </Drawer>
    </Space>
  );
};

export default TaskLogsPage;
