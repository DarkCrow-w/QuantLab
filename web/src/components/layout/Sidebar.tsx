import { useEffect } from 'react';
import { Button, DatePicker, InputNumber, Select, Space, Typography, Collapse } from 'antd';
import {
  CaretRightOutlined,
  ExperimentOutlined,
  StockOutlined,
  CalendarOutlined,
  DollarOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import { useBacktestStore } from '../../stores/backtest';

const { Text } = Typography;

const labelStyle: React.CSSProperties = {
  color: '#848e9c',
  fontSize: 11,
  textTransform: 'uppercase' as const,
  letterSpacing: '0.5px',
  marginBottom: 4,
  display: 'block',
};

function SectionHeader({ icon, title }: { icon: React.ReactNode; title: string }) {
  return (
    <Space size={6} style={{ color: '#eaecef', fontSize: 13, fontWeight: 500 }}>
      {icon}
      {title}
    </Space>
  );
}

export default function Sidebar() {
  const store = useBacktestStore();

  useEffect(() => {
    store.loadStrategies();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const currentStrategy = store.strategies.find((s) => s.name === store.strategy);

  const collapseItems = [
    {
      key: 'strategy',
      label: <SectionHeader icon={<ExperimentOutlined />} title="策略配置" />,
      children: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div>
            <Text style={labelStyle}>策略选择</Text>
            <Select
              style={{ width: '100%' }}
              value={store.strategy}
              onChange={(v) => {
                store.setField('strategy', v);
                const strat = store.strategies.find((s) => s.name === v);
                if (strat) {
                  const params: Record<string, number> = {};
                  strat.params_schema.forEach((p) => { params[p.name] = p.default; });
                  store.setField('strategyParams', params);
                }
              }}
              options={store.strategies.map((s) => ({ value: s.name, label: s.display_name }))}
              size="small"
            />
          </div>
          {currentStrategy?.params_schema.map((p) => (
            <div key={p.name}>
              <Text style={labelStyle}>{p.label}</Text>
              <InputNumber
                style={{ width: '100%' }}
                size="small"
                min={p.min}
                max={p.max}
                step={p.type === 'float' ? 0.1 : 1}
                value={store.strategyParams[p.name] ?? p.default}
                onChange={(v) => v !== null && store.setStrategyParam(p.name, v)}
              />
            </div>
          ))}
        </div>
      ),
    },
    {
      key: 'symbol',
      label: <SectionHeader icon={<StockOutlined />} title="交易标的" />,
      children: (
        <div>
          <Text style={labelStyle}>股票代码</Text>
          <Select
            mode="tags"
            style={{ width: '100%' }}
            size="small"
            value={store.symbols.split(/[,\s]+/).filter(Boolean)}
            onChange={(v) => store.setField('symbols', v.join(','))}
            placeholder="输入代码回车添加"
            tokenSeparators={[',', ' ']}
          />
        </div>
      ),
    },
    {
      key: 'date',
      label: <SectionHeader icon={<CalendarOutlined />} title="回测区间" />,
      children: (
        <Space direction="vertical" style={{ width: '100%' }} size={8}>
          <div>
            <Text style={labelStyle}>开始日期</Text>
            <DatePicker
              style={{ width: '100%' }}
              size="small"
              value={dayjs(store.startDate)}
              onChange={(d) => d && store.setField('startDate', d.format('YYYY-MM-DD'))}
            />
          </div>
          <div>
            <Text style={labelStyle}>结束日期</Text>
            <DatePicker
              style={{ width: '100%' }}
              size="small"
              value={dayjs(store.endDate)}
              onChange={(d) => d && store.setField('endDate', d.format('YYYY-MM-DD'))}
            />
          </div>
        </Space>
      ),
    },
    {
      key: 'capital',
      label: <SectionHeader icon={<DollarOutlined />} title="资金设置" />,
      children: (
        <div>
          <Text style={labelStyle}>初始资金</Text>
          <InputNumber
            style={{ width: '100%' }}
            size="small"
            min={10000}
            step={100000}
            value={store.initialCash}
            onChange={(v) => v !== null && store.setField('initialCash', v)}
            formatter={(v) => `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
          />
        </div>
      ),
    },
    {
      key: 'risk',
      label: <SectionHeader icon={<SafetyCertificateOutlined />} title="风控参数" />,
      children: (
        <Space direction="vertical" style={{ width: '100%' }} size={8}>
          <div>
            <Text style={labelStyle}>最大仓位</Text>
            <InputNumber
              style={{ width: '100%' }}
              size="small"
              min={0.1}
              max={1}
              step={0.1}
              value={store.maxPositionPct}
              onChange={(v) => v !== null && store.setField('maxPositionPct', v)}
              formatter={(v) => `${(Number(v) * 100).toFixed(0)}%`}
              parser={(v) => Number(v!.replace('%', '')) / 100}
            />
          </div>
          <div>
            <Text style={labelStyle}>最大回撤</Text>
            <InputNumber
              style={{ width: '100%' }}
              size="small"
              min={0.05}
              max={0.5}
              step={0.05}
              value={store.maxDrawdown}
              onChange={(v) => v !== null && store.setField('maxDrawdown', v)}
              formatter={(v) => `${(Number(v) * 100).toFixed(0)}%`}
              parser={(v) => Number(v!.replace('%', '')) / 100}
            />
          </div>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ flex: 1, overflow: 'auto', padding: '8px 0' }}>
        <Collapse
          items={collapseItems}
          defaultActiveKey={['strategy', 'symbol', 'date', 'capital', 'risk']}
          ghost
          size="small"
          expandIcon={({ isActive }) => (
            <CaretRightOutlined rotate={isActive ? 90 : 0} style={{ color: '#5e6673', fontSize: 10 }} />
          )}
          style={{ background: 'transparent' }}
        />
      </div>
      <div style={{ padding: '12px 16px', borderTop: '1px solid #1e2126' }}>
        <Button
          type="primary"
          size="middle"
          block
          loading={store.loading}
          onClick={store.run}
          style={{
            height: 36,
            fontWeight: 600,
            fontSize: 13,
            background: 'linear-gradient(135deg, #1890ff 0%, #722ed1 100%)',
            border: 'none',
            borderRadius: 6,
          }}
        >
          {store.loading ? '运行中...' : '运行回测'}
        </Button>
      </div>
    </div>
  );
}
