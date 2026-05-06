import { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import type { KlineBar, TradeRecord } from '../../types';

interface Props {
  kline: KlineBar[];
  trades: TradeRecord[];
  symbol: string;
  fastPeriod: number;
  slowPeriod: number;
}

function calcMA(closes: number[], period: number): (number | null)[] {
  const result: (number | null)[] = [];
  for (let i = 0; i < closes.length; i++) {
    if (i < period - 1) {
      result.push(null);
    } else {
      let sum = 0;
      for (let j = i - period + 1; j <= i; j++) sum += closes[j];
      result.push(+(sum / period).toFixed(2));
    }
  }
  return result;
}

export default function KlineChart({ kline, trades, symbol, fastPeriod, slowPeriod }: Props) {
  const option = useMemo(() => {
    const dates = kline.map((b) => b.dt);
    const ohlc = kline.map((b) => [b.open, b.close, b.low, b.high]);
    const volumes = kline.map((b) => b.volume);
    const closes = kline.map((b) => b.close);
    const maFast = calcMA(closes, fastPeriod);
    const maSlow = calcMA(closes, slowPeriod);

    const symbolTrades = trades.filter((t) => t.symbol === symbol);
    const buyMarkers = symbolTrades
      .filter((t) => t.side === 'BUY')
      .map((t) => ({
        name: 'B',
        coord: [t.dt, t.price * 0.97],
        value: `B ${t.price.toFixed(2)}`,
        itemStyle: { color: '#f6465d' },
        symbol: 'triangle',
        symbolSize: 10,
        symbolRotate: 0,
        label: {
          show: true,
          formatter: 'B',
          color: '#f6465d',
          fontSize: 9,
          fontWeight: 700,
          position: 'bottom',
        },
      }));
    const sellMarkers = symbolTrades
      .filter((t) => t.side === 'SELL')
      .map((t) => ({
        name: 'S',
        coord: [t.dt, t.price * 1.03],
        value: `S ${t.price.toFixed(2)}`,
        itemStyle: { color: '#0ecb81' },
        symbol: 'triangle',
        symbolSize: 10,
        symbolRotate: 180,
        label: {
          show: true,
          formatter: 'S',
          color: '#0ecb81',
          fontSize: 9,
          fontWeight: 700,
          position: 'top',
        },
      }));

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
        data: [`MA${fastPeriod}`, `MA${slowPeriod}`],
        textStyle: { color: '#5e6673', fontSize: 11 },
        top: 4,
        right: 10,
        itemWidth: 14,
        itemHeight: 2,
      },
      axisPointer: { link: [{ xAxisIndex: [0, 1] }] },
      grid: [
        { left: 56, right: 16, top: 30, height: '58%' },
        { left: 56, right: 16, top: '76%', height: '16%' },
      ],
      xAxis: [
        {
          type: 'category',
          data: dates,
          gridIndex: 0,
          axisLine: { lineStyle: { color: '#1e2126' } },
          axisTick: { show: false },
          axisLabel: { show: false },
          splitLine: { show: false },
        },
        {
          type: 'category',
          data: dates,
          gridIndex: 1,
          axisLine: { lineStyle: { color: '#1e2126' } },
          axisTick: { show: false },
          axisLabel: { color: '#5e6673', fontSize: 10, margin: 6 },
          splitLine: { show: false },
        },
      ],
      yAxis: [
        {
          scale: true,
          gridIndex: 0,
          splitLine: { lineStyle: { color: '#1e2126', type: 'dashed' } },
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: { color: '#5e6673', fontSize: 10, margin: 8 },
        },
        {
          scale: true,
          gridIndex: 1,
          splitLine: { show: false },
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: { show: false },
        },
      ],
      dataZoom: [
        { type: 'inside', xAxisIndex: [0, 1], start: 60, end: 100 },
        {
          type: 'slider',
          xAxisIndex: [0, 1],
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
          markPoint: {
            data: [...buyMarkers, ...sellMarkers],
          },
        },
        {
          name: `MA${fastPeriod}`,
          type: 'line',
          data: maFast,
          xAxisIndex: 0,
          yAxisIndex: 0,
          smooth: true,
          lineStyle: { width: 1, color: '#f0b90b' },
          symbol: 'none',
          z: 2,
        },
        {
          name: `MA${slowPeriod}`,
          type: 'line',
          data: maSlow,
          xAxisIndex: 0,
          yAxisIndex: 0,
          smooth: true,
          lineStyle: { width: 1, color: '#722ed1' },
          symbol: 'none',
          z: 2,
        },
        {
          name: 'Vol',
          type: 'bar',
          data: volumes.map((v, i) => ({
            value: v,
            itemStyle: {
              color: ohlc[i][1] >= ohlc[i][0]
                ? 'rgba(246,70,93,0.35)'
                : 'rgba(14,203,129,0.35)',
            },
          })),
          xAxisIndex: 1,
          yAxisIndex: 1,
          barMaxWidth: 8,
        },
      ],
    };
  }, [kline, trades, symbol, fastPeriod, slowPeriod]);

  return (
    <ReactECharts
      option={option}
      style={{ height: 420, width: '100%' }}
      opts={{ renderer: 'canvas' }}
    />
  );
}
