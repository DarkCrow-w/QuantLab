import { useState } from 'react';
import { Alert, Tabs } from 'antd';
import {
  LineChartOutlined,
  FundOutlined,
  UnorderedListOutlined,
} from '@ant-design/icons';
import { useBacktestStore } from '../stores/backtest';
import MetricsCards from '../components/backtest/MetricsCards';
import TradesTable from '../components/backtest/TradesTable';
import KlineChart, { type SubplotKey } from '../components/chart/KlineChart';
import OverlaySelector, {
  SubplotSelector,
  keysToOverlays,
} from '../components/chart/OverlaySelector';
import EquityChart from '../components/chart/EquityChart';
import Loading from '../components/common/Loading';

function EmptyState() {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100%',
        minHeight: 400,
        gap: 16,
      }}
    >
      <div
        style={{
          width: 64,
          height: 64,
          borderRadius: 16,
          background: '#141619',
          border: '1px solid #1e2126',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <FundOutlined style={{ fontSize: 28, color: '#2b2f36' }} />
      </div>
      <div style={{ color: '#5e6673', fontSize: 14 }}>配置参数后点击运行回测</div>
      <div style={{ color: '#2b2f36', fontSize: 12 }}>回测结果将在此处展示</div>
    </div>
  );
}

function PanelCard({
  children,
  style,
}: {
  children: React.ReactNode;
  style?: React.CSSProperties;
}) {
  return (
    <div
      style={{
        background: '#141619',
        borderRadius: 8,
        border: '1px solid #1e2126',
        overflow: 'hidden',
        ...style,
      }}
    >
      {children}
    </div>
  );
}

function PanelHeader({ title, icon }: { title: string; icon: React.ReactNode }) {
  return (
    <div
      style={{
        padding: '8px 14px',
        borderBottom: '1px solid #1e2126',
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        color: '#848e9c',
        fontSize: 12,
        fontWeight: 500,
      }}
    >
      {icon}
      {title}
    </div>
  );
}

export default function BacktestPage() {
  const { result, loading, error } = useBacktestStore();
  const [activeSymbol, setActiveSymbol] = useState<string>('');
  const [overlayKeys, setOverlayKeys] = useState<string[]>(['MA5', 'MA20', 'BBI']);
  const [subplots, setSubplots] = useState<SubplotKey[]>(['VOL', 'MACD']);

  if (loading) return <Loading />;
  if (error)
    return (
      <Alert
        type="error"
        message="回测失败"
        description={error}
        showIcon
        style={{ margin: 20, background: '#1a1d21', border: '1px solid #f6465d40' }}
      />
    );
  if (!result) return <EmptyState />;

  const symbols = Object.keys(result.kline_data);
  const currentSymbol =
    activeSymbol && symbols.includes(activeSymbol) ? activeSymbol : symbols[0];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* Metrics Bar */}
      <MetricsCards metrics={result.metrics} />

      {/* K-line Chart */}
      {symbols.length > 0 && (
        <PanelCard>
          <div
            style={{
              padding: '6px 14px 0',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 16,
            }}
          >
            <Tabs
              activeKey={currentSymbol}
              onChange={setActiveSymbol}
              size="small"
              items={symbols.map((s) => ({
                key: s,
                label: (
                  <span className="mono" style={{ fontSize: 12 }}>
                    {s}
                  </span>
                ),
              }))}
              style={{ marginBottom: 0, flex: 1 }}
            />
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <OverlaySelector value={overlayKeys} onChange={setOverlayKeys} />
              <span style={{ color: '#2b2f36' }}>|</span>
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
        </PanelCard>
      )}

      {/* Equity + Trades side by side on wide screens */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <PanelCard>
          <PanelHeader title="收益与回撤" icon={<LineChartOutlined />} />
          <div style={{ padding: '0 6px' }}>
            <EquityChart
              data={result.equity_curve}
              initialCash={result.metrics.initial_cash}
            />
          </div>
        </PanelCard>

        <PanelCard>
          <PanelHeader title="交易记录" icon={<UnorderedListOutlined />} />
          <div style={{ maxHeight: 280, overflow: 'auto' }}>
            <TradesTable trades={result.trades} />
          </div>
        </PanelCard>
      </div>
    </div>
  );
}
