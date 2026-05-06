import { Layout } from 'antd';
import Header from './Header';

interface Props {
  sidebar: React.ReactNode | null;
  activePage: string;
  onPageChange: (page: string) => void;
  children: React.ReactNode;
}

export default function AppLayout({ sidebar, activePage, onPageChange, children }: Props) {
  return (
    <Layout style={{ minHeight: '100vh', background: '#0b0e11' }}>
      <Header activePage={activePage} onPageChange={onPageChange} />
      <Layout style={{ background: '#0b0e11' }}>
        {sidebar !== null && (
          <Layout.Sider
            width={260}
            style={{
              background: '#0f1114',
              borderRight: '1px solid #1e2126',
              overflow: 'auto',
              height: 'calc(100vh - 48px)',
            }}
          >
            {sidebar}
          </Layout.Sider>
        )}
        <Layout.Content
          style={{
            padding: sidebar !== null ? 12 : 0,
            overflow: sidebar !== null ? 'auto' : 'hidden',
            height: 'calc(100vh - 48px)',
            background: '#0b0e11',
          }}
        >
          {children}
        </Layout.Content>
      </Layout>
    </Layout>
  );
}
