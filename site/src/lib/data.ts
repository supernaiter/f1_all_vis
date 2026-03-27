/**
 * データ読み込みユーティリティ
 * h2h_engine.pyが出力したJSONを読み込む
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

export interface LapEntry {
  lap: number;
  time: number;
  stint: number | null;
  compound: string | null;
  tyre_life: number | null;
  is_clean: boolean;
}

export interface DeltaEntry {
  lap: number;
  delta: number;
}

export interface StintLapEntry {
  tyre_life: number;
  time: number;
  lap: number;
}

export interface PerLapData {
  pace: {
    drv1_laps: LapEntry[];
    drv2_laps: LapEntry[];
    deltas: DeltaEntry[];
  };
  sectors: Record<string, {
    drv1: { lap: number; time: number }[];
    drv2: { lap: number; time: number }[];
    deltas: DeltaEntry[];
  }>;
  speed: Record<string, {
    drv1_values: number[];
    drv2_values: number[];
  }>;
  stints: Record<string, {
    stint: number;
    compound: string;
    laps: StintLapEntry[];
    trend: { slope: number; intercept: number } | null;
  }[]>;
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
  per_lap: PerLapData;
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
 * H2H全ページ共通のgetStaticPaths
 */
export function getH2HStaticPaths() {
  const gps = listGPs();
  const paths: any[] = [];

  for (const gp of gps) {
    const index = loadH2HIndex(gp.dir_name);
    if (!index) continue;

    for (const pair of index.pairs) {
      const slug = `${gp.year}-r${String(gp.round).padStart(2, '0')}-${gp.gp_name.toLowerCase()}/${pair.driver1.toLowerCase()}-vs-${pair.driver2.toLowerCase()}`;
      paths.push({
        params: { slug },
        props: {
          dirName: gp.dir_name,
          pairDir: pair.path,
          gpMeta: index.meta,
        },
      });
    }
  }

  return paths;
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
