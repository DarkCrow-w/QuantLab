import { Checkbox } from 'antd';
import type { SubplotKey } from './KlineChart';
import { OVERLAY_PRESETS } from './overlayPresets';

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
      options={OVERLAY_PRESETS.map((p) => ({ label: p.label, value: p.key }))}
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
