import { lazy, Suspense, useState } from 'react';
import { ConfigProvider, theme } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import AppLayout from './components/layout/AppLayout';
import Sidebar from './components/layout/Sidebar';
import ScreeningSidebar from './components/layout/ScreeningSidebar';
import Loading from './components/common/Loading';

const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const DataPage = lazy(() => import('./pages/DataPage'));
const TradingPage = lazy(() => import('./pages/TradingPage'));
const ResearchPage = lazy(() => import('./pages/ResearchPage'));
const StrategyPage = lazy(() => import('./pages/StrategyPage'));
const FactorPage = lazy(() => import('./pages/FactorPage'));
const RiskPage = lazy(() => import('./pages/RiskPage'));
const BacktestPage = lazy(() => import('./pages/BacktestPage'));
const ScreeningPage = lazy(() => import('./pages/ScreeningPage'));
const AgentPage = lazy(() => import('./pages/AgentPage'));

export default function App() {
  const [activePage, setActivePage] = useState('dashboard');
  const sidebar = activePage === 'backtest'
    ? <Sidebar />
    : activePage === 'screening'
      ? <ScreeningSidebar />
      : null;

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
        sidebar={sidebar}
      >
        <Suspense fallback={<Loading label="模块加载中..." />}>
          {activePage === 'dashboard' ? (
            <DashboardPage onPageChange={setActivePage} />
          ) : activePage === 'data' ? (
            <DataPage />
          ) : activePage === 'trading' ? (
            <TradingPage />
          ) : activePage === 'research' ? (
            <ResearchPage />
          ) : activePage === 'strategy' ? (
            <StrategyPage />
          ) : activePage === 'factors' ? (
            <FactorPage />
          ) : activePage === 'risk' ? (
            <RiskPage />
          ) : activePage === 'backtest' ? (
            <BacktestPage />
          ) : activePage === 'screening' ? (
            <ScreeningPage />
          ) : (
            <AgentPage />
          )}
        </Suspense>
      </AppLayout>
    </ConfigProvider>
  );
}
