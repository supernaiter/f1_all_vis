"""
============================================================
2026 R01 Australia × R02 China — クロスGPレースペース比較
============================================================
両レースのレースペースを正規化し、チーム間のマシン能力差の変化を可視化。

出力:
  data/cross_gp_analysis/png/  — 6枚のチャート
  data/cross_gp_analysis/csv/  — 3件のデータ
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
from matplotlib.patches import FancyArrowPatch
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# GP設定
# ============================================================
GP_DATA = {
    'R01': {
        'name': 'オーストラリア',
        'name_en': 'Australia',
        'round': 1,
        'total_laps': 58,
        'laps_csv': 'data/2026_R01_Australia/export/race_laps.csv',
        'results_csv': 'data/2026_R01_Australia/export/race_results.csv',
        'vsc_periods': [(12, 14), (18, 20), (34, 34)],
        'sc_periods': [],
    },
    'R02': {
        'name': '中国',
        'name_en': 'China',
        'round': 2,
        'total_laps': 56,
        'laps_csv': 'data/2026_R02_China/export/race_laps.csv',
        'results_csv': 'data/2026_R02_China/export/race_results.csv',
        'vsc_periods': [],
        'sc_periods': [(10, 13)],
    },
}

# 出力ディレクトリ
OUT_DIR = Path('./data/cross_gp_analysis')
PNG_DIR = OUT_DIR / 'png'
CSV_DIR = OUT_DIR / 'csv'
PNG_DIR.mkdir(parents=True, exist_ok=True)
CSV_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# ライトテーマ
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
    'marker_s':   80,
}

# チームカラー（ライト背景用）
TEAM_COLORS = {
    'McLaren': '#E07800', 'Ferrari': '#DC0000', 'Red Bull Racing': '#2B5DAB',
    'Mercedes': '#00B89F', 'Aston Martin': '#1B7A5A', 'Williams': '#3BA3E0',
    'Racing Bulls': '#4A72CC', 'Alpine': '#0078AA', 'Haas F1 Team': '#7A7A7A',
    'Audi': '#3AAA3A', 'Cadillac': '#888888',
}

# チーム略称
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

# 日本語フォント
for font_name in ['Noto Sans JP', 'Yu Gothic', 'Meiryo', 'MS Gothic',
                   'Hiragino Sans', 'Hiragino Kaku Gothic Pro']:
    try:
        matplotlib.font_manager.FontProperties(family=font_name)
        plt.rcParams['font.family'] = font_name
        break
    except Exception:
        continue

# ============================================================
# データ読み込み
# ============================================================
def load_race_data(gp_key):
    """CSVからレースデータを読み込む"""
    gp = GP_DATA[gp_key]
    laps = pd.read_csv(gp['laps_csv'])
    results = pd.read_csv(gp['results_csv'])
    return laps, results


# ============================================================
# クリーンラップフィルタ
# ============================================================
def get_neutralized_laps(gp_key):
    """SC/VSC期間 ± 1周バッファのラップ番号セットを返す"""
    gp = GP_DATA[gp_key]
    exclude = set()
    for start, end in gp['vsc_periods'] + gp['sc_periods']:
        for lap in range(max(1, start - 1), end + 2):
            exclude.add(lap)
    return exclude


def get_clean_laps(laps_df, gp_key):
    """クリーンラップのみに絞り込む"""
    neutralized = get_neutralized_laps(gp_key)

    df = laps_df.copy()
    # LapTimeがNaNの行を除外
    df = df.dropna(subset=['LapTime_sec'])

    # Lap 1除外
    df = df[df['LapNumber'] > 1]

    # ピットイン/アウトラップ除外
    df = df[df['PitInTime_sec'].isna() & df['PitOutTime_sec'].isna()]

    # TrackStatus: '1'=グリーンのみ（文字列と数値の両方に対応）
    df = df[df['TrackStatus'].astype(str) == '1']

    # SC/VSC期間±バッファ除外
    df = df[~df['LapNumber'].isin(neutralized)]

    # 107%フィルタ（セッション最速基準）
    fastest = df['LapTime_sec'].min()
    df = df[df['LapTime_sec'] <= fastest * 1.07]

    return df


# ============================================================
# 正規化・集計
# ============================================================
def compute_driver_pace(clean_df):
    """ドライバー別の中央値ペースを算出"""
    driver_pace = clean_df.groupby(['Driver', 'Team']).agg(
        MedianPace=('LapTime_sec', 'median'),
        MeanPace=('LapTime_sec', 'mean'),
        CleanLaps=('LapTime_sec', 'count'),
        StdPace=('LapTime_sec', 'std'),
    ).reset_index()
    return driver_pace


def normalize_pace(driver_pace_df):
    """フィールド中央値比率で正規化（%）"""
    # セッション基準 = 全ドライバーの中央値ペースの中央値
    session_ref = driver_pace_df['MedianPace'].median()
    driver_pace_df = driver_pace_df.copy()
    driver_pace_df['NormPace_pct'] = (driver_pace_df['MedianPace'] / session_ref) * 100
    driver_pace_df['SessionRef'] = session_ref
    return driver_pace_df


def compute_team_pace(driver_pace_df):
    """チーム別ペースを算出（ドライバー中央値の平均）"""
    # 最低10周以上のクリーンラップを持つドライバーのみ
    valid = driver_pace_df[driver_pace_df['CleanLaps'] >= 10].copy()

    team_pace = valid.groupby('Team').agg(
        TeamNormPace=('NormPace_pct', 'mean'),
        DriverCount=('Driver', 'count'),
        Drivers=('Driver', lambda x: ', '.join(sorted(x))),
        TeamMedianSec=('MedianPace', 'mean'),
    ).reset_index()

    # ペース順にランク付け
    team_pace = team_pace.sort_values('TeamNormPace').reset_index(drop=True)
    team_pace['Rank'] = range(1, len(team_pace) + 1)

    return team_pace


# ============================================================
# デグラデーション分析
# ============================================================
def compute_deg_rates(clean_df, gp_key):
    """スティント別のデグラデーションレートを線形回帰で算出"""
    results = []

    for (drv, team, stint, compound), grp in clean_df.groupby(
            ['Driver', 'Team', 'Stint', 'Compound']):
        grp = grp.sort_values('TyreLife')
        if len(grp) < 5:
            continue

        x = grp['TyreLife'].values
        y = grp['LapTime_sec'].values

        # 線形回帰
        coeffs = np.polyfit(x, y, 1)
        slope = coeffs[0]  # 秒/ラップ

        results.append({
            'GP': gp_key,
            'Driver': drv,
            'Team': team,
            'Stint': stint,
            'Compound': compound,
            'DegRate_sec_per_lap': slope,
            'StintLaps': len(grp),
            'MeanPace': y.mean(),
        })

    return pd.DataFrame(results)


# ============================================================
# 共通描画ヘルパー
# ============================================================
def setup_ax(ax, title='', xlabel='', ylabel=''):
    """軸の共通設定"""
    ax.set_facecolor(LT['bg'])
    ax.set_title(title, fontsize=LT['title_size'], color=LT['text'],
                 fontweight='bold', pad=15)
    ax.set_xlabel(xlabel, fontsize=LT['label_size'], color=LT['axis'])
    ax.set_ylabel(ylabel, fontsize=LT['label_size'], color=LT['axis'])
    ax.tick_params(colors=LT['axis'], labelsize=LT['tick_size'])
    ax.grid(True, which='major', color=LT['grid_maj'], linewidth=0.5, alpha=0.7)
    ax.grid(True, which='minor', color=LT['grid_min'], linewidth=0.3, alpha=0.5)
    for spine in ax.spines.values():
        spine.set_color(LT['spine'])


def save_fig(fig, filename):
    """チャートを保存"""
    path = PNG_DIR / filename
    fig.savefig(path, dpi=180, bbox_inches='tight', facecolor=LT['bg'])
    plt.close(fig)
    print(f'  保存: {path}')


# ============================================================
# メイン処理
# ============================================================
print('=' * 60)
print('クロスGPレースペース比較: R01 Australia × R02 China')
print('=' * 60)

# --- データ読み込み & クリーンラップ抽出 ---
all_driver_pace = {}
all_team_pace = {}
all_clean_laps = {}
all_results = {}

for gp_key in ['R01', 'R02']:
    gp = GP_DATA[gp_key]
    print(f'\n--- {gp_key} {gp["name"]} ---')

    laps, results = load_race_data(gp_key)
    all_results[gp_key] = results
    print(f'  全ラップ: {len(laps)}')

    clean = get_clean_laps(laps, gp_key)
    all_clean_laps[gp_key] = clean
    print(f'  クリーンラップ: {len(clean)}')

    drv_pace = compute_driver_pace(clean)
    drv_pace = normalize_pace(drv_pace)
    drv_pace['GP'] = gp_key
    all_driver_pace[gp_key] = drv_pace
    print(f'  ドライバー数: {len(drv_pace)}')

    team_pace = compute_team_pace(drv_pace)
    team_pace['GP'] = gp_key
    all_team_pace[gp_key] = team_pace
    print(f'  チーム数: {len(team_pace)}')

# --- 統合データフレーム ---
df_drv = pd.concat([all_driver_pace['R01'], all_driver_pace['R02']], ignore_index=True)
df_team = pd.concat([all_team_pace['R01'], all_team_pace['R02']], ignore_index=True)

# リーダー（各GPの最速チーム）からのギャップに変換
for gp_key in ['R01', 'R02']:
    mask = df_team['GP'] == gp_key
    leader_pace = df_team.loc[mask, 'TeamNormPace'].min()
    df_team.loc[mask, 'GapToLeader_pct'] = df_team.loc[mask, 'TeamNormPace'] - leader_pace

    mask_drv = df_drv['GP'] == gp_key
    leader_drv = df_drv.loc[mask_drv, 'NormPace_pct'].min()
    df_drv.loc[mask_drv, 'GapToLeader_pct'] = df_drv.loc[mask_drv, 'NormPace_pct'] - leader_drv

# ============================================================
# Chart 1: チームペース順位変動（バンプチャート）
# ============================================================
print('\n--- Chart 1: チームペース順位変動 ---')

# 両GPに存在するチームのみ
teams_r01 = set(all_team_pace['R01']['Team'])
teams_r02 = set(all_team_pace['R02']['Team'])
common_teams = teams_r01 & teams_r02

fig, ax = plt.subplots(figsize=(14, 10), facecolor=LT['bg'])
setup_ax(ax, title='チームレースペース順位変動 — R01 vs R02',
         xlabel='', ylabel='ペース順位（1 = 最速）')

x_positions = [0.3, 0.7]  # R01, R02のX座標

for team in common_teams:
    r01 = all_team_pace['R01'][all_team_pace['R01']['Team'] == team]
    r02 = all_team_pace['R02'][all_team_pace['R02']['Team'] == team]
    if r01.empty or r02.empty:
        continue

    rank1 = r01['Rank'].values[0]
    rank2 = r02['Rank'].values[0]
    color = TEAM_COLORS.get(team, '#999999')
    short = TEAM_SHORT.get(team, team[:3])

    # 接続線
    ax.plot(x_positions, [rank1, rank2], color=color, linewidth=3.5,
            alpha=0.85, zorder=2, solid_capstyle='round')

    # マーカー
    ax.scatter(x_positions[0], rank1, color=color, s=200, zorder=3, edgecolors='white', linewidth=1.5)
    ax.scatter(x_positions[1], rank2, color=color, s=200, zorder=3, edgecolors='white', linewidth=1.5)

    # ラベル（左: R01、右: R02）
    gap1 = all_team_pace['R01'][all_team_pace['R01']['Team'] == team]['TeamNormPace'].values[0]
    gap2 = all_team_pace['R02'][all_team_pace['R02']['Team'] == team]['TeamNormPace'].values[0]

    ax.text(x_positions[0] - 0.04, rank1, f'{short}  {gap1:.2f}%',
            ha='right', va='center', fontsize=11, color=color, fontweight='bold')
    ax.text(x_positions[1] + 0.04, rank2, f'{gap2:.2f}%  {short}',
            ha='left', va='center', fontsize=11, color=color, fontweight='bold')

    # 順位変動の矢印注記
    delta_rank = rank1 - rank2  # 正=改善（順位が上がった）
    if delta_rank > 0:
        arrow_text = f'+{delta_rank}'
        arrow_color = '#228B22'
    elif delta_rank < 0:
        arrow_text = f'{delta_rank}'
        arrow_color = '#DC143C'
    else:
        arrow_text = '→'
        arrow_color = LT['axis']

    ax.text(0.5, (rank1 + rank2) / 2, arrow_text,
            ha='center', va='center', fontsize=10, color=arrow_color,
            fontweight='bold', alpha=0.7,
            bbox=dict(boxstyle='round,pad=0.2', facecolor=LT['bg'],
                      edgecolor=arrow_color, alpha=0.5))

# 軸設定
max_rank = max(len(teams_r01), len(teams_r02))
ax.set_ylim(max_rank + 0.5, 0.5)
ax.set_xlim(0.05, 0.95)
ax.set_xticks(x_positions)
ax.set_xticklabels(['R01\nオーストラリア', 'R02\n中国'], fontsize=14, fontweight='bold')
ax.yaxis.set_major_locator(MultipleLocator(1))
ax.set_yticks(range(1, max_rank + 1))

# 注記
ax.text(0.5, max_rank + 0.3,
        '正規化ペース% = ドライバー中央値ラップタイム ÷ フィールド中央値 × 100',
        ha='center', va='top', fontsize=9, color=LT['axis'], style='italic')

save_fig(fig, 'chart1_team_bump.png')


# ============================================================
# Chart 2: チーム別ペース差比較（グループバーチャート）
# ============================================================
print('\n--- Chart 2: チーム別ペース差比較 ---')

# R02の順位でソート
r02_order = all_team_pace['R02'].sort_values('Rank')['Team'].tolist()
# 共通チームのみ、R02順にソート
plot_teams = [t for t in r02_order if t in common_teams]

fig, ax = plt.subplots(figsize=(18, 10), facecolor=LT['bg'])
setup_ax(ax, title='チーム別レースペースギャップ比較 — R01 vs R02',
         xlabel='', ylabel='リーダーとのギャップ（%）')

bar_width = 0.35
x = np.arange(len(plot_teams))

gaps_r01 = []
gaps_r02 = []
for team in plot_teams:
    r01 = df_team[(df_team['GP'] == 'R01') & (df_team['Team'] == team)]
    r02 = df_team[(df_team['GP'] == 'R02') & (df_team['Team'] == team)]
    gaps_r01.append(r01['GapToLeader_pct'].values[0] if not r01.empty else np.nan)
    gaps_r02.append(r02['GapToLeader_pct'].values[0] if not r02.empty else np.nan)

gaps_r01 = np.array(gaps_r01)
gaps_r02 = np.array(gaps_r02)

# バーの色をチームカラーに
colors = [TEAM_COLORS.get(t, '#999999') for t in plot_teams]
colors_light = [matplotlib.colors.to_rgba(c, 0.5) for c in colors]  # R01: 薄め
colors_dark = [matplotlib.colors.to_rgba(c, 0.9) for c in colors]   # R02: 濃い

bars1 = ax.bar(x - bar_width/2, gaps_r01, bar_width, color=colors_light,
               edgecolor=[c for c in colors], linewidth=1.0, label='R01 オーストラリア')
bars2 = ax.bar(x + bar_width/2, gaps_r02, bar_width, color=colors_dark,
               edgecolor=[c for c in colors], linewidth=1.0, label='R02 中国')

# デルタ注記
for i, team in enumerate(plot_teams):
    if np.isnan(gaps_r01[i]) or np.isnan(gaps_r02[i]):
        continue
    delta = gaps_r02[i] - gaps_r01[i]
    color = '#228B22' if delta < 0 else '#DC143C' if delta > 0 else LT['axis']
    sign = '' if delta < 0 else '+'
    y_pos = max(gaps_r01[i], gaps_r02[i]) + 0.05
    ax.text(x[i], y_pos, f'{sign}{delta:.2f}%',
            ha='center', va='bottom', fontsize=9, color=color, fontweight='bold')

# X軸ラベル
labels = [TEAM_SHORT.get(t, t[:3]) for t in plot_teams]
ax.set_xticks(x)
ax.set_xticklabels(labels, fontsize=12, fontweight='bold')
ax.yaxis.set_minor_locator(MultipleLocator(0.1))

# 凡例
ax.legend(fontsize=12, loc='upper left', framealpha=0.9)

# 0%ライン
ax.axhline(y=0, color=LT['text'], linewidth=0.8, alpha=0.3)

save_fig(fig, 'chart2_team_pace_bars.png')


# ============================================================
# Chart 3: ドライバー別ペースドットプロット
# ============================================================
print('\n--- Chart 3: ドライバー別ペースドットプロット ---')

# 両GPで10周以上のクリーンラップを持つドライバー
drv_r01 = set(all_driver_pace['R01'][all_driver_pace['R01']['CleanLaps'] >= 10]['Driver'])
drv_r02 = set(all_driver_pace['R02'][all_driver_pace['R02']['CleanLaps'] >= 10]['Driver'])
common_drivers = sorted(drv_r01 & drv_r02)

# チーム順にソート（R02のチームペース順）
drv_team_map = dict(zip(df_drv['Driver'], df_drv['Team']))
team_rank_r02 = dict(zip(all_team_pace['R02']['Team'], all_team_pace['R02']['Rank']))
common_drivers.sort(key=lambda d: (team_rank_r02.get(drv_team_map.get(d, ''), 99), d))

fig, ax = plt.subplots(figsize=(18, 9), facecolor=LT['bg'])
setup_ax(ax, title='ドライバー別正規化ペース変化 — R01 vs R02',
         xlabel='', ylabel='リーダーとのギャップ（%）')

x_drv = np.arange(len(common_drivers))

for i, drv in enumerate(common_drivers):
    r01 = df_drv[(df_drv['GP'] == 'R01') & (df_drv['Driver'] == drv)]
    r02 = df_drv[(df_drv['GP'] == 'R02') & (df_drv['Driver'] == drv)]
    if r01.empty or r02.empty:
        continue

    gap1 = r01['GapToLeader_pct'].values[0]
    gap2 = r02['GapToLeader_pct'].values[0]
    team = r01['Team'].values[0]
    color = TEAM_COLORS.get(team, '#999999')

    # 接続線
    ax.plot([i, i], [gap1, gap2], color=color, linewidth=1.5, alpha=0.5, zorder=1)

    # R01: ○
    ax.scatter(i, gap1, marker='o', s=LT['marker_s'], color=color,
               edgecolors='white', linewidth=1.0, zorder=3, alpha=0.7)
    # R02: ◇
    ax.scatter(i, gap2, marker='D', s=LT['marker_s'] * 0.8, color=color,
               edgecolors='white', linewidth=1.0, zorder=3)

ax.set_xticks(x_drv)
ax.set_xticklabels(common_drivers, fontsize=10, fontweight='bold', rotation=45, ha='right')
ax.yaxis.set_minor_locator(MultipleLocator(0.1))
ax.axhline(y=0, color=LT['text'], linewidth=0.8, alpha=0.3)

# 凡例（手動）
from matplotlib.lines import Line2D
legend_elements = [
    Line2D([0], [0], marker='o', color='w', markerfacecolor=LT['axis'],
           markersize=10, label='R01 オーストラリア'),
    Line2D([0], [0], marker='D', color='w', markerfacecolor=LT['axis'],
           markersize=9, label='R02 中国'),
]
ax.legend(handles=legend_elements, fontsize=12, loc='upper left', framealpha=0.9)

# チーム区切り線
prev_team = None
for i, drv in enumerate(common_drivers):
    team = drv_team_map.get(drv, '')
    if prev_team is not None and team != prev_team:
        ax.axvline(x=i - 0.5, color=LT['grid_maj'], linewidth=1.0, linestyle='--', alpha=0.5)
    prev_team = team

save_fig(fig, 'chart3_driver_pace_dots.png')


# ============================================================
# Chart 4: ペース一貫性（ボックスプロット）
# ============================================================
print('\n--- Chart 4: ペース一貫性 ---')

fig, axes = plt.subplots(1, 2, figsize=(20, 10), facecolor=LT['bg'], sharey=True)

for idx, gp_key in enumerate(['R01', 'R02']):
    ax = axes[idx]
    gp = GP_DATA[gp_key]
    clean = all_clean_laps[gp_key]

    # セッション基準で正規化
    session_ref = clean['LapTime_sec'].median()
    clean = clean.copy()
    clean['NormLap_pct'] = (clean['LapTime_sec'] / session_ref) * 100

    # チーム順（そのGPのチームペース順）
    team_order = all_team_pace[gp_key].sort_values('Rank')['Team'].tolist()

    box_data = []
    box_labels = []
    box_colors = []
    for team in team_order:
        team_laps = clean[clean['Team'] == team]['NormLap_pct'].dropna()
        if len(team_laps) < 5:
            continue
        box_data.append(team_laps.values)
        box_labels.append(TEAM_SHORT.get(team, team[:3]))
        box_colors.append(TEAM_COLORS.get(team, '#999999'))

    setup_ax(ax, title=f'{gp_key} {gp["name"]}',
             xlabel='', ylabel='正規化ラップタイム（%）' if idx == 0 else '')

    bp = ax.boxplot(box_data, labels=box_labels, patch_artist=True,
                    widths=0.6, showfliers=False,
                    medianprops=dict(color=LT['text'], linewidth=2),
                    whiskerprops=dict(color=LT['axis']),
                    capprops=dict(color=LT['axis']))

    for patch, color in zip(bp['boxes'], box_colors):
        patch.set_facecolor(matplotlib.colors.to_rgba(color, 0.4))
        patch.set_edgecolor(color)
        patch.set_linewidth(1.5)

    ax.tick_params(axis='x', rotation=45)
    ax.yaxis.set_minor_locator(MultipleLocator(0.1))

    # 100%ライン
    ax.axhline(y=100, color=LT['text'], linewidth=0.8, alpha=0.3, linestyle='--')

fig.suptitle('チーム別ペース一貫性（クリーンラップ分布）— R01 vs R02',
             fontsize=LT['title_size'], color=LT['text'], fontweight='bold', y=0.98)
fig.tight_layout(rect=[0, 0, 1, 0.95])

save_fig(fig, 'chart4_pace_consistency.png')


# ============================================================
# Chart 5: タイヤデグラデーション比較
# ============================================================
print('\n--- Chart 5: タイヤデグラデーション比較 ---')

# 両GPのデグレートを算出
deg_all = []
for gp_key in ['R01', 'R02']:
    deg = compute_deg_rates(all_clean_laps[gp_key], gp_key)
    deg_all.append(deg)

df_deg = pd.concat(deg_all, ignore_index=True)

# チーム別に集約（中央値）
team_deg = df_deg.groupby(['GP', 'Team', 'Compound']).agg(
    MedianDeg=('DegRate_sec_per_lap', 'median'),
    StintCount=('DegRate_sec_per_lap', 'count'),
).reset_index()

# Medium/Hardのみ対象
compounds_to_plot = ['MEDIUM', 'HARD']
team_deg = team_deg[team_deg['Compound'].isin(compounds_to_plot)]

fig, axes = plt.subplots(1, len(compounds_to_plot), figsize=(18, 10),
                          facecolor=LT['bg'], sharey=True)
if len(compounds_to_plot) == 1:
    axes = [axes]

for c_idx, compound in enumerate(compounds_to_plot):
    ax = axes[c_idx]
    cmp_data = team_deg[team_deg['Compound'] == compound]

    # 両GPにデータがあるチーム
    teams_in_compound = set()
    for gp_key in ['R01', 'R02']:
        gp_teams = set(cmp_data[cmp_data['GP'] == gp_key]['Team'])
        if not teams_in_compound:
            teams_in_compound = gp_teams
        else:
            teams_in_compound = teams_in_compound | gp_teams

    # R02チームペース順でソート
    team_order_r02 = all_team_pace['R02'].sort_values('Rank')['Team'].tolist()
    teams_sorted = [t for t in team_order_r02 if t in teams_in_compound]

    x = np.arange(len(teams_sorted))
    bar_width = 0.35

    vals_r01 = []
    vals_r02 = []
    for team in teams_sorted:
        r01_val = cmp_data[(cmp_data['GP'] == 'R01') & (cmp_data['Team'] == team)]['MedianDeg']
        r02_val = cmp_data[(cmp_data['GP'] == 'R02') & (cmp_data['Team'] == team)]['MedianDeg']
        vals_r01.append(r01_val.values[0] if len(r01_val) > 0 else np.nan)
        vals_r02.append(r02_val.values[0] if len(r02_val) > 0 else np.nan)

    vals_r01 = np.array(vals_r01)
    vals_r02 = np.array(vals_r02)

    colors = [TEAM_COLORS.get(t, '#999999') for t in teams_sorted]
    colors_light = [matplotlib.colors.to_rgba(c, 0.5) for c in colors]
    colors_dark = [matplotlib.colors.to_rgba(c, 0.9) for c in colors]

    setup_ax(ax, title=f'{compound}',
             xlabel='', ylabel='デグラデーション（秒/ラップ）' if c_idx == 0 else '')

    # NaNを0に置換してプロット（NaNのバーは表示されない）
    mask_r01 = ~np.isnan(vals_r01)
    mask_r02 = ~np.isnan(vals_r02)

    for i in range(len(teams_sorted)):
        if mask_r01[i]:
            ax.bar(x[i] - bar_width/2, vals_r01[i], bar_width,
                   color=colors_light[i], edgecolor=colors[i], linewidth=1.0)
        if mask_r02[i]:
            ax.bar(x[i] + bar_width/2, vals_r02[i], bar_width,
                   color=colors_dark[i], edgecolor=colors[i], linewidth=1.0)

    labels = [TEAM_SHORT.get(t, t[:3]) for t in teams_sorted]
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=10, fontweight='bold', rotation=45, ha='right')
    ax.yaxis.set_minor_locator(MultipleLocator(0.01))

    # 基準線
    ax.axhline(y=0.05, color='#228B22', linewidth=0.8, alpha=0.4, linestyle='--')
    ax.axhline(y=0.10, color='#DC143C', linewidth=0.8, alpha=0.4, linestyle='--')
    ax.text(len(teams_sorted) - 0.5, 0.05, '低デグ', fontsize=8, color='#228B22', va='bottom')
    ax.text(len(teams_sorted) - 0.5, 0.10, '高デグ', fontsize=8, color='#DC143C', va='bottom')

# 共通凡例
from matplotlib.patches import Patch
legend_elements = [
    Patch(facecolor=LT['grid_maj'], edgecolor=LT['axis'], alpha=0.5, label='R01 オーストラリア'),
    Patch(facecolor=LT['axis'], edgecolor=LT['axis'], alpha=0.9, label='R02 中国'),
]
fig.legend(handles=legend_elements, fontsize=12, loc='upper right',
           bbox_to_anchor=(0.98, 0.93), framealpha=0.9)

fig.suptitle('チーム別タイヤデグラデーション比較 — R01 vs R02',
             fontsize=LT['title_size'], color=LT['text'], fontweight='bold', y=0.98)
fig.tight_layout(rect=[0, 0, 1, 0.95])

save_fig(fig, 'chart5_deg_comparison.png')


# ============================================================
# Chart 6: マシン能力ギャップ サマリーテーブル
# ============================================================
print('\n--- Chart 6: マシン能力ギャップ サマリーテーブル ---')

# テーブルデータ作成
table_rows = []
for team in plot_teams:
    r01 = all_team_pace['R01'][all_team_pace['R01']['Team'] == team]
    r02 = all_team_pace['R02'][all_team_pace['R02']['Team'] == team]

    pace_r01 = r01['TeamNormPace'].values[0] if not r01.empty else np.nan
    pace_r02 = r02['TeamNormPace'].values[0] if not r02.empty else np.nan
    rank_r01 = int(r01['Rank'].values[0]) if not r01.empty else '-'
    rank_r02 = int(r02['Rank'].values[0]) if not r02.empty else '-'
    gap_r01 = r01['GapToLeader_pct'].values[0] if 'GapToLeader_pct' in df_team.columns else np.nan
    gap_r02 = r02['GapToLeader_pct'].values[0] if 'GapToLeader_pct' in df_team.columns else np.nan

    # df_teamからギャップを取得
    r01_gap_row = df_team[(df_team['GP'] == 'R01') & (df_team['Team'] == team)]
    r02_gap_row = df_team[(df_team['GP'] == 'R02') & (df_team['Team'] == team)]
    gap_r01 = r01_gap_row['GapToLeader_pct'].values[0] if not r01_gap_row.empty else np.nan
    gap_r02 = r02_gap_row['GapToLeader_pct'].values[0] if not r02_gap_row.empty else np.nan

    delta = pace_r02 - pace_r01 if not (np.isnan(pace_r01) or np.isnan(pace_r02)) else np.nan
    rank_change = (rank_r01 - rank_r02) if isinstance(rank_r01, int) and isinstance(rank_r02, int) else '-'

    drivers_r01 = r01['Drivers'].values[0] if not r01.empty else ''
    drivers_r02 = r02['Drivers'].values[0] if not r02.empty else ''

    table_rows.append({
        'Team': TEAM_SHORT.get(team, team[:3]),
        'TeamFull': team,
        'R01 Gap%': f'+{gap_r01:.2f}' if not np.isnan(gap_r01) else '-',
        'R02 Gap%': f'+{gap_r02:.2f}' if not np.isnan(gap_r02) else '-',
        'Delta': delta,
        'R01 Rank': rank_r01,
        'R02 Rank': rank_r02,
        'Rank Chg': rank_change,
        'R01 Drivers': drivers_r01,
        'R02 Drivers': drivers_r02,
    })

# matplotlibテーブル描画
fig, ax = plt.subplots(figsize=(18, 10), facecolor=LT['bg'])
ax.set_facecolor(LT['bg'])
ax.axis('off')

col_labels = ['チーム', 'R01\nGap%', 'R02\nGap%', 'Delta\n(R02-R01)', 'R01\n順位', 'R02\n順位', '順位\n変動', 'R01ドライバー', 'R02ドライバー']

cell_text = []
cell_colors = []
for row in table_rows:
    delta = row['Delta']
    if not np.isnan(delta) if isinstance(delta, float) else True:
        if isinstance(delta, float):
            delta_str = f'{delta:+.2f}%'
            if delta < -0.05:
                delta_color = '#E8F5E9'  # 薄緑（改善）
            elif delta > 0.05:
                delta_color = '#FFEBEE'  # 薄赤（悪化）
            else:
                delta_color = LT['bg']
        else:
            delta_str = '-'
            delta_color = LT['bg']
    else:
        delta_str = '-'
        delta_color = LT['bg']

    rank_chg = row['Rank Chg']
    if isinstance(rank_chg, int):
        if rank_chg > 0:
            rank_str = f'+{rank_chg}'
            rank_color = '#E8F5E9'
        elif rank_chg < 0:
            rank_str = f'{rank_chg}'
            rank_color = '#FFEBEE'
        else:
            rank_str = '→'
            rank_color = LT['bg']
    else:
        rank_str = '-'
        rank_color = LT['bg']

    cell_text.append([
        row['Team'], row['R01 Gap%'], row['R02 Gap%'],
        delta_str, str(row['R01 Rank']), str(row['R02 Rank']),
        rank_str, row['R01 Drivers'], row['R02 Drivers'],
    ])
    cell_colors.append([
        LT['bg'], LT['bg'], LT['bg'],
        delta_color, LT['bg'], LT['bg'],
        rank_color, LT['card_bg'], LT['card_bg'],
    ])

table = ax.table(cellText=cell_text, colLabels=col_labels,
                 cellLoc='center', loc='center',
                 cellColours=cell_colors)

table.auto_set_font_size(False)
table.set_fontsize(11)
table.scale(1.0, 2.0)

# ヘッダー行のスタイル
for j, label in enumerate(col_labels):
    cell = table[0, j]
    cell.set_facecolor('#2C3E50')
    cell.set_text_props(color='white', fontweight='bold', fontsize=10)

# チームカラーの帯を左端セルに
for i, row in enumerate(table_rows):
    cell = table[i + 1, 0]
    team_color = TEAM_COLORS.get(row['TeamFull'], '#999999')
    cell.set_text_props(fontweight='bold', color=team_color)

ax.set_title('マシン能力ギャップ サマリー — R01 vs R02',
             fontsize=LT['title_size'], color=LT['text'], fontweight='bold', pad=20)

# 注記
ax.text(0.5, 0.02,
        'Gap% = リーダーチームとの正規化ペース差。Delta < 0 は改善（緑）、> 0 は悪化（赤）。'
        '正規化基準 = フィールド中央値ラップタイム。',
        ha='center', va='bottom', fontsize=9, color=LT['axis'], style='italic',
        transform=ax.transAxes)

save_fig(fig, 'chart6_machine_gap_table.png')


# ============================================================
# CSV出力
# ============================================================
print('\n--- CSV出力 ---')

# チームサマリー
team_summary = pd.DataFrame(table_rows)
team_summary.to_csv(CSV_DIR / 'cross_gp_team_summary.csv', index=False, encoding='utf-8-sig')
print(f'  保存: {CSV_DIR / "cross_gp_team_summary.csv"}')

# ドライバーサマリー
drv_summary = df_drv[['GP', 'Driver', 'Team', 'MedianPace', 'NormPace_pct',
                       'GapToLeader_pct', 'CleanLaps', 'StdPace']].copy()
drv_summary = drv_summary.sort_values(['GP', 'GapToLeader_pct'])
drv_summary.to_csv(CSV_DIR / 'cross_gp_driver_summary.csv', index=False, encoding='utf-8-sig')
print(f'  保存: {CSV_DIR / "cross_gp_driver_summary.csv"}')

# デグラデーションレート
df_deg.to_csv(CSV_DIR / 'cross_gp_deg_rates.csv', index=False, encoding='utf-8-sig')
print(f'  保存: {CSV_DIR / "cross_gp_deg_rates.csv"}')

print('\n' + '=' * 60)
print('完了: 6枚のチャートと3件のCSVを出力しました。')
print(f'出力先: {OUT_DIR}')
print('=' * 60)
