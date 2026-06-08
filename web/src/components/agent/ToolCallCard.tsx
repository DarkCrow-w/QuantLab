import { Collapse, Spin, Tag } from 'antd';
import {
  BarChartOutlined,
  CheckCircleOutlined,
  DatabaseOutlined,
  LineChartOutlined,
  LoadingOutlined,
  SearchOutlined,
  UnorderedListOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import type { AgentToolCall } from '../../types';

const TOOL_LABELS: Record<string, { label: string; icon: React.ReactNode }> = {
  run_backtest_tool: { label: '执行回测', icon: <BarChartOutlined /> },
  list_strategies_tool: { label: '获取策略列表', icon: <UnorderedListOutlined /> },
  compare_backtests_tool: { label: '对比回测', icon: <BarChartOutlined /> },
  screen_stocks_tool: { label: '条件选股', icon: <SearchOutlined /> },
  get_kline_data_tool: { label: '获取 K 线数据', icon: <LineChartOutlined /> },
  list_cached_stocks_tool: { label: '查询缓存股票', icon: <DatabaseOutlined /> },
  get_all_a_stock_list_tool: { label: '获取 A 股列表', icon: <DatabaseOutlined /> },
  resolve_stock_symbol_tool: { label: '识别股票名称', icon: <SearchOutlined /> },
  analyze_technicals_tool: { label: '技术指标分析', icon: <LineChartOutlined /> },
};

function StatusIcon({ status }: { status: AgentToolCall['status'] }) {
  if (status === 'running') {
    return <Spin indicator={<LoadingOutlined spin />} size="small" />;
  }
  if (status === 'done') {
    return <CheckCircleOutlined style={{ color: '#0ecb81' }} />;
  }
  return <WarningOutlined style={{ color: '#f6465d' }} />;
}

export default function ToolCallCard({ toolCall }: { toolCall: AgentToolCall }) {
  const info = TOOL_LABELS[toolCall.tool] ?? {
    label: toolCall.tool,
    icon: null,
  };
  const items = toolCall.result
    ? [
        {
          key: 'result',
          label: <span className="agent-tool-result-label">查看工具结果</span>,
          children: (
            <pre className="agent-tool-result">
              {JSON.stringify(toolCall.result, null, 2)}
            </pre>
          ),
        },
      ]
    : [];

  return (
    <div className="agent-tool-card">
      <div className="agent-tool-title">
        <StatusIcon status={toolCall.status} />
        <span>{info.icon}</span>
        <strong>{info.label}</strong>
        {toolCall.agent && <Tag>{toolCall.agent}</Tag>}
      </div>
      {Object.keys(toolCall.input).length > 0 && (
        <div className="agent-tool-input">
          {Object.entries(toolCall.input)
            .slice(0, 4)
            .map(([key, value]) => `${key}: ${JSON.stringify(value)}`)
            .join(' | ')}
        </div>
      )}
      {items.length > 0 && <Collapse ghost size="small" items={items} />}
    </div>
  );
}
