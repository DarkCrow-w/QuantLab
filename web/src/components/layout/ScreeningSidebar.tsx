import { useEffect } from 'react';
import { Button, Collapse, DatePicker, InputNumber, Select, Space, Typography } from 'antd';
import {
  CaretRightOutlined,
  ExperimentOutlined,
  CalendarOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import { useScreeningStore } from '../../stores/screening';

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

export default function ScreeningSidebar() {
  const store = useScreeningStore();

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
                  strat.params_schema.forEach((p) => {
                    params[p.name] = p.default;
                  });
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
      key: 'date',
      label: <SectionHeader icon={<CalendarOutlined />} title="选股日期" />,
      children: (
        <div>
          <Text style={labelStyle}>扫描截止日</Text>
          <DatePicker
            style={{ width: '100%' }}
            size="small"
            value={dayjs(store.scanDate)}
            onChange={(d) => d && store.setField('scanDate', d.format('YYYY-MM-DD'))}
          />
        </div>
      ),
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ flex: 1, overflow: 'auto', padding: '8px 0' }}>
        <Collapse
          items={collapseItems}
          defaultActiveKey={['strategy', 'date']}
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
          icon={<SearchOutlined />}
          loading={store.loading}
          onClick={store.scan}
          style={{
            height: 36,
            fontWeight: 600,
            fontSize: 13,
            background: 'linear-gradient(135deg, #1890ff 0%, #722ed1 100%)',
            border: 'none',
            borderRadius: 6,
          }}
        >
          {store.loading ? '选股中...' : '开始选股'}
        </Button>
      </div>
    </div>
  );
}
