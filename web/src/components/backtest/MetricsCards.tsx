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

const formatPct = (value: number) => `${(value * 100).toFixed(2)}%`;

function formatMoney(value: number): string {
  if (Math.abs(value) >= 1e8) return `${(value / 1e8).toFixed(2)} 亿`;
  if (Math.abs(value) >= 1e4) return `${(value / 1e4).toFixed(2)} 万`;
  return value.toFixed(2);
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
      label: '夏普比率',
      value: metrics.sharpe_ratio !== null ? metrics.sharpe_ratio.toFixed(3) : '--',
      color: metrics.sharpe_ratio !== null && metrics.sharpe_ratio > 1 ? 'var(--profit)' : undefined,
    },
    {
      label: '胜率',
      value: metrics.win_rate !== null ? `${(metrics.win_rate * 100).toFixed(1)}%` : '--',
      color: metrics.win_rate !== null && metrics.win_rate >= 0.5 ? 'var(--profit)' : undefined,
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
    <div className="metric-grid">
      {items.map((item) => (
        <div className="metric-item" key={item.label}>
          <div className="metric-label">{item.label}</div>
          <div className="metric-value" style={{ color: item.color }}>{item.value}</div>
          {item.sub && <div className="metric-sub">{item.sub}</div>}
        </div>
      ))}
    </div>
  );
}
