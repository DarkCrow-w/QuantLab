import { useEffect, useRef } from 'react';
import { Button, Select, Spin, Tag, Tooltip } from 'antd';
import {
  ApartmentOutlined,
  BarChartOutlined,
  BulbOutlined,
  LineChartOutlined,
  LoadingOutlined,
  PlusOutlined,
  RadarChartOutlined,
  ReloadOutlined,
  RobotOutlined,
} from '@ant-design/icons';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useAgentStore } from '../../stores/agent';
import AgentStatusBar from './AgentStatusBar';
import ChatInput from './ChatInput';
import MessageBubble from './MessageBubble';
import ToolCallCard from './ToolCallCard';
import type { AgentMode } from '../../types';

const modeFallbacks = [
  { key: 'auto', label: '自动协作', agent: 'supervisor' },
  { key: 'quant', label: 'Quant Agent', agent: 'quant_agent' },
  { key: 'market', label: '行情分析', agent: 'market_agent' },
  { key: 'screening', label: '智能选股', agent: 'screening_agent' },
  { key: 'backtest', label: '策略回测', agent: 'backtest_agent' },
] as const;

const modeIcons: Record<AgentMode, React.ReactNode> = {
  auto: <ApartmentOutlined />,
  quant: <BulbOutlined />,
  market: <LineChartOutlined />,
  screening: <RadarChartOutlined />,
  backtest: <BarChartOutlined />,
};

const modeDescriptions: Record<AgentMode, string> = {
  auto: '主管自动调度行情、选股、回测和决策专家',
  quant: '使用项目内行情、指标、选股和回测能力进行综合研究',
  market: '专注 K 线、指标、趋势、支撑与压力',
  screening: '专注策略扫描、候选排序与信号解释',
  backtest: '专注策略回测、参数比较与风险评价',
};

const prompts = [
  [
    'Quant 视角诊断',
    '从趋势、量价、波动与风险维度形成可验证的研究结论',
    '请用 Quant 视角解释交易纪律，并给我一套可以每天执行的检查清单。',
  ],
  [
    '分析一只股票',
    '调用本地行情和技术指标，输出可验证的研究结论',
    '请分析 000001 最近 120 个交易日的趋势、成交量、KDJ、RSI、MACD 和 BBI，并提示主要风险。',
  ],
  [
    '扫描市场机会',
    '调用 QuantLab 选股能力寻找候选标的',
    '请使用多因子思路扫描当前市场，给出最值得进一步研究的 10 个候选，并解释筛选逻辑。',
  ],
  [
    '设计组合策略',
    '把自然语言想法转换为可执行的指标组合',
    '请用 KDJ、RSI、MACD、成交量、DMI、DMA 和 BBI，设计一个趋势启动选股策略。',
  ],
];

export default function ChatContainer() {
  const store = useAgentStore();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    store.loadRuntime();
    store.connect();
    return () => store.disconnect();
    // Store actions are stable Zustand functions.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [store.messages, store.streamingContent, store.pendingToolCalls]);

  const providerLabel =
    store.runtime?.provider === 'deepseek'
      ? 'DeepSeek'
      : store.runtime?.provider === 'anthropic'
        ? 'Anthropic'
        : 'Agent';

  return (
    <div className="agent-shell">
      <header className="agent-header">
        <div>
          <h1>AI 量化研究员</h1>
          <p>{modeDescriptions[store.selectedMode]}</p>
        </div>
        <div className="agent-header-actions">
          <Select
            className="agent-mode-select"
            value={store.selectedMode}
            disabled={store.isStreaming}
            onChange={(value: AgentMode) => store.setAgentMode(value)}
            options={(store.runtime?.modes ?? modeFallbacks).map((mode) => ({
              value: mode.key,
              label: (
                <span className="agent-mode-option">
                  {modeIcons[mode.key]}
                  {mode.label}
                </span>
              ),
            }))}
            aria-label="选择 AI Agent"
          />
          {store.runtime && (
            <Tag color={store.runtime.enabled ? 'blue' : 'error'}>
              {providerLabel} · {store.runtime.model}
            </Tag>
          )}
          <div
            className={`connection-state ${
              store.connectionState === 'connected' ? 'connected' : ''
            }`}
          >
            <i />
            {store.connectionState === 'connected'
              ? '研究服务在线'
              : store.connectionState === 'connecting'
                ? '正在连接'
                : '研究服务离线'}
          </div>
          {store.connectionState !== 'connected' && (
            <Tooltip title="重新连接">
              <Button
                size="small"
                icon={<ReloadOutlined />}
                onClick={store.reconnect}
                aria-label="重新连接"
              />
            </Tooltip>
          )}
          <Button
            size="small"
            icon={<PlusOutlined />}
            onClick={store.clearSession}
            disabled={store.isStreaming}
          >
            新对话
          </Button>
        </div>
      </header>

      {store.connectionError && (
        <div className="agent-connection-error">{store.connectionError}</div>
      )}
      <AgentStatusBar agents={store.activeAgents} />

      <div className="agent-scroll">
        {store.messages.length === 0 && !store.isStreaming && (
          <div className="agent-welcome">
            <div className="agent-welcome-inner">
              <div className="agent-welcome-mark">
                <RobotOutlined />
              </div>
              <h2>把研究问题交给协作式 AI 团队</h2>
              <p>
                {store.selectedMode === 'quant'
                  ? 'Quant Agent 会核对研究周期和持仓背景，再调用真实数据工具形成可验证判断。'
                  : '你可以让主管自动调度，也可以在右上角直接选择某个专业 Agent。所有研究结论均由项目内数据和工具支撑。'}
              </p>
              <div className="prompt-grid">
                {prompts.map(([title, detail, prompt]) => (
                  <button
                    type="button"
                    key={title}
                    onClick={() => store.sendMessage(prompt)}
                    disabled={store.isStreaming || store.runtime?.enabled === false}
                  >
                    <strong>{title}</strong>
                    <span>{detail}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {store.messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}

        {store.isStreaming && (
          <div className="agent-message">
            <div className="agent-avatar">
              <RobotOutlined />
            </div>
            <div className="agent-bubble-wrap">
              {store.pendingToolCalls.map((toolCall) => (
                <ToolCallCard key={toolCall.id} toolCall={toolCall} />
              ))}
              {store.streamingContent ? (
                <div className="agent-bubble">
                  <div className="agent-markdown">
                    <Markdown remarkPlugins={[remarkGfm]}>
                      {store.streamingContent}
                    </Markdown>
                  </div>
                  <span className="streaming-cursor" />
                </div>
              ) : (
                <div className="agent-thinking">
                  <Spin indicator={<LoadingOutlined spin />} />
                  <span>研究主管正在拆解问题</span>
                </div>
              )}
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <ChatInput />
    </div>
  );
}
