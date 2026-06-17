import { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import type { EquityPoint } from '../../types';

interface Props {
  data: EquityPoint[];
  initialCash: number;
}

export default function EquityChart({ data, initialCash }: Props) {
  const option = useMemo(() => {
    const dates = data.map((d) => d.dt);
    const returns = data.map((d) => +((d.equity / initialCash - 1) * 100).toFixed(4));

    const drawdowns = data.reduce<{ peak: number; values: number[] }>(
      (acc, d) => {
        const peak = Math.max(acc.peak, d.equity);
        const drawdown = peak > 0 ? +((d.equity / peak - 1) * 100).toFixed(4) : 0;
        return { peak, values: [...acc.values, drawdown] };
      },
      { peak: 0, values: [] },
    ).values;

    return {
      backgroundColor: 'transparent',
      animation: false,
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#1a1d21',
        borderColor: '#2b2f36',
        textStyle: { color: '#eaecef', fontSize: 12, fontFamily: "'JetBrains Mono', monospace" },
        padding: [8, 12],
        formatter: (params: { value: number; axisValue: string; seriesName: string }[]) => {
          let html = `<div style="margin-bottom:4px;color:#5e6673">${params[0].axisValue}</div>`;
          params.forEach((p) => {
            const color = p.seriesName === '回撤' ? '#f6465d' : '#1890ff';
            html += `<div style="color:${color};font-size:12px">${p.seriesName}: ${p.value.toFixed(2)}%</div>`;
          });
          return html;
        },
      },
      legend: {
        data: ['收益率', '回撤'],
        textStyle: { color: '#5e6673', fontSize: 11 },
        top: 4,
        right: 10,
        itemWidth: 14,
        itemHeight: 2,
      },
      grid: { left: 56, right: 16, top: 30, bottom: 32 },
      xAxis: {
        type: 'category',
        data: dates,
        axisLine: { lineStyle: { color: '#1e2126' } },
        axisTick: { show: false },
        axisLabel: { color: '#5e6673', fontSize: 10, margin: 6 },
        splitLine: { show: false },
      },
      yAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: '#1e2126', type: 'dashed' } },
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          color: '#5e6673',
          fontSize: 10,
          formatter: '{value}%',
        },
      },
      dataZoom: [{ type: 'inside', start: 0, end: 100 }],
      series: [
        {
          name: '收益率',
          type: 'line',
          data: returns,
          smooth: true,
          symbol: 'none',
          lineStyle: { color: '#1890ff', width: 1.5 },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(24,144,255,0.15)' },
                { offset: 1, color: 'rgba(24,144,255,0)' },
              ],
            },
          },
          z: 3,
        },
        {
          name: '回撤',
          type: 'line',
          data: drawdowns,
          smooth: true,
          symbol: 'none',
          lineStyle: { color: '#f6465d', width: 1, type: 'dashed' },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(246,70,93,0)' },
                { offset: 1, color: 'rgba(246,70,93,0.08)' },
              ],
            },
          },
          z: 2,
        },
      ],
    };
  }, [data, initialCash]);

  return (
    <ReactECharts
      option={option}
      style={{ height: 220, width: '100%' }}
      opts={{ renderer: 'canvas' }}
    />
  );
}
