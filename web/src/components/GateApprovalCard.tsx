import React, { useState } from 'react';
import { Card, Button, Space, Typography, Input, Tag } from 'antd';
import { CheckOutlined, CloseOutlined, EditOutlined } from '@ant-design/icons';
import type { Gate } from '@/types/gate';
import { formatRelativeTime } from '@/utils/formatters';

const { Text, Paragraph } = Typography;
const { TextArea } = Input;

interface GateApprovalCardProps {
  gate: Gate;
  onApprove: (id: string, comment?: string) => void;
  onReject: (id: string, comment: string) => void;
  onRevise?: (id: string, comment: string, revisedContent?: string) => void;
  loading?: boolean;
}

const GateApprovalCard: React.FC<GateApprovalCardProps> = ({ gate, onApprove, onReject, onRevise, loading }) => {
  const [comment, setComment] = useState('');
  const [revisedContent, setRevisedContent] = useState('');
  const [mode, setMode] = useState<'actions' | 'reject' | 'revise'>('actions');

  const waitingTime = formatRelativeTime(gate.created_at);
  const stageName = gate.content?.stage ?? gate.agent_role;
  const summary = gate.content?.summary ?? '';

  return (
    <Card
      id={`gate-card-${gate.id}`}
      size="small"
      title={
        <Space>
          <Tag color="orange">{gate.gate_type}</Tag>
          <Text>Stage: {stageName}</Text>
          {gate.is_dynamic && <Tag color="gold">Dynamic</Tag>}
          {(gate.retry_count ?? 0) > 0 && <Tag color="blue">Retry {gate.retry_count}</Tag>}
        </Space>
      }
      extra={<Text type="secondary">{waitingTime}</Text>}
    >
      <Paragraph ellipsis={{ rows: 3, expandable: true }}>{summary}</Paragraph>
      <Paragraph type="secondary" style={{ fontSize: 12 }}>
        Task: {gate.task_id}
      </Paragraph>

      {gate.status === 'pending' ? (
        mode === 'reject' ? (
          <div>
            <Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 4 }}>
              Your feedback will be sent to the AI agent for revision.
            </Paragraph>
            <TextArea
              rows={2}
              placeholder="Rejection reason..."
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              style={{ marginBottom: 8 }}
            />
            <Space>
              <Button
                danger
                size="small"
                loading={loading}
                onClick={() => onReject(gate.id, comment)}
                disabled={!comment.trim()}
              >
                Confirm Reject
              </Button>
              <Button size="small" onClick={() => setMode('actions')}>
                Cancel
              </Button>
            </Space>
          </div>
        ) : mode === 'revise' ? (
          <div>
            <Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 4 }}>
              Provide modifications. The stage will re-execute with your instructions.
            </Paragraph>
            <TextArea
              rows={2}
              placeholder="Revision instructions..."
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              style={{ marginBottom: 8 }}
            />
            <TextArea
              rows={3}
              placeholder="Optional: paste revised content here..."
              value={revisedContent}
              onChange={(e) => setRevisedContent(e.target.value)}
              style={{ marginBottom: 8 }}
            />
            <Space>
              <Button
                type="primary"
                size="small"
                loading={loading}
                onClick={() => onRevise?.(gate.id, comment, revisedContent || undefined)}
                disabled={!comment.trim()}
              >
                Submit Revision
              </Button>
              <Button size="small" onClick={() => setMode('actions')}>
                Cancel
              </Button>
            </Space>
          </div>
        ) : (
          <Space>
            <Button
              type="primary"
              icon={<CheckOutlined />}
              size="small"
              loading={loading}
              onClick={() => onApprove(gate.id, comment || undefined)}
            >
              Approve
            </Button>
            {onRevise && (
              <Button
                icon={<EditOutlined />}
                size="small"
                onClick={() => setMode('revise')}
              >
                Revise
              </Button>
            )}
            <Button
              danger
              icon={<CloseOutlined />}
              size="small"
              onClick={() => setMode('reject')}
            >
              Reject
            </Button>
          </Space>
        )
      ) : (
        <Space>
          <Tag color={gate.status === 'approved' ? 'green' : gate.status === 'revised' ? 'blue' : 'red'}>
            {gate.status}
          </Tag>
          {gate.reviewer && <Text type="secondary">by {gate.reviewer}</Text>}
        </Space>
      )}
    </Card>
  );
};

export default GateApprovalCard;
