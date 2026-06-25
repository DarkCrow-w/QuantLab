import { useEffect, useState } from 'react';
import { App as AntdApp, Button, Drawer, Form, Input, InputNumber, Select, Space, Switch, Table, Tag } from 'antd';
import { DeleteOutlined, EditOutlined, PlusOutlined, SaveOutlined, ThunderboltOutlined } from '@ant-design/icons';
import {
  createManagedFactor,
  deleteManagedFactor,
  fetchManagedFactors,
  mineFactors,
  updateManagedFactor,
} from '../api/client';
import type { FactorMiningResult, ManagedFactor, ManagedFactorDraft } from '../types';

const emptyFactor: ManagedFactorDraft = {
  key: '',
  label: '',
  category: 'custom',
  description: '',
  expression: '',
  default_weight: 1,
  enabled: true,
};

export default function FactorPage() {
  const { message } = AntdApp.useApp();
  const [factors, setFactors] = useState<ManagedFactor[]>([]);
  const [editing, setEditing] = useState<ManagedFactor | null>(null);
  const [draft, setDraft] = useState<ManagedFactorDraft>(emptyFactor);
  const [open, setOpen] = useState(false);
  const [mining, setMining] = useState<FactorMiningResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [miningLoading, setMiningLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      setFactors(await fetchManagedFactors());
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  function startCreate() {
    setEditing(null);
    setDraft(emptyFactor);
    setOpen(true);
  }

  function startEdit(row: ManagedFactor) {
    setEditing(row);
    setDraft({
      key: row.key,
      label: row.label,
      category: row.category,
      description: row.description,
      expression: row.expression,
      default_weight: row.default_weight,
      enabled: row.enabled,
    });
    setOpen(true);
  }

  async function save() {
    if (!draft.key.trim() || !draft.label.trim()) {
      message.warning('请填写因子 key 和名称');
      return;
    }
    if (editing) await updateManagedFactor(editing.id, draft);
    else await createManagedFactor(draft);
    message.success('因子已保存');
    setOpen(false);
    await load();
  }

  async function remove(row: ManagedFactor) {
    await deleteManagedFactor(row.id);
    message.success('因子已删除');
    await load();
  }

  async function runMining() {
    setMiningLoading(true);
    try {
      setMining(await mineFactors({ lookback: 220, forward_days: 5, min_samples: 30 }));
    } finally {
      setMiningLoading(false);
    }
  }

  return (
    <div className="asset-page">
      <div className="workspace-heading">
        <div>
          <h1>因子研究</h1>
          <p>管理内置与自定义因子，并对本地缓存股票做基础 IC 挖掘</p>
        </div>
        <Space>
          <Button icon={<ThunderboltOutlined />} loading={miningLoading} onClick={runMining}>运行因子挖掘</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={startCreate}>自定义因子</Button>
        </Space>
      </div>

      <div className="asset-grid">
        <div className="surface-panel">
          <div className="panel-heading">因子库</div>
          <Table
            rowKey="id"
            loading={loading}
            dataSource={factors}
            pagination={{ pageSize: 10 }}
            columns={[
              { title: '因子', dataIndex: 'label', render: (v, row) => <Space><strong>{v}</strong><Tag>{row.source}</Tag>{row.enabled ? <Tag color="success">启用</Tag> : <Tag>停用</Tag>}</Space> },
              { title: 'key', dataIndex: 'key', render: (v) => <span className="mono accent-text">{v}</span> },
              { title: '分类', dataIndex: 'category', width: 110 },
              { title: '权重', dataIndex: 'default_weight', width: 90 },
              { title: '表达式', dataIndex: 'expression', ellipsis: true },
              {
                title: '操作',
                width: 120,
                render: (_, row) => (
                  <Space>
                    <Button icon={<EditOutlined />} onClick={() => startEdit(row)} />
                    <Button danger disabled={row.source === 'builtin'} icon={<DeleteOutlined />} onClick={() => remove(row)} />
                  </Space>
                ),
              },
            ]}
          />
        </div>
        <div className="surface-panel">
          <div className="panel-heading">因子挖掘结果</div>
          <Table
            rowKey="key"
            dataSource={mining?.items || []}
            loading={miningLoading}
            pagination={false}
            size="small"
            columns={[
              { title: '候选因子', dataIndex: 'label' },
              { title: '分类', dataIndex: 'category', width: 90 },
              { title: 'IC', dataIndex: 'ic', width: 90, render: (v: number | null) => v == null ? '-' : v.toFixed(4) },
              { title: '|IC|', dataIndex: 'abs_ic', width: 90, render: (v: number | null) => v == null ? '-' : v.toFixed(4) },
              { title: '样本', dataIndex: 'samples', width: 90 },
            ]}
          />
          {mining && <div className="asset-note">扫描 {mining.symbols} 只标的，窗口 {mining.lookback}，未来 {mining.forward_days} 日收益。</div>}
        </div>
      </div>

      <Drawer title={editing ? '编辑因子' : '自定义因子'} open={open} size="large" onClose={() => setOpen(false)}>
        <Form layout="vertical">
          <Form.Item label="Key"><Input value={draft.key} onChange={(e) => setDraft({ ...draft, key: e.target.value })} /></Form.Item>
          <Form.Item label="名称"><Input value={draft.label} onChange={(e) => setDraft({ ...draft, label: e.target.value })} /></Form.Item>
          <Form.Item label="分类"><Select value={draft.category} onChange={(category) => setDraft({ ...draft, category })} options={['trend', 'momentum', 'volume', 'risk', 'custom'].map((v) => ({ value: v, label: v }))} /></Form.Item>
          <Form.Item label="默认权重"><InputNumber style={{ width: '100%' }} min={0} max={100} value={draft.default_weight} onChange={(default_weight) => setDraft({ ...draft, default_weight: Number(default_weight ?? 1) })} /></Form.Item>
          <Form.Item label="表达式"><Input.TextArea rows={3} value={draft.expression} onChange={(e) => setDraft({ ...draft, expression: e.target.value })} placeholder="例如 close / close.shift(20) - 1" /></Form.Item>
          <Form.Item label="说明"><Input.TextArea rows={4} value={draft.description} onChange={(e) => setDraft({ ...draft, description: e.target.value })} /></Form.Item>
          <Form.Item label="启用"><Switch checked={draft.enabled} onChange={(enabled) => setDraft({ ...draft, enabled })} /></Form.Item>
          <Button type="primary" icon={<SaveOutlined />} block onClick={save}>保存因子</Button>
        </Form>
      </Drawer>
    </div>
  );
}
