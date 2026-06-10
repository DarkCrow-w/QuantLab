import { useState } from 'react';
import { Drawer, Grid, Layout } from 'antd';
import Header from './Header';

interface Props {
  sidebar: React.ReactNode | null;
  activePage: string;
  onPageChange: (page: string) => void;
  children: React.ReactNode;
}

export default function AppLayout({ sidebar, activePage, onPageChange, children }: Props) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const screens = Grid.useBreakpoint();
  const isMobile = !screens.lg;
  const hasSidebar = sidebar !== null;

  return (
    <Layout className="app-shell">
      <Header
        activePage={activePage}
        onPageChange={onPageChange}
        hasSidebar={hasSidebar}
        onOpenSidebar={() => setDrawerOpen(true)}
      />
      <Layout className="app-body">
        {hasSidebar && !isMobile && (
          <Layout.Sider
            width={288}
            className="workspace-sider"
          >
            {sidebar}
          </Layout.Sider>
        )}
        <Layout.Content className={`workspace-content ${hasSidebar ? 'with-sidebar' : 'agent-workspace'}`}>
          {children}
        </Layout.Content>
      </Layout>
      <Drawer
        open={drawerOpen && hasSidebar && isMobile}
        onClose={() => setDrawerOpen(false)}
        placement="left"
        width="min(88vw, 320px)"
        title="研究参数"
        styles={{ body: { padding: 0 }, header: { minHeight: 52 } }}
      >
        {sidebar}
      </Drawer>
    </Layout>
  );
}
