import { useEffect, useState } from 'react';
import { Alert, Button, Skeleton, Space, Tag } from 'antd';
import {
  ApiOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  CodeOutlined,
  ExclamationCircleOutlined,
  SafetyCertificateOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { fetchTradingStatus, type TradingStatus } from '../api/client';

function FieldTile({ label, value, sub }: { label: string; value: React.ReactNode; sub: string }) {
  return (
    <div className="trading-field-tile">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{sub}</small>
    </div>
  );
}

export default function TradingPage() {
  const [status, setStatus] = useState<TradingStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const next = await fetchTradingStatus();
        if (!cancelled) setStatus(next);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : '交易状态读取失败');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return <Skeleton active paragraph={{ rows: 10 }} />;
  }

  if (error || !status) {
    return <Alert type="error" showIcon title="交易运行状态不可用" description={error || '未返回状态'} />;
  }

  return (
    <div className="trading-page">
      <div className="workspace-heading">
        <div>
          <h1>交易运行中心</h1>
          <p>以人工启动为边界，集中查看仿真、实盘、风控和上线确认状态</p>
        </div>
        <Space>
          <Tag color={status.ready ? 'success' : 'warning'}>
            {status.ready ? '静态检查通过' : '待修复'}
          </Tag>
          <Tag color="processing">manual_start</Tag>
        </Space>
      </div>

      <Alert
        type="warning"
        showIcon
        title="实盘交易保持人工启动"
        description="此页面只展示运行状态和启动指令，不会连接券商、不解锁账户、也不会通过 Web UI 自动下单。"
      />

      <div className="trading-stat-grid">
        <FieldTile
          label="策略"
          value={status.strategy.name}
          sub={Object.entries(status.strategy.params).map(([k, v]) => `${k}=${v}`).join(' · ') || '默认参数'}
        />
        <FieldTile
          label="标的"
          value={`${status.data.symbols.length} 只`}
          sub={status.data.symbols.join(', ') || '未配置'}
        />
        <FieldTile
          label="风控"
          value={`${Math.round(status.risk.max_position_pct * 100)}% 仓位`}
          sub={`最大回撤 ${Math.round(status.risk.max_drawdown * 100)}%`}
        />
        <FieldTile
          label="券商"
          value={status.broker.type}
          sub={`${status.broker.host}:${status.broker.port}`}
        />
        <FieldTile
          label="调度"
          value={`${String(status.schedule.hour).padStart(2, '0')}:${String(status.schedule.minute).padStart(2, '0')}`}
          sub={status.schedule.cron}
        />
      </div>

      <div className="trading-command-panel">
        <div>
          <CodeOutlined />
          <strong>实盘启动命令</strong>
          <code>{status.entrypoint}</code>
        </div>
        <div>
          <ThunderboltOutlined />
          <strong>仿真/回测验证</strong>
          <code>{status.simulation.entrypoint}</code>
        </div>
      </div>

      <div className="trading-grid">
        <div className="surface-panel">
          <div className="panel-heading"><SafetyCertificateOutlined /> 运行检查</div>
          <div className="trading-check-list">
            {status.checks.map((check) => (
              <div key={check.key}>
                {check.level === 'ok' ? <CheckCircleOutlined /> : <ExclamationCircleOutlined />}
                <strong>{check.label}</strong>
                <span>{check.message}</span>
                <Tag color={check.level === 'ok' ? 'success' : 'warning'}>
                  {check.level.toUpperCase()}
                </Tag>
              </div>
            ))}
          </div>
        </div>

        <div className="surface-panel">
          <div className="panel-heading"><ClockCircleOutlined /> 人工确认清单</div>
          <div className="manual-confirm-list">
            {status.manual_confirmations.map((item, index) => (
              <div key={item}>
                <span className="mono">{String(index + 1).padStart(2, '0')}</span>
                <p>{item}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="surface-panel">
        <div className="panel-heading"><ApiOutlined /> 配置摘要</div>
        <div className="trading-config-summary">
          <div><span>配置文件</span><code>{status.config_path}</code></div>
          <div><span>数据源</span><code>{status.data.source}</code></div>
          <div><span>数据区间</span><code>{status.data.start_date} ~ {status.data.end_date}</code></div>
          <div><span>经纪商</span><code>{status.broker.connects_on_start ? '启动时连接' : '惰性连接'}</code></div>
        </div>
      </div>

      <Button type="primary" disabled>
        Web 实盘启动保持禁用
      </Button>
    </div>
  );
}
