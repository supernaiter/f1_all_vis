/**
 * ECharts F1ダークテーマ — サイトCSS変数に合わせた配色
 */
export const F1_DARK_THEME = {
  color: ['#00B89F', '#DC0000', '#3BA3E0', '#FFD700', '#FF3333', '#7A7A7A'],
  backgroundColor: 'transparent',
  textStyle: {
    color: '#EEEEEE',
    fontFamily: 'Hiragino Sans, Yu Gothic, system-ui, sans-serif',
  },
  title: {
    textStyle: { color: '#EEEEEE', fontWeight: 'bold' },
    subtextStyle: { color: '#8899AA' },
  },
  legend: {
    textStyle: { color: '#8899AA' },
  },
  tooltip: {
    backgroundColor: '#1a1a2e',
    borderColor: '#333355',
    borderWidth: 1,
    textStyle: { color: '#EEEEEE', fontSize: 13 },
  },
  xAxis: {
    axisLine: { lineStyle: { color: '#333355' } },
    axisLabel: { color: '#8899AA' },
    splitLine: { lineStyle: { color: '#333355', type: 'dashed' as const } },
    axisTick: { lineStyle: { color: '#333355' } },
  },
  yAxis: {
    axisLine: { lineStyle: { color: '#333355' } },
    axisLabel: { color: '#8899AA' },
    splitLine: { lineStyle: { color: '#333355', type: 'dashed' as const } },
    axisTick: { lineStyle: { color: '#333355' } },
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
