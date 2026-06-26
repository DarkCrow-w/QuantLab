import { create } from 'zustand';
import type { BacktestResult, StrategyInfo } from '../types';
import { fetchFactorStrategies, fetchStrategyList, runBacktest } from '../api/client';

interface BacktestStore {
  // Strategy list
  strategies: StrategyInfo[];
  loadStrategies: () => Promise<void>;

  // Form state
  symbols: string;
  startDate: string;
  endDate: string;
  strategy: string;
  strategyParams: Record<string, number>;
  initialCash: number;
  maxPositionPct: number;
  maxDrawdown: number;
  commissionRate: number;
  setField: (field: string, value: unknown) => void;
  setStrategyParam: (name: string, value: number) => void;

  // Result
  result: BacktestResult | null;
  loading: boolean;
  error: string | null;
  run: () => Promise<void>;
}

export const useBacktestStore = create<BacktestStore>((set, get) => ({
  strategies: [],
  loadStrategies: async () => {
    const [basicStrategies, factorStrategies] = await Promise.all([
      fetchStrategyList(),
      fetchFactorStrategies(),
    ]);
    const compositeStrategies: StrategyInfo[] = factorStrategies.map((strategy) => ({
      name: `composite:${strategy.id}`,
      display_name: `组合 · ${strategy.name}`,
      params_schema: [],
    }));
    const basicStrategyOptions = basicStrategies.map((strategy) => ({
      ...strategy,
      display_name: `基础 · ${strategy.display_name}`,
    }));
    const strategies = [...compositeStrategies, ...basicStrategyOptions];
    const current = get().strategy;
    set({ strategies });
    if (strategies.length > 0 && !strategies.some((item) => item.name === current)) {
      const first = strategies.find((item) => item.name === 'composite:builtin_ma_cross') ?? strategies[0];
      set({ strategy: first.name, strategyParams: {} });
    }
  },

  symbols: '600519',
  startDate: '2023-01-01',
  endDate: '2024-12-31',
  strategy: 'composite:builtin_ma_cross',
  strategyParams: {},
  initialCash: 1000000,
  maxPositionPct: 0.3,
  maxDrawdown: 0.2,
  commissionRate: 0.00025,
  setField: (field, value) => set({ [field]: value } as Partial<BacktestStore>),
  setStrategyParam: (name, value) =>
    set((s) => ({ strategyParams: { ...s.strategyParams, [name]: value } })),

  result: null,
  loading: false,
  error: null,
  run: async () => {
    const s = get();
    set({ loading: true, error: null });
    try {
      const result = await runBacktest({
        symbols: s.symbols.split(/[,\s]+/).filter(Boolean),
        start_date: s.startDate,
        end_date: s.endDate,
        strategy: s.strategy,
        strategy_params: s.strategyParams,
        initial_cash: s.initialCash,
        max_position_pct: s.maxPositionPct,
        max_drawdown: s.maxDrawdown,
        commission_rate: s.commissionRate,
      });
      set({ result, loading: false });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '回测失败';
      set({ error: msg, loading: false });
    }
  },
}));
