/**
 * ECharts F1ダークテーマ — サイトCSS変数に合わせた配色
 */
export const F1_DARK_THEME = {
  color: ['#e10600', '#28973e', '#3BA3E0', '#FFD700', '#FF3333', '#7A7A7A'],
  backgroundColor: 'transparent',
  textStyle: {
    color: '#ffffff',
    fontFamily: 'Hiragino Sans, Yu Gothic, system-ui, sans-serif',
  },
  title: {
    textStyle: { color: '#ffffff', fontWeight: 'bold' },
    subtextStyle: { color: '#aaaaaa' },
  },
  legend: {
    textStyle: { color: '#aaaaaa' },
  },
  tooltip: {
    backgroundColor: '#1c1c25',
    borderColor: '#303037',
    borderWidth: 1,
    textStyle: { color: '#ffffff', fontSize: 13 },
  },
  xAxis: {
    axisLine: { lineStyle: { color: '#303037' } },
    axisLabel: { color: '#aaaaaa' },
    splitLine: { lineStyle: { color: '#303037', type: 'dashed' as const } },
    axisTick: { lineStyle: { color: '#303037' } },
  },
  yAxis: {
    axisLine: { lineStyle: { color: '#303037' } },
    axisLabel: { color: '#aaaaaa' },
    splitLine: { lineStyle: { color: '#303037', type: 'dashed' as const } },
    axisTick: { lineStyle: { color: '#303037' } },
  },
};

export const COMPOUND_COLORS: Record<string, string> = {
  SOFT: '#FF3333',
  MEDIUM: '#FFD700',
  HARD: '#FFFFFF',
  INTERMEDIATE: '#39B54A',
  WET: '#0072CE',
};

// SC/VSC markArea用のスタイル
export const SC_AREA_STYLE = {
  color: 'rgba(255, 200, 0, 0.08)',
  borderColor: 'rgba(255, 200, 0, 0.3)',
  borderWidth: 1,
  borderType: 'dashed' as const,
};

export const VSC_AREA_STYLE = {
  color: 'rgba(255, 200, 0, 0.05)',
  borderColor: 'rgba(255, 200, 0, 0.15)',
  borderWidth: 1,
  borderType: 'dotted' as const,
};
