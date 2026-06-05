import { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Empty,
  Input,
  InputNumber,
  Popconfirm,
  Segmented,
  Select,
  Spin,
  Switch,
  Table,
  Tag,
  Tooltip,
} from 'antd';
import {
  CopyOutlined,
  DeleteOutlined,
  FunctionOutlined,
  PlusOutlined,
  SaveOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import type {
  CompositeCondition,
  CompositeMetricDef,
  CompositeStock,
} from '../../types';
import { useScreeningStore } from '../../stores/screening';
import KlineChart, { type SubplotKey } from '../chart/KlineChart';
import OverlaySelector, {
  SubplotSelector,
  keysToOverlays,
} from '../chart/OverlaySelector';

const RISE = '#f6465d';
const FALL = '#0ecb81';

const CATEGORY_LABELS: Record<string, string> = {
  price: '价格行情',
  trend: '趋势指标',
  momentum: '动量指标',
  volume: '量价指标',
  risk: '风险指标',
  technical: '技术指标',
  custom: '自定义周期',
  pattern: '高级形态',
  fundamental: '基本面',
};

const OPERATOR_LABELS: Record<string, string> = {
  eq: '等于',
  neq: '不等于',
  gt: '大于',
  gte: '大于等于',
  lt: '小于',
  lte: '小于等于',
  between: '介于',
  above_metric: '高于指标',
  below_metric: '低于指标',
  cross_above: '上穿',
  cross_below: '下穿',
  rising: '连续走高',
  falling: '连续走低',
};

const METRIC_OPERATORS = new Set([
  'above_metric',
  'below_metric',
  'cross_above',
  'cross_below',
]);

const COMMON_METRIC_KEYS = [
  'kdj_k',
  'kdj_d',
  'kdj_j',
  'kdj_k_custom',
  'rsi6',
  'rsi12',
  'rsi24',
  'rsi_custom',
  'dif',
  'dea',
  'macd',
  'macd_dif_custom',
  'macd_dea_custom',
  'macd_bar_custom',
  'volume',
  'volume_ratio_5',
  'volume_ratio_10',
  'volume_ma_custom',
  'pdi',
  'mdi',
  'adx',
  'dmi_pdi_custom',
  'dmi_mdi_custom',
  'dmi_adx_custom',
  'dma',
  'dma_ama',
  'dma_custom',
  'dma_ama_custom',
  'bbi',
  'bbi_custom',
  'cci',
  'cci_custom',
];

function MetricTarget({
  condition,
  metric,
  metrics,
  onChange,
}: {
  condition: CompositeCondition;
  metric?: CompositeMetricDef;
  metrics: CompositeMetricDef[];
  onChange: (patch: Partial<CompositeCondition>) => void;
}) {
  if (METRIC_OPERATORS.has(condition.operator)) {
    return (
      <Select
        showSearch
        optionFilterProp="label"
        value={condition.compare_metric ?? undefined}
        placeholder="选择对比指标"
        options={metrics
          .filter((item) => item.value_type === 'number' && item.key !== condition.metric)
          .map((item) => ({ value: item.key, label: item.label }))}
        onChange={(compare_metric) => onChange({ compare_metric, value: null })}
      />
    );
  }
  if (condition.operator === 'between') {
    return (
      <div className="factor-range-input">
        <InputNumber
          value={typeof condition.value === 'number' ? condition.value : 0}
          onChange={(value) => onChange({ value: value ?? 0 })}
        />
        <span>至</span>
        <InputNumber
          value={condition.value2 ?? 0}
          onChange={(value) => onChange({ value2: value ?? 0 })}
        />
      </div>
    );
  }
  if (condition.operator === 'rising' || condition.operator === 'falling') {
    return (
      <InputNumber
        min={2}
        max={60}
        addonAfter="期"
        value={condition.periods}
        onChange={(periods) => onChange({ periods: periods ?? 3 })}
      />
    );
  }
  if (metric?.value_type === 'category') {
    return (
      <Select
        value={typeof condition.value === 'string' ? condition.value : metric.options[0]}
        options={metric.options.map((value) => ({ value, label: value }))}
        onChange={(value) => onChange({ value })}
      />
    );
  }
  return (
    <InputNumber
      value={typeof condition.value === 'number' ? condition.value : 0}
      addonAfter={metric?.unit || undefined}
      onChange={(value) => onChange({ value: value ?? 0 })}
    />
  );
}

function ConditionRow({
  groupId,
  condition,
  metrics,
}: {
  groupId: string;
  condition: CompositeCondition;
  metrics: CompositeMetricDef[];
}) {
  const update = useScreeningStore((state) => state.updateComposerCondition);
  const remove = useScreeningStore((state) => state.removeComposerCondition);
  const metric = metrics.find((item) => item.key === condition.metric);
  const groupedMetrics = useMemo(
    () => {
      const commonSet = new Set(COMMON_METRIC_KEYS);
      const common = COMMON_METRIC_KEYS
        .map((key) => metrics.find((item) => item.key === key))
        .filter((item): item is CompositeMetricDef => Boolean(item));
      const categories = Object.entries(
        metrics.reduce<Record<string, CompositeMetricDef[]>>((groups, item) => {
          if (!commonSet.has(item.key)) {
            (groups[item.category] ??= []).push(item);
          }
          return groups;
        }, {}),
      ).map(([category, items]) => ({
        label: CATEGORY_LABELS[category] ?? category,
        options: items.map((item) => ({
          value: item.key,
          label: item.label,
          title: item.description,
        })),
      }));
      return [
        {
          label: '常用指标',
          options: common.map((item) => ({
            value: item.key,
            label: item.label,
            title: item.description,
          })),
        },
        ...categories,
      ];
    },
    [metrics],
  );

  const patch = (value: Partial<CompositeCondition>) =>
    update(groupId, condition.id, value);

  return (
    <div className={`factor-condition-row ${condition.enabled ? '' : 'is-disabled'}`}>
      <Switch
        size="small"
        checked={condition.enabled}
        onChange={(enabled) => patch({ enabled })}
        aria-label="启用条件"
      />
      <div className="factor-condition-main">
        <Select
          className="factor-metric-select"
          showSearch
          optionFilterProp="label"
          value={condition.metric}
          options={groupedMetrics}
          onChange={(metricKey) => {
            const next = metrics.find((item) => item.key === metricKey);
            const operator = next?.operators[0] ?? 'gte';
            patch({
              metric: metricKey,
              operator,
              value: next?.value_type === 'category' ? next.options[0] : 0,
              value2: null,
              compare_metric: null,
              params: Object.fromEntries(
                (next?.params ?? []).map((param) => [param.key, param.default]),
              ),
            });
          }}
        />
        {metric?.params.map((param) => (
          <InputNumber
            key={param.key}
            className="factor-param-input"
            min={param.min}
            max={param.max}
            step={param.step}
            addonBefore={param.label}
            value={condition.params[param.key] ?? param.default}
            onChange={(value) =>
              patch({
                params: { ...condition.params, [param.key]: value ?? param.default },
              })
            }
          />
        ))}
        <Select
          className="factor-operator-select"
          value={condition.operator}
          options={(metric?.operators ?? []).map((operator) => ({
            value: operator,
            label: OPERATOR_LABELS[operator] ?? operator,
          }))}
          onChange={(operator) =>
            patch({
              operator,
              compare_metric: METRIC_OPERATORS.has(operator)
                ? condition.compare_metric ?? metrics.find((item) => item.key !== condition.metric)?.key
                : null,
            })
          }
        />
        <div className="factor-target-control">
          <MetricTarget
            condition={condition}
            metric={metric}
            metrics={metrics}
            onChange={patch}
          />
        </div>
      </div>
      <Tooltip title="必须满足：不通过时直接淘汰">
        <label className="factor-required-toggle">
          <Switch
            size="small"
            checked={condition.required}
            onChange={(required) => patch({ required })}
          />
          <span>必须</span>
        </label>
      </Tooltip>
      <Tooltip title="该条件在综合评分中的权重">
        <InputNumber
          className="factor-weight-input"
          min={0}
          max={100}
          step={0.5}
          addonBefore="权重"
          value={condition.weight}
          onChange={(weight) => patch({ weight: weight ?? 0 })}
        />
      </Tooltip>
      <Tooltip title="删除条件">
        <Button
          type="text"
          danger
          icon={<DeleteOutlined />}
          aria-label="删除条件"
          onClick={() => remove(groupId, condition.id)}
        />
      </Tooltip>
    </div>
  );
}

function ResultPanel() {
  const {
    composerResult,
    composerRunning,
    selectedSymbol,
    klineData,
    klineLoading,
    selectSymbol,
  } = useScreeningStore();
  const [overlayKeys, setOverlayKeys] = useState<string[]>(['MA5', 'MA20', 'BBI']);
  const [subplots, setSubplots] = useState<SubplotKey[]>(['VOL', 'MACD']);
  const selected = composerResult?.stocks.find((stock) => stock.symbol === selectedSymbol);

  const columns = [
    {
      title: '代码',
      dataIndex: 'symbol',
      width: 92,
      render: (symbol: string) => <span className="factor-symbol">{symbol}</span>,
    },
    {
      title: '综合分',
      dataIndex: 'score',
      width: 150,
      sorter: (a: CompositeStock, b: CompositeStock) => a.score - b.score,
      render: (score: number) => (
        <div className="factor-score-cell">
          <div><span style={{ width: `${score}%` }} /></div>
          <strong>{score.toFixed(1)}</strong>
        </div>
      ),
    },
    {
      title: '通过条件',
      width: 100,
      render: (_: unknown, stock: CompositeStock) => (
        <span className="mono">
          {stock.passed_conditions}/{stock.available_conditions}
        </span>
      ),
    },
    {
      title: '最新价',
      dataIndex: 'close',
      width: 90,
      align: 'right' as const,
      render: (value: number) => <span className="mono">{value.toFixed(2)}</span>,
    },
    {
      title: '涨跌幅',
      dataIndex: 'pct_chg',
      width: 90,
      align: 'right' as const,
      sorter: (a: CompositeStock, b: CompositeStock) => a.pct_chg - b.pct_chg,
      render: (value: number) => (
        <span className="mono" style={{ color: value >= 0 ? RISE : FALL }}>
          {value >= 0 ? '+' : ''}{value.toFixed(2)}%
        </span>
      ),
    },
    {
      title: '换手率',
      dataIndex: 'turnover_rate',
      width: 90,
      align: 'right' as const,
      render: (value?: number | null) => (
        <span className="mono">{value == null ? '--' : `${value.toFixed(2)}%`}</span>
      ),
    },
    {
      title: '命中逻辑',
      dataIndex: 'reasons',
      ellipsis: true,
      render: (reasons: string[]) => (
        <span className="factor-reason-preview">{reasons.slice(0, 2).join(' · ')}</span>
      ),
    },
  ];

  if (composerRunning) {
    return (
      <div className="factor-result-loading">
        <Spin size="large" />
        <strong>正在执行全市场组合扫描</strong>
        <span>按股票流式读取数据，完成后统一排序</span>
      </div>
    );
  }
  if (!composerResult) {
    return (
      <div className="factor-result-empty">
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="配置条件后运行策略，结果会在这里展开"
        />
      </div>
    );
  }

  return (
    <section className="factor-results">
      <div className="factor-result-summary">
        <div><span>扫描股票</span><strong>{composerResult.total_scanned}</strong></div>
        <div><span>策略命中</span><strong>{composerResult.total_matched}</strong></div>
        <div><span>返回结果</span><strong>{composerResult.returned}</strong></div>
        <div><span>运行耗时</span><strong>{composerResult.elapsed_seconds}s</strong></div>
        <div><span>交易日期</span><strong>{composerResult.scan_date}</strong></div>
      </div>
      {composerResult.warnings.map((warning) => (
        <Alert key={warning} type="warning" showIcon message={warning} />
      ))}
      <Table
        className="factor-result-table"
        dataSource={composerResult.stocks}
        columns={columns}
        rowKey="symbol"
        size="small"
        pagination={composerResult.stocks.length > 50 ? { pageSize: 50 } : false}
        scroll={{ x: 920, y: selectedSymbol ? 280 : 520 }}
        locale={{ emptyText: '没有股票满足当前组合策略' }}
        onRow={(stock) => ({
          onClick: () => selectSymbol(stock.symbol),
          className: stock.symbol === selectedSymbol ? 'is-selected' : '',
        })}
      />
      {selected && (
        <div className="factor-selected-reasons">
          <span>命中依据</span>
          {selected.reasons.map((reason) => (
            <Tag key={reason} color="success">{reason}</Tag>
          ))}
          {selected.failures.map((failure) => (
            <Tag key={failure} color="error">{failure}</Tag>
          ))}
        </div>
      )}
      {selectedSymbol && (
        <div className="factor-chart-panel">
          <div className="factor-chart-toolbar">
            <strong>{selectedSymbol} K线走势</strong>
            <div>
              <OverlaySelector value={overlayKeys} onChange={setOverlayKeys} />
              <SubplotSelector value={subplots} onChange={setSubplots} />
            </div>
          </div>
          {klineLoading ? (
            <div className="factor-chart-loading"><Spin /></div>
          ) : klineData?.length ? (
            <KlineChart
              kline={klineData}
              trades={[]}
              symbol={selectedSymbol}
              overlays={keysToOverlays(overlayKeys)}
              subplots={subplots}
            />
          ) : (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无 K 线数据" />
          )}
        </div>
      )}
    </section>
  );
}

export default function FactorStrategyBuilder() {
  const {
    composerDraft,
    composerMetrics,
    activeFactorStrategyId,
    composerDirty,
    composerSaving,
    error,
    loadComposer,
    updateComposerDraft,
    updateComposerGroup,
    removeComposerGroup,
    addComposerCondition,
    addComposerGroup,
    saveFactorStrategy,
    duplicateFactorStrategy,
  } = useScreeningStore();

  const enabledCount = composerDraft.groups.reduce(
    (total, group) => total + group.conditions.filter((condition) => condition.enabled).length,
    0,
  );

  useEffect(() => {
    if (composerMetrics.length === 0) {
      loadComposer();
    }
  }, [composerMetrics.length, loadComposer]);

  return (
    <div className="factor-workbench">
      <section className="factor-builder">
        <header className="factor-builder-header">
          <div className="factor-title-edit">
            <div>
              <FunctionOutlined />
              <Input
                variant="borderless"
                value={composerDraft.name}
                onChange={(event) => updateComposerDraft({ name: event.target.value })}
                placeholder="策略名称"
              />
            </div>
            <Input
              variant="borderless"
              value={composerDraft.description}
              onChange={(event) => updateComposerDraft({ description: event.target.value })}
              placeholder="补充这套策略的交易逻辑与适用场景"
            />
          </div>
          <div className="factor-header-actions">
            <Tag color={activeFactorStrategyId ? 'blue' : 'gold'}>
              {activeFactorStrategyId ? (composerDirty ? '有未保存修改' : '已保存') : '新策略'}
            </Tag>
            <Tag>{enabledCount} 个条件</Tag>
            <Tooltip title="复制为新策略">
              <Button icon={<CopyOutlined />} onClick={duplicateFactorStrategy} />
            </Tooltip>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              loading={composerSaving}
              disabled={!composerDraft.name.trim()}
              onClick={saveFactorStrategy}
            >
              保存策略
            </Button>
          </div>
        </header>

        {error && (
          <Alert
            closable
            type="error"
            showIcon
            message="组合策略操作失败"
            description={error}
          />
        )}

        <div className="factor-global-rule">
          <span>条件组之间</span>
          <Segmented
            value={composerDraft.logic}
            options={[
              { label: '全部满足', value: 'all' },
              { label: '任一满足', value: 'any' },
            ]}
            onChange={(logic) => updateComposerDraft({ logic: logic as 'all' | 'any' })}
          />
          <span>时进入评分，并要求综合分不低于</span>
          <InputNumber
            min={0}
            max={100}
            addonAfter="分"
            value={composerDraft.min_score}
            onChange={(min_score) => updateComposerDraft({ min_score: min_score ?? 0 })}
          />
        </div>

        <div className="factor-groups">
          {composerDraft.groups.map((group, groupIndex) => (
            <section className="factor-group" key={group.id}>
              <header className="factor-group-header">
                <span className="factor-group-index">{groupIndex + 1}</span>
                <Input
                  variant="borderless"
                  value={group.name}
                  onChange={(event) =>
                    updateComposerGroup(group.id, { name: event.target.value })
                  }
                />
                <span>组内条件</span>
                <Segmented
                  size="small"
                  value={group.logic}
                  options={[
                    { label: '全部满足', value: 'all' },
                    { label: '任一满足', value: 'any' },
                  ]}
                  onChange={(logic) =>
                    updateComposerGroup(group.id, { logic: logic as 'all' | 'any' })
                  }
                />
                <Button
                  type="text"
                  icon={<PlusOutlined />}
                  onClick={() => addComposerCondition(group.id)}
                >
                  添加条件
                </Button>
                <Popconfirm
                  title="删除这个条件组？"
                  onConfirm={() => removeComposerGroup(group.id)}
                >
                  <Tooltip title="删除条件组">
                    <Button
                      type="text"
                      danger
                      icon={<DeleteOutlined />}
                      disabled={composerDraft.groups.length === 1}
                      aria-label="删除条件组"
                    />
                  </Tooltip>
                </Popconfirm>
              </header>
              <div className="factor-condition-list">
                {group.conditions.map((condition) => (
                  <ConditionRow
                    key={condition.id}
                    groupId={group.id}
                    condition={condition}
                    metrics={composerMetrics}
                  />
                ))}
                {group.conditions.length === 0 && (
                  <button
                    className="factor-inline-add"
                    type="button"
                    onClick={() => addComposerCondition(group.id)}
                  >
                    <PlusOutlined /> 添加第一个条件
                  </button>
                )}
              </div>
            </section>
          ))}
          <Button
            className="factor-add-group"
            type="dashed"
            icon={<PlusOutlined />}
            onClick={addComposerGroup}
          >
            添加条件组
          </Button>
        </div>
      </section>

      <div className="factor-result-heading">
        <ThunderboltOutlined />
        <strong>策略运行结果</strong>
      </div>
      <ResultPanel />
    </div>
  );
}
