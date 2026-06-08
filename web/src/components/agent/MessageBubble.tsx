import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { RobotOutlined, UserOutlined } from '@ant-design/icons';
import type { ChatMessage } from '../../types';
import ToolCallCard from './ToolCallCard';

export default function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';
  return (
    <div className={`agent-message ${isUser ? 'user' : ''}`}>
      <div className="agent-avatar">
        {isUser ? <UserOutlined /> : <RobotOutlined />}
      </div>
      <div className="agent-bubble-wrap">
        {message.images?.length ? (
          <div className="agent-message-images">
            {message.images.map((image, index) => (
              <img
                key={`${image.slice(0, 16)}-${index}`}
                src={`data:image/png;base64,${image}`}
                alt="用户上传的分析图片"
              />
            ))}
          </div>
        ) : null}
        {message.toolCalls?.map((toolCall) => (
          <ToolCallCard key={toolCall.id} toolCall={toolCall} />
        ))}
        {message.content && (
          <div className="agent-bubble">
            {isUser ? (
              <span style={{ whiteSpace: 'pre-wrap' }}>{message.content}</span>
            ) : (
              <div className="agent-markdown">
                <Markdown remarkPlugins={[remarkGfm]}>
                  {message.content}
                </Markdown>
              </div>
            )}
          </div>
        )}
        <div className="agent-time">
          {new Date(message.timestamp).toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </div>
      </div>
    </div>
  );
}
