import { Table, Tag } from 'antd';
import type { TradeRecord } from '../../types';

interface Props {
  trades: TradeRecord[];
}

export default function TradesTable({ trades }: Props) {
  const columns = [
    {
      title: '日期',
      dataIndex: 'dt',
      key: 'dt',
      width: 110,
      sorter: (a: TradeRecord, b: TradeRecord) => a.dt.localeCompare(b.dt),
      render: (v: string) => <span className="mono" style={{ fontSize: 12 }}>{v}</span>,
    },
    {
      title: '标的',
      dataIndex: 'symbol',
      key: 'symbol',
      width: 80,
      filters: [...new Set(trades.map((t) => t.symbol))].map((s) => ({ text: s, value: s })),
      onFilter: (value: unknown, record: TradeRecord) => record.symbol === value,
      render: (v: string) => <span className="mono" style={{ color: '#1890ff', fontSize: 12 }}>{v}</span>,
    },
    {
      title: '方向',
      dataIndex: 'side',
      key: 'side',
      width: 70,
      render: (side: string) => (
        <Tag
          style={{
            background: side === 'BUY' ? 'rgba(246,70,93,0.12)' : 'rgba(14,203,129,0.12)',
            color: side === 'BUY' ? '#f6465d' : '#0ecb81',
            border: 'none',
            borderRadius: 3,
            fontSize: 11,
            fontWeight: 600,
            padding: '0 8px',
            lineHeight: '20px',
          }}
        >
          {side === 'BUY' ? 'B' : 'S'}
        </Tag>
      ),
      filters: [
        { text: '买入', value: 'BUY' },
        { text: '卖出', value: 'SELL' },
      ],
      onFilter: (value: unknown, record: TradeRecord) => record.side === value,
    },
    {
      title: '数量',
      dataIndex: 'qty',
      key: 'qty',
      width: 90,
      align: 'right' as const,
      render: (v: number) => <span className="mono" style={{ fontSize: 12 }}>{v.toLocaleString()}</span>,
    },
    {
      title: '价格',
      dataIndex: 'price',
      key: 'price',
      width: 100,
      align: 'right' as const,
      render: (v: number) => <span className="mono" style={{ fontSize: 12 }}>{v.toFixed(2)}</span>,
      sorter: (a: TradeRecord, b: TradeRecord) => a.price - b.price,
    },
    {
      title: '金额',
      key: 'amount',
      width: 120,
      align: 'right' as const,
      render: (_: unknown, r: TradeRecord) => (
        <span className="mono" style={{ fontSize: 12, color: '#848e9c' }}>
          {(r.price * r.qty).toLocaleString('zh-CN', { maximumFractionDigits: 0 })}
        </span>
      ),
    },
    {
      title: '佣金',
      dataIndex: 'commission',
      key: 'commission',
      width: 80,
      align: 'right' as const,
      render: (v: number) => <span className="mono" style={{ fontSize: 12, color: '#5e6673' }}>{v.toFixed(2)}</span>,
    },
  ];

  return (
    <Table
      dataSource={trades}
      columns={columns}
      rowKey={(r) => `${r.dt}-${r.symbol}-${r.side}-${r.qty}-${r.price}-${r.commission}`}
      size="small"
      pagination={{
        pageSize: 20,
        showSizeChanger: true,
        showTotal: (t) => <span style={{ color: '#5e6673', fontSize: 12 }}>共 {t} 条</span>,
        size: 'small',
      }}
      scroll={{ x: 650 }}
    />
  );
}
