import { Spin } from 'antd';
import { LoadingOutlined } from '@ant-design/icons';

export default function Loading() {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100%',
        minHeight: 300,
        gap: 16,
      }}
    >
      <Spin indicator={<LoadingOutlined style={{ fontSize: 32, color: '#1890ff' }} spin />} />
      <div style={{ color: '#5e6673', fontSize: 13 }}>策略回测中，请稍候...</div>
    </div>
  );
}
