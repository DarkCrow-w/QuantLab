import axios from 'axios';
import type {
  BacktestRequest,
  BacktestGridRequest,
  BacktestGridResult,
  BacktestResult,
  CompositeMetricDef,
  CompositeScanResult,
  FactorDef,
  FactorMiningRequest,
  FactorMiningResult,
  FactorStrategy,
  FactorStrategyDraft,
  KlineBar,
  ManagedFactor,
  ManagedFactorDraft,
  PerformanceMetrics,
  RiskEvaluationResult,
  RiskRule,
  RiskRuleDraft,
  ScoreRequest,
  ScoreResult,
  ScreenRequest,
  ScreenResult,
  StrategyAsset,
  StrategyAssetDraft,
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

export async function fetchStrategyAssets(): Promise<StrategyAsset[]> {
  const { data } = await api.get<StrategyAsset[]>('/strategy/assets');
  return data;
}

export async function createStrategyAsset(draft: StrategyAssetDraft): Promise<StrategyAsset> {
  const { data } = await api.post<StrategyAsset>('/strategy/assets', draft);
  return data;
}

export async function updateStrategyAsset(
  id: string,
  draft: StrategyAssetDraft,
): Promise<StrategyAsset> {
  const { data } = await api.put<StrategyAsset>(`/strategy/assets/${id}`, draft);
  return data;
}

export async function deleteStrategyAsset(id: string): Promise<void> {
  await api.delete(`/strategy/assets/${id}`);
}

export interface HealthStatus {
  status: 'ok';
  service: string;
  version: string;
}

export async function fetchHealth(): Promise<HealthStatus> {
  const { data } = await api.get<HealthStatus>('/health');
  return data;
}

export interface SystemCheck {
  key: string;
  label: string;
  level: 'ok' | 'warning' | 'error';
  message: string;
  detail: Record<string, unknown>;
  required: boolean;
}

export interface SystemStatus {
  status: 'ok' | 'warning' | 'error';
  score: number;
  generated_at: string;
  summary: {
    required_ok: number;
    required_total: number;
    warnings: number;
    errors: number;
  };
  checks: SystemCheck[];
  latest_data_job: DataJob | null;
}

export async function fetchSystemStatus(): Promise<SystemStatus> {
  const { data } = await api.get<SystemStatus>('/system/status');
  return data;
}

export interface TradingCheck {
  key: string;
  label: string;
  level: 'ok' | 'warning' | 'error';
  message: string;
  detail: Record<string, unknown>;
}

export interface TradingStatus {
  mode: 'live';
  ready: boolean;
  safety_mode: 'manual_start';
  config_path: string;
  entrypoint: string;
  strategy: {
    name: string;
    params: Record<string, number>;
  };
  data: {
    source: string;
    symbols: string[];
    start_date?: string;
    end_date?: string;
    use_cache: boolean;
  };
  risk: {
    manager: string;
    max_position_pct: number;
    max_drawdown: number;
  };
  broker: {
    type: string;
    host: string;
    port: number;
    connects_on_start: boolean;
  };
  schedule: {
    cron: string;
    hour: number;
    minute: number;
  };
  simulation: {
    available: boolean;
    broker: string;
    entrypoint: string;
  };
  checks: TradingCheck[];
  manual_confirmations: string[];
}

export async function fetchTradingStatus(): Promise<TradingStatus> {
  const { data } = await api.get<TradingStatus>('/trading/status');
  return data;
}

export interface ResearchBacktestRun {
  id: string;
  created_at: string;
  updated_at: string;
  strategy: string;
  symbols: string[];
  start_date: string;
  end_date: string;
  total_return: number;
  annual_return: number;
  max_drawdown: number;
  sharpe_ratio: number | null;
  win_rate: number | null;
  trade_count: number;
  final_equity: number;
  tags: string[];
  note: string;
  favorite: boolean;
}

export interface ResearchBacktestDetail extends ResearchBacktestRun {
  request: BacktestRequest;
  metrics: PerformanceMetrics;
  result: BacktestResult;
}

export interface ResearchSummary {
  total_backtests: number;
  latest_at: string | null;
  avg_total_return: number | null;
  best_total_return: number | null;
  worst_drawdown: number | null;
  best_run: ResearchBacktestRun | null;
  favorite_count: number;
  tags: Array<{ tag: string; count: number }>;
}

export async function fetchResearchSummary(): Promise<ResearchSummary> {
  const { data } = await api.get<ResearchSummary>('/research/summary');
  return data;
}

export async function fetchResearchBacktests(
  limit = 50,
  filters?: { favorite?: boolean; tag?: string },
): Promise<ResearchBacktestRun[]> {
  const { data } = await api.get<ResearchBacktestRun[]>('/research/backtests', {
    params: { limit, ...filters },
  });
  return data;
}

export async function fetchResearchBacktest(runId: string): Promise<ResearchBacktestDetail> {
  const { data } = await api.get<ResearchBacktestDetail>(`/research/backtests/${runId}`);
  return data;
}

export async function updateResearchBacktestMetadata(
  runId: string,
  patch: { tags?: string[]; note?: string; favorite?: boolean },
): Promise<ResearchBacktestDetail> {
  const { data } = await api.patch<ResearchBacktestDetail>(
    `/research/backtests/${runId}/metadata`,
    patch,
  );
  return data;
}

export async function exportResearchReport(runIds: string[]): Promise<string> {
  const { data } = await api.post<string>(
    '/research/reports/backtests.md',
    { run_ids: runIds },
    { responseType: 'text' },
  );
  return data;
}

export async function runBacktest(req: BacktestRequest): Promise<BacktestResult> {
  const { data } = await api.post<BacktestResult>('/backtest/run', req);
  return data;
}

export async function runBacktestGrid(req: BacktestGridRequest): Promise<BacktestGridResult> {
  const { data } = await api.post<BacktestGridResult>('/backtest/grid', req);
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

export interface CacheStatusInfo {
  symbol: string;
  freq: string;
  last_dt?: string;
  source?: string;
  ts_updated?: string;
}

export interface IndicatorInfo {
  name: string;
  params: string[];
  columns: string[];
  lookback: number;
  version: string;
}

export interface UniverseItem {
  symbol: string;
  name?: string;
  market?: string;
  [key: string]: unknown;
}

export async function fetchCacheList(): Promise<CacheInfo[]> {
  const { data } = await api.get<CacheInfo[]>('/market/cache');
  return data;
}

export async function fetchCacheStatus(): Promise<CacheStatusInfo[]> {
  const { data } = await api.get<CacheStatusInfo[]>('/market/cache/status');
  return data;
}

export async function fetchIndicators(): Promise<IndicatorInfo[]> {
  const { data } = await api.get<IndicatorInfo[]>('/market/indicators');
  return data;
}

export async function fetchUniverse(market?: string): Promise<UniverseItem[]> {
  const { data } = await api.get<UniverseItem[]>('/market/universe', {
    params: market ? { market } : undefined,
  });
  return data;
}

export type DataSource = 'tushare' | 'tdx' | 'akshare' | 'baostock';

export async function refreshUniverse(
  source: DataSource = 'tdx',
): Promise<{ symbols: number; source: string }> {
  const { data } = await api.post<{ symbols: number; source: string }>(
    '/market/v2/refresh-universe',
    null,
    { params: { source } },
  );
  return data;
}

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

export interface AgentRuntime {
  enabled: boolean;
  provider: string;
  model: string;
  configured: boolean;
  reason?: string | null;
  modes?: Array<{ key: string; label: string; agent: string }>;
}

export async function fetchAgentRuntime(): Promise<AgentRuntime> {
  const { data } = await api.get<AgentRuntime>('/agent/status');
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

export async function fetchManagedFactors(): Promise<ManagedFactor[]> {
  const { data } = await api.get<ManagedFactor[]>('/factors');
  return data;
}

export async function createManagedFactor(draft: ManagedFactorDraft): Promise<ManagedFactor> {
  const { data } = await api.post<ManagedFactor>('/factors', draft);
  return data;
}

export async function updateManagedFactor(
  id: string,
  draft: ManagedFactorDraft,
): Promise<ManagedFactor> {
  const { data } = await api.put<ManagedFactor>(`/factors/${id}`, draft);
  return data;
}

export async function deleteManagedFactor(id: string): Promise<void> {
  await api.delete(`/factors/${id}`);
}

export async function mineFactors(req: FactorMiningRequest): Promise<FactorMiningResult> {
  const { data } = await api.post<FactorMiningResult>('/factors/mine', req);
  return data;
}

export async function fetchRiskRules(): Promise<RiskRule[]> {
  const { data } = await api.get<RiskRule[]>('/risk/rules');
  return data;
}

export async function createRiskRule(draft: RiskRuleDraft): Promise<RiskRule> {
  const { data } = await api.post<RiskRule>('/risk/rules', draft);
  return data;
}

export async function updateRiskRule(id: string, draft: RiskRuleDraft): Promise<RiskRule> {
  const { data } = await api.put<RiskRule>(`/risk/rules/${id}`, draft);
  return data;
}

export async function deleteRiskRule(id: string): Promise<void> {
  await api.delete(`/risk/rules/${id}`);
}

export async function evaluateRisk(ruleId: string): Promise<RiskEvaluationResult> {
  const { data } = await api.post<RiskEvaluationResult>('/risk/evaluate', {
    rule_id: ruleId,
    equity: 100000,
    position_value: 25000,
    order_value: 8000,
    drawdown: 0.06,
    symbol_count: 4,
  });
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
