import { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import type { KlineBar, TradeRecord } from '../../types';

export type Overlay =
  | { type: 'MA'; period: number; color: string }
  | { type: 'BBI'; color: string };

export type SubplotKey = 'VOL' | 'MACD' | 'KDJ' | 'RSI';

interface Props {
  kline: KlineBar[];
  trades: TradeRecord[];
  symbol: string;
  overlays: Overlay[];
  subplots: SubplotKey[];
}

// ── 指标计算（与 quant/data/indicators.py 公式对齐）────────────────────────
function calcMA(values: number[], period: number): (number | null)[] {
  const out: (number | null)[] = [];
  for (let i = 0; i < values.length; i++) {
    if (i < period - 1) {
      out.push(null);
    } else {
      let s = 0;
      for (let j = i - period + 1; j <= i; j++) s += values[j];
      out.push(+(s / period).toFixed(2));
    }
  }
  return out;
}

// BBI = (MA3 + MA6 + MA12 + MA24) / 4
function calcBBI(closes: number[]): (number | null)[] {
  const m3 = calcMA(closes, 3);
  const m6 = calcMA(closes, 6);
  const m12 = calcMA(closes, 12);
  const m24 = calcMA(closes, 24);
  return closes.map((_, i) => {
    const a = m3[i], b = m6[i], c = m12[i], d = m24[i];
    if (a == null || b == null || c == null || d == null) return null;
    return +((a + b + c + d) / 4).toFixed(2);
  });
}

// KDJ(9,3,3): RSV = (close-LLn)/(HHn-LLn)*100; K=2/3*Kprev+1/3*RSV; D=2/3*Dprev+1/3*K; J=3K-2D
function calcKDJ(highs: number[], lows: number[], closes: number[], n = 9) {
  const k: (number | null)[] = [];
  const d: (number | null)[] = [];
  const j: (number | null)[] = [];
  let pk = 50, pd = 50;
  for (let i = 0; i < closes.length; i++) {
    if (i < n - 1) {
      k.push(null); d.push(null); j.push(null);
      continue;
    }
    let hh = -Infinity, ll = Infinity;
    for (let p = i - n + 1; p <= i; p++) {
      if (highs[p] > hh) hh = highs[p];
      if (lows[p] < ll) ll = lows[p];
    }
    const rng = hh - ll;
    const rsv = rng === 0 ? 50 : ((closes[i] - ll) / rng) * 100;
    const ck = (2 / 3) * pk + (1 / 3) * rsv;
    const cd = (2 / 3) * pd + (1 / 3) * ck;
    k.push(+ck.toFixed(2));
    d.push(+cd.toFixed(2));
    j.push(+(3 * ck - 2 * cd).toFixed(2));
    pk = ck; pd = cd;
  }
  return { k, d, j };
}

// RSI(N) Wilder: Y = (X + (M-1)*Yprev)/M
function calcRSI(closes: number[], period: number): (number | null)[] {
  const out: (number | null)[] = [null];
  if (closes.length < 2) return closes.map(() => null);
  let avgU = Math.max(closes[1] - closes[0], 0);
  let avgD = Math.max(closes[0] - closes[1], 0);
  out.push(avgD === 0 ? 100 : +(100 - 100 / (1 + avgU / avgD)).toFixed(2));
  for (let i = 2; i < closes.length; i++) {
    const diff = closes[i] - closes[i - 1];
    const u = Math.max(diff, 0), dn = Math.max(-diff, 0);
    avgU = (u + (period - 1) * avgU) / period;
    avgD = (dn + (period - 1) * avgD) / period;
    out.push(avgD === 0 ? 100 : +(100 - 100 / (1 + avgU / avgD)).toFixed(2));
  }
  return out;
}

// MACD(12,26,9): EMA12 - EMA26 = DIF; EMA(DIF,9) = DEA; MACD = (DIF - DEA) * 2
function calcMACD(closes: number[]) {
  const ema = (vals: number[], n: number) => {
    const a = 2 / (n + 1);
    const e: number[] = [vals[0]];
    for (let i = 1; i < vals.length; i++) e.push(e[i - 1] + a * (vals[i] - e[i - 1]));
    return e;
  };
  const e12 = ema(closes, 12);
  const e26 = ema(closes, 26);
  const dif = e12.map((v, i) => +(v - e26[i]).toFixed(4));
  const dea = ema(dif, 9).map((v) => +v.toFixed(4));
  const macd = dif.map((v, i) => +((v - dea[i]) * 2).toFixed(4));
  return { dif, dea, macd };
}

function overlayLabel(o: Overlay): string {
  return o.type === 'MA' ? `MA${o.period}` : 'BBI';
}

// 按副图数量分配高度（百分比）
function gridLayout(subplotCount: number) {
  // [mainPct, subPct] 表
  const table: Record<number, [number, number]> = {
    0: [88, 0],
    1: [62, 22],
    2: [50, 17],
    3: [42, 14],
    4: [36, 12],
  };
  return table[subplotCount] ?? table[4];
}

export default function KlineChart({ kline, trades, symbol, overlays, subplots }: Props) {
  const option = useMemo(() => {
    const dates = kline.map((b) => b.dt);
    const ohlc = kline.map((b) => [b.open, b.close, b.low, b.high]);
    const opens = kline.map((b) => b.open);
    const highs = kline.map((b) => b.high);
    const lows = kline.map((b) => b.low);
    const closes = kline.map((b) => b.close);
    const volumes = kline.map((b) => b.volume);

    // ── 主图叠加线 ─────
    const overlaySeries = overlays.map((o) => ({
      name: overlayLabel(o),
      type: 'line' as const,
      data: o.type === 'MA' ? calcMA(closes, o.period) : calcBBI(closes),
      xAxisIndex: 0,
      yAxisIndex: 0,
      smooth: true,
      lineStyle: { width: 1, color: o.color },
      symbol: 'none',
      z: 2,
    }));

    // ── 副图布局 ─────
    const N = subplots.length;
    const [mainPct, subPct] = gridLayout(N);
    const grids: any[] = [{ left: 56, right: 16, top: 30, height: `${mainPct}%` }];
    const xAxis: any[] = [
      {
        type: 'category', data: dates, gridIndex: 0,
        axisLine: { lineStyle: { color: '#1e2126' } },
        axisTick: { show: false },
        axisLabel: { show: N === 0 },
        splitLine: { show: false },
      },
    ];
    const yAxis: any[] = [
      {
        scale: true, gridIndex: 0,
        splitLine: { lineStyle: { color: '#1e2126', type: 'dashed' } },
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: '#5e6673', fontSize: 10, margin: 8 },
      },
    ];

    // 主图位置（百分比起点：top=30 像素 + mainPct%；近似换算：30px ≈ 7%）
    let topCursor = 7 + mainPct + 2;
    const subSeries: any[] = [];
    const legendNames: string[] = overlays.map(overlayLabel);

    subplots.forEach((sp, idx) => {
      const gi = idx + 1;
      const isLast = idx === N - 1;
      grids.push({ left: 56, right: 16, top: `${topCursor}%`, height: `${subPct}%` });
      xAxis.push({
        type: 'category', data: dates, gridIndex: gi,
        axisLine: { lineStyle: { color: '#1e2126' } },
        axisTick: { show: false },
        axisLabel: isLast
          ? { color: '#5e6673', fontSize: 10, margin: 6 }
          : { show: false },
        splitLine: { show: false },
      });
      yAxis.push({
        scale: true, gridIndex: gi,
        splitLine: { show: false },
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: '#5e6673', fontSize: 9, margin: 6 },
      });
      topCursor += subPct + 2;

      if (sp === 'VOL') {
        subSeries.push({
          name: 'Vol',
          type: 'bar',
          data: volumes.map((v, i) => ({
            value: v,
            itemStyle: {
              color: closes[i] >= opens[i]
                ? 'rgba(246,70,93,0.55)'
                : 'rgba(14,203,129,0.55)',
            },
          })),
          xAxisIndex: gi,
          yAxisIndex: gi,
          barMaxWidth: 8,
        });
        legendNames.push('Vol');
      } else if (sp === 'MACD') {
        const { dif, dea, macd } = calcMACD(closes);
        subSeries.push({
          name: 'MACD',
          type: 'bar',
          data: macd.map((v) => ({
            value: v,
            itemStyle: { color: v >= 0 ? 'rgba(246,70,93,0.7)' : 'rgba(14,203,129,0.7)' },
          })),
          xAxisIndex: gi, yAxisIndex: gi, barMaxWidth: 4,
        });
        subSeries.push({
          name: 'DIF', type: 'line', data: dif,
          xAxisIndex: gi, yAxisIndex: gi,
          smooth: true, symbol: 'none',
          lineStyle: { width: 1, color: '#eaecef' },
        });
        subSeries.push({
          name: 'DEA', type: 'line', data: dea,
          xAxisIndex: gi, yAxisIndex: gi,
          smooth: true, symbol: 'none',
          lineStyle: { width: 1, color: '#f0b90b' },
        });
        legendNames.push('MACD', 'DIF', 'DEA');
      } else if (sp === 'KDJ') {
        const { k, d, j } = calcKDJ(highs, lows, closes);
        subSeries.push({
          name: 'K', type: 'line', data: k,
          xAxisIndex: gi, yAxisIndex: gi,
          smooth: true, symbol: 'none',
          lineStyle: { width: 1, color: '#f0b90b' },
        });
        subSeries.push({
          name: 'D', type: 'line', data: d,
          xAxisIndex: gi, yAxisIndex: gi,
          smooth: true, symbol: 'none',
          lineStyle: { width: 1, color: '#722ed1' },
        });
        subSeries.push({
          name: 'J', type: 'line', data: j,
          xAxisIndex: gi, yAxisIndex: gi,
          smooth: true, symbol: 'none',
          lineStyle: { width: 1, color: '#13c2c2' },
        });
        legendNames.push('K', 'D', 'J');
      } else if (sp === 'RSI') {
        subSeries.push({
          name: 'RSI6', type: 'line', data: calcRSI(closes, 6),
          xAxisIndex: gi, yAxisIndex: gi,
          smooth: true, symbol: 'none',
          lineStyle: { width: 1, color: '#f0b90b' },
        });
        subSeries.push({
          name: 'RSI12', type: 'line', data: calcRSI(closes, 12),
          xAxisIndex: gi, yAxisIndex: gi,
          smooth: true, symbol: 'none',
          lineStyle: { width: 1, color: '#1890ff' },
        });
        legendNames.push('RSI6', 'RSI12');
      }
    });

    // ── 买卖标记 ─────
    const symbolTrades = trades.filter((t) => t.symbol === symbol);
    const buyMarkers = symbolTrades
      .filter((t) => t.side === 'BUY')
      .map((t) => ({
        coord: [t.dt, t.price * 0.97],
        value: `B ${t.price.toFixed(2)}`,
        itemStyle: { color: '#f6465d' },
        symbol: 'triangle', symbolSize: 10, symbolRotate: 0,
        label: { show: true, formatter: 'B', color: '#f6465d', fontSize: 9, fontWeight: 700, position: 'bottom' },
      }));
    const sellMarkers = symbolTrades
      .filter((t) => t.side === 'SELL')
      .map((t) => ({
        coord: [t.dt, t.price * 1.03],
        value: `S ${t.price.toFixed(2)}`,
        itemStyle: { color: '#0ecb81' },
        symbol: 'triangle', symbolSize: 10, symbolRotate: 180,
        label: { show: true, formatter: 'S', color: '#0ecb81', fontSize: 9, fontWeight: 700, position: 'top' },
      }));

    const allXAxisIdx = Array.from({ length: 1 + N }, (_, i) => i);

    return {
      backgroundColor: 'transparent',
      animation: false,
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross', crossStyle: { color: '#5e6673' } },
        backgroundColor: '#1a1d21',
        borderColor: '#2b2f36',
        textStyle: { color: '#eaecef', fontSize: 12, fontFamily: "'JetBrains Mono', monospace" },
        padding: [8, 12],
      },
      legend: {
        data: legendNames,
        textStyle: { color: '#5e6673', fontSize: 11 },
        top: 4,
        right: 10,
        itemWidth: 14,
        itemHeight: 2,
      },
      axisPointer: { link: [{ xAxisIndex: allXAxisIdx }] },
      grid: grids,
      xAxis,
      yAxis,
      dataZoom: [
        { type: 'inside', xAxisIndex: allXAxisIdx, start: 60, end: 100 },
        {
          type: 'slider',
          xAxisIndex: allXAxisIdx,
          bottom: 4,
          height: 16,
          borderColor: 'transparent',
          backgroundColor: '#141619',
          fillerColor: 'rgba(24,144,255,0.15)',
          handleStyle: { color: '#1890ff', borderColor: '#1890ff' },
          moveHandleStyle: { color: '#1890ff' },
          textStyle: { color: '#5e6673', fontSize: 10 },
          dataBackground: {
            lineStyle: { color: '#2b2f36' },
            areaStyle: { color: '#1a1d21' },
          },
        },
      ],
      series: [
        {
          name: 'K线',
          type: 'candlestick',
          data: ohlc,
          xAxisIndex: 0,
          yAxisIndex: 0,
          itemStyle: {
            color: '#f6465d',
            color0: '#0ecb81',
            borderColor: '#f6465d',
            borderColor0: '#0ecb81',
            borderWidth: 1,
          },
          markPoint: { data: [...buyMarkers, ...sellMarkers] },
        },
        ...overlaySeries,
        ...subSeries,
      ],
    };
  }, [kline, trades, symbol, overlays, subplots]);

  // 主图 + 副图数量 → 容器高度
  const height = 360 + subplots.length * 80;

  return (
    <ReactECharts
      option={option}
      style={{ height, width: '100%' }}
      opts={{ renderer: 'canvas' }}
      notMerge
    />
  );
}
