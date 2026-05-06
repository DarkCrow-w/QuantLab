import { useState, useRef, useCallback, useEffect } from 'react';
import { Layout, Space, Typography, Tag, Button, Modal, Table, Progress, message, Segmented } from 'antd';
import { ThunderboltFilled, SyncOutlined, DatabaseOutlined, CloudDownloadOutlined } from '@ant-design/icons';
import { fetchCacheList, updateMarketData, startDownloadAll, getDownloadProgress } from '../../api/client';
import type { CacheInfo, UpdateResult, DownloadProgress, DataSource } from '../../api/client';

interface HeaderProps {
  activePage: string;
  onPageChange: (page: string) => void;
}

export default function Header({ activePage, onPageChange }: HeaderProps) {
  const [open, setOpen] = useState(false);
  const [cache, setCache] = useState<CacheInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [updating, setUpdating] = useState(false);
  const [results, setResults] = useState<UpdateResult[] | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [dlProgress, setDlProgress] = useState<DownloadProgress | null>(null);
  const [source, setSource] = useState<DataSource>('tdx');
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => () => stopPolling(), [stopPolling]);

  const doDownloadAll = async () => {
    setDownloading(true);
    setDlProgress(null);
    try {
      const res = await startDownloadAll(source);
      if (res.status === 'already_running') {
        message.warning('下载任务已在运行中');
      }
      // Start polling
      pollRef.current = setInterval(async () => {
        try {
          const p = await getDownloadProgress();
          setDlProgress(p);
          if (!p.running && (p.result || p.current > 0)) {
            stopPolling();
            setDownloading(false);
            if (p.result && !('error' in p.result)) {
              message.success(
                `下载完成: ${p.result.success} 成功, ${p.result.skipped} 跳过, ${p.result.failed} 失败`,
              );
              setCache(await fetchCacheList());
            } else if (p.result && 'error' in p.result) {
              message.error(`下载出错: ${(p.result as { error: string }).error}`);
            }
          }
        } catch {
          // ignore polling errors
        }
      }, 2000);
    } catch {
      message.error('启动下载失败');
      setDownloading(false);
    }
  };

  const openPanel = async () => {
    setOpen(true);
    setResults(null);
    setLoading(true);
    try {
      setCache(await fetchCacheList());
    } finally {
      setLoading(false);
    }
  };

  const doUpdate = async (symbols?: string[]) => {
    setUpdating(true);
    setResults(null);
    try {
      const res = await updateMarketData(symbols, source);
      setResults(res);
      const ok = res.filter((r) => r.new_bars > 0).length;
      const skip = res.filter((r) => r.status === 'up_to_date').length;
      const fail = res.filter((r) => r.status === 'error').length;
      message.success(`更新完成: ${ok} 只有新数据, ${skip} 只已最新, ${fail} 只失败`);
      setCache(await fetchCacheList());
    } catch {
      message.error('更新失败');
    } finally {
      setUpdating(false);
    }
  };

  const columns = [
    {
      title: '代码',
      dataIndex: 'symbol',
      key: 'symbol',
      width: 80,
      render: (v: string) => <span className="mono" style={{ color: '#1890ff' }}>{v}</span>,
    },
    { title: 'K线数', dataIndex: 'bars', key: 'bars', width: 70, align: 'right' as const },
    { title: '起始', dataIndex: 'start', key: 'start', width: 100 },
    { title: '截止', dataIndex: 'end', key: 'end', width: 100 },
    {
      title: '',
      key: 'action',
      width: 60,
      render: (_: unknown, r: CacheInfo) => (
        <Button
          type="link"
          size="small"
          icon={<SyncOutlined />}
          loading={updating}
          onClick={() => doUpdate([r.symbol])}
          style={{ padding: 0, fontSize: 12 }}
        >
          更新
        </Button>
      ),
    },
  ];

  const resultColumns = [
    {
      title: '代码',
      dataIndex: 'symbol',
      key: 'symbol',
      width: 80,
      render: (v: string) => <span className="mono" style={{ color: '#1890ff' }}>{v}</span>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (v: string) => {
        const map: Record<string, { color: string; text: string }> = {
          updated: { color: '#0ecb81', text: '已更新' },
          up_to_date: { color: '#848e9c', text: '已最新' },
          no_new_data: { color: '#848e9c', text: '无新数据' },
          error: { color: '#f6465d', text: '失败' },
        };
        const s = map[v] ?? { color: '#848e9c', text: v };
        return <span style={{ color: s.color, fontSize: 12 }}>{s.text}</span>;
      },
    },
    {
      title: '新增',
      dataIndex: 'new_bars',
      key: 'new_bars',
      width: 60,
      align: 'right' as const,
      render: (v: number) => (
        <span className="mono" style={{ color: v > 0 ? '#0ecb81' : '#5e6673' }}>
          +{v}
        </span>
      ),
    },
    { title: '截止', dataIndex: 'end', key: 'end', width: 100 },
  ];

  return (
    <>
      <Layout.Header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 20px',
          height: 48,
          lineHeight: '48px',
          background: '#0f1114',
          borderBottom: '1px solid #1e2126',
        }}
      >
        <Space size={10} align="center">
          <div
            style={{
              width: 28,
              height: 28,
              borderRadius: 6,
              background: 'linear-gradient(135deg, #1890ff 0%, #722ed1 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <ThunderboltFilled style={{ fontSize: 15, color: '#fff' }} />
          </div>
          <Typography.Text
            strong
            style={{ color: '#eaecef', fontSize: 15, letterSpacing: '-0.3px' }}
          >
            QuantLab
          </Typography.Text>
          <Segmented
            size="small"
            value={activePage}
            onChange={(v) => onPageChange(v as string)}
            options={[
              { label: '回测', value: 'backtest' },
              { label: '选股', value: 'screening' },
              { label: 'AI 助手', value: 'agent' },
            ]}
            style={{
              background: '#1a1d21',
              fontSize: 12,
              height: 26,
            }}
          />
        </Space>

        <Space size={12}>
          <Button
            size="small"
            icon={<DatabaseOutlined />}
            onClick={openPanel}
            style={{
              background: '#1a1d21',
              borderColor: '#2b2f36',
              color: '#848e9c',
              fontSize: 12,
              height: 28,
            }}
          >
            数据管理
          </Button>
          <Typography.Text style={{ color: '#5e6673', fontSize: 12 }}>v0.1.0</Typography.Text>
        </Space>
      </Layout.Header>

      <Modal
        title={
          <Space>
            <DatabaseOutlined style={{ color: '#1890ff' }} />
            <span>A股日线数据管理</span>
          </Space>
        }
        open={open}
        onCancel={() => setOpen(false)}
        width={560}
        footer={
          <Space>
            <Button onClick={() => setOpen(false)}>关闭</Button>
            <Button
              type="primary"
              icon={<SyncOutlined spin={updating} />}
              loading={updating}
              onClick={() => doUpdate()}
            >
              全部更新
            </Button>
            <Button
              icon={<CloudDownloadOutlined />}
              loading={downloading}
              onClick={doDownloadAll}
              style={{
                background: '#722ed1',
                borderColor: '#722ed1',
                color: '#fff',
              }}
            >
              下载全A股
            </Button>
          </Space>
        }
        styles={{
          body: { background: '#141619' },
          mask: { background: 'rgba(0,0,0,0.6)' },
        }}
        style={{ top: 80 }}
      >
        <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ color: '#848e9c', fontSize: 12, flexShrink: 0 }}>数据源</span>
          <Segmented
            size="small"
            value={source}
            onChange={(v) => setSource(v as DataSource)}
            disabled={updating || downloading}
            options={[
              { label: '通达信', value: 'tdx' },
              { label: 'TuShare', value: 'tushare' },
            ]}
            style={{ background: '#1a1d21' }}
          />
          <span style={{ color: '#5e6673', fontSize: 11 }}>
            {source === 'tdx' ? '免费·无限流·不复权' : '需Token·有限流·前复权'}
          </span>
        </div>

        {downloading || (dlProgress && !dlProgress.running && dlProgress.result) ? (
          <div style={{ marginBottom: 16 }}>
            <div style={{ color: '#848e9c', fontSize: 12, marginBottom: 8 }}>
              {downloading
                ? `正在下载: ${dlProgress?.symbol || '准备中...'} (${dlProgress?.current || 0}/${dlProgress?.total || '?'})`
                : '下载完成'}
            </div>
            <Progress
              percent={
                dlProgress && dlProgress.total > 0
                  ? Math.round((dlProgress.current / dlProgress.total) * 100)
                  : 0
              }
              strokeColor={{ from: '#1890ff', to: '#722ed1' }}
              size="small"
              status={downloading ? 'active' : 'success'}
            />
            {dlProgress?.result && !('error' in dlProgress.result) && !downloading && (
              <div style={{ color: '#5e6673', fontSize: 12, marginTop: 4 }}>
                共 {dlProgress.result.total} 只 | 成功 {dlProgress.result.success} | 跳过{' '}
                {dlProgress.result.skipped} | 失败 {dlProgress.result.failed}
                {dlProgress.result.errors.length > 0 && (
                  <span style={{ color: '#f6465d' }}>
                    {' '}
                    | 错误: {dlProgress.result.errors.slice(0, 3).join(', ')}
                    {dlProgress.result.errors.length > 3 && '...'}
                  </span>
                )}
              </div>
            )}
          </div>
        ) : null}
        {results ? (
          <>
            <div style={{ color: '#848e9c', fontSize: 12, marginBottom: 8 }}>更新结果</div>
            <Table
              dataSource={results}
              columns={resultColumns}
              rowKey="symbol"
              size="small"
              pagination={false}
              loading={updating}
              scroll={{ y: 300 }}
            />
          </>
        ) : (
          <>
            <div style={{ color: '#848e9c', fontSize: 12, marginBottom: 8 }}>
              已缓存 {cache.length} 只股票
            </div>
            <Table
              dataSource={cache}
              columns={columns}
              rowKey="symbol"
              size="small"
              pagination={false}
              loading={loading}
              scroll={{ y: 300 }}
            />
          </>
        )}
      </Modal>
    </>
  );
}
