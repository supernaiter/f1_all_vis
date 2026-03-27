/**
 * データ読み込みユーティリティ
 * h2h_engine.pyが出力したJSON+PNGを読み込む
 */
import fs from 'node:fs';
import path from 'node:path';

const DATA_ROOT = path.resolve('/Volumes/intersd2/2026_1_4/Motorsports-Visualised/data');

export interface H2HPair {
  driver1: string;
  driver2: string;
  team1: string;
  team2: string;
  delta_median_sec: number | null;
  faster: string | null;
  path: string;
}

export interface H2HIndex {
  meta: {
    year: number;
    round: number;
    gp_name: string;
    total_pairs: number;
    total_laps: number;
  };
  pairs: H2HPair[];
}

export interface H2HAnalysis {
  meta: {
    year: number;
    round: number;
    gp_name: string;
    driver1: string;
    driver2: string;
    team1: string;
    team2: string;
    total_laps: number;
    vsc_periods: number[][];
    sc_periods: number[][];
  };
  race_result: Record<string, {
    grid: number;
    finish: number;
    status: string;
    pit_laps: number[];
  }>;
  pace: {
    drv1: { median: number; mean: number; std: number; clean_laps: number; total_laps: number };
    drv2: { median: number; mean: number; std: number; clean_laps: number; total_laps: number };
    delta_median_sec: number | null;
    faster: string | null;
  };
  sectors: Record<string, any>;
  speed: Record<string, any>;
  stints: Record<string, any[]>;
  degradation: Record<string, any[]>;
  charts: string[];
  seo: {
    title: string;
    title_ja: string;
    description: string;
    keywords: string[];
  };
}

/**
 * 全GPディレクトリを検出
 */
export function listGPs(): { year: number; round: number; gp_name: string; dir_name: string }[] {
  const dirs = fs.readdirSync(DATA_ROOT)
    .filter(d => /^\d{4}_R\d{2}_/.test(d))
    .sort();

  return dirs.map(d => {
    const match = d.match(/^(\d{4})_R(\d{2})_(.+)$/);
    if (!match) return null;
    return {
      year: parseInt(match[1]),
      round: parseInt(match[2]),
      gp_name: match[3],
      dir_name: d,
    };
  }).filter(Boolean) as any[];
}

/**
 * GPのH2Hインデックスを読み込む
 */
export function loadH2HIndex(dirName: string): H2HIndex | null {
  const indexPath = path.join(DATA_ROOT, dirName, 'h2h', 'index.json');
  if (!fs.existsSync(indexPath)) return null;
  return JSON.parse(fs.readFileSync(indexPath, 'utf-8'));
}

/**
 * 個別H2H分析を読み込む
 */
export function loadH2HAnalysis(dirName: string, pairDir: string): H2HAnalysis | null {
  const analysisPath = path.join(DATA_ROOT, dirName, pairDir, 'analysis.json');
  if (!fs.existsSync(analysisPath)) return null;
  return JSON.parse(fs.readFileSync(analysisPath, 'utf-8'));
}

/**
 * チャート画像のURLパスを返す（prebuildでpublic/charts/にコピー済み前提）
 */
export function getChartUrl(dirName: string, pairDir: string, chartFile: string): string | null {
  const chartPath = path.join(DATA_ROOT, dirName, pairDir, chartFile);
  if (!fs.existsSync(chartPath)) return null;
  // pairDir = "h2h/ANT_vs_NOR/" → pairSlug = "ANT_vs_NOR"
  const pairSlug = pairDir.replace(/^h2h\//, '').replace(/\/$/, '');
  return `/charts/${dirName}/${pairSlug}/${chartFile}`;
}

/**
 * チームカラーマップ
 */
export const TEAM_COLORS: Record<string, string> = {
  'McLaren': '#E07800', 'Ferrari': '#DC0000', 'Red Bull Racing': '#2B5DAB',
  'Mercedes': '#00B89F', 'Aston Martin': '#1B7A5A', 'Williams': '#3BA3E0',
  'Racing Bulls': '#4A72CC', 'Alpine': '#0078AA', 'Haas F1 Team': '#7A7A7A',
  'Audi': '#3AAA3A', 'Cadillac': '#888888',
};

export const TEAM_SHORT: Record<string, string> = {
  'McLaren': 'MCL', 'Ferrari': 'FER', 'Red Bull Racing': 'RBR',
  'Mercedes': 'MER', 'Aston Martin': 'AMR', 'Williams': 'WIL',
  'Racing Bulls': 'RBU', 'Alpine': 'ALP', 'Haas F1 Team': 'HAS',
  'Audi': 'AUD', 'Cadillac': 'CAD',
};
