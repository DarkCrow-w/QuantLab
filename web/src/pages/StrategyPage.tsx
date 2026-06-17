import { useEffect, useMemo } from 'react';
import { Alert, Button, Empty, Popconfirm, Space, Tag } from 'antd';
import {
  DeleteOutlined,
  ForkOutlined,
  PlusOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import FactorStrategyBuilder from '../components/screening/FactorStrategyBuilder';
import { useScreeningStore } from '../stores/screening';
import type { CompositeCondition, FactorStrategyDraft } from '../types';

const makeId = () =>
  globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`;

function condition(
  metric: string,
  operator: string,
  value: number | string | null,
  weight = 1,
): CompositeCondition {
  return {
    id: makeId(),
    metric,
    operator,
    value,
    value2: null,
    compare_metric: null,
    params: {},
    periods: 3,
    weight,
    required: true,
    enabled: true,
  };
}

function lowKdjVolumePreset(): FactorStrategyDraft {
  return {
    name: 'KDJ低位放量',
    description: '示例：KDJ-K 低于 20，同时成交量达到上一交易日 2 倍以上。',
    logic: 'all',
    groups: [
      {
        id: makeId(),
        name: '低位动量',
        logic: 'all',
        conditions: [
          condition('kdj_k', 'lt', 20, 1),
          condition('volume_ratio_1', 'gte', 2, 1.5),
        ],
      },
    ],
    min_score: 80,
    top_n: 100,
    lookback: 250,
  };
}

export default function StrategyPage() {
  const {
    activeFactorStrategyId,
    composerDirty,
    composerDraft,
    composerMetrics,
    composerRunning,
    error,
    factorStrategies,
    loadComposer,
    newFactorStrategy,
    removeFactorStrategy,
    runComposer,
    selectFactorStrategy,
    updateComposerDraft,
  } = useScreeningStore();

  useEffect(() => {
    void loadComposer();
  }, [loadComposer]);

  const enabledCount = useMemo(
    () => composerDraft.groups.reduce(
      (total, group) => total + group.conditions.filter((item) => item.enabled).length,
      0,
    ),
    [composerDraft.groups],
  );

  const applyLowKdjVolume = () => {
    updateComposerDraft(lowKdjVolumePreset());
  };

  return (
    <div className="strategy-management-page">
      <div className="workspace-heading">
        <div>
          <h1>策略管理</h1>
          <p>用指标、条件组和权重组合可管理策略，例如 KDJ 低位、成交量较昨日放大等</p>
        </div>
        <Space wrap>
          <Button icon={<ForkOutlined />} onClick={applyLowKdjVolume}>
            低位KDJ+昨日倍量
          </Button>
          <Button icon={<PlusOutlined />} onClick={newFactorStrategy}>
            新建组合策略
          </Button>
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            loading={composerRunning}
            disabled={composerMetrics.length === 0}
            onClick={runComposer}
          >
            运行策略
          </Button>
        </Space>
      </div>

      {error && (
        <Alert
          closable
          type="error"
          showIcon
          title="策略操作失败"
          description={error}
        />
      )}

      <div className="strategy-management-grid">
        <aside className="surface-panel strategy-list-panel">
          <div className="panel-heading">
            <span>策略库</span>
            <Tag>{factorStrategies.length}</Tag>
          </div>
          <div className="strategy-list">
            {factorStrategies.map((strategy) => {
              const active = strategy.id === activeFactorStrategyId;
              const conditionCount = strategy.groups.reduce(
                (total, group) => total + group.conditions.length,
                0,
              );
              return (
                <button
                  key={strategy.id}
                  type="button"
                  className={active ? 'active' : ''}
                  onClick={() => selectFactorStrategy(strategy.id)}
                >
                  <strong>{strategy.name}</strong>
                  <span>{strategy.description || '暂无说明'}</span>
                  <small>
                    {strategy.groups.length} 组 / {conditionCount} 条条件
                    {' · '}
                    {strategy.updated_at}
                  </small>
                </button>
              );
            })}
            {factorStrategies.length === 0 && (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="还没有保存的组合策略"
              />
            )}
          </div>
          <div className="strategy-list-footer">
            <div>
              <strong>{composerDraft.name}</strong>
              <span>{enabledCount} 条启用条件 · {composerDirty ? '未保存' : '已同步'}</span>
            </div>
            <Popconfirm
              title="删除当前策略？"
              disabled={!activeFactorStrategyId}
              onConfirm={removeFactorStrategy}
            >
              <Button
                danger
                icon={<DeleteOutlined />}
                disabled={!activeFactorStrategyId}
              />
            </Popconfirm>
          </div>
        </aside>

        <main className="strategy-builder-panel">
          <FactorStrategyBuilder />
        </main>
      </div>
    </div>
  );
}
