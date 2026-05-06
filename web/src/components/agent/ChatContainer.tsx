import { useEffect, useRef } from 'react';
import { Spin } from 'antd';
import { LoadingOutlined, RobotOutlined } from '@ant-design/icons';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useAgentStore } from '../../stores/agent';
import MessageBubble from './MessageBubble';
import ToolCallCard from './ToolCallCard';
import AgentStatusBar from './AgentStatusBar';
import ChatInput from './ChatInput';

export default function ChatContainer() {
  const messages = useAgentStore((s) => s.messages);
  const isStreaming = useAgentStore((s) => s.isStreaming);
  const streamingContent = useAgentStore((s) => s.streamingContent);
  const activeAgents = useAgentStore((s) => s.activeAgents);
  const pendingToolCalls = useAgentStore((s) => s.pendingToolCalls);
  const connect = useAgentStore((s) => s.connect);
  const connected = useAgentStore((s) => s.connected);
  const bottomRef = useRef<HTMLDivElement>(null);

  // 自动连接 WebSocket
  useEffect(() => {
    connect();
  }, [connect]);

  // 自动滚动到底部
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingContent, pendingToolCalls]);

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        background: '#0b0e11',
      }}
    >
      {/* Agent 状态栏 */}
      <AgentStatusBar agents={activeAgents} />

      {/* 消息区域 */}
      <div
        style={{
          flex: 1,
          overflow: 'auto',
          padding: '8px 0',
        }}
      >
        {/* 欢迎信息 */}
        {messages.length === 0 && !isStreaming && (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              color: '#5e6673',
              gap: 12,
            }}
          >
            <RobotOutlined style={{ fontSize: 48, color: '#722ed1' }} />
            <div style={{ fontSize: 16, color: '#848e9c' }}>QuantLab AI 助手</div>
            <div style={{ fontSize: 12, maxWidth: 400, textAlign: 'center', lineHeight: 1.8 }}>
              你可以用自然语言执行回测、选股和行情查询。例如：
              <br />
              "帮我用 MA 交叉策略回测 600519，2023 年全年"
              <br />
              "找出最近有买入信号的股票"
              <br />
              "查看 000001 最近 60 天的 K 线"
            </div>
            {!connected && (
              <div style={{ fontSize: 11, color: '#f6465d' }}>
                WebSocket 未连接，请检查后端是否启动
              </div>
            )}
          </div>
        )}

        {/* 历史消息 */}
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {/* 流式输出区域 */}
        {isStreaming && (
          <div style={{ padding: '12px 16px', display: 'flex', gap: 10 }}>
            <div
              style={{
                width: 30,
                height: 30,
                borderRadius: '50%',
                background: '#722ed1',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              <RobotOutlined style={{ color: '#fff', fontSize: 14 }} />
            </div>
            <div style={{ maxWidth: '75%', minWidth: 0 }}>
              {/* 进行中的 tool calls */}
              {pendingToolCalls.map((tc) => (
                <ToolCallCard key={tc.id} toolCall={tc} />
              ))}

              {/* 流式文本 */}
              {streamingContent ? (
                <div
                  style={{
                    background: '#1a1d21',
                    borderRadius: '12px 12px 12px 4px',
                    padding: '10px 14px',
                    color: '#eaecef',
                    fontSize: 13,
                    lineHeight: 1.6,
                  }}
                >
                  <div className="agent-markdown">
                    <Markdown remarkPlugins={[remarkGfm]}>{streamingContent}</Markdown>
                  </div>
                  <span className="streaming-cursor" />
                </div>
              ) : (
                <Spin indicator={<LoadingOutlined spin style={{ color: '#722ed1' }} />} />
              )}
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* 输入区域 */}
      <ChatInput />
    </div>
  );
}
