/**
 * ソーシャルカード共通テーマ定数
 * 全Canvas系ページ（career-arc, cards, season, teams, circuits等）で使用
 */

export const CARD = {
  W: 1080,
  H: 1080,
  CANVAS_W: 968,
  CANVAS_H: 900,
} as const;

export const CARD_THEME = {
  bg: '#060606',
  grid: '#0e0e14',
  gridAlt: '#1a1a1a',
  text: '#e0e0e0',
  textDim: '#555',
  textMuted: '#333',
  textFaint: '#252525',
  accent: '#FFD700',
  watermark: '#181818',
  subtitle: '#6a6a6a',
} as const;

export const CARD_FONTS = {
  title: "'Bebas Neue', sans-serif",
  body: "'IBM Plex Mono', monospace",
  google: 'https://fonts.googleapis.com/css2?family=Bebas+Neue&family=IBM+Plex+Mono:wght@400;600&display=swap',
} as const;

export const CARD_PAD = {
  top: 48,
  right: 56,
  bottom: 56,
  left: 56,
  chart: { t: 20, r: 40, b: 60, l: 60 },
} as const;
