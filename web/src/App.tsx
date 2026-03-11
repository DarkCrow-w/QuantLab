import { useState } from 'react';
import { ConfigProvider, theme } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import AppLayout from './components/layout/AppLayout';
import Sidebar from './components/layout/Sidebar';
import ScreeningSidebar from './components/layout/ScreeningSidebar';
import BacktestPage from './pages/BacktestPage';
import ScreeningPage from './pages/ScreeningPage';
import AgentPage from './pages/AgentPage';

export default function App() {
  const [activePage, setActivePage] = useState('backtest');

  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorPrimary: '#1890ff',
          borderRadius: 4,
          colorBgContainer: '#141619',
          colorBgElevated: '#1a1d21',
          colorBorder: '#2b2f36',
          colorText: '#eaecef',
          colorTextSecondary: '#848e9c',
          fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
          fontSize: 13,
        },
        components: {
          Button: {
            primaryShadow: 'none',
          },
          Card: {
            paddingLG: 16,
          },
        },
      }}
    >
      <AppLayout
        activePage={activePage}
        onPageChange={setActivePage}
        sidebar={activePage === 'agent' ? null : activePage === 'backtest' ? <Sidebar /> : <ScreeningSidebar />}
      >
        {activePage === 'backtest' ? (
          <BacktestPage />
        ) : activePage === 'screening' ? (
          <ScreeningPage />
        ) : (
          <AgentPage />
        )}
      </AppLayout>
    </ConfigProvider>
  );
}
