import { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, Button, Drawer, Input, InputNumber, Select, Skeleton, Table, Tag } from 'antd';
import {
  BarChartOutlined,
  DownloadOutlined,
  ExperimentOutlined,
  FundProjectionScreenOutlined,
  LineChartOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  SaveOutlined,
  StarFilled,
  StarOutlined,
} from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import {
  exportResearchReport,
  fetchResearchBacktest,
  fetchResearchBacktests,
  fetchResearchSummary,
  runBacktestGrid,
  updateResearchBacktestMetadata,
  type ResearchBacktestDetail,
  type ResearchBacktestRun,
  type ResearchSummary,
} from '../api/client';
import type { BacktestGridItem, BacktestGridResult, BacktestGridSortKey } from '../types';
import EquityChart from '../components/chart/EquityChart';
import TradesTable from '../components/backtest/TradesTable';

function pct(value: number | null | undefined) {
  if (value == null) return '-';
  return `${(value * 100).toFixed(2)}%`;
}

function parseGridValues(value: string) {
  return value
    .split(/[,\s]+/)
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => {
      const numeric = Number(item);
      return Number.isFinite(numeric) ? numeric : item;
    });
}

function StatTile({ label, value, sub }: { label: string; value: React.ReactNode; sub: string }) {
  return (
    <div className="research-stat-tile">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{sub}</small>
    </div>
  );
}

function metricLabel(key: BacktestGridSortKey) {
  const labels: Record<BacktestGridSortKey, string> = {
    total_return: '总收益',
    annual_return: '年化收益',
    max_drawdown: '最大回撤',
    sharpe_ratio: 'Sharpe',
    win_rate: '胜率',
    final_equity: '最终权益',
  };
  return labels[key];
}

function metricValue(item: BacktestGridItem, key: BacktestGridSortKey) {
  if (!item.metrics) return null;
  return item.metrics[key];
}

function formatMetricValue(value: number | null | undefined, key: BacktestGridSortKey) {
  if (value == null) return '-';
  if (key === 'total_return' || key === 'annual_return' || key === 'max_drawdown' || key === 'win_rate') {
    return pct(value);
  }
  if (key === 'final_equity') return value.toLocaleString(undefined, { maximumFractionDigits: 0 });
  return value.toFixed(4);
}

function buildGridInsight(result: BacktestGridResult | null) {
  const completed = result?.results.filter((item) => item.status === 'completed' && item.metrics) || [];
  const values = completed
    .map((item) => metricValue(item, result?.sort_by || 'total_return'))
    .filter((value): value is number => value != null);
  const returns = completed
    .map((item) => item.metrics?.total_return)
    .filter((value): value is number => value != null);
  const average = values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
  return {
    completed,
    values,
    average,
    positiveRate: returns.length ? returns.filter((value) => value > 0).length / returns.length : null,
    best: result?.best || null,
    worst: completed.length ? completed[completed.length - 1] : null,
  };
}

function GridHeatmap({
  result,
  onOpen,
}: {
  result: BacktestGridResult;
  onOpen: (item: BacktestGridItem) => void;
}) {
  const completed = result.results.filter((item) => item.status === 'completed' && item.metrics);
  const paramKeys = Object.keys(completed[0]?.strategy_params || {});
  if (completed.length === 0 || paramKeys.length < 2) {
    return null;
  }
  const [xKey, yKey] = paramKeys;
  const xValues = Array.from(new Set(completed.map((item) => String(item.strategy_params[xKey])))).sort(compareGridValue);
  const yValues = Array.from(new Set(completed.map((item) => String(item.strategy_params[yKey])))).sort(compareGridValue);
  const values = completed
    .map((item) => metricValue(item, result.sort_by))
    .filter((value): value is number => value != null);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const byKey = new Map(
    completed.map((item) => [`${item.strategy_params[xKey]}::${item.strategy_params[yKey]}`, item]),
  );

  return (
    <div className="grid-heatmap-wrap">
      <div className="grid-heatmap-title">
        <strong>{metricLabel(result.sort_by)} 参数热力图</strong>
        <span>{xKey} × {yKey}</span>
      </div>
      <div
        className="grid-heatmap"
        style={{ gridTemplateColumns: `92px repeat(${xValues.length}, minmax(82px, 1fr))` }}
      >
        <div className="grid-heatmap-axis">{yKey} \\ {xKey}</div>
        {xValues.map((value) => (
          <div className="grid-heatmap-axis" key={`x-${value}`}>{value}</div>
        ))}
        {yValues.map((yValue) => (
          <FragmentRow
            key={yValue}
            yKey={yKey}
            yValue={yValue}
            xValues={xValues}
            byKey={byKey}
            metric={result.sort_by}
            min={min}
            max={max}
            onOpen={onOpen}
          />
        ))}
      </div>
    </div>
  );
}

function FragmentRow({
  yKey,
  yValue,
  xValues,
  byKey,
  metric,
  min,
  max,
  onOpen,
}: {
  yKey: string;
  yValue: string;
  xValues: string[];
  byKey: Map<string, BacktestGridItem>;
  metric: BacktestGridSortKey;
  min: number;
  max: number;
  onOpen: (item: BacktestGridItem) => void;
}) {
  return (
    <>
      <div className="grid-heatmap-axis">{yKey}={yValue}</div>
      {xValues.map((xValue) => {
        const item = byKey.get(`${xValue}::${yValue}`);
        const value = item ? metricValue(item, metric) : null;
        return (
          <button
            key={`${xValue}-${yValue}`}
            className="grid-heatmap-cell"
            style={{ background: heatColor(value, min, max) }}
            disabled={!item?.run_id}
            onClick={() => item && onOpen(item)}
            title={item ? JSON.stringify(item.strategy_params) : 'missing'}
          >
            <strong>{formatMetricValue(value, metric)}</strong>
            <span>{item?.metrics ? `DD ${pct(item.metrics.max_drawdown)}` : '-'}</span>
          </button>
        );
      })}
    </>
  );
}

function compareGridValue(a: string, b: string) {
  const left = Number(a);
  const right = Number(b);
  if (Number.isFinite(left) && Number.isFinite(right)) return left - right;
  return a.localeCompare(b);
}

function heatColor(value: number | null, min: number, max: number) {
  if (value == null || !Number.isFinite(value)) return '#12191e';
  const span = max - min || 1;
  const strength = Math.max(0.12, Math.min(1, (value - min) / span));
  if (value >= 0) {
    return `rgba(42, 157, 143, ${0.2 + strength * 0.58})`;
  }
  return `rgba(214, 74, 74, ${0.2 + (1 - strength) * 0.58})`;
}

function labelRun(run: ResearchBacktestDetail | ResearchBacktestRun) {
  const params = 'request' in run ? Object.entries(run.request.strategy_params || {}) : [];
  const paramText = params.length
    ? params.map(([key, value]) => `${key}=${value}`).join(', ')
    : run.strategy;
  return `${run.id.slice(0, 6)} ${paramText}`;
}

function CompareEquityChart({ runs }: { runs: ResearchBacktestDetail[] }) {
  const option = useMemo(() => {
    const dateSet = new Set<string>();
    runs.forEach((run) => run.result.equity_curve.forEach((point) => dateSet.add(point.dt)));
    const dates = Array.from(dateSet).sort();
    const series = runs.map((run, index) => {
      const byDate = new Map(run.result.equity_curve.map((point) => [point.dt, point.equity]));
      return {
        name: labelRun(run),
        type: 'line',
        smooth: true,
        symbol: 'none',
        data: dates.map((date) => {
          const equity = byDate.get(date);
          return equity == null
            ? null
            : +((equity / run.metrics.initial_cash - 1) * 100).toFixed(4);
        }),
        lineStyle: { width: index === 0 ? 2 : 1.4 },
      };
    });
    return {
      backgroundColor: 'transparent',
      animation: false,
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#1a1d21',
        borderColor: '#2b2f36',
        textStyle: { color: '#eaecef', fontSize: 12 },
        valueFormatter: (value: number | null) => (value == null ? '-' : `${value.toFixed(2)}%`),
      },
      legend: {
        type: 'scroll',
        top: 4,
        right: 8,
        left: 8,
        textStyle: { color: '#8b98a5', fontSize: 10 },
      },
      grid: { left: 54, right: 18, top: 40, bottom: 34 },
      xAxis: {
        type: 'category',
        data: dates,
        axisLine: { lineStyle: { color: '#1e2126' } },
        axisTick: { show: false },
        axisLabel: { color: '#5e6673', fontSize: 10 },
      },
      yAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: '#1e2126', type: 'dashed' } },
        axisLabel: { color: '#5e6673', fontSize: 10, formatter: '{value}%' },
      },
      dataZoom: [{ type: 'inside', start: 0, end: 100 }],
      series,
    };
  }, [runs]);

  return <ReactECharts option={option} style={{ height: 260, width: '100%' }} opts={{ renderer: 'canvas' }} />;
}

export default function ResearchPage() {
  const [summary, setSummary] = useState<ResearchSummary | null>(null);
  const [runs, setRuns] = useState<ResearchBacktestRun[]>([]);
  const [detail, setDetail] = useState<ResearchBacktestDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedRunIds, setSelectedRunIds] = useState<React.Key[]>([]);
  const [compareDetails, setCompareDetails] = useState<ResearchBacktestDetail[]>([]);
  const [compareLoading, setCompareLoading] = useState(false);
  const [favoriteOnly, setFavoriteOnly] = useState(false);
  const [tagFilter, setTagFilter] = useState<string | undefined>();
  const [metadataSaving, setMetadataSaving] = useState(false);
  const [draftTags, setDraftTags] = useState('');
  const [draftNote, setDraftNote] = useState('');
  const [reportExporting, setReportExporting] = useState(false);
  const [gridSymbol, setGridSymbol] = useState('600519');
  const [gridStartDate, setGridStartDate] = useState('2024-01-01');
  const [gridEndDate, setGridEndDate] = useState('2024-03-31');
  const [fastGrid, setFastGrid] = useState('5, 10, 15');
  const [slowGrid, setSlowGrid] = useState('20, 30');
  const [gridSortBy, setGridSortBy] = useState<BacktestGridSortKey>('total_return');
  const [gridMaxRuns, setGridMaxRuns] = useState(20);
  const [gridRunning, setGridRunning] = useState(false);
  const [gridResult, setGridResult] = useState<BacktestGridResult | null>(null);
  const gridInsight = useMemo(() => buildGridInsight(gridResult), [gridResult]);
  const compareSummary = useMemo(() => {
    const returns = compareDetails.map((run) => run.total_return);
    const drawdowns = compareDetails.map((run) => run.max_drawdown);
    const sharpes = compareDetails
      .map((run) => run.sharpe_ratio)
      .filter((value): value is number => value != null);
    return {
      bestReturn: returns.length ? Math.max(...returns) : null,
      leastDrawdown: drawdowns.length ? Math.max(...drawdowns) : null,
      bestSharpe: sharpes.length ? Math.max(...sharpes) : null,
    };
  }, [compareDetails]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [nextSummary, nextRuns] = await Promise.all([
        fetchResearchSummary(),
        fetchResearchBacktests(50, {
          favorite: favoriteOnly || undefined,
          tag: tagFilter,
        }),
      ]);
      setSummary(nextSummary);
      setRuns(nextRuns);
    } catch (e) {
      setError(e instanceof Error ? e.message : '研究资产读取失败');
    } finally {
      setLoading(false);
    }
  }, [favoriteOnly, tagFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  const applyUpdatedRun = (updated: ResearchBacktestDetail) => {
    setRuns((items) => items.map((item) => (item.id === updated.id ? updated : item)));
    setCompareDetails((items) => items.map((item) => (item.id === updated.id ? updated : item)));
    setDetail((current) => (current?.id === updated.id ? updated : current));
  };

  const openDetail = async (run: ResearchBacktestRun) => {
    setDetailLoading(true);
    try {
      const nextDetail = await fetchResearchBacktest(run.id);
      setDetail(nextDetail);
      setDraftTags(nextDetail.tags.join(', '));
      setDraftNote(nextDetail.note);
    } catch (e) {
      setError(e instanceof Error ? e.message : '实验详情读取失败');
    } finally {
      setDetailLoading(false);
    }
  };

  const openGridRun = async (item: BacktestGridItem) => {
    if (!item.run_id) return;
    setDetailLoading(true);
    try {
      const nextDetail = await fetchResearchBacktest(item.run_id);
      setDetail(nextDetail);
      setDraftTags(nextDetail.tags.join(', '));
      setDraftNote(nextDetail.note);
    } catch (e) {
      setError(e instanceof Error ? e.message : '实验详情读取失败');
    } finally {
      setDetailLoading(false);
    }
  };

  const saveMetadata = async () => {
    if (!detail) return;
    setMetadataSaving(true);
    setError(null);
    try {
      const updated = await updateResearchBacktestMetadata(detail.id, {
        tags: draftTags.split(/[,\s]+/).map((item) => item.trim()).filter(Boolean),
        note: draftNote,
      });
      applyUpdatedRun(updated);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : '实验元数据保存失败');
    } finally {
      setMetadataSaving(false);
    }
  };

  const toggleFavorite = async (run: ResearchBacktestRun) => {
    setError(null);
    try {
      const updated = await updateResearchBacktestMetadata(run.id, {
        favorite: !run.favorite,
      });
      applyUpdatedRun(updated);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : '收藏状态保存失败');
    }
  };

  const downloadReport = async (runIds: string[]) => {
    if (runIds.length === 0) return;
    setReportExporting(true);
    setError(null);
    try {
      const content = await exportResearchReport(runIds);
      const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `quantlab-report-${new Date().toISOString().slice(0, 10)}.md`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : '研究报告导出失败');
    } finally {
      setReportExporting(false);
    }
  };

  const runComparison = async () => {
    const ids = selectedRunIds.slice(0, 6).map(String);
    if (ids.length < 2) return;
    setCompareLoading(true);
    setError(null);
    try {
      const details = await Promise.all(ids.map((id) => fetchResearchBacktest(id)));
      setCompareDetails(details);
    } catch (e) {
      setError(e instanceof Error ? e.message : '实验对比读取失败');
    } finally {
      setCompareLoading(false);
    }
  };

  const runGrid = async () => {
    setGridRunning(true);
    setError(null);
    try {
      const result = await runBacktestGrid({
        base: {
          symbols: gridSymbol.split(/[,\s]+/).filter(Boolean),
          start_date: gridStartDate,
          end_date: gridEndDate,
          strategy: 'ma_cross',
          strategy_params: {},
          initial_cash: 1000000,
          max_position_pct: 0.3,
          max_drawdown: 0.2,
          commission_rate: 0.00025,
        },
        parameters: {
          fast_period: parseGridValues(fastGrid),
          slow_period: parseGridValues(slowGrid),
        },
        max_runs: gridMaxRuns,
        sort_by: gridSortBy,
        sort_order: 'desc',
      });
      setGridResult(result);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : '参数实验运行失败');
    } finally {
      setGridRunning(false);
    }
  };

  const columns = [
    {
      title: '',
      key: 'favorite',
      width: 46,
      render: (_: unknown, row: ResearchBacktestRun) => (
        <Button
          type="text"
          size="small"
          className={row.favorite ? 'favorite-button active' : 'favorite-button'}
          icon={row.favorite ? <StarFilled /> : <StarOutlined />}
          onClick={(event) => {
            event.stopPropagation();
            void toggleFavorite(row);
          }}
        />
      ),
    },
    {
      title: '时间',
      dataIndex: 'created_at',
      width: 160,
      render: (value: string) => <span className="mono">{value.replace('T', ' ')}</span>,
    },
    {
      title: '策略',
      dataIndex: 'strategy',
      width: 130,
      render: (value: string) => <Tag color="processing">{value}</Tag>,
    },
    {
      title: '标的',
      dataIndex: 'symbols',
      width: 150,
      render: (value: string[]) => <span className="mono">{value.join(', ')}</span>,
    },
    {
      title: '区间',
      key: 'period',
      width: 210,
      render: (_: unknown, row: ResearchBacktestRun) => (
        <span className="mono">{row.start_date} ~ {row.end_date}</span>
      ),
    },
    {
      title: '收益',
      dataIndex: 'total_return',
      width: 110,
      sorter: (a: ResearchBacktestRun, b: ResearchBacktestRun) => a.total_return - b.total_return,
      render: (value: number) => (
        <span className={value >= 0 ? 'profit' : 'loss'}>{pct(value)}</span>
      ),
    },
    {
      title: '回撤',
      dataIndex: 'max_drawdown',
      width: 110,
      render: (value: number) => <span className="loss">{pct(value)}</span>,
    },
    {
      title: '交易',
      dataIndex: 'trade_count',
      width: 80,
      align: 'right' as const,
    },
    {
      title: '标签',
      dataIndex: 'tags',
      width: 170,
      render: (tags: string[]) => (
        <div className="research-tag-cell">
          {tags.length ? tags.map((tag) => <Tag key={tag}>{tag}</Tag>) : <span>-</span>}
        </div>
      ),
    },
  ];

  const gridColumns = [
    {
      title: '状态',
      dataIndex: 'status',
      width: 90,
      render: (value: string) => (
        <Tag color={value === 'completed' ? 'success' : 'error'}>
          {value === 'completed' ? '完成' : '失败'}
        </Tag>
      ),
    },
    {
      title: '参数',
      dataIndex: 'strategy_params',
      width: 220,
      render: (value: BacktestGridItem['strategy_params']) => (
        <span className="mono">
          {Object.entries(value).map(([key, val]) => `${key}=${val}`).join(', ')}
        </span>
      ),
    },
    {
      title: '收益',
      width: 90,
      render: (_: unknown, row: BacktestGridItem) => (
        <span className={(row.metrics?.total_return || 0) >= 0 ? 'profit' : 'loss'}>
          {pct(row.metrics?.total_return)}
        </span>
      ),
    },
    {
      title: '回撤',
      width: 90,
      render: (_: unknown, row: BacktestGridItem) => (
        <span className="loss">{pct(row.metrics?.max_drawdown)}</span>
      ),
    },
    {
      title: 'Sharpe',
      width: 90,
      render: (_: unknown, row: BacktestGridItem) => row.metrics?.sharpe_ratio ?? '-',
    },
    {
      title: '交易',
      width: 80,
      render: (_: unknown, row: BacktestGridItem) => row.metrics?.trade_count ?? '-',
    },
    {
      title: '错误',
      dataIndex: 'error',
      ellipsis: true,
      render: (value: string | null) => value || '-',
    },
  ];

  const compareColumns = [
    {
      title: '实验',
      width: 190,
      render: (_: unknown, row: ResearchBacktestDetail) => (
        <span className="mono">{labelRun(row)}</span>
      ),
    },
    {
      title: '收益',
      width: 90,
      sorter: (a: ResearchBacktestDetail, b: ResearchBacktestDetail) => a.total_return - b.total_return,
      render: (_: unknown, row: ResearchBacktestDetail) => (
        <span className={row.total_return >= 0 ? 'profit' : 'loss'}>{pct(row.total_return)}</span>
      ),
    },
    {
      title: '年化',
      width: 90,
      render: (_: unknown, row: ResearchBacktestDetail) => pct(row.annual_return),
    },
    {
      title: '回撤',
      width: 90,
      sorter: (a: ResearchBacktestDetail, b: ResearchBacktestDetail) => a.max_drawdown - b.max_drawdown,
      render: (_: unknown, row: ResearchBacktestDetail) => <span className="loss">{pct(row.max_drawdown)}</span>,
    },
    {
      title: 'Sharpe',
      width: 90,
      sorter: (a: ResearchBacktestDetail, b: ResearchBacktestDetail) => (a.sharpe_ratio || 0) - (b.sharpe_ratio || 0),
      render: (_: unknown, row: ResearchBacktestDetail) => row.sharpe_ratio ?? '-',
    },
    {
      title: '胜率',
      width: 90,
      render: (_: unknown, row: ResearchBacktestDetail) => pct(row.win_rate),
    },
    {
      title: '参数',
      render: (_: unknown, row: ResearchBacktestDetail) => (
        <span className="mono">{JSON.stringify(row.request.strategy_params || {})}</span>
      ),
    },
  ];

  return (
    <div className="research-page">
      <div className="workspace-heading">
        <div>
          <h1>研究资产库</h1>
          <p>沉淀回测实验、策略参数、绩效指标和交易明细</p>
        </div>
        <Button icon={<ReloadOutlined />} loading={loading} onClick={() => void load()}>
          刷新
        </Button>
      </div>

      {error && <Alert type="error" showIcon title="读取失败" description={error} />}

      {loading ? (
        <Skeleton active paragraph={{ rows: 9 }} />
      ) : (
        <>
          <div className="research-stat-grid">
            <StatTile
              label="回测实验"
              value={summary?.total_backtests || 0}
              sub={summary?.latest_at ? `最近 ${summary.latest_at.replace('T', ' ')}` : '暂无记录'}
            />
            <StatTile
              label="平均收益"
              value={pct(summary?.avg_total_return)}
              sub="按已保存实验统计"
            />
            <StatTile
              label="最佳收益"
              value={pct(summary?.best_total_return)}
              sub={summary?.best_run?.strategy || '暂无最佳实验'}
            />
            <StatTile
              label="最大回撤"
              value={pct(summary?.worst_drawdown)}
              sub="历史实验最低回撤"
            />
          </div>

          <div className="surface-panel">
            <div className="panel-heading"><PlayCircleOutlined /> 参数网格实验</div>
            <div className="grid-lab-form">
              <label>
                <span>标的</span>
                <Input value={gridSymbol} onChange={(event) => setGridSymbol(event.target.value)} />
              </label>
              <label>
                <span>开始</span>
                <Input value={gridStartDate} onChange={(event) => setGridStartDate(event.target.value)} />
              </label>
              <label>
                <span>结束</span>
                <Input value={gridEndDate} onChange={(event) => setGridEndDate(event.target.value)} />
              </label>
              <label>
                <span>fast_period</span>
                <Input value={fastGrid} onChange={(event) => setFastGrid(event.target.value)} />
              </label>
              <label>
                <span>slow_period</span>
                <Input value={slowGrid} onChange={(event) => setSlowGrid(event.target.value)} />
              </label>
              <label>
                <span>排序</span>
                <Select
                  value={gridSortBy}
                  onChange={setGridSortBy}
                  options={[
                    { value: 'total_return', label: '总收益' },
                    { value: 'annual_return', label: '年化收益' },
                    { value: 'max_drawdown', label: '最大回撤' },
                    { value: 'sharpe_ratio', label: 'Sharpe' },
                    { value: 'win_rate', label: '胜率' },
                    { value: 'final_equity', label: '最终权益' },
                  ]}
                />
              </label>
              <label>
                <span>上限</span>
                <InputNumber min={1} max={100} value={gridMaxRuns} onChange={(value) => setGridMaxRuns(value || 1)} />
              </label>
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                loading={gridRunning}
                onClick={() => void runGrid()}
              >
                运行网格
              </Button>
            </div>
            {gridResult && (
              <div className="grid-lab-result">
                <div className="grid-lab-summary">
                  <span>请求 <strong>{gridResult.requested}</strong></span>
                  <span>完成 <strong>{gridResult.completed}</strong></span>
                  <span>失败 <strong>{gridResult.failed}</strong></span>
                  <span>正收益 <strong>{pct(gridInsight.positiveRate)}</strong></span>
                  <span>均值 <strong>{formatMetricValue(gridInsight.average, gridResult.sort_by)}</strong></span>
                  <span>
                    最优{' '}
                    <strong>
                      {gridResult.best
                        ? Object.entries(gridResult.best.strategy_params).map(([key, val]) => `${key}=${val}`).join(', ')
                        : '-'}
                    </strong>
                  </span>
                  <span>
                    最弱{' '}
                    <strong>
                      {gridInsight.worst
                        ? Object.entries(gridInsight.worst.strategy_params).map(([key, val]) => `${key}=${val}`).join(', ')
                        : '-'}
                    </strong>
                  </span>
                </div>
                <GridHeatmap result={gridResult} onOpen={openGridRun} />
                <Table
                  dataSource={gridResult.results}
                  columns={gridColumns}
                  rowKey={(row) => row.run_id || JSON.stringify(row.strategy_params)}
                  size="small"
                  pagination={false}
                  scroll={{ x: 860, y: 260 }}
                  onRow={(record) => ({
                    onClick: () => void openGridRun(record),
                    style: { cursor: record.run_id ? 'pointer' : 'default' },
                  })}
                />
              </div>
            )}
          </div>

          <div className="surface-panel">
            <div className="panel-heading"><ExperimentOutlined /> 回测实验记录</div>
            <div className="research-filter-bar">
              <Button
                icon={favoriteOnly ? <StarFilled /> : <StarOutlined />}
                type={favoriteOnly ? 'primary' : 'default'}
                onClick={() => setFavoriteOnly((value) => !value)}
              >
                收藏 {summary?.favorite_count || 0}
              </Button>
              <Select
                allowClear
                placeholder="按标签筛选"
                value={tagFilter}
                onChange={(value) => setTagFilter(value)}
                options={(summary?.tags || []).map((item) => ({
                  value: item.tag,
                  label: `${item.tag} (${item.count})`,
                }))}
                style={{ minWidth: 180 }}
              />
              {(favoriteOnly || tagFilter) && (
                <Button
                  onClick={() => {
                    setFavoriteOnly(false);
                    setTagFilter(undefined);
                  }}
                >
                  清除筛选
                </Button>
              )}
            </div>
            <div className="compare-toolbar">
              <div>
                <strong>实验对比</strong>
                <span>选择 2-6 条历史实验，生成指标对比和归一化权益曲线。</span>
              </div>
              <Button
                icon={<LineChartOutlined />}
                loading={compareLoading}
                disabled={selectedRunIds.length < 2}
                onClick={() => void runComparison()}
              >
                生成对比
              </Button>
              <Button
                icon={<DownloadOutlined />}
                loading={reportExporting}
                disabled={selectedRunIds.length === 0}
                onClick={() => void downloadReport(selectedRunIds.map(String))}
              >
                导出报告
              </Button>
            </div>
            {compareDetails.length > 0 && (
              <div className="compare-panel">
                <div className="compare-summary-strip">
                  <span>已对比 <strong>{compareDetails.length}</strong></span>
                  <span>
                    最佳收益{' '}
                    <strong>{pct(compareSummary.bestReturn)}</strong>
                  </span>
                  <span>
                    最小回撤{' '}
                    <strong>{pct(compareSummary.leastDrawdown)}</strong>
                  </span>
                  <span>
                    最高 Sharpe{' '}
                    <strong>{compareSummary.bestSharpe == null ? '-' : compareSummary.bestSharpe.toFixed(4)}</strong>
                  </span>
                </div>
                <CompareEquityChart runs={compareDetails} />
                <Table
                  dataSource={compareDetails}
                  columns={compareColumns}
                  rowKey="id"
                  size="small"
                  pagination={false}
                  scroll={{ x: 860 }}
                  onRow={(record) => ({
                    onClick: () => openDetail(record),
                    style: { cursor: 'pointer' },
                  })}
                />
              </div>
            )}
            <Table
              dataSource={runs}
              columns={columns}
              rowKey="id"
              size="small"
              rowSelection={{
                selectedRowKeys: selectedRunIds,
                preserveSelectedRowKeys: true,
                onChange: (keys) => setSelectedRunIds(keys.slice(0, 6)),
                getCheckboxProps: (record) => ({
                  disabled: selectedRunIds.length >= 6 && !selectedRunIds.includes(record.id),
                }),
              }}
              pagination={{ pageSize: 20, showSizeChanger: false }}
              scroll={{ x: 980, y: 460 }}
              locale={{ emptyText: '暂无实验记录，运行一次回测后会自动保存' }}
              onRow={(record) => ({
                onClick: () => openDetail(record),
                style: { cursor: 'pointer' },
              })}
            />
          </div>
        </>
      )}

      <Drawer
        open={Boolean(detail) || detailLoading}
        onClose={() => setDetail(null)}
        title={detail ? `实验 ${detail.id.slice(0, 8)}` : '实验详情'}
        size="large"
      >
        {detailLoading || !detail ? (
          <Skeleton active paragraph={{ rows: 8 }} />
        ) : (
          <div className="research-detail">
            <div className="research-detail-grid">
              <StatTile label="策略" value={detail.strategy} sub={detail.symbols.join(', ')} />
              <StatTile label="总收益" value={pct(detail.total_return)} sub={`年化 ${pct(detail.annual_return)}`} />
              <StatTile label="最大回撤" value={pct(detail.max_drawdown)} sub={`Sharpe ${detail.sharpe_ratio ?? '-'}`} />
              <StatTile label="交易次数" value={detail.trade_count} sub={`胜率 ${pct(detail.win_rate)}`} />
            </div>

            <div className="surface-panel">
              <div className="panel-heading">
                {detail.favorite ? <StarFilled /> : <StarOutlined />}
                研究备注
              </div>
              <div className="metadata-editor">
                <label>
                  <span>标签</span>
                  <Input
                    value={draftTags}
                    onChange={(event) => setDraftTags(event.target.value)}
                    placeholder="candidate, stable, watchlist"
                  />
                </label>
                <label>
                  <span>备注</span>
                  <Input.TextArea
                    value={draftNote}
                    onChange={(event) => setDraftNote(event.target.value)}
                    autoSize={{ minRows: 3, maxRows: 6 }}
                    placeholder="记录参数选择、风险解释或复盘结论"
                  />
                </label>
                <div className="metadata-actions">
                  <Button
                    icon={detail.favorite ? <StarFilled /> : <StarOutlined />}
                    onClick={() => void toggleFavorite(detail)}
                  >
                    {detail.favorite ? '取消收藏' : '收藏实验'}
                  </Button>
                  <Button
                    icon={<DownloadOutlined />}
                    loading={reportExporting}
                    onClick={() => void downloadReport([detail.id])}
                  >
                    导出报告
                  </Button>
                  <Button
                    type="primary"
                    icon={<SaveOutlined />}
                    loading={metadataSaving}
                    onClick={() => void saveMetadata()}
                  >
                    保存备注
                  </Button>
                </div>
              </div>
            </div>

            <div className="surface-panel">
              <div className="panel-heading"><BarChartOutlined /> 权益曲线</div>
              <EquityChart
                data={detail.result.equity_curve}
                initialCash={detail.metrics.initial_cash}
              />
            </div>

            <div className="surface-panel">
              <div className="panel-heading"><FundProjectionScreenOutlined /> 交易明细</div>
              <TradesTable trades={detail.result.trades} />
            </div>

            <div className="surface-panel">
              <div className="panel-heading">请求参数</div>
              <pre className="research-json">{JSON.stringify(detail.request, null, 2)}</pre>
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
}
