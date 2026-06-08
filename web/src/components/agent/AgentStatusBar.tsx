import { Tag } from 'antd';
import { CheckCircleOutlined, LoadingOutlined } from '@ant-design/icons';
import type { AgentStatus } from '../../types';

export default function AgentStatusBar({ agents }: { agents: AgentStatus[] }) {
  if (agents.length === 0) return null;

  return (
    <div className="agent-status-bar">
      {agents.map((agent) => (
        <Tag
          key={agent.name}
          icon={
            agent.status === 'working' ? (
              <LoadingOutlined spin />
            ) : (
              <CheckCircleOutlined />
            )
          }
          color={agent.status === 'working' ? 'processing' : 'success'}
        >
          {agent.displayName}
          {agent.task ? ` · ${agent.task}` : ''}
        </Tag>
      ))}
    </div>
  );
}
