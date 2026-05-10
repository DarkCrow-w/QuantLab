import { useState } from 'react';
import { Alert, Spin, Table, Tag } from 'antd';
import { FundOutlined, SearchOutlined } from '@ant-design/icons';
import { useScreeningStore } from '../stores/screening';
import KlineChart, { type SubplotKey } from '../components/chart/KlineChart';
import OverlaySelector, {
  SubplotSelector,
  keysToOverlays,
} from '../components/chart/OverlaySelector';

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
        <SearchOutlined style={{ fontSize: 28, color: '#2b2f36' }} />
      </div>
      <div style={{ color: '#5e6673', fontSize: 14 }}>配置策略后点击开始选股</div>
      <div style={{ color: '#2b2f36', fontSize: 12 }}>扫描全部已缓存股票，找出买入信号</div>
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

function formatVolume(v: number): string {
  if (v >= 1e8) return (v / 1e8).toFixed(2) + '亿';
  if (v >= 1e4) return (v / 1e4).toFixed(0) + '万';
  return v.toFixed(0);
}

function formatAmount(v: number): string {
  if (v >= 1e8) return (v / 1e8).toFixed(2) + '亿';
  if (v >= 1e4) return (v / 1e4).toFixed(0) + '万';
  return v.toFixed(0);
}

export default function ScreeningPage() {
  const { result, loading, error, selectedSymbol, klineData, klineLoading, selectSymbol } =
    useScreeningStore();
  const [overlayKeys, setOverlayKeys] = useState<string[]>(['MA5', 'MA20', 'BBI']);
  const [subplots, setSubplots] = useState<SubplotKey[]>(['VOL', 'MACD']);

  if (loading) {
    return (
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: '100%',
          minHeight: 400,
        }}
      >
        <Spin size="large" tip="正在扫描全部股票..." style={{ color: '#848e9c' }}>
          <div style={{ padding: 50 }} />
        </Spin>
      </div>
    );
  }

  if (error) {
    return (
      <Alert
        type="error"
        message="选股失败"
        description={error}
        showIcon
        style={{ margin: 20, background: '#1a1d21', border: '1px solid #f6465d40' }}
      />
    );
  }

  if (!result) return <EmptyState />;

  const columns = [
    {
      title: '代码',
      dataIndex: 'symbol',
      key: 'symbol',
      width: 90,
      render: (v: string) => (
        <span className="mono" style={{ color: '#1890ff', fontWeight: 500 }}>
          {v}
        </span>
      ),
    },
    {
      title: '信号日期',
      dataIndex: 'signal_date',
      key: 'signal_date',
      width: 110,
      sorter: (a: { signal_date: string }, b: { signal_date: string }) =>
        a.signal_date.localeCompare(b.signal_date),
    },
    {
      title: '收盘价',
      dataIndex: 'close',
      key: 'close',
      width: 90,
      align: 'right' as const,
      sorter: (a: { close: number }, b: { close: number }) => a.close - b.close,
      render: (v: number) => <span className="mono">{v.toFixed(2)}</span>,
    },
    {
      title: '成交量',
      dataIndex: 'volume',
      key: 'volume',
      width: 90,
      align: 'right' as const,
      sorter: (a: { volume: number }, b: { volume: number }) => a.volume - b.volume,
      render: (v: number) => <span className="mono">{formatVolume(v)}</span>,
    },
    {
      title: '成交额',
      dataIndex: 'amount',
      key: 'amount',
      width: 90,
      align: 'right' as const,
      sorter: (a: { amount: number }, b: { amount: number }) => a.amount - b.amount,
      render: (v: number) => <span className="mono">{formatAmount(v)}</span>,
    },
    {
      title: '信号强度',
      dataIndex: 'strength',
      key: 'strength',
      width: 80,
      align: 'center' as const,
      sorter: (a: { strength: number }, b: { strength: number }) => a.strength - b.strength,
      render: (v: number) => (
        <Tag
          color={v >= 0.8 ? '#f6465d' : v >= 0.5 ? '#f0b90b' : '#848e9c'}
          style={{ margin: 0, borderRadius: 3, border: 'none', fontSize: 11 }}
        >
          {(v * 100).toFixed(0)}%
        </Tag>
      ),
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* Stats Bar */}
      <PanelCard style={{ padding: '10px 16px' }}>
        <div style={{ display: 'flex', gap: 24, alignItems: 'center', fontSize: 13 }}>
          <div>
            <FundOutlined style={{ color: '#1890ff', marginRight: 6 }} />
            <span style={{ color: '#848e9c' }}>扫描</span>{' '}
            <span className="mono" style={{ color: '#eaecef', fontWeight: 500 }}>
              {result.total_scanned}
            </span>{' '}
            <span style={{ color: '#848e9c' }}>只</span>
          </div>
          <div>
            <span style={{ color: '#848e9c' }}>命中</span>{' '}
            <span
              className="mono"
              style={{ color: result.matches.length > 0 ? '#0ecb81' : '#5e6673', fontWeight: 600 }}
            >
              {result.matches.length}
            </span>{' '}
            <span style={{ color: '#848e9c' }}>只</span>
          </div>
          <div>
            <span style={{ color: '#848e9c' }}>耗时</span>{' '}
            <span className="mono" style={{ color: '#eaecef' }}>
              {result.elapsed_seconds}s
            </span>
          </div>
          <div>
            <span style={{ color: '#848e9c' }}>日期</span>{' '}
            <span className="mono" style={{ color: '#eaecef' }}>
              {result.scan_date}
            </span>
          </div>
        </div>
      </PanelCard>

      {/* Results Table */}
      <PanelCard>
        <Table
          dataSource={result.matches}
          columns={columns}
          rowKey="symbol"
          size="small"
          pagination={result.matches.length > 50 ? { pageSize: 50, size: 'small' } : false}
          scroll={{ y: selectedSymbol ? 260 : 500 }}
          onRow={(record) => ({
            onClick: () => selectSymbol(record.symbol),
            style: {
              cursor: 'pointer',
              background: record.symbol === selectedSymbol ? '#1a1d21' : undefined,
            },
          })}
          locale={{ emptyText: '未找到符合条件的股票' }}
        />
      </PanelCard>

      {/* K-line Chart */}
      {selectedSymbol && (
        <PanelCard>
          <div
            style={{
              padding: '8px 14px',
              borderBottom: '1px solid #1e2126',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 16,
              color: '#848e9c',
              fontSize: 12,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span className="mono" style={{ color: '#1890ff', fontWeight: 500 }}>
                {selectedSymbol}
              </span>
              <span>K线走势</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <OverlaySelector value={overlayKeys} onChange={setOverlayKeys} />
              <span style={{ color: '#2b2f36' }}>|</span>
              <SubplotSelector value={subplots} onChange={setSubplots} />
            </div>
          </div>
          {klineLoading ? (
            <div style={{ padding: 40, textAlign: 'center' }}>
              <Spin size="small" />
            </div>
          ) : klineData && klineData.length > 0 ? (
            <div style={{ padding: '0 6px' }}>
              <KlineChart
                kline={klineData}
                trades={[]}
                symbol={selectedSymbol}
                overlays={keysToOverlays(overlayKeys)}
                subplots={subplots}
              />
            </div>
          ) : (
            <div style={{ padding: 40, textAlign: 'center', color: '#5e6673' }}>
              暂无K线数据
            </div>
          )}
        </PanelCard>
      )}
    </div>
  );
}
