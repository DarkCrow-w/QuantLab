import { useEffect, useMemo, useState } from 'react';
import { Alert, Button, Empty, Popconfirm, Space, Tag } from 'antd';
import {
  DeleteOutlined,
  DownOutlined,
  FileSearchOutlined,
  ForkOutlined,
  PlusOutlined,
  RightOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import FactorStrategyBuilder from '../components/screening/FactorStrategyBuilder';
import { useScreeningStore } from '../stores/screening';
import { deleteBasicStrategyTemplate, fetchStrategyList } from '../api/client';
import type { CompositeCondition, FactorStrategyDraft, StrategyInfo } from '../types';

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
  const [basicStrategies, setBasicStrategies] = useState<StrategyInfo[]>([]);
  const [activeBasicStrategy, setActiveBasicStrategy] = useState<string | null>(null);
  const [basicCollapsed, setBasicCollapsed] = useState(false);
  const [compositeCollapsed, setCompositeCollapsed] = useState(false);
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
    void fetchStrategyList().then(setBasicStrategies);
  }, [loadComposer]);

  const enabledCount = useMemo(
    () => composerDraft.groups.reduce(
      (total, group) => total + group.conditions.filter((item) => item.enabled).length,
      0,
    ),
    [composerDraft.groups],
  );

  const applyLowKdjVolume = () => {
    setActiveBasicStrategy(null);
    updateComposerDraft(lowKdjVolumePreset());
  };

  const selectBasicStrategy = (name: string) => {
    setActiveBasicStrategy(name);
  };

  const removeBasicStrategy = async (name: string) => {
    await deleteBasicStrategyTemplate(name);
    setBasicStrategies((items) => items.filter((strategy) => strategy.name !== name));
    if (activeBasicStrategy === name) {
      setActiveBasicStrategy(null);
    }
  };

  const selectCompositeStrategy = (id: string) => {
    setActiveBasicStrategy(null);
    selectFactorStrategy(id);
  };

  const openActiveSamples = () => {
    if (!activeFactorStrategyId || typeof window === 'undefined') return;
    window.history.pushState(
      { page: 'samples' },
      '',
      `/samples?strategy=${encodeURIComponent(activeFactorStrategyId)}`,
    );
    window.dispatchEvent(new PopStateEvent('popstate'));
  };

  const activeBasic = basicStrategies.find((strategy) => strategy.name === activeBasicStrategy);
  const canDeleteActiveFactorStrategy = Boolean(activeFactorStrategyId);

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
            icon={<FileSearchOutlined />}
            disabled={!activeFactorStrategyId}
            onClick={openActiveSamples}
          >
            查看当前策略样例
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
            <span>基础策略模板</span>
            <Space size={6}>
              <Tag>{basicStrategies.length}</Tag>
              <Button
                size="small"
                type="text"
                icon={basicCollapsed ? <RightOutlined /> : <DownOutlined />}
                aria-label={basicCollapsed ? '展开基础策略模板' : '收起基础策略模板'}
                onClick={() => setBasicCollapsed((value) => !value)}
              />
            </Space>
          </div>
          {!basicCollapsed && (
            <div className="strategy-list">
              {basicStrategies.map((strategy) => (
                <div
                  key={strategy.name}
                  className={`strategy-list-item ${strategy.name === activeBasicStrategy ? 'active' : ''}`}
                >
                  <button
                    type="button"
                    title={strategy.params_schema.map((param) => param.name).join(', ')}
                    onClick={() => selectBasicStrategy(strategy.name)}
                  >
                    <strong>{strategy.display_name}</strong>
                    <span>{strategy.name}</span>
                    <small>
                      {strategy.params_schema.length} 个参数
                    </small>
                  </button>
                  <Popconfirm
                    title="删除这个基础模板？"
                    onConfirm={() => removeBasicStrategy(strategy.name)}
                  >
                    <Button
                      danger
                      type="text"
                      size="small"
                      icon={<DeleteOutlined />}
                      aria-label={`删除 ${strategy.display_name}`}
                    />
                  </Popconfirm>
                </div>
              ))}
              {basicStrategies.length === 0 && (
                <Empty
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                  description="暂无基础策略模板"
                />
              )}
            </div>
          )}

          <div className="panel-heading" style={{ marginTop: 14 }}>
            <span>组合策略库</span>
            <Space size={6}>
              <Tag>{factorStrategies.length}</Tag>
              <Button
                size="small"
                type="text"
                icon={compositeCollapsed ? <RightOutlined /> : <DownOutlined />}
                aria-label={compositeCollapsed ? '展开组合策略库' : '收起组合策略库'}
                onClick={() => setCompositeCollapsed((value) => !value)}
              />
            </Space>
          </div>
          {!compositeCollapsed && (
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
                    onClick={() => selectCompositeStrategy(strategy.id)}
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
          )}
          <div className="strategy-list-footer">
            <div>
              <strong>{composerDraft.name}</strong>
              <span>{enabledCount} 条启用条件 · {composerDirty ? '未保存' : '已同步'}</span>
            </div>
            <Popconfirm
              title="删除当前策略？"
              disabled={!canDeleteActiveFactorStrategy}
              onConfirm={removeFactorStrategy}
            >
              <Button
                danger
                icon={<DeleteOutlined />}
                disabled={!canDeleteActiveFactorStrategy}
              />
            </Popconfirm>
          </div>
        </aside>

        <main className="strategy-builder-panel">
          {activeBasic ? (
            <section className="surface-panel" style={{ padding: 18 }}>
              <div className="panel-heading">
                <span>{activeBasic.display_name}</span>
                <Tag color="blue">基础策略</Tag>
              </div>
              <p style={{ color: '#848e9c', marginTop: 8 }}>
                这是可直接用于回测和选股扫描的代码策略模板。它的参数在回测工作台或智能选股的策略配置里填写；
                组合条件编辑器只适用于右侧“组合策略库”里的可视化条件策略。
              </p>
              <div className="strategy-list" style={{ marginTop: 14 }}>
                {activeBasic.params_schema.map((param) => (
                  <div key={param.name} className="surface-panel" style={{ padding: 12 }}>
                    <strong>{param.label}</strong>
                    <span className="mono">{param.name}</span>
                    <small>
                      类型：{param.type}
                      {' · 默认值：'}
                      {String(param.default)}
                      {param.min !== null && param.min !== undefined ? ` · 最小：${param.min}` : ''}
                      {param.max !== null && param.max !== undefined ? ` · 最大：${param.max}` : ''}
                    </small>
                  </div>
                ))}
              </div>
            </section>
          ) : (
            <FactorStrategyBuilder />
          )}
        </main>
      </div>
    </div>
  );
}
