export interface ParamSchema {
  name: string;
  type: string;
  default: number;
  min: number;
  max: number;
  label: string;
}

export interface StrategyInfo {
  name: string;
  display_name: string;
  params_schema: ParamSchema[];
}

export interface PerformanceMetrics {
  initial_cash: number;
  final_equity: number;
  total_return: number;
  annual_return: number;
  max_drawdown: number;
  trade_count: number;
  total_commission: number;
  win_rate: number | null;
  sharpe_ratio: number | null;
  profit_loss_ratio: number | null;
}

export interface TradeRecord {
  dt: string;
  symbol: string;
  side: string;
  qty: number;
  price: number;
  commission: number;
}

export interface EquityPoint {
  dt: string;
  equity: number;
}

export interface KlineBar {
  dt: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface BacktestRequest {
  symbols: string[];
  start_date: string;
  end_date: string;
  strategy: string;
  strategy_params: Record<string, number>;
  initial_cash: number;
  max_position_pct: number;
  max_drawdown: number;
  commission_rate: number;
}

export interface BacktestResult {
  metrics: PerformanceMetrics;
  equity_curve: EquityPoint[];
  trades: TradeRecord[];
  kline_data: Record<string, KlineBar[]>;
}

// ── Screening ──

export interface ScreenRequest {
  strategy: string;
  strategy_params: Record<string, number>;
  scan_date?: string;
  lookback?: number;
}

export interface ScreenMatch {
  symbol: string;
  signal_date: string;
  close: number;
  volume: number;
  amount: number;
  strength: number;
}

export interface ScreenResult {
  strategy: string;
  scan_date: string;
  total_scanned: number;
  matches: ScreenMatch[];
  elapsed_seconds: number;
}

// ── Agent ──

export interface AgentToolCall {
  id: string;
  tool: string;
  agent?: string;
  input: Record<string, unknown>;
  result?: Record<string, unknown>;
  status: 'running' | 'done' | 'error';
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  images?: string[];
  toolCalls?: AgentToolCall[];
  agentName?: string;
  timestamp: number;
}

export interface AgentStatus {
  name: string;
  displayName: string;
  status: 'working' | 'done';
  task?: string;
}

export interface ServerFrame {
  type: string;
  session_id?: string;
  agent?: string;
  content?: string;
  tool?: string;
  input?: Record<string, unknown>;
  data?: Record<string, unknown>;
  usage?: Record<string, unknown>;
  error?: string;
}

export interface SessionSummary {
  session_id: string;
  message_count: number;
  created_at: string;
  last_active: string;
}
