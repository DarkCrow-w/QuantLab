import axios from 'axios';
import type { BacktestRequest, BacktestResult, KlineBar, ScreenRequest, ScreenResult, StrategyInfo } from '../types';

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
});

export async function fetchStrategyList(): Promise<StrategyInfo[]> {
  const { data } = await api.get<StrategyInfo[]>('/strategy/list');
  return data;
}

export async function runBacktest(req: BacktestRequest): Promise<BacktestResult> {
  const { data } = await api.post<BacktestResult>('/backtest/run', req);
  return data;
}

export interface CacheInfo {
  symbol: string;
  bars: number;
  start: string;
  end: string;
}

export interface UpdateResult {
  symbol: string;
  status: string;
  bars?: number;
  end?: string;
  new_bars: number;
  error?: string;
}

export async function fetchCacheList(): Promise<CacheInfo[]> {
  const { data } = await api.get<CacheInfo[]>('/market/cache');
  return data;
}

export type DataSource = 'tushare' | 'tdx';

export async function updateMarketData(symbols?: string[], source: DataSource = 'tushare'): Promise<UpdateResult[]> {
  const { data } = await api.post<UpdateResult[]>('/market/update', { symbols: symbols || null, source });
  return data;
}

export interface DownloadProgress {
  running: boolean;
  current: number;
  total: number;
  symbol: string;
  result: {
    total: number;
    success: number;
    skipped: number;
    failed: number;
    errors: string[];
  } | null;
}

export async function startDownloadAll(source: DataSource = 'tushare'): Promise<{ status: string }> {
  const { data } = await api.post('/market/download-all', { source });
  return data;
}

export async function getDownloadProgress(): Promise<DownloadProgress> {
  const { data } = await api.get<DownloadProgress>('/market/download-all/progress');
  return data;
}

// ── Screening ──

export async function runScreening(req: ScreenRequest): Promise<ScreenResult> {
  const { data } = await api.post<ScreenResult>('/screening/scan', req);
  return data;
}

export async function fetchKline(symbol: string, startDate: string, endDate: string): Promise<KlineBar[]> {
  const { data } = await api.get<KlineBar[]>('/market/kline', {
    params: { symbol, start_date: startDate, end_date: endDate },
  });
  return data;
}
