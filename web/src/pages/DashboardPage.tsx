import { useEffect, useMemo, useState } from 'react';
import { Alert, Button, Progress, Skeleton, Tag } from 'antd';
import {
  ApiOutlined,
  BarChartOutlined,
  DatabaseOutlined,
  ExperimentOutlined,
  RadarChartOutlined,
  RobotOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons';
import {
  fetchAgentRuntime,
  fetchHealth,
  getCurrentDataJob,
  fetchSystemStatus,
  type AgentRuntime,
  type DataJob,
  type HealthStatus,
  type SystemCheck,
  type SystemStatus,
} from '../api/client';

interface Props {
  onPageChange: (page: string) => void;
}

function MetricTile({
  label,
  value,
  sub,
  tone = 'neutral',
}: {
  label: string;
  value: React.ReactNode;
  sub: string;
  tone?: 'neutral' | 'good' | 'warn';
}) {
  return (
    <div className={`overview-tile ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{sub}</small>
    </div>
  );
}

function CapabilityCard({
  icon,
  title,
  desc,
  status,
  action,
}: {
  icon: React.ReactNode;
  title: string;
  desc: string;
  status: React.ReactNode;
  action: React.ReactNode;
}) {
  return (
    <div className="capability-card">
      <div className="capability-card-icon">{icon}</div>
      <div className="capability-card-copy">
        <strong>{title}</strong>
        <span>{desc}</span>
      </div>
      <div className="capability-card-status">{status}</div>
      {action}
    </div>
  );
}

export default function DashboardPage({ onPageChange }: Props) {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [agent, setAgent] = useState<AgentRuntime | null>(null);
  const [system, setSystem] = useState<SystemStatus | null>(null);
  const [job, setJob] = useState<DataJob | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [nextHealth, nextAgent, nextSystem, nextJob] =
          await Promise.all([
            fetchHealth(),
            fetchAgentRuntime(),
            fetchSystemStatus(),
            getCurrentDataJob(),
          ]);
        if (cancelled) return;
        setHealth(nextHealth);
        setAgent(nextAgent);
        setSystem(nextSystem);
        setJob(nextJob.running ? nextJob : null);
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : '系统状态读取失败');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const checksByKey = useMemo(() => {
    const map: Record<string, SystemCheck> = {};
    system?.checks.forEach((check) => {
      map[check.key] = check;
    });
    return map;
  }, [system]);
  const dataCache = checksByKey.data_cache;
  const strategies = checksByKey.strategies;
  const indicators = checksByKey.indicators;
  const universe = checksByKey.universe;
  const cacheCount = Number(dataCache?.detail.cached_symbols || 0);
  const cacheBars = Number(dataCache?.detail.bars || 0);
  const strategyCount = Number(strategies?.detail.count || 0);
  const indicatorCount = Number(indicators?.detail.count || 0);
  const dataCoverage = system?.score || 0;

  return (
    <div className="dashboard-page">
      <div className="workspace-heading">
        <div>
          <h1>量化研究控制台</h1>
          <p>一站式管理数据、策略、选股、回测、AI 研究与运行状态</p>
        </div>
        <div className="workspace-meta">
          <span><ApiOutlined /> {health?.service || 'QuantLab API'}</span>
          <span><SafetyCertificateOutlined /> 风控与模拟撮合</span>
        </div>
      </div>

      {error && (
        <Alert type="error" showIcon title="系统状态读取失败" description={error} />
      )}

      {loading ? (
        <Skeleton active paragraph={{ rows: 8 }} />
      ) : (
        <>
          <div className="overview-grid">
            <MetricTile
              label="API 状态"
              value={health?.status === 'ok' ? '在线' : '未知'}
              sub={`版本 ${health?.version || 'unknown'}`}
              tone={health?.status === 'ok' ? 'good' : 'warn'}
            />
            <MetricTile
              label="本地缓存"
              value={`${cacheCount} 只`}
              sub={`${cacheBars.toLocaleString()} 根 K 线`}
              tone={cacheCount ? 'good' : 'warn'}
            />
            <MetricTile
              label="策略库"
              value={`${strategyCount} 个`}
              sub="回测与选股共用"
            />
            <MetricTile
              label="技术指标"
              value={`${indicatorCount} 个`}
              sub="可用于行情与因子"
            />
            <MetricTile
              label="AI 研究员"
              value={agent?.enabled ? '可用' : '未配置'}
              sub={agent?.configured ? `${agent.provider} / ${agent.model}` : '填写 API Key 后启用'}
              tone={agent?.enabled ? 'good' : 'warn'}
            />
          </div>

          <div className="ops-strip">
            <div>
              <strong>数据准备度</strong>
              <span>
                {system
                  ? `${system.summary.required_ok}/${system.summary.required_total} 个必需检查已通过`
                  : '缓存越完整，回测、选股和 Agent 工具调用越稳定'}
              </span>
            </div>
            <Progress percent={dataCoverage} size="small" status={dataCoverage ? 'active' : 'normal'} />
            {job && job.status !== 'idle' ? (
              <Tag color={job.running ? 'processing' : job.status === 'completed' ? 'success' : 'default'}>
                {job.status} · {job.completed}/{job.total}
              </Tag>
            ) : (
              <Tag>暂无数据任务</Tag>
            )}
          </div>

          <div className="capability-grid">
            <CapabilityCard
              icon={<DatabaseOutlined />}
              title="数据平台"
              desc="管理本地缓存、全市场下载、增量更新、指标物化和任务进度。"
              status={<Tag color={cacheCount ? 'success' : 'warning'}>{cacheCount ? '已有缓存' : '待初始化'}</Tag>}
              action={<Button onClick={() => onPageChange('data')}>打开</Button>}
            />
            <CapabilityCard
              icon={<ExperimentOutlined />}
              title="策略回测"
              desc="配置策略参数、风控比例和交易成本，查看 K 线、权益曲线和成交记录。"
              status={<Tag color="processing">{strategyCount} 个策略</Tag>}
              action={<Button onClick={() => onPageChange('backtest')}>打开</Button>}
            />
            <CapabilityCard
              icon={<RadarChartOutlined />}
              title="智能选股"
              desc="基于策略信号、五因子评分和可视化条件组合筛选本地股票池。"
              status={<Tag color="processing">因子工作台</Tag>}
              action={<Button onClick={() => onPageChange('screening')}>打开</Button>}
            />
            <CapabilityCard
              icon={<RobotOutlined />}
              title="AI 研究员"
              desc="通过多 Agent 工具调用行情、回测和选股模块，辅助生成研究结论。"
              status={<Tag color={agent?.enabled ? 'success' : 'warning'}>{agent?.enabled ? '可用' : '待配置'}</Tag>}
              action={<Button onClick={() => onPageChange('agent')}>打开</Button>}
            />
            <CapabilityCard
              icon={<BarChartOutlined />}
              title="上线验收"
              desc="后端测试、前端构建、健康检查和 UI 冒烟共同覆盖 clone 后启动路径。"
              status={<Tag color="success">已接入</Tag>}
              action={<Button onClick={() => onPageChange('data')}>查看数据</Button>}
            />
          </div>

          <div className="surface-panel">
            <div className="panel-heading">上线就绪检查</div>
            <div className="readiness-list">
              {(system?.checks || []).map((check) => (
                <div key={check.key}>
                  <Tag color={check.level === 'ok' ? 'success' : check.level === 'error' ? 'error' : 'warning'}>
                    {check.level === 'ok' ? 'OK' : check.level === 'error' ? 'ERROR' : 'WARN'}
                  </Tag>
                  <strong>{check.label}</strong>
                  <span>{check.message}</span>
                  {!check.required && <small>可选</small>}
                </div>
              ))}
              {universe?.level === 'warning' && (
                <div className="readiness-hint">
                  <DatabaseOutlined />
                  <span>建议先在数据平台刷新股票池并下载常用标的，之后再运行全市场选股。</span>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
