import { Collapse, Spin, Tag } from 'antd';
import {
  CheckCircleOutlined,
  LoadingOutlined,
  WarningOutlined,
  BarChartOutlined,
  SearchOutlined,
  LineChartOutlined,
  DatabaseOutlined,
  UnorderedListOutlined,
} from '@ant-design/icons';
import type { AgentToolCall } from '../../types';

const TOOL_LABELS: Record<string, { label: string; icon: React.ReactNode }> = {
  run_backtest_tool: { label: '执行回测', icon: <BarChartOutlined /> },
  list_strategies_tool: { label: '获取策略列表', icon: <UnorderedListOutlined /> },
  compare_backtests_tool: { label: '对比回测', icon: <BarChartOutlined /> },
  screen_stocks_tool: { label: '条件选股', icon: <SearchOutlined /> },
  get_kline_data_tool: { label: '获取K线数据', icon: <LineChartOutlined /> },
  list_cached_stocks_tool: { label: '查询缓存列表', icon: <DatabaseOutlined /> },
  get_all_a_stock_list_tool: { label: '获取A股列表', icon: <DatabaseOutlined /> },
  analyze_technicals_tool: { label: '技术指标分析', icon: <LineChartOutlined /> },
};

function StatusIcon({ status }: { status: AgentToolCall['status'] }) {
  if (status === 'running') return <Spin indicator={<LoadingOutlined spin />} size="small" />;
  if (status === 'done') return <CheckCircleOutlined style={{ color: '#0ecb81' }} />;
  return <WarningOutlined style={{ color: '#f6465d' }} />;
}

export default function ToolCallCard({ toolCall }: { toolCall: AgentToolCall }) {
  const info = TOOL_LABELS[toolCall.tool] ?? { label: toolCall.tool, icon: null };

  const items = toolCall.result
    ? [
        {
          key: '1',
          label: (
            <span style={{ fontSize: 11, color: '#848e9c' }}>查看结果</span>
          ),
          children: (
            <pre
              style={{
                fontSize: 11,
                color: '#848e9c',
                margin: 0,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-all',
                maxHeight: 200,
                overflow: 'auto',
              }}
            >
              {JSON.stringify(toolCall.result, null, 2)}
            </pre>
          ),
        },
      ]
    : [];

  return (
    <div
      style={{
        background: '#141619',
        border: '1px solid #1e2126',
        borderRadius: 8,
        padding: '8px 12px',
        marginBottom: 8,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <StatusIcon status={toolCall.status} />
        <span style={{ color: '#848e9c', fontSize: 12 }}>{info.icon}</span>
        <span style={{ color: '#eaecef', fontSize: 12, fontWeight: 500 }}>{info.label}</span>
        {toolCall.agent && (
          <Tag
            style={{
              fontSize: 10,
              lineHeight: '16px',
              padding: '0 4px',
              background: '#1a1d21',
              borderColor: '#2b2f36',
              color: '#848e9c',
            }}
          >
            {toolCall.agent}
          </Tag>
        )}
      </div>

      {/* 参数摘要 */}
      {toolCall.input && Object.keys(toolCall.input).length > 0 && (
        <div style={{ marginTop: 4, fontSize: 11, color: '#5e6673' }}>
          {Object.entries(toolCall.input)
            .slice(0, 4)
            .map(([k, v]) => `${k}: ${JSON.stringify(v)}`)
            .join(' | ')}
        </div>
      )}

      {/* 可折叠结果 */}
      {items.length > 0 && (
        <Collapse
          ghost
          size="small"
          items={items}
          style={{ marginTop: 4 }}
        />
      )}
    </div>
  );
}
