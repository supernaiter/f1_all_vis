"""
============================================================
汎用ドライバーH2Hレースペース比較エンジン
============================================================
pSEO 2.0アーキテクチャ: 任意のGP × 任意のドライバーペアに対して
構造化JSON + PNGチャートを自動生成する。

使い方:
  # 単一ペア
  python h2h_engine.py 2026 Australia 1 RUS LEC

  # 全ペア自動生成
  python h2h_engine.py 2026 Australia 1 --all

  # チームメイトのみ
  python h2h_engine.py 2026 Australia 1 --teammates

出力:
  data/{YEAR}_R{ROUND}_{GP}/h2h/{DRV1}_vs_{DRV2}/
    ├── analysis.json    ← 構造化分析データ（pSEOスキーマ）
    ├── chart_laptime_delta.png
    ├── chart_speed_boxplot.png
    ├── chart_sector_compare.png
    └── chart_sector_table.png
"""

import sys
import json
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# スタイル定数
# ============================================================
LT = {
    'bg':       '#FFFFFF',
    'card_bg':  '#F7F7FA',
    'text':     '#1a1a2e',
    'axis':     '#444444',
    'grid_maj': '#CCCCCC',
    'grid_min': '#E8E8E8',
    'spine':    '#AAAAAA',
    'sc':       '#FFD700',
    'sc_alpha': 0.20,
    'title_size': 18,
    'label_size': 13,
    'tick_size':  11,
    'line_w':     2.8,
}

TEAM_COLORS = {
    'McLaren': '#E07800', 'Ferrari': '#DC0000', 'Red Bull Racing': '#2B5DAB',
    'Mercedes': '#00B89F', 'Aston Martin': '#1B7A5A', 'Williams': '#3BA3E0',
    'Racing Bulls': '#4A72CC', 'Alpine': '#0078AA', 'Haas F1 Team': '#7A7A7A',
    'Audi': '#3AAA3A', 'Cadillac': '#888888',
}

TEAM_SHORT = {
    'McLaren': 'MCL', 'Ferrari': 'FER', 'Red Bull Racing': 'RBR',
    'Mercedes': 'MER', 'Aston Martin': 'AMR', 'Williams': 'WIL',
    'Racing Bulls': 'RBU', 'Alpine': 'ALP', 'Haas F1 Team': 'HAS',
    'Audi': 'AUD', 'Cadillac': 'CAD',
}

TYRE_COLORS = {
    'SOFT': '#DD2222', 'MEDIUM': '#CCAA00', 'HARD': '#555555',
    'INTERMEDIATE': '#2E9440', 'WET': '#0060B0',
}

SPEED_COLS = ['SpeedI1', 'SpeedI2', 'SpeedFL', 'SpeedST']
SPEED_LABELS = ['S1末端', 'S2末端', 'FL', 'ST']

FUEL_EFFECT = -0.06  # 燃料燃焼によるラップタイム改善（秒/ラップ）

# 日本語フォント
for font_name in ['Hiragino Sans', 'Hiragino Kaku Gothic Pro', 'Noto Sans JP',
                   'Yu Gothic', 'Meiryo', 'MS Gothic']:
    available = {f.name for f in matplotlib.font_manager.fontManager.ttflist}
    if font_name in available:
        plt.rcParams['font.family'] = font_name
        break


# ============================================================
# データ読み込み
# ============================================================
class GPData:
    """1GPのレースデータを管理"""

    def __init__(self, year, gp_name, round_number):
        self.year = year
        self.gp_name = gp_name
        self.round_number = round_number
        self.base_dir = Path(f'./data/{year}_R{round_number:02d}_{gp_name}/export')

        # データ読み込み
        self.laps = pd.read_csv(self.base_dir / 'race_laps.csv')
        self.results = pd.read_csv(self.base_dir / 'race_results.csv')
        self.rcm = pd.read_csv(self.base_dir / 'race_control_messages.csv')

        self.total_laps = int(self.laps['LapNumber'].max())

        # ドライバー情報マップ
        self.drv_team = dict(zip(self.results['Abbreviation'], self.results['TeamName']))
        self.drv_pos = dict(zip(self.results['Abbreviation'],
                                self.results['Position'].astype(int)))
        self.drv_grid = {}
        for _, row in self.results.iterrows():
            gp = row.get('GridPosition', np.nan)
            self.drv_grid[row['Abbreviation']] = int(gp) if pd.notna(gp) else 0
        self.drv_status = dict(zip(self.results['Abbreviation'], self.results['Status']))

        # SC/VSC期間を自動検出
        self.vsc_periods, self.sc_periods = self._detect_neutralizations()
        self.neutralized_laps = self._build_neutralized_set()

        # ピットストップ情報
        self.pit_laps = self._detect_pit_laps()

        # 全ドライバーのクリーンラップ
        self.clean_laps = self._build_clean_laps()

        # 完走ドライバー一覧（十分な周回数）
        min_laps = self.total_laps * 0.5
        self.valid_drivers = [
            drv for drv in self.results['Abbreviation']
            if len(self.laps[self.laps['Driver'] == drv]) >= min_laps
        ]

    def _detect_neutralizations(self):
        """SC/VSC期間をrace_control_messagesから自動検出"""
        vsc_periods = []
        sc_periods = []
        current_vsc_start = None
        current_sc_start = None

        for _, row in self.rcm.iterrows():
            msg = str(row.get('Message', ''))
            lap = row.get('Lap', None)
            if lap is None or pd.isna(lap):
                continue
            lap = int(lap)

            # VSC
            if 'VSC DEPLOYED' in msg:
                current_vsc_start = lap
            elif 'VSC ENDING' in msg and current_vsc_start is not None:
                vsc_periods.append((current_vsc_start, lap))
                current_vsc_start = None

            # SC
            if 'SAFETY CAR DEPLOYED' in msg and 'VIRTUAL' not in msg:
                current_sc_start = lap
            elif 'SAFETY CAR IN THIS LAP' in msg and current_sc_start is not None:
                sc_periods.append((current_sc_start, lap))
                current_sc_start = None

        # 閉じられなかった期間の処理
        if current_vsc_start is not None:
            vsc_periods.append((current_vsc_start, current_vsc_start + 1))
        if current_sc_start is not None:
            sc_periods.append((current_sc_start, current_sc_start + 2))

        return vsc_periods, sc_periods

    def _build_neutralized_set(self):
        """SC/VSC期間 ± バッファのラップ番号セット"""
        exclude = set()
        for start, end in self.vsc_periods + self.sc_periods:
            for lap in range(max(1, start - 1), end + 2):
                exclude.add(lap)
        return exclude

    def _detect_pit_laps(self):
        """ドライバーごとのピットインラップを検出"""
        pit_laps = {}
        for drv in self.results['Abbreviation']:
            drv_laps = self.laps[self.laps['Driver'] == drv]
            pits = drv_laps[drv_laps['PitInTime_sec'].notna()]['LapNumber'].astype(int).tolist()
            pit_laps[drv] = pits
        return pit_laps

    def _build_clean_laps(self):
        """全ドライバーのクリーンラップを構築"""
        clean = {}
        for drv in self.results['Abbreviation']:
            df = self.laps[self.laps['Driver'] == drv].copy()
            df = df.dropna(subset=['LapTime_sec'])
            df = df[df['LapNumber'] > 1]
            df = df[df['PitInTime_sec'].isna() & df['PitOutTime_sec'].isna()]
            df = df[df['TrackStatus'].astype(str) == '1']
            df = df[~df['LapNumber'].isin(self.neutralized_laps)]

            # 107%フィルタ
            if not df.empty:
                fastest = df['LapTime_sec'].min()
                df = df[df['LapTime_sec'] <= fastest * 1.07]

            clean[drv] = df
        return clean

    def get_teammates(self):
        """チームメイトペアのリストを返す"""
        team_drivers = {}
        for drv in self.valid_drivers:
            team = self.drv_team.get(drv, '')
            if team not in team_drivers:
                team_drivers[team] = []
            team_drivers[team].append(drv)

        pairs = []
        for team, drivers in team_drivers.items():
            if len(drivers) >= 2:
                # 順位が高い方をdrv1にする
                drivers.sort(key=lambda d: self.drv_pos.get(d, 99))
                pairs.append((drivers[0], drivers[1]))
        return pairs

    def get_all_pairs(self):
        """有効ドライバー全ペアを返す"""
        from itertools import combinations
        # 順位順にソート
        sorted_drivers = sorted(self.valid_drivers,
                                key=lambda d: self.drv_pos.get(d, 99))
        return list(combinations(sorted_drivers, 2))


# ============================================================
# H2H分析エンジン
# ============================================================
class H2HAnalysis:
    """2名のドライバーのH2H分析を実行し、JSON + PNGを出力"""

    def __init__(self, gp_data: GPData, drv1: str, drv2: str):
        self.gp = gp_data
        self.drv1 = drv1
        self.drv2 = drv2

        self.team1 = gp_data.drv_team.get(drv1, 'Unknown')
        self.team2 = gp_data.drv_team.get(drv2, 'Unknown')
        self.color1 = TEAM_COLORS.get(self.team1, '#999999')
        self.color2 = TEAM_COLORS.get(self.team2, '#DC0000')

        # 出力ディレクトリ
        self.out_dir = Path(
            f'./data/{gp_data.year}_R{gp_data.round_number:02d}_{gp_data.gp_name}'
            f'/h2h/{drv1}_vs_{drv2}'
        )
        self.out_dir.mkdir(parents=True, exist_ok=True)

        # ドライバーデータ
        self.laps1 = gp_data.laps[gp_data.laps['Driver'] == drv1].copy()
        self.laps2 = gp_data.laps[gp_data.laps['Driver'] == drv2].copy()
        self.clean1 = gp_data.clean_laps.get(drv1, pd.DataFrame())
        self.clean2 = gp_data.clean_laps.get(drv2, pd.DataFrame())

    # --- 分析ロジック ---

    def compute_pace(self):
        """ペース統計を算出"""
        result = {}
        for label, clean in [('drv1', self.clean1), ('drv2', self.clean2)]:
            drv = self.drv1 if label == 'drv1' else self.drv2
            if clean.empty:
                result[label] = {'median': None, 'mean': None, 'std': None,
                                 'clean_laps': 0, 'total_laps': 0}
                continue
            result[label] = {
                'median': round(clean['LapTime_sec'].median(), 3),
                'mean': round(clean['LapTime_sec'].mean(), 3),
                'std': round(clean['LapTime_sec'].std(), 3),
                'clean_laps': len(clean),
                'total_laps': int(self.laps1['LapNumber'].max()) if label == 'drv1'
                              else int(self.laps2['LapNumber'].max()),
            }

        # デルタ
        if result['drv1']['median'] and result['drv2']['median']:
            result['delta_median_sec'] = round(
                result['drv1']['median'] - result['drv2']['median'], 3)
            result['faster'] = self.drv1 if result['delta_median_sec'] < 0 else self.drv2
        else:
            result['delta_median_sec'] = None
            result['faster'] = None

        return result

    def compute_sectors(self):
        """セクター分析"""
        sectors = {}
        for sec_name, col in [('S1', 'Sector1Time_sec'), ('S2', 'Sector2Time_sec'),
                               ('S3', 'Sector3Time_sec')]:
            c1 = self.clean1[col].dropna()
            c2 = self.clean2[col].dropna()

            # 共通ラップでのデルタ
            common = set(self.clean1['LapNumber']) & set(self.clean2['LapNumber'])
            if common:
                d1 = self.clean1[self.clean1['LapNumber'].isin(common)][col].dropna()
                d2 = self.clean2[self.clean2['LapNumber'].isin(common)][col].dropna()
                cum_delta = round(d1.sum() - d2.sum(), 3) if len(d1) == len(d2) else None
            else:
                cum_delta = None

            # 勝敗カウント（共通ラップ）
            wins1, wins2 = 0, 0
            for lap in common:
                v1 = self.clean1[self.clean1['LapNumber'] == lap][col].values
                v2 = self.clean2[self.clean2['LapNumber'] == lap][col].values
                if len(v1) > 0 and len(v2) > 0:
                    if v1[0] < v2[0]:
                        wins1 += 1
                    elif v2[0] < v1[0]:
                        wins2 += 1

            sectors[sec_name] = {
                f'{self.drv1}_avg': round(c1.mean(), 3) if not c1.empty else None,
                f'{self.drv2}_avg': round(c2.mean(), 3) if not c2.empty else None,
                'delta_sec': round(c1.mean() - c2.mean(), 3) if not c1.empty and not c2.empty else None,
                'cumulative_delta_sec': cum_delta,
                f'{self.drv1}_wins': wins1,
                f'{self.drv2}_wins': wins2,
                'common_laps': len(common),
            }

        return sectors

    def compute_speed(self):
        """スピード分析"""
        speed = {}
        for col, label in zip(SPEED_COLS, SPEED_LABELS):
            c1 = self.clean1[col].dropna()
            c2 = self.clean2[col].dropna()
            speed[label] = {
                f'{self.drv1}_median': round(c1.median(), 1) if not c1.empty else None,
                f'{self.drv2}_median': round(c2.median(), 1) if not c2.empty else None,
                'delta_kmh': round(c1.median() - c2.median(), 1)
                    if not c1.empty and not c2.empty else None,
            }
        return speed

    def compute_stints(self):
        """スティント別分析"""
        stints = {}
        for label, laps_df, clean_df in [('drv1', self.laps1, self.clean1),
                                          ('drv2', self.laps2, self.clean2)]:
            drv = self.drv1 if label == 'drv1' else self.drv2
            drv_stints = []
            for stint_num in sorted(laps_df['Stint'].dropna().unique()):
                stint_laps = laps_df[laps_df['Stint'] == stint_num]
                clean_stint = clean_df[clean_df['Stint'] == stint_num]
                compound = stint_laps['Compound'].mode()
                compound = compound.iloc[0] if not compound.empty else 'UNKNOWN'

                drv_stints.append({
                    'stint': int(stint_num),
                    'compound': compound,
                    'total_laps': len(stint_laps),
                    'clean_laps': len(clean_stint),
                    'median_pace': round(clean_stint['LapTime_sec'].median(), 3)
                        if not clean_stint.empty else None,
                    'mean_pace': round(clean_stint['LapTime_sec'].mean(), 3)
                        if not clean_stint.empty else None,
                })
            stints[label] = drv_stints
        return stints

    def compute_degradation(self):
        """デグラデーション分析"""
        deg = {}
        for label, clean_df in [('drv1', self.clean1), ('drv2', self.clean2)]:
            drv = self.drv1 if label == 'drv1' else self.drv2
            drv_deg = []

            for (stint, compound), grp in clean_df.groupby(['Stint', 'Compound']):
                grp = grp.sort_values('TyreLife')
                if len(grp) < 5:
                    continue
                x = grp['TyreLife'].values
                y = grp['LapTime_sec'].values
                coeffs = np.polyfit(x, y, 1)
                raw_rate = round(coeffs[0], 4)
                corrected = round(raw_rate - FUEL_EFFECT, 4)

                drv_deg.append({
                    'stint': int(stint),
                    'compound': compound,
                    'raw_deg_sec_per_lap': raw_rate,
                    'fuel_corrected_deg': corrected,
                    'clean_laps': len(grp),
                })
            deg[label] = drv_deg
        return deg

    # --- ECharts用 per-lapデータ ---

    def build_per_lap_data(self):
        """クライアント側ECharts描画用のper-lap配列を構築"""
        common_laps = sorted(
            set(self.clean1['LapNumber'].astype(int)) &
            set(self.clean2['LapNumber'].astype(int))
        )
        clean1_set = set(self.clean1['LapNumber'].astype(int))
        clean2_set = set(self.clean2['LapNumber'].astype(int))

        # --- ペースデータ ---
        def lap_series(laps_df, clean_set):
            valid = laps_df.dropna(subset=['LapTime_sec']).copy()
            valid = valid[valid['LapTime_sec'] < valid['LapTime_sec'].quantile(0.98) * 1.15]
            valid = valid.sort_values('LapNumber')
            out = []
            for _, r in valid.iterrows():
                out.append({
                    'lap': int(r['LapNumber']),
                    'time': round(r['LapTime_sec'], 3),
                    'stint': int(r['Stint']) if pd.notna(r.get('Stint')) else None,
                    'compound': r['Compound'] if pd.notna(r.get('Compound')) else None,
                    'tyre_life': int(r['TyreLife']) if pd.notna(r.get('TyreLife')) else None,
                    'is_clean': int(r['LapNumber']) in clean_set,
                })
            return out

        deltas = []
        c1_map = self.clean1.set_index(self.clean1['LapNumber'].astype(int))
        c2_map = self.clean2.set_index(self.clean2['LapNumber'].astype(int))
        for lap in common_laps:
            t1 = c1_map.loc[lap, 'LapTime_sec']
            t2 = c2_map.loc[lap, 'LapTime_sec']
            if isinstance(t1, pd.Series):
                t1 = t1.iloc[0]
            if isinstance(t2, pd.Series):
                t2 = t2.iloc[0]
            deltas.append({'lap': int(lap), 'delta': round(float(t1 - t2), 3)})

        pace_data = {
            'drv1_laps': lap_series(self.laps1, clean1_set),
            'drv2_laps': lap_series(self.laps2, clean2_set),
            'deltas': deltas,
        }

        # --- セクターデータ ---
        sector_data = {}
        for sec_name, col in [('S1', 'Sector1Time_sec'), ('S2', 'Sector2Time_sec'), ('S3', 'Sector3Time_sec')]:
            s1 = self.clean1.dropna(subset=[col])[['LapNumber', col]].sort_values('LapNumber')
            s2 = self.clean2.dropna(subset=[col])[['LapNumber', col]].sort_values('LapNumber')

            sec_deltas = []
            for lap in common_laps:
                v1_rows = self.clean1[self.clean1['LapNumber'].astype(int) == lap]
                v2_rows = self.clean2[self.clean2['LapNumber'].astype(int) == lap]
                if len(v1_rows) > 0 and len(v2_rows) > 0:
                    v1 = v1_rows[col].iloc[0]
                    v2 = v2_rows[col].iloc[0]
                    if pd.notna(v1) and pd.notna(v2):
                        sec_deltas.append({'lap': int(lap), 'delta': round(float(v1 - v2), 3)})

            sector_data[sec_name] = {
                'drv1': [{'lap': int(r['LapNumber']), 'time': round(r[col], 3)} for _, r in s1.iterrows()],
                'drv2': [{'lap': int(r['LapNumber']), 'time': round(r[col], 3)} for _, r in s2.iterrows()],
                'deltas': sec_deltas,
            }

        # --- スピードデータ（ボックスプロット用の生配列）---
        speed_data = {}
        for col, label in zip(SPEED_COLS, SPEED_LABELS):
            c1 = self.clean1[col].dropna()
            c2 = self.clean2[col].dropna()
            speed_data[label] = {
                'drv1_values': [round(float(v), 1) for v in c1.tolist()],
                'drv2_values': [round(float(v), 1) for v in c2.tolist()],
            }

        # --- スティントデータ（デグラデーション可視化用）---
        stint_data = {}
        for label, clean_df in [('drv1', self.clean1), ('drv2', self.clean2)]:
            drv_stints = []
            for (stint, compound), grp in clean_df.groupby(['Stint', 'Compound']):
                grp = grp.sort_values('TyreLife')
                laps_arr = [{'tyre_life': int(r['TyreLife']), 'time': round(r['LapTime_sec'], 3),
                             'lap': int(r['LapNumber'])} for _, r in grp.iterrows()]
                trend = None
                if len(grp) >= 5:
                    coeffs = np.polyfit(grp['TyreLife'].values, grp['LapTime_sec'].values, 1)
                    trend = {'slope': round(float(coeffs[0]), 4), 'intercept': round(float(coeffs[1]), 3)}
                drv_stints.append({
                    'stint': int(stint), 'compound': compound,
                    'laps': laps_arr, 'trend': trend,
                })
            stint_data[label] = drv_stints

        return {
            'pace': pace_data,
            'sectors': sector_data,
            'speed': speed_data,
            'stints': stint_data,
        }

    # --- JSON出力 ---

    def build_json(self):
        """pSEO 2.0スキーマに沿った構造化JSONを構築"""
        pace = self.compute_pace()
        sectors = self.compute_sectors()
        speed = self.compute_speed()
        stints = self.compute_stints()
        degradation = self.compute_degradation()
        per_lap = self.build_per_lap_data()

        return {
            'meta': {
                'year': self.gp.year,
                'round': self.gp.round_number,
                'gp_name': self.gp.gp_name,
                'driver1': self.drv1,
                'driver2': self.drv2,
                'team1': self.team1,
                'team2': self.team2,
                'total_laps': self.gp.total_laps,
                'vsc_periods': self.gp.vsc_periods,
                'sc_periods': self.gp.sc_periods,
            },
            'race_result': {
                self.drv1: {
                    'grid': self.gp.drv_grid.get(self.drv1, 0),
                    'finish': self.gp.drv_pos.get(self.drv1, 0),
                    'status': self.gp.drv_status.get(self.drv1, ''),
                    'pit_laps': self.gp.pit_laps.get(self.drv1, []),
                },
                self.drv2: {
                    'grid': self.gp.drv_grid.get(self.drv2, 0),
                    'finish': self.gp.drv_pos.get(self.drv2, 0),
                    'status': self.gp.drv_status.get(self.drv2, ''),
                    'pit_laps': self.gp.pit_laps.get(self.drv2, []),
                },
            },
            'pace': pace,
            'sectors': sectors,
            'speed': speed,
            'stints': stints,
            'degradation': degradation,
            'per_lap': per_lap,
            'charts': [
                'chart_laptime_delta.png',
                'chart_speed_boxplot.png',
                'chart_sector_compare.png',
                'chart_sector_table.png',
            ],
            'seo': {
                'title': f'{self.drv1} vs {self.drv2} Race Pace — {self.gp.year} {self.gp.gp_name} GP',
                'title_ja': f'{self.drv1} vs {self.drv2} レースペース比較 — {self.gp.year} {self.gp.gp_name}GP',
                'description': self._build_description(pace),
                'keywords': [
                    self.drv1, self.drv2, self.gp.gp_name, 'F1', str(self.gp.year),
                    'race pace', 'comparison', self.team1, self.team2,
                ],
            },
        }

    def _build_description(self, pace):
        delta = pace.get('delta_median_sec')
        faster = pace.get('faster', '')
        if delta is not None:
            return (f'{self.gp.year} {self.gp.gp_name}GP: {faster}が'
                    f'{abs(delta):.3f}秒/ラップ速いペース。'
                    f'セクター・スピード・デグラデーションの詳細比較。')
        return f'{self.gp.year} {self.gp.gp_name}GP: {self.drv1} vs {self.drv2} レースペース比較。'

    # --- チャート生成 ---

    def _setup_ax(self, ax, title='', xlabel='', ylabel=''):
        ax.set_facecolor(LT['bg'])
        ax.set_title(title, fontsize=LT['title_size'], color=LT['text'],
                     fontweight='bold', pad=12)
        ax.set_xlabel(xlabel, fontsize=LT['label_size'], color=LT['axis'])
        ax.set_ylabel(ylabel, fontsize=LT['label_size'], color=LT['axis'])
        ax.tick_params(colors=LT['axis'], labelsize=LT['tick_size'])
        ax.grid(True, which='major', color=LT['grid_maj'], linewidth=0.5, alpha=0.7)
        ax.grid(True, which='minor', color=LT['grid_min'], linewidth=0.3, alpha=0.5)
        for spine in ax.spines.values():
            spine.set_color(LT['spine'])

    def _add_neutralization(self, ax):
        """SC/VSC期間を背景に描画"""
        for start, end in self.gp.vsc_periods:
            ax.axvspan(start - 0.5, end + 0.5, color=LT['sc'], alpha=LT['sc_alpha'])
        for start, end in self.gp.sc_periods:
            ax.axvspan(start - 0.5, end + 0.5, color='#FF6B35', alpha=LT['sc_alpha'])

    def _save(self, fig, filename):
        path = self.out_dir / filename
        fig.savefig(path, dpi=180, bbox_inches='tight', facecolor=LT['bg'])
        plt.close(fig)

    def generate_chart_laptime_delta(self):
        """Chart 1: ラップタイム + デルタ + スピードトラップ"""
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(16, 14), facecolor=LT['bg'])

        # --- ax1: ラップタイム ---
        self._setup_ax(ax1, title=f'{self.drv1} vs {self.drv2} — ラップタイム推移',
                       ylabel='ラップタイム（秒）')
        self._add_neutralization(ax1)

        for drv, laps_df, color in [(self.drv1, self.laps1, self.color1),
                                     (self.drv2, self.laps2, self.color2)]:
            valid = laps_df.dropna(subset=['LapTime_sec'])
            valid = valid[valid['LapTime_sec'] < valid['LapTime_sec'].quantile(0.98) * 1.15]
            for stint in sorted(valid['Stint'].dropna().unique()):
                s = valid[valid['Stint'] == stint].sort_values('LapNumber')
                ax1.plot(s['LapNumber'], s['LapTime_sec'], color=color,
                         linewidth=1.8, alpha=0.85, zorder=2)
                # タイヤカラーマーカー
                compound = s['Compound'].mode()
                compound = compound.iloc[0] if not compound.empty else 'UNKNOWN'
                mc = TYRE_COLORS.get(compound, '#999999')
                ax1.scatter(s['LapNumber'], s['LapTime_sec'], color=mc,
                            s=15, zorder=3, edgecolors=color, linewidth=0.5)

            # ピットマーカー
            for pit_lap in self.gp.pit_laps.get(drv, []):
                ax1.axvline(x=pit_lap, color=color, linewidth=0.8, alpha=0.4, linestyle='--')

        ax1.legend([self.drv1, self.drv2], fontsize=11, loc='upper right')
        ax1.xaxis.set_major_locator(MultipleLocator(5))
        ax1.xaxis.set_minor_locator(MultipleLocator(1))

        # --- ax2: デルタ ---
        self._setup_ax(ax2, ylabel=f'デルタ（秒）— 負={self.drv1}が速い')
        self._add_neutralization(ax2)

        common_laps = sorted(set(self.clean1['LapNumber']) & set(self.clean2['LapNumber']))
        deltas = []
        for lap in common_laps:
            t1 = self.clean1[self.clean1['LapNumber'] == lap]['LapTime_sec'].values
            t2 = self.clean2[self.clean2['LapNumber'] == lap]['LapTime_sec'].values
            if len(t1) > 0 and len(t2) > 0:
                deltas.append((lap, t1[0] - t2[0]))

        if deltas:
            laps_d, vals_d = zip(*deltas)
            colors_d = [self.color1 if v < 0 else self.color2 for v in vals_d]
            ax2.bar(laps_d, vals_d, color=colors_d, alpha=0.7, width=0.8)
            ax2.axhline(y=0, color=LT['text'], linewidth=0.5)

        ax2.xaxis.set_major_locator(MultipleLocator(5))
        ax2.xaxis.set_minor_locator(MultipleLocator(1))

        # --- ax3: スピードトラップ ---
        self._setup_ax(ax3, xlabel='ラップ番号', ylabel='スピードトラップ（km/h）')
        self._add_neutralization(ax3)

        for drv, laps_df, color in [(self.drv1, self.laps1, self.color1),
                                     (self.drv2, self.laps2, self.color2)]:
            valid = laps_df.dropna(subset=['SpeedST'])
            for stint in sorted(valid['Stint'].dropna().unique()):
                s = valid[valid['Stint'] == stint].sort_values('LapNumber')
                ax3.plot(s['LapNumber'], s['SpeedST'], color=color,
                         linewidth=1.5, alpha=0.8)
                ax3.scatter(s['LapNumber'], s['SpeedST'], color=color,
                            s=12, alpha=0.6)

        ax3.xaxis.set_major_locator(MultipleLocator(5))
        ax3.xaxis.set_minor_locator(MultipleLocator(1))

        fig.tight_layout()
        self._save(fig, 'chart_laptime_delta.png')

    def generate_chart_speed_boxplot(self):
        """Chart 2: スピード分布ボックスプロット"""
        fig, ax = plt.subplots(figsize=(14, 7), facecolor=LT['bg'])
        self._setup_ax(ax, title=f'{self.drv1} vs {self.drv2} — スピード分布',
                       ylabel='速度（km/h）')

        positions = []
        box_data = []
        box_colors = []
        x_labels = []

        for i, (col, label) in enumerate(zip(SPEED_COLS, SPEED_LABELS)):
            c1 = self.clean1[col].dropna().values
            c2 = self.clean2[col].dropna().values

            if len(c1) > 0:
                box_data.append(c1)
                positions.append(i * 3)
                box_colors.append(self.color1)
            if len(c2) > 0:
                box_data.append(c2)
                positions.append(i * 3 + 1)
                box_colors.append(self.color2)

            x_labels.append((i * 3 + 0.5, label))

        bp = ax.boxplot(box_data, positions=positions, patch_artist=True,
                        widths=0.7, showfliers=False,
                        medianprops=dict(color=LT['text'], linewidth=2),
                        whiskerprops=dict(color=LT['axis']),
                        capprops=dict(color=LT['axis']))

        for patch, color in zip(bp['boxes'], box_colors):
            patch.set_facecolor(matplotlib.colors.to_rgba(color, 0.4))
            patch.set_edgecolor(color)
            patch.set_linewidth(1.5)

        ax.set_xticks([pos for pos, _ in x_labels])
        ax.set_xticklabels([label for _, label in x_labels], fontsize=12)

        # 凡例
        from matplotlib.patches import Patch
        ax.legend(handles=[
            Patch(facecolor=matplotlib.colors.to_rgba(self.color1, 0.4),
                  edgecolor=self.color1, label=self.drv1),
            Patch(facecolor=matplotlib.colors.to_rgba(self.color2, 0.4),
                  edgecolor=self.color2, label=self.drv2),
        ], fontsize=12, loc='upper right')

        fig.tight_layout()
        self._save(fig, 'chart_speed_boxplot.png')

    def generate_chart_sector_compare(self):
        """Chart 3: セクター比較（3セクター × 2パネル）"""
        fig, axes = plt.subplots(6, 1, figsize=(16, 20), facecolor=LT['bg'])

        sector_cols = [('Sector1Time_sec', 'S1'), ('Sector2Time_sec', 'S2'),
                       ('Sector3Time_sec', 'S3')]

        for s_idx, (col, sec_label) in enumerate(sector_cols):
            ax_time = axes[s_idx * 2]
            ax_delta = axes[s_idx * 2 + 1]

            # セクタータイム
            self._setup_ax(ax_time, title=f'{sec_label} タイム',
                           ylabel='秒')
            self._add_neutralization(ax_time)

            for drv, clean_df, color in [(self.drv1, self.clean1, self.color1),
                                          (self.drv2, self.clean2, self.color2)]:
                valid = clean_df.dropna(subset=[col])
                for stint in sorted(valid['Stint'].dropna().unique()):
                    s = valid[valid['Stint'] == stint].sort_values('LapNumber')
                    ax_time.plot(s['LapNumber'], s[col], color=color,
                                linewidth=1.5, alpha=0.8)
                    ax_time.scatter(s['LapNumber'], s[col], color=color,
                                   s=10, alpha=0.6)

            ax_time.xaxis.set_major_locator(MultipleLocator(5))

            # セクターデルタ
            self._setup_ax(ax_delta, ylabel=f'デルタ（秒）— 負={self.drv1}が速い')
            self._add_neutralization(ax_delta)

            common = sorted(set(self.clean1['LapNumber']) & set(self.clean2['LapNumber']))
            for lap in common:
                v1 = self.clean1[self.clean1['LapNumber'] == lap][col].values
                v2 = self.clean2[self.clean2['LapNumber'] == lap][col].values
                if len(v1) > 0 and len(v2) > 0 and not np.isnan(v1[0]) and not np.isnan(v2[0]):
                    d = v1[0] - v2[0]
                    c = self.color1 if d < 0 else self.color2
                    ax_delta.bar(lap, d, color=c, alpha=0.6, width=0.8)

            ax_delta.axhline(y=0, color=LT['text'], linewidth=0.5)
            ax_delta.xaxis.set_major_locator(MultipleLocator(5))

        axes[-1].set_xlabel('ラップ番号', fontsize=LT['label_size'], color=LT['axis'])
        fig.tight_layout()
        self._save(fig, 'chart_sector_compare.png')

    def generate_chart_sector_table(self):
        """Chart 4: セクターサマリーテーブル"""
        sectors = self.compute_sectors()

        fig, ax = plt.subplots(figsize=(12, 4), facecolor=LT['bg'])
        ax.set_facecolor(LT['bg'])
        ax.axis('off')

        col_labels = ['セクター', f'{self.drv1} 平均', f'{self.drv2} 平均',
                      '差（秒）', f'{self.drv1} 勝ち', f'{self.drv2} 勝ち', '共通ラップ']

        cell_text = []
        cell_colors = []
        for sec_name in ['S1', 'S2', 'S3']:
            s = sectors[sec_name]
            avg1 = s.get(f'{self.drv1}_avg')
            avg2 = s.get(f'{self.drv2}_avg')
            delta = s.get('delta_sec')
            w1 = s.get(f'{self.drv1}_wins', 0)
            w2 = s.get(f'{self.drv2}_wins', 0)
            common = s.get('common_laps', 0)

            # デルタの色
            if delta is not None:
                if delta < -0.01:
                    delta_color = '#E8F5E9'  # drv1が速い=緑
                elif delta > 0.01:
                    delta_color = '#FFEBEE'  # drv2が速い=赤
                else:
                    delta_color = LT['bg']
            else:
                delta_color = LT['bg']

            cell_text.append([
                sec_name,
                f'{avg1:.3f}' if avg1 else '-',
                f'{avg2:.3f}' if avg2 else '-',
                f'{delta:+.3f}' if delta else '-',
                str(w1), str(w2), str(common),
            ])
            cell_colors.append([
                LT['bg'], LT['bg'], LT['bg'],
                delta_color, LT['bg'], LT['bg'], LT['bg'],
            ])

        table = ax.table(cellText=cell_text, colLabels=col_labels,
                         cellLoc='center', loc='center',
                         cellColours=cell_colors)
        table.auto_set_font_size(False)
        table.set_fontsize(12)
        table.scale(1.0, 2.0)

        # ヘッダースタイル
        for j in range(len(col_labels)):
            cell = table[0, j]
            cell.set_facecolor('#2C3E50')
            cell.set_text_props(color='white', fontweight='bold', fontsize=11)

        ax.set_title(f'{self.drv1} vs {self.drv2} — セクターサマリー',
                     fontsize=LT['title_size'], color=LT['text'],
                     fontweight='bold', pad=15)

        fig.tight_layout()
        self._save(fig, 'chart_sector_table.png')

    # --- メイン実行 ---

    def run(self, generate_png=False):
        """全分析を実行し、JSONを出力（--png指定時はPNGも生成）"""
        print(f'  {self.drv1} vs {self.drv2} ...')

        # チャート生成（オプション）
        if generate_png:
            self.generate_chart_laptime_delta()
            self.generate_chart_speed_boxplot()
            self.generate_chart_sector_compare()
            self.generate_chart_sector_table()

        # JSON出力
        analysis = self.build_json()
        json_path = self.out_dir / 'analysis.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2)

        return analysis


# ============================================================
# バッチ実行
# ============================================================
def run_batch(year, gp_name, round_number, pairs):
    """複数ペアのH2H分析をバッチ実行"""
    print('=' * 60)
    print(f'{year} R{round_number:02d} {gp_name} — H2Hレースペース比較エンジン')
    print('=' * 60)

    gp = GPData(year, gp_name, round_number)
    print(f'レース: {gp.total_laps}周')
    print(f'VSC: {gp.vsc_periods}, SC: {gp.sc_periods}')
    print(f'有効ドライバー: {len(gp.valid_drivers)}名')
    print(f'生成ペア数: {len(pairs)}')
    print()

    results = []
    for drv1, drv2 in pairs:
        if drv1 not in gp.drv_team or drv2 not in gp.drv_team:
            print(f'  スキップ: {drv1} vs {drv2}（ドライバー不在）')
            continue
        h2h = H2HAnalysis(gp, drv1, drv2)
        analysis = h2h.run()
        results.append(analysis)

    # インデックスJSON出力
    index = {
        'meta': {
            'year': year,
            'round': round_number,
            'gp_name': gp_name,
            'total_pairs': len(results),
            'total_laps': gp.total_laps,
        },
        'pairs': [
            {
                'driver1': r['meta']['driver1'],
                'driver2': r['meta']['driver2'],
                'team1': r['meta']['team1'],
                'team2': r['meta']['team2'],
                'delta_median_sec': r['pace'].get('delta_median_sec'),
                'faster': r['pace'].get('faster'),
                'path': f"h2h/{r['meta']['driver1']}_vs_{r['meta']['driver2']}/",
            }
            for r in results
        ],
    }

    index_dir = Path(f'./data/{year}_R{round_number:02d}_{gp_name}/h2h')
    index_dir.mkdir(parents=True, exist_ok=True)
    with open(index_dir / 'index.json', 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print()
    print(f'完了: {len(results)}ペア分のJSON+PNGを出力')
    print(f'インデックス: {index_dir / "index.json"}')
    return results


# ============================================================
# CLI
# ============================================================
if __name__ == '__main__':
    if len(sys.argv) < 4:
        print('使い方:')
        print('  python h2h_engine.py YEAR GP_NAME ROUND [DRV1 DRV2]')
        print('  python h2h_engine.py YEAR GP_NAME ROUND --all')
        print('  python h2h_engine.py YEAR GP_NAME ROUND --teammates')
        print('  python h2h_engine.py YEAR GP_NAME ROUND --top10')
        print()
        print('例:')
        print('  python h2h_engine.py 2026 Australia 1 RUS LEC')
        print('  python h2h_engine.py 2026 China 2 --teammates')
        print('  python h2h_engine.py 2026 Australia 1 --all')
        sys.exit(1)

    year = int(sys.argv[1])
    gp_name = sys.argv[2]
    round_num = int(sys.argv[3])

    if len(sys.argv) == 6:
        # 単一ペア
        drv1, drv2 = sys.argv[4].upper(), sys.argv[5].upper()
        pairs = [(drv1, drv2)]
    elif len(sys.argv) == 5:
        mode = sys.argv[4]
        gp = GPData(year, gp_name, round_num)

        if mode == '--all':
            pairs = gp.get_all_pairs()
        elif mode == '--teammates':
            pairs = gp.get_teammates()
        elif mode == '--top10':
            # トップ10の全ペア
            from itertools import combinations
            top10 = sorted(gp.valid_drivers,
                          key=lambda d: gp.drv_pos.get(d, 99))[:10]
            pairs = list(combinations(top10, 2))
        else:
            print(f'不明なモード: {mode}')
            sys.exit(1)
    else:
        print('引数が不足しています。')
        sys.exit(1)

    run_batch(year, gp_name, round_num, pairs)
