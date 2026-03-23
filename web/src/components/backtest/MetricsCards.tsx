import type { PerformanceMetrics } from '../../types';

interface Props {
  metrics: PerformanceMetrics;
}

interface MetricItem {
  label: string;
  value: string;
  color?: string;
  sub?: string;
}

function formatPct(v: number): string {
  return `${(v * 100).toFixed(2)}%`;
}

function formatMoney(v: number): string {
  if (v >= 1e8) return `${(v / 1e8).toFixed(2)}亿`;
  if (v >= 1e4) return `${(v / 1e4).toFixed(2)}万`;
  return v.toFixed(2);
}

export default function MetricsCards({ metrics }: Props) {
  const pnl = metrics.final_equity - metrics.initial_cash;

  const items: MetricItem[] = [
    {
      label: '总收益率',
      value: formatPct(metrics.total_return),
      color: metrics.total_return >= 0 ? 'var(--profit)' : 'var(--loss)',
      sub: `盈亏 ${pnl >= 0 ? '+' : ''}${formatMoney(pnl)}`,
    },
    {
      label: '年化收益',
      value: formatPct(metrics.annual_return),
      color: metrics.annual_return >= 0 ? 'var(--profit)' : 'var(--loss)',
    },
    {
      label: '最大回撤',
      value: formatPct(Math.abs(metrics.max_drawdown)),
      color: 'var(--loss)',
    },
    {
      label: 'Sharpe',
      value: metrics.sharpe_ratio !== null ? metrics.sharpe_ratio.toFixed(3) : '--',
      color: metrics.sharpe_ratio !== null && metrics.sharpe_ratio > 1 ? 'var(--profit)' : 'var(--text-primary)',
    },
    {
      label: '胜率',
      value: metrics.win_rate !== null ? `${(metrics.win_rate * 100).toFixed(1)}%` : '--',
      color: metrics.win_rate !== null && metrics.win_rate >= 0.5 ? 'var(--profit)' : 'var(--text-primary)',
    },
    {
      label: '盈亏比',
      value: metrics.profit_loss_ratio !== null ? metrics.profit_loss_ratio.toFixed(2) : '--',
    },
    {
      label: '交易次数',
      value: `${metrics.trade_count}`,
      sub: `佣金 ${formatMoney(metrics.total_commission)}`,
    },
  ];

  return (
    <div
      style={{
        display: 'flex',
        gap: 1,
        background: '#1e2126',
        borderRadius: 8,
        overflow: 'hidden',
      }}
    >
      {items.map((item) => (
        <div
          key={item.label}
          style={{
            flex: 1,
            background: '#141619',
            padding: '12px 14px',
            minWidth: 0,
          }}
        >
          <div style={{ color: '#5e6673', fontSize: 11, marginBottom: 4, whiteSpace: 'nowrap' }}>
            {item.label}
          </div>
          <div
            className="mono"
            style={{
              color: item.color ?? 'var(--text-primary)',
              fontSize: 18,
              fontWeight: 600,
              lineHeight: 1.2,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {item.value}
          </div>
          {item.sub && (
            <div style={{ color: '#5e6673', fontSize: 11, marginTop: 2 }} className="mono">
              {item.sub}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
