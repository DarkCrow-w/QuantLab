import { Space, Tag } from 'antd';
import { LoadingOutlined, CheckCircleOutlined } from '@ant-design/icons';
import type { AgentStatus } from '../../types';

export default function AgentStatusBar({ agents }: { agents: AgentStatus[] }) {
  if (agents.length === 0) return null;

  return (
    <div
      style={{
        display: 'flex',
        gap: 8,
        padding: '6px 16px',
        background: '#0f1114',
        borderBottom: '1px solid #1e2126',
        flexWrap: 'wrap',
      }}
    >
      {agents.map((a) => (
        <Tag
          key={a.name}
          icon={a.status === 'working' ? <LoadingOutlined spin /> : <CheckCircleOutlined />}
          color={a.status === 'working' ? 'processing' : 'success'}
          style={{ fontSize: 11, margin: 0 }}
        >
          {a.displayName}
          {a.task ? ` — ${a.task}` : ''}
        </Tag>
      ))}
    </div>
  );
}
