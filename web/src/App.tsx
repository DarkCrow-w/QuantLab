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
          colorPrimary: '#2f8cff',
          colorSuccess: '#19c37d',
          colorWarning: '#e6a23c',
          colorError: '#f05b67',
          borderRadius: 6,
          colorBgBase: '#090d10',
          colorBgContainer: '#11181d',
          colorBgElevated: '#162027',
          colorBorder: '#263640',
          colorText: '#e7eef3',
          colorTextSecondary: '#8d9ba7',
          fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
          fontSize: 13,
        },
        components: {
          Button: {
            primaryShadow: 'none',
            borderRadius: 6,
          },
          Card: {
            paddingLG: 16,
          },
          Segmented: {
            itemSelectedBg: '#24323c',
          },
          Table: {
            headerBg: '#162027',
            rowHoverBg: '#162027',
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
