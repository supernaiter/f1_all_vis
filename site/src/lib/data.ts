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

/**
 * ドライバー2者比較: ペア一覧
 * data/drivers/pairs/ 配下のディレクトリ名を返す
 */
export function listDriverPairs(): string[] {
  const dir = path.join(DATA_ROOT, 'drivers', 'pairs');
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir, { withFileTypes: true })
    .filter(e => e.isDirectory())
    .map(e => e.name)
    .sort();
}

export interface DriverCompareCareerArc {
  driver1: { code: string; name: string; color: string; cumWins: number[]; cumPts: number[]; debut: number };
  driver2: { code: string; name: string; color: string; cumWins: number[]; cumPts: number[]; debut: number };
}

/**
 * ドライバー比較データ読み込み
 * data/drivers/pairs/{pair}/{type}.json を読む
 */
export function loadDriverCompare(pair: string, type: string): any | null {
  const p = path.join(DATA_ROOT, 'drivers', 'pairs', pair, `${type}.json`);
  if (!fs.existsSync(p)) return null;
  return JSON.parse(fs.readFileSync(p, 'utf-8'));
}

// ============================================================
// TYPE-C: ドライバー3者比較（1,540トリプル × 2種）
// ============================================================
export interface DriverCompareCareerArcTriple {
  driver1: { code: string; name: string; color: string; cumWins: number[]; cumPts: number[]; debut: number };
  driver2: { code: string; name: string; color: string; cumWins: number[]; cumPts: number[]; debut: number };
  driver3: { code: string; name: string; color: string; cumWins: number[]; cumPts: number[]; debut: number };
}

/**
 * ドライバー3者比較: トリプル一覧
 * data/drivers/triples/ 配下のディレクトリ名を返す（辞書順スラッグ、例: alb-ant-bea）
 */
export function listDriverTriples(): string[] {
  const dir = path.join(DATA_ROOT, 'drivers', 'triples');
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir, { withFileTypes: true })
    .filter(e => e.isDirectory())
    .map(e => e.name)
    .sort();
}

/**
 * ドライバー3者比較データ読み込み
 * data/drivers/triples/{triple}/{type}.json を読む
 */
export function loadDriverTriple(triple: string, type: string): any | null {
  const p = path.join(DATA_ROOT, 'drivers', 'triples', triple, `${type}.json`);
  if (!fs.existsSync(p)) return null;
  return JSON.parse(fs.readFileSync(p, 'utf-8'));
}

// ============================================================
// TYPE-D: サーキット2者比較
// ============================================================
export interface CircuitRadarData {
  type: 'radar';
  axes: string[];
  circuit1: { slug: string; name: string; country: string; color: string; values: number[] };
  circuit2: { slug: string; name: string; country: string; color: string; values: number[] };
  meta: { subtitle: string; source: string };
}

export interface CircuitEraAdjustedData {
  type: 'era_adjusted_qualifying';
  circuit1: { slug: string; name: string; color: string; era_points: any[] };
  circuit2: { slug: string; name: string; color: string; era_points: any[] };
  meta: { subtitle: string; source: string; note?: string };
}

export function listCircuitPairs(): string[] {
  const dir = path.join(DATA_ROOT, 'circuits', 'pairs');
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir, { withFileTypes: true })
    .filter(e => e.isDirectory())
    .map(e => e.name)
    .sort();
}

export function loadCircuitCompare(pair: string, type: 'radar' | 'era_adjusted'): any | null {
  const p = path.join(DATA_ROOT, 'circuits', 'pairs', pair, `${type}.json`);
  if (!fs.existsSync(p)) return null;
  return JSON.parse(fs.readFileSync(p, 'utf-8'));
}

// ============================================================
// TYPE-H: ティア表
// ============================================================
export interface TierData {
  title: string;
  subtitle: string;
  tiers: { label: string; color: string; drivers: { code: string; name: string; note?: string }[] }[];
}

export function listTierPages(): string[] {
  const dir = path.join(DATA_ROOT, 'tiers');
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir)
    .filter(f => f.endsWith('.json'))
    .map(f => f.replace(/\.json$/, '').replace(/_/g, '-'))
    .sort();
}

export function loadTierData(slug: string): TierData | null {
  const fname = slug.replace(/-/g, '_') + '.json';
  const p = path.join(DATA_ROOT, 'tiers', fname);
  if (!fs.existsSync(p)) return null;
  return JSON.parse(fs.readFileSync(p, 'utf-8'));
}

// ============================================================
// TYPE-G: ピラー / 単体分析
// ============================================================
export interface PillarData {
  slug: string;
  title: string;
  subtitle: string;
  source: 'static' | 'pending';
  kind: string;
  entries: { rank?: number; code: string; name: string; value: number | string; note?: string }[];
  meta?: Record<string, any>;
}

export function listPillarPages(): string[] {
  const dir = path.join(DATA_ROOT, 'insights');
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir)
    .filter(f => f.endsWith('.json'))
    .map(f => f.replace(/\.json$/, '').replace(/_/g, '-'))
    .sort();
}

export function loadPillarData(slug: string): PillarData | null {
  const fname = slug.replace(/-/g, '_') + '.json';
  const p = path.join(DATA_ROOT, 'insights', fname);
  if (!fs.existsSync(p)) return null;
  return JSON.parse(fs.readFileSync(p, 'utf-8'));
}

// ============================================================
// TYPE-A: GPカード
// ============================================================
export const CARD_TYPES = [
  'lap1-delta', 'tyre-cliff', 'pace-variance', 'what-if',
  'braking-point', 'corner-speed', 'overtake-replay',
] as const;

export function listGPsWithCards(): { dir_name: string; slug: string; gp_name: string; round: number; year: number }[] {
  return listGPs().map(gp => {
    const cardsDir = path.join(DATA_ROOT, gp.dir_name, 'cards');
    if (!fs.existsSync(cardsDir)) return null;
    const slug = `${gp.year}-r${String(gp.round).padStart(2, '0')}-${gp.gp_name.toLowerCase()}`;
    return { ...gp, slug };
  }).filter(Boolean) as any[];
}

export function loadCardData(dirName: string, cardType: string): any | null {
  // cardType は kebab-case。ファイル名は snake_case
  const fname = cardType.replace(/-/g, '_') + '.json';
  const p = path.join(DATA_ROOT, dirName, 'cards', fname);
  if (!fs.existsSync(p)) return null;
  return JSON.parse(fs.readFileSync(p, 'utf-8'));
}

// ============================================================
// TYPE-E: チーム2者比較（GP単位）
// ============================================================
export const TEAM_COMPARE_TYPES = ['dna', 'variance'] as const;

export function listTeamGpSlugs(): string[] {
  const dir = path.join(DATA_ROOT, 'teams');
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir, { withFileTypes: true })
    .filter(e => e.isDirectory())
    .map(e => e.name)
    .sort();
}

export function listTeamPairs(gpSlug: string): string[] {
  const dir = path.join(DATA_ROOT, 'teams', gpSlug);
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir, { withFileTypes: true })
    .filter(e => e.isDirectory())
    .map(e => e.name)
    .sort();
}

export function loadTeamCompare(gpSlug: string, pair: string, type: 'dna' | 'variance'): any | null {
  const p = path.join(DATA_ROOT, 'teams', gpSlug, pair, `${type}.json`);
  if (!fs.existsSync(p)) return null;
  return JSON.parse(fs.readFileSync(p, 'utf-8'));
}

// ============================================================
// TYPE-F: シーズン横断
// ============================================================
export const SEASON_TYPES = [
  'championship', 'constructors', 'title-probability',
  'momentum', 'power-ranking', 'upgrades',
] as const;

export function loadSeasonData(type: string, year = 2026): any | null {
  const fname = type.replace(/-/g, '_') + '.json';
  const p = path.join(DATA_ROOT, 'season', String(year), fname);
  if (!fs.existsSync(p)) return null;
  return JSON.parse(fs.readFileSync(p, 'utf-8'));
}

// タイヤカラー（サーバーサイド用）
export const TYRE_COLORS: Record<string, string> = {
  SOFT: '#FF3333', MEDIUM: '#FFD700', HARD: '#FFFFFF',
  INTERMEDIATE: '#39B54A', WET: '#0072CE',
};

// F1公式ドライバーヘッドショット（開発用・一時利用）
const F1_IMG_BASE = 'https://media.formula1.com/image/upload/c_thumb,g_face,w_440,h_440/q_auto/v1740000001/common/f1/2025';
export const DRIVER_HEADSHOTS: Record<string, string> = {
  'VER': `${F1_IMG_BASE}/redbullracing/maxver01/2025redbullracingmaxver01right.webp`,
  'NOR': `${F1_IMG_BASE}/mclaren/lannor01/2025mclarenlannor01right.webp`,
  'LEC': `${F1_IMG_BASE}/ferrari/chalec01/2025ferrarichalec01right.webp`,
  'HAM': `${F1_IMG_BASE}/ferrari/lewham01/2025ferrarilewham01right.webp`,
  'RUS': `${F1_IMG_BASE}/mercedes/georus01/2025mercedesgeorus01right.webp`,
  'PIA': `${F1_IMG_BASE}/mclaren/oscpia01/2025mclarenoscpia01right.webp`,
  'TSU': `${F1_IMG_BASE}/redbullracing/yuktsu01/2025redbullracingyuktsu01right.webp`,
  'ALO': `${F1_IMG_BASE}/astonmartin/feralo01/2025astonmartinferalo01right.webp`,
  'STR': `${F1_IMG_BASE}/astonmartin/lanstr01/2025astonmartinlanstr01right.webp`,
  'SAI': `${F1_IMG_BASE}/williams/carsai01/2025williamscarsai01right.webp`,
  'ALB': `${F1_IMG_BASE}/williams/alealb01/2025williamsalealb01right.webp`,
  'LAW': `${F1_IMG_BASE}/racingbulls/lialaw01/2025racingbullslialaw01right.webp`,
  'HAD': `${F1_IMG_BASE}/racingbulls/isahad01/2025racingbullsisahad01right.webp`,
  'GAS': `${F1_IMG_BASE}/alpine/piegas01/2025alpinepiegas01right.webp`,
  'COL': `${F1_IMG_BASE}/alpine/fracol01/2025alpinefracol01right.webp`,
  'OCO': `${F1_IMG_BASE}/haasf1team/estoco01/2025haasf1teamestoco01right.webp`,
  'BEA': `${F1_IMG_BASE}/haasf1team/olibea01/2025haasf1teamolibea01right.webp`,
  'HUL': `${F1_IMG_BASE}/kicksauber/nichul01/2025kicksaubernichul01right.webp`,
  'BOR': `${F1_IMG_BASE}/kicksauber/gabbor01/2025kicksaubergabbor01right.webp`,
  'ANT': `${F1_IMG_BASE}/mercedes/andant01/2025mercedesandant01right.webp`,
  'LIN': `${F1_IMG_BASE}/mclaren/lannor01/2025mclarenlannor01right.webp`,
};
