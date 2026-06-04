import axios from 'axios';
import type {
  BacktestRequest,
  BacktestResult,
  CompositeMetricDef,
  CompositeScanResult,
  FactorDef,
  FactorStrategy,
  FactorStrategyDraft,
  KlineBar,
  ScoreRequest,
  ScoreResult,
  ScreenRequest,
  ScreenResult,
  StrategyInfo,
} from '../types';

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

export interface DataJobItem {
  symbol: string;
  status: 'updated' | 'skipped' | 'failed';
  message: string;
  updated_at: string;
}

export interface DataJob {
  id?: string;
  kind?: 'update' | 'download';
  source?: DataSource;
  status:
    | 'idle'
    | 'queued'
    | 'running'
    | 'paused'
    | 'cancelling'
    | 'cancelled'
    | 'completed'
    | 'failed'
    | 'interrupted';
  running: boolean;
  paused?: boolean;
  total: number;
  completed: number;
  updated?: number;
  skipped?: number;
  failed?: number;
  current_symbol?: string;
  current_status?: string;
  percent: number;
  elapsed_s?: number;
  speed?: number;
  eta_s?: number | null;
  error?: string | null;
  recent: DataJobItem[];
  result?: {
    requested_symbols?: string[];
    total?: number;
    success?: number;
    skipped?: number;
    failed?: number;
    errors?: string[];
  };
}

export interface DataJobStart {
  status: 'started' | 'busy';
  job: DataJob;
}

export async function updateMarketData(
  symbols?: string[],
  source: DataSource = 'tdx',
): Promise<DataJobStart> {
  const { data } = await api.post<DataJobStart>('/market/update', {
    symbols: symbols || null,
    source,
    materialize_indicators: false,
  });
  return data;
}

export async function startDownloadAll(source: DataSource = 'tdx'): Promise<DataJobStart> {
  const { data } = await api.post<DataJobStart>('/market/download-all', {
    source,
    materialize_indicators: false,
  });
  return data;
}

export async function getCurrentDataJob(): Promise<DataJob> {
  const { data } = await api.get<DataJob>('/market/jobs/current');
  return data;
}

export interface DataJobAction {
  status: 'paused' | 'resumed' | 'cancelling';
  job: DataJob;
}

export async function pauseDataJob(jobId: string): Promise<DataJobAction> {
  const { data } = await api.post<DataJobAction>(`/market/jobs/${jobId}/pause`);
  return data;
}

export async function resumeDataJob(jobId: string): Promise<DataJobAction> {
  const { data } = await api.post<DataJobAction>(`/market/jobs/${jobId}/resume`);
  return data;
}

export async function cancelDataJob(jobId: string): Promise<DataJobAction> {
  const { data } = await api.post<DataJobAction>(`/market/jobs/${jobId}/cancel`);
  return data;
}

// ── Screening ──

export async function runScreening(req: ScreenRequest): Promise<ScreenResult> {
  const { data } = await api.post<ScreenResult>('/screening/scan', req);
  return data;
}

export async function runScoring(req: ScoreRequest): Promise<ScoreResult> {
  const { data } = await api.post<ScoreResult>('/screening/score', req);
  return data;
}

export async function fetchFactorDefs(): Promise<FactorDef[]> {
  const { data } = await api.get<FactorDef[]>('/screening/factors');
  return data;
}

export async function fetchCompositeMetrics(): Promise<CompositeMetricDef[]> {
  const { data } = await api.get<CompositeMetricDef[]>('/screening/composer/metrics');
  return data;
}

export async function fetchFactorStrategies(): Promise<FactorStrategy[]> {
  const { data } = await api.get<FactorStrategy[]>('/screening/composer/strategies');
  return data;
}

export async function createFactorStrategy(
  draft: FactorStrategyDraft,
): Promise<FactorStrategy> {
  const { data } = await api.post<FactorStrategy>('/screening/composer/strategies', draft);
  return data;
}

export async function updateFactorStrategy(
  id: string,
  draft: FactorStrategyDraft,
): Promise<FactorStrategy> {
  const { data } = await api.put<FactorStrategy>(`/screening/composer/strategies/${id}`, draft);
  return data;
}

export async function deleteFactorStrategy(id: string): Promise<void> {
  await api.delete(`/screening/composer/strategies/${id}`);
}

export async function runCompositeScreening(req: {
  strategy_id?: string | null;
  definition?: FactorStrategyDraft;
  scan_date?: string;
  max_symbols?: number;
}): Promise<CompositeScanResult> {
  const { data } = await api.post<CompositeScanResult>('/screening/composer/scan', req);
  return data;
}

export async function fetchKline(symbol: string, startDate: string, endDate: string): Promise<KlineBar[]> {
  const { data } = await api.get<KlineBar[]>('/market/kline', {
    params: { symbol, start_date: startDate, end_date: endDate },
  });
  return data;
}
