import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { UserOutlined, RobotOutlined } from '@ant-design/icons';
import type { ChatMessage } from '../../types';
import ToolCallCard from './ToolCallCard';

export default function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';

  return (
    <div
      style={{
        display: 'flex',
        gap: 10,
        padding: '12px 16px',
        alignItems: 'flex-start',
        flexDirection: isUser ? 'row-reverse' : 'row',
      }}
    >
      {/* Avatar */}
      <div
        style={{
          width: 30,
          height: 30,
          borderRadius: '50%',
          background: isUser ? '#1890ff' : '#722ed1',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
        }}
      >
        {isUser ? (
          <UserOutlined style={{ color: '#fff', fontSize: 14 }} />
        ) : (
          <RobotOutlined style={{ color: '#fff', fontSize: 14 }} />
        )}
      </div>

      {/* Content */}
      <div
        style={{
          maxWidth: '75%',
          minWidth: 0,
        }}
      >
        {/* User images */}
        {message.images && message.images.length > 0 && (
          <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
            {message.images.map((img, i) => (
              <img
                key={i}
                src={`data:image/png;base64,${img}`}
                alt=""
                style={{
                  maxWidth: 300,
                  maxHeight: 200,
                  borderRadius: 8,
                  border: '1px solid #2b2f36',
                }}
              />
            ))}
          </div>
        )}

        {/* Tool calls (before text) */}
        {message.toolCalls?.map((tc) => (
          <ToolCallCard key={tc.id} toolCall={tc} />
        ))}

        {/* Text content */}
        {message.content && (
          <div
            style={{
              background: isUser ? '#1890ff' : '#1a1d21',
              borderRadius: isUser ? '12px 12px 4px 12px' : '12px 12px 12px 4px',
              padding: '10px 14px',
              color: isUser ? '#fff' : '#eaecef',
              fontSize: 13,
              lineHeight: 1.6,
              wordBreak: 'break-word',
            }}
          >
            {isUser ? (
              <span style={{ whiteSpace: 'pre-wrap' }}>{message.content}</span>
            ) : (
              <div className="agent-markdown">
                <Markdown remarkPlugins={[remarkGfm]}>{message.content}</Markdown>
              </div>
            )}
          </div>
        )}

        {/* Timestamp */}
        <div
          style={{
            fontSize: 10,
            color: '#5e6673',
            marginTop: 4,
            textAlign: isUser ? 'right' : 'left',
          }}
        >
          {new Date(message.timestamp).toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </div>
      </div>
    </div>
  );
}
