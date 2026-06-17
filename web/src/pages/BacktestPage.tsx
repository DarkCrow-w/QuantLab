import { useState } from 'react';
import { Alert, Tabs } from 'antd';
import {
  BarChartOutlined,
  FundOutlined,
  LineChartOutlined,
  SafetyCertificateOutlined,
  UnorderedListOutlined,
} from '@ant-design/icons';
import { useBacktestStore } from '../stores/backtest';
import MetricsCards from '../components/backtest/MetricsCards';
import TradesTable from '../components/backtest/TradesTable';
import KlineChart, { type SubplotKey } from '../components/chart/KlineChart';
import OverlaySelector, { SubplotSelector } from '../components/chart/OverlaySelector';
import { keysToOverlays } from '../components/chart/overlayPresets';
import EquityChart from '../components/chart/EquityChart';
import Loading from '../components/common/Loading';

function EmptyState() {
  return (
    <div className="workspace-page">
      <WorkspaceHeading />
      <div className="terminal-empty">
        <div className="terminal-empty-inner">
          <div className="terminal-empty-icon"><FundOutlined /></div>
          <h2>创建一次策略实验</h2>
          <p>从左侧设置策略、交易标的、回测区间与风险参数。运行后将在这里生成绩效指标、行情信号、资金曲线和逐笔交易记录。</p>
          <div className="terminal-empty-steps">
            <span>01 配置策略</span>
            <span>02 运行回测</span>
            <span>03 评估表现</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function WorkspaceHeading() {
  return (
    <div className="workspace-heading">
      <div>
        <h1>策略回测工作台</h1>
        <p>验证交易逻辑、风险暴露与历史稳定性</p>
      </div>
      <div className="workspace-meta">
        <span><BarChartOutlined /> 日线频率</span>
        <span><SafetyCertificateOutlined /> 风控已启用</span>
      </div>
    </div>
  );
}

function Panel({
  children,
  style,
}: {
  children: React.ReactNode;
  style?: React.CSSProperties;
}) {
  return <div className="surface-panel" style={style}>{children}</div>;
}

function PanelHeader({ title, icon }: { title: string; icon: React.ReactNode }) {
  return <div className="panel-heading">{icon}{title}</div>;
}

export default function BacktestPage() {
  const { result, loading, error } = useBacktestStore();
  const [activeSymbol, setActiveSymbol] = useState('');
  const [overlayKeys, setOverlayKeys] = useState<string[]>(['MA5', 'MA20', 'BBI']);
  const [subplots, setSubplots] = useState<SubplotKey[]>(['VOL', 'MACD']);

  if (loading) return <Loading />;
  if (error) {
    return (
      <Alert
        type="error"
        title="回测失败"
        description={error}
        showIcon
        style={{ margin: 20 }}
      />
    );
  }
  if (!result) return <EmptyState />;

  const symbols = Object.keys(result.kline_data);
  const currentSymbol = activeSymbol && symbols.includes(activeSymbol) ? activeSymbol : symbols[0];

  return (
    <div className="workspace-page">
      <WorkspaceHeading />
      <MetricsCards metrics={result.metrics} />

      {symbols.length > 0 && (
        <Panel>
          <div style={{ padding: '6px 14px 0', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
            <Tabs
              activeKey={currentSymbol}
              onChange={setActiveSymbol}
              size="small"
              items={symbols.map((symbol) => ({
                key: symbol,
                label: <span className="mono">{symbol}</span>,
              }))}
              style={{ marginBottom: 0, flex: 1 }}
            />
            <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
              <OverlaySelector value={overlayKeys} onChange={setOverlayKeys} />
              <SubplotSelector value={subplots} onChange={setSubplots} />
            </div>
          </div>
          <div style={{ padding: '0 6px' }}>
            <KlineChart
              kline={result.kline_data[currentSymbol]}
              trades={result.trades}
              symbol={currentSymbol}
              overlays={keysToOverlays(overlayKeys)}
              subplots={subplots}
            />
          </div>
        </Panel>
      )}

      <div className="analytics-grid">
        <Panel>
          <PanelHeader title="收益与回撤" icon={<LineChartOutlined />} />
          <div style={{ padding: '0 6px' }}>
            <EquityChart data={result.equity_curve} initialCash={result.metrics.initial_cash} />
          </div>
        </Panel>
        <Panel>
          <PanelHeader title="交易记录" icon={<UnorderedListOutlined />} />
          <div style={{ maxHeight: 280, overflow: 'auto' }}>
            <TradesTable trades={result.trades} />
          </div>
        </Panel>
      </div>
    </div>
  );
}
