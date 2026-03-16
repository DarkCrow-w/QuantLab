import { create } from 'zustand';
import dayjs from 'dayjs';
import type { KlineBar, ScreenResult, StrategyInfo } from '../types';
import { fetchKline, fetchStrategyList, runScreening } from '../api/client';

interface ScreeningStore {
  // Strategy list
  strategies: StrategyInfo[];
  loadStrategies: () => Promise<void>;

  // Form state
  strategy: string;
  strategyParams: Record<string, number>;
  scanDate: string;
  setField: (field: string, value: unknown) => void;
  setStrategyParam: (name: string, value: number) => void;

  // Result
  result: ScreenResult | null;
  loading: boolean;
  error: string | null;
  scan: () => Promise<void>;

  // Selected symbol for chart
  selectedSymbol: string | null;
  klineData: KlineBar[] | null;
  klineLoading: boolean;
  selectSymbol: (symbol: string) => Promise<void>;
}

export const useScreeningStore = create<ScreeningStore>((set, get) => ({
  strategies: [],
  loadStrategies: async () => {
    const strategies = await fetchStrategyList();
    set({ strategies });
    if (strategies.length > 0) {
      const first = strategies[0];
      const params: Record<string, number> = {};
      first.params_schema.forEach((p) => {
        params[p.name] = p.default;
      });
      set({ strategy: first.name, strategyParams: params });
    }
  },

  strategy: 'ma_cross',
  strategyParams: { fast_period: 5, slow_period: 20 },
  scanDate: dayjs().format('YYYY-MM-DD'),
  setField: (field, value) => set({ [field]: value } as Partial<ScreeningStore>),
  setStrategyParam: (name, value) =>
    set((s) => ({ strategyParams: { ...s.strategyParams, [name]: value } })),

  result: null,
  loading: false,
  error: null,
  scan: async () => {
    const s = get();
    set({ loading: true, error: null, selectedSymbol: null, klineData: null });
    try {
      const result = await runScreening({
        strategy: s.strategy,
        strategy_params: s.strategyParams,
        scan_date: s.scanDate,
      });
      set({ result, loading: false });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '选股失败';
      set({ error: msg, loading: false });
    }
  },

  selectedSymbol: null,
  klineData: null,
  klineLoading: false,
  selectSymbol: async (symbol: string) => {
    const s = get();
    set({ selectedSymbol: symbol, klineData: null, klineLoading: true });
    try {
      const endDate = s.scanDate;
      const startDate = dayjs(endDate).subtract(6, 'month').format('YYYY-MM-DD');
      const data = await fetchKline(symbol, startDate, endDate);
      set({ klineData: data, klineLoading: false });
    } catch {
      set({ klineLoading: false });
    }
  },
}));
