import type { Overlay } from './KlineChart';

export const OVERLAY_PRESETS: { key: string; label: string; overlay: Overlay }[] = [
  { key: 'MA5', label: 'MA5', overlay: { type: 'MA', period: 5, color: '#f0b90b' } },
  { key: 'MA10', label: 'MA10', overlay: { type: 'MA', period: 10, color: '#1890ff' } },
  { key: 'MA20', label: 'MA20', overlay: { type: 'MA', period: 20, color: '#722ed1' } },
  { key: 'MA60', label: 'MA60', overlay: { type: 'MA', period: 60, color: '#13c2c2' } },
  { key: 'BBI', label: 'BBI', overlay: { type: 'BBI', color: '#ff7a45' } },
];

export const PRESET_KEYS = OVERLAY_PRESETS.map((preset) => preset.key);

export function keysToOverlays(keys: string[]): Overlay[] {
  return OVERLAY_PRESETS
    .filter((preset) => keys.includes(preset.key))
    .map((preset) => preset.overlay);
}
