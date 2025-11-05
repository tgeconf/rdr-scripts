import { Color } from 'three';

const palette = [
  '#4f46e5',
  '#0ea5e9',
  '#7c3aed',
  '#22d3ee',
  '#f97316',
  '#14b8a6',
  '#ec4899',
  '#a855f7',
  '#38bdf8',
  '#f59e0b'
];

const memoized = new Map<number, Color>();

export const getClusterColor = (clusterId: number): Color => {
  const existing = memoized.get(clusterId);
  if (existing) {
    return existing;
  }
  const color = new Color(palette[Math.abs(clusterId) % palette.length]);
  memoized.set(clusterId, color);
  return color;
};

export const getClusterColorHex = (clusterId: number) => getClusterColor(clusterId).getStyle();
