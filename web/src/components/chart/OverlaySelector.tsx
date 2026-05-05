import { Checkbox } from 'antd';
import type { Overlay, SubplotKey } from './KlineChart';

const PRESETS: { key: string; label: string; overlay: Overlay }[] = [
  { key: 'MA5',  label: 'MA5',  overlay: { type: 'MA', period: 5,  color: '#f0b90b' } },
  { key: 'MA10', label: 'MA10', overlay: { type: 'MA', period: 10, color: '#1890ff' } },
  { key: 'MA20', label: 'MA20', overlay: { type: 'MA', period: 20, color: '#722ed1' } },
  { key: 'MA60', label: 'MA60', overlay: { type: 'MA', period: 60, color: '#13c2c2' } },
  { key: 'BBI',  label: 'BBI',  overlay: { type: 'BBI', color: '#ff7a45' } },
];

export const PRESET_KEYS = PRESETS.map((p) => p.key);

export function keysToOverlays(keys: string[]): Overlay[] {
  return PRESETS.filter((p) => keys.includes(p.key)).map((p) => p.overlay);
}

export default function OverlaySelector({
  value,
  onChange,
}: {
  value: string[];
  onChange: (keys: string[]) => void;
}) {
  return (
    <Checkbox.Group
      value={value}
      onChange={(v) => onChange(v as string[])}
      options={PRESETS.map((p) => ({ label: p.label, value: p.key }))}
      style={{ fontSize: 11 }}
    />
  );
}

// ── 副图选择器 ───────────────────────────────────────────────
const SUBPLOTS: { key: SubplotKey; label: string }[] = [
  { key: 'VOL',  label: '成交量' },
  { key: 'MACD', label: 'MACD' },
  { key: 'KDJ',  label: 'KDJ' },
  { key: 'RSI',  label: 'RSI' },
];

export function SubplotSelector({
  value,
  onChange,
}: {
  value: SubplotKey[];
  onChange: (keys: SubplotKey[]) => void;
}) {
  return (
    <Checkbox.Group
      value={value}
      onChange={(v) => onChange(v as SubplotKey[])}
      options={SUBPLOTS.map((s) => ({ label: s.label, value: s.key }))}
      style={{ fontSize: 11 }}
    />
  );
}
