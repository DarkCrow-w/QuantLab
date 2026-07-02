import { useEffect, useMemo, useState } from 'react';
import { Alert, Button, Descriptions, Empty, Select, Skeleton, Space, Tag } from 'antd';
import {
  AppstoreOutlined,
  ReloadOutlined,
  SelectOutlined,
} from '@ant-design/icons';
import KlineChart from '../components/chart/KlineChart';
import { fetchStrategySamples } from '../api/client';
import type { StrategySampleLibrary, StrategySampleTrade } from '../types';

const DEFAULT_SAMPLE_STRATEGY = 'preset_volume_pullback_swing_dip';

function strategyFromLocation() {
  if (typeof window === 'undefined') return DEFAULT_SAMPLE_STRATEGY;
  return new URLSearchParams(window.location.search).get('strategy') ?? DEFAULT_SAMPLE_STRATEGY;
}

function pctColor(value?: number) {
  if (value === undefined) return '#8d9ba7';
  return value >= 0 ? '#19c37d' : '#f05b67';
}

function pctText(value?: number | null) {
  if (value === undefined || value === null) return '-';
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
}

function statusText(trade: StrategySampleTrade) {
  if (trade.trade_status === 'stop_loss') return '止损';
  if (trade.trade_status === 'holding') return '持有中';
  return '清仓';
}

function statusColor(trade: StrategySampleTrade) {
  if (trade.trade_status === 'stop_loss') return 'red';
  if (trade.trade_status === 'holding') return 'blue';
  return undefined;
}

function exitDateText(trade: StrategySampleTrade) {
  if (trade.trade_status === 'holding') return `截至 ${trade.exit_date}`;
  return `${statusText(trade)} ${trade.exit_date}`;
}

export default function SampleLibraryPage() {
  const [strategy, setStrategy] = useState(strategyFromLocation);
  const [library, setLibrary] = useState<StrategySampleLibrary | null>(null);
  const [activeTradeId, setActiveTradeId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async (nextStrategy = strategy) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchStrategySamples(nextStrategy);
      setLibrary(data);
      setActiveTradeId(data.trades[0]?.id ?? null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '读取策略样例库失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load(strategy);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [strategy]);

  const changeStrategy = (nextStrategy: string) => {
    setStrategy(nextStrategy);
    if (typeof window !== 'undefined') {
      window.history.replaceState(
        { page: 'samples' },
        '',
        `/samples?strategy=${encodeURIComponent(nextStrategy)}`,
      );
    }
  };

  const activeTrade = useMemo(
    () => library?.trades.find((trade) => trade.id === activeTradeId) ?? library?.trades[0],
    [activeTradeId, library],
  );

  const strategyOptions = library?.strategies.map((item) => ({
    value: item.id ?? item.name,
    label: `${item.display_name}${item.trade_count ? ` · ${item.trade_count}笔交易` : ' · 暂无用例'}`,
  })) ?? [{ value: DEFAULT_SAMPLE_STRATEGY, label: '放量缩量回调抄底' }];

  return (
    <div className="sample-library-page">
      <div className="workspace-heading">
        <div>
          <h1>策略样例库</h1>
          <p>先选择策略，再查看该策略下沉淀过的交易样例；每个矩形块代表一次完整交易或持有中的交易。</p>
        </div>
        <Space wrap>
          <Select
            value={strategy}
            options={strategyOptions}
            style={{ width: 320 }}
            onChange={changeStrategy}
          />
          <Button icon={<ReloadOutlined />} loading={loading} onClick={() => load()}>
            刷新
          </Button>
        </Space>
      </div>

      {error && <Alert type="error" showIcon title="样例库加载失败" description={error} />}

      {loading && !library ? (
        <Skeleton active paragraph={{ rows: 10 }} />
      ) : library ? (
        <>
          <div className="sample-summary-grid">
            <div><span>样例</span><strong>{library.summary.sample_count}</strong></div>
            <div><span>交易</span><strong>{library.summary.trade_count}</strong></div>
            <div><span>胜率</span><strong>{(library.summary.win_rate * 100).toFixed(1)}%</strong></div>
            <div>
              <span>平均收益</span>
              <strong style={{ color: pctColor(library.summary.avg_return_pct) }}>
                {pctText(library.summary.avg_return_pct)}
              </strong>
            </div>
            <div>
              <span>最好</span>
              <strong style={{ color: pctColor(library.summary.best_return_pct) }}>
                {pctText(library.summary.best_return_pct)}
              </strong>
            </div>
            <div>
              <span>最差</span>
              <strong style={{ color: pctColor(library.summary.worst_return_pct) }}>
                {pctText(library.summary.worst_return_pct)}
              </strong>
            </div>
          </div>

          <div className="sample-workbench">
            <section className="surface-panel sample-block-panel">
              <div className="panel-heading">
                <span><AppstoreOutlined /> 交易样例</span>
                <Tag>{library.trades.length}</Tag>
              </div>
              {library.trades.length ? (
                <div className="sample-trade-grid">
                  {library.trades.map((trade) => (
                    <TradeBlock
                      key={trade.id}
                      trade={trade}
                      active={trade.id === activeTrade?.id}
                      onClick={() => setActiveTradeId(trade.id)}
                    />
                  ))}
                </div>
              ) : (
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="该策略暂无交易样例" />
              )}
            </section>

            <section className="surface-panel sample-detail-panel">
              {activeTrade ? (
                <TradeDetail trade={activeTrade} />
              ) : (
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="选择一笔交易查看详情" />
              )}
            </section>
          </div>
        </>
      ) : (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无样例数据" />
      )}
    </div>
  );
}

function TradeBlock({
  trade,
  active,
  onClick,
}: {
  trade: StrategySampleTrade;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={`sample-trade-block ${active ? 'active' : ''}`}
      onClick={onClick}
    >
      <span className="sample-trade-symbol mono">{trade.symbol}</span>
      <strong style={{ color: pctColor(trade.total_return_pct) }}>
        {pctText(trade.total_return_pct)}
      </strong>
      <small>命中 {trade.buy_date}</small>
      <small>{exitDateText(trade)}</small>
      <em>{trade.holding_days ?? '-'}天</em>
    </button>
  );
}

function TradeDetail({ trade }: { trade: StrategySampleTrade }) {
  const kline = trade.kline ?? [];
  const chartTrades = trade.chart_trades ?? [];
  return (
    <>
      <div className="panel-heading">
        <span><SelectOutlined /> {trade.symbol}{trade.name ? ` ${trade.name}` : ''} 交易详情</span>
        <Space size={6}>
          <Tag color="green">命中 {trade.buy_date}</Tag>
          <Tag color={statusColor(trade)}>{exitDateText(trade)}</Tag>
        </Space>
      </div>

      <Descriptions
        className="sample-trade-detail"
        size="small"
        column={{ xs: 1, sm: 2, lg: 4 }}
        items={[
          { key: 'buy', label: '买入价', children: trade.buy_price?.toFixed(2) ?? '-' },
          { key: 'reduce', label: '减仓价', children: trade.reduce_price?.toFixed(2) ?? '-' },
          { key: 'exit', label: trade.trade_status === 'holding' ? '当前价' : '退出价', children: trade.exit_price?.toFixed(2) ?? '-' },
          {
            key: 'return',
            label: trade.trade_status === 'holding' ? '浮动收益' : '合成收益',
            children: (
              <strong style={{ color: pctColor(trade.total_return_pct) }}>
                {pctText(trade.total_return_pct)}
              </strong>
            ),
          },
          { key: 'reduceReturn', label: '减仓收益', children: pctText(trade.reduce_return_pct) },
          { key: 'exitReturn', label: trade.trade_status === 'holding' ? '剩余浮盈' : '退出收益', children: pctText(trade.exit_return_pct) },
          { key: 'days', label: '持有天数', children: trade.holding_days ? `${trade.holding_days}天` : '-' },
          {
            key: 'window',
            label: '观察区间',
            children: `${trade.observation_start ?? '-'} ~ ${trade.observation_end ?? '-'}`,
          },
        ]}
      />

      <p className="sample-reason">{trade.reason}</p>

      {kline.length ? (
        <KlineChart
          symbol={trade.symbol}
          kline={kline}
          trades={chartTrades}
          overlays={[
            { type: 'MA', period: 60, color: '#8d9ba7' },
            { type: 'BBI', color: '#f6bd16' },
          ]}
          subplots={['VOL', 'KDJ', 'RSI']}
        />
      ) : (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无K线数据" />
      )}
    </>
  );
}
