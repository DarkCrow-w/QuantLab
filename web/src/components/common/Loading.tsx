import { Spin } from 'antd';
import { LoadingOutlined } from '@ant-design/icons';

interface LoadingProps {
  label?: string;
}

export default function Loading({ label = '加载中...' }: LoadingProps) {
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
      <div style={{ color: '#8d9ba7', fontSize: 13 }}>{label}</div>
    </div>
  );
}
