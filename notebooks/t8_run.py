#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T8: R01-R03横断 チーム/ドライバーパフォーマンストレンド分析
- チーム別ペーストレンド（燃料補正済）
- ドライバー別成長率（正規化ペース）
- チーム力関係の変動
- タイヤデグレートGP間比較（HARDコンパウンド）
- 一貫性スコア（標準偏差）
- コンストラクターポイント累計推移
"""

import matplotlib
matplotlib.use('Agg')  # GUIなし環境対応
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
import pandas as pd
import os
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# パス設定
# ============================================================
BASE_DIR = '/Volumes/lyssr_workspace/2026_1_4/Motorsports-Visualised'
OUTPUT_DIR = os.path.join(BASE_DIR, 'notebooks', 'output')
DATA_DIR = os.path.join(BASE_DIR, 'data')

FUEL_PACE_CSV = os.path.join(OUTPUT_DIR, 'fuel_corrected_pace.csv')
DEG_RATES_CSV = os.path.join(OUTPUT_DIR, 'deg_rates_clean.csv')

RACE_RESULTS = {
    'R01': os.path.join(DATA_DIR, '2026_R01_Australia', 'export', 'race_results.csv'),
    'R02': os.path.join(DATA_DIR, '2026_R02_China', 'export', 'race_results.csv'),
    'R03': os.path.join(DATA_DIR, '2026_R03_Japan', 'export', 'race_results.csv'),
}

# GP表示名マッピング
GP_LABELS = {
    'R01_Australia': 'R01\nAUS',
    'R02_China':     'R02\nCHN',
    'R03_Japan':     'R03\nJPN',
}
GP_KEYS = ['R01_Australia', 'R02_China', 'R03_Japan']

# チームカラー（F1 2026）
TEAM_COLORS = {
    'McLaren':         '#F47600',
    'Ferrari':         '#ED1131',
    'Mercedes':        '#00D7B6',
    'Red Bull Racing': '#4781D7',
    'Aston Martin':    '#229971',
    'Williams':        '#1868DB',
    'Racing Bulls':    '#6C98FF',
    'Alpine':          '#00A1E8',
    'Haas F1 Team':    '#9C9FA2',
    'Audi':            '#F50537',
    'Cadillac':        '#909090',
}

# グラフスタイル
STYLE = {
    'bg_color':   '#1a1a2e',
    'text_color': '#ffffff',
    'grid_color': '#333355',
    'figsize':    (18, 14),
}

# ============================================================
# Step 1: データ読み込み
# ============================================================
print('=== T8: R01-R03横断パフォーマンストレンド分析 ===\n')
print('[1/6] データ読み込み中...')

try:
    df_pace = pd.read_csv(FUEL_PACE_CSV)
    print(f'  fuel_corrected_pace.csv: {len(df_pace)} 行')
except FileNotFoundError as e:
    print(f'  エラー: fuel_corrected_pace.csv が見つかりません: {e}')
    raise

try:
    df_deg = pd.read_csv(DEG_RATES_CSV)
    print(f'  deg_rates_clean.csv: {len(df_deg)} 行')
except FileNotFoundError as e:
    print(f'  エラー: deg_rates_clean.csv が見つかりません: {e}')
    raise

# レースリザルト読み込み
race_dfs = {}
for key, path in RACE_RESULTS.items():
    try:
        rdf = pd.read_csv(path)
        race_dfs[key] = rdf
        print(f'  {key} race_results.csv: {len(rdf)} 行')
    except FileNotFoundError as e:
        print(f'  エラー: {key} race_results.csv が見つかりません: {e}')
        raise

# ============================================================
# Step 2: チーム別ペーストレンド集計
# ============================================================
print('\n[2/6] チーム別ペーストレンド集計中...')

# チーム単位で2ドライバーの平均FuelCorrectedMedianPace を計算
team_pace_records = []
for gp in GP_KEYS:
    gp_df = df_pace[df_pace['GP'] == gp]
    if gp_df.empty:
        print(f'  警告: {gp} のデータが存在しません')
        continue
    team_mean = gp_df.groupby('Team')['FuelCorrectedMedianPace'].mean().reset_index()
    team_mean['GP'] = gp
    team_pace_records.append(team_mean)

df_team_pace = pd.concat(team_pace_records, ignore_index=True)

# GP別のリーダー（最速チーム）ペースを取得
leader_pace = df_team_pace.groupby('GP')['FuelCorrectedMedianPace'].min().rename('LeaderPace')
df_team_pace = df_team_pace.join(leader_pace, on='GP')

# 正規化ペース = (チームペース - リーダーペース) / リーダーペース * 100 (%)
df_team_pace['NormPace'] = (
    (df_team_pace['FuelCorrectedMedianPace'] - df_team_pace['LeaderPace'])
    / df_team_pace['LeaderPace'] * 100
)

print(f'  チーム数: {df_team_pace["Team"].nunique()}')
print(f'  GPデータ: {df_team_pace["GP"].unique().tolist()}')

# ============================================================
# Step 3: ドライバー別正規化ペース（成長率）
# ============================================================
print('\n[3/6] ドライバー別成長率計算中...')

# ドライバー単位で正規化ペースを計算
driver_pace_records = []
for gp in GP_KEYS:
    gp_df = df_pace[df_pace['GP'] == gp].copy()
    if gp_df.empty:
        continue
    # GPリーダーのペース（最速ドライバー）
    leader_pace_val = gp_df['FuelCorrectedMedianPace'].min()
    gp_df['NormPace'] = (
        (gp_df['FuelCorrectedMedianPace'] - leader_pace_val)
        / leader_pace_val * 100
    )
    gp_df['GP_short'] = gp
    driver_pace_records.append(gp_df)

df_driver_norm = pd.concat(driver_pace_records, ignore_index=True)

# ============================================================
# Step 4: コンストラクターポイント集計
# ============================================================
print('\n[4/6] コンストラクターポイント集計中...')

constructor_points = {}
cumulative_points = {}

for key, rdf in race_dfs.items():
    team_pts = rdf.groupby('TeamName')['Points'].sum()
    constructor_points[key] = team_pts

# 累計ポイント計算（R01→R02→R03）
all_teams = set()
for pts in constructor_points.values():
    all_teams.update(pts.index.tolist())
all_teams = sorted(all_teams)

cumulative = {team: 0 for team in all_teams}
cumulative_by_gp = {}
for key in ['R01', 'R02', 'R03']:
    pts = constructor_points.get(key, pd.Series(dtype=float))
    for team in all_teams:
        cumulative[team] += pts.get(team, 0)
    cumulative_by_gp[key] = cumulative.copy()

print(f'  チーム数: {len(all_teams)}')

# ============================================================
# Step 5: タイヤデグレートGP間比較（HARDコンパウンド）
# ============================================================
print('\n[5/6] タイヤデグレート比較（HARD）集計中...')

# HARDコンパウンドのみ抽出、正のデグレートのみ（負は計測誤差/初期グリップ改善）
df_hard = df_deg[
    (df_deg['Compound'] == 'HARD') &
    (df_deg['DegRate'] > 0)
].copy()

# チーム×GP平均デグレート
hard_team_deg = df_hard.groupby(['GP', 'Team'])['DegRate'].mean().reset_index()
hard_team_deg.columns = ['GP', 'Team', 'HardDegRate']
print(f'  HARDデグ有効スティント数: {len(df_hard)}')

# ============================================================
# Step 6: 一貫性スコア計算
# ============================================================
print('\n[6/6] 一貫性スコア計算中...')

# ドライバー別: 3GP正規化ペースの標準偏差（全3GPデータがあるドライバーのみ）
driver_gp_norm = df_driver_norm.pivot_table(
    index='Driver', columns='GP_short', values='NormPace'
)

# 3GP全て出場しているドライバーのみ
driver_gp_norm = driver_gp_norm.dropna(
    subset=['R01_Australia', 'R02_China', 'R03_Japan'],
    how='any'
)

driver_gp_norm['ConsistencyScore'] = driver_gp_norm[
    ['R01_Australia', 'R02_China', 'R03_Japan']
].std(axis=1)

# チーム情報付与（最後のGPの情報を使用）
driver_team_map = df_driver_norm.groupby('Driver')['Team'].last()
driver_gp_norm['Team'] = driver_gp_norm.index.map(driver_team_map)

# チーム別一貫性スコア（ドライバー平均）
team_consistency = driver_gp_norm.groupby('Team')['ConsistencyScore'].mean().sort_values()

print(f'  3GP全参加ドライバー数: {len(driver_gp_norm)}')
print(f'  一貫性スコア（チーム平均）:')
for team, score in team_consistency.items():
    print(f'    {team}: {score:.3f}')

# ============================================================
# Step 7: CSV出力
# ============================================================
print('\nCSV出力中...')

# チームベースのピボット（ペース）
team_pivot = df_team_pace.pivot_table(
    index='Team', columns='GP', values='FuelCorrectedMedianPace'
).reset_index()
team_pivot.columns = ['Team', 'R01_Pace', 'R02_Pace', 'R03_Pace']

norm_pivot = df_team_pace.pivot_table(
    index='Team', columns='GP', values='NormPace'
).reset_index()
norm_pivot.columns = ['Team', 'R01_NormPace', 'R02_NormPace', 'R03_NormPace']

# コンストラクターポイント合計
total_points = {}
for team in all_teams:
    total_points[team] = cumulative_by_gp['R03'].get(team, 0)

# 一貫性スコア（チーム平均）
team_cons = team_consistency.reset_index()
team_cons.columns = ['Team', 'ConsistencyScore']

# 統合CSV作成
out_df = team_pivot.merge(norm_pivot, on='Team', how='outer')
out_df['ConsistencyScore'] = out_df['Team'].map(team_consistency.to_dict())
out_df['TotalPoints'] = out_df['Team'].map(total_points)

# カラム並び替え
out_df = out_df[['Team', 'R01_Pace', 'R02_Pace', 'R03_Pace',
                  'R01_NormPace', 'R02_NormPace', 'R03_NormPace',
                  'ConsistencyScore', 'TotalPoints']]
out_df = out_df.sort_values('TotalPoints', ascending=False)

csv_path = os.path.join(OUTPUT_DIR, 'cross_gp_team_trends.csv')
out_df.to_csv(csv_path, index=False, float_format='%.4f')
print(f'  -> {csv_path}')
print(out_df.to_string(index=False))

# ============================================================
# Step 8: グラフ描画（4パネル）
# ============================================================
print('\nグラフ描画中...')

fig = plt.figure(figsize=STYLE['figsize'], facecolor=STYLE['bg_color'])
fig.suptitle(
    'R01-R03 Cross-GP Performance Trends\nR01 Australia / R02 China / R03 Japan',
    fontsize=16, color=STYLE['text_color'], fontweight='bold', y=0.98
)

gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.45, wspace=0.35)

ax1 = fig.add_subplot(gs[0, 0])  # チームペース推移
ax2 = fig.add_subplot(gs[0, 1])  # ドライバー正規化ペース成長率
ax3 = fig.add_subplot(gs[1, 0])  # コンストラクターポイント累計
ax4 = fig.add_subplot(gs[1, 1])  # タイヤデグレート比較

gp_x = [0, 1, 2]
gp_labels_short = ['R01\nAUS', 'R02\nCHN', 'R03\nJPN']

# -------- Panel 1: チーム別燃料補正ペース推移 --------
ax1.set_facecolor(STYLE['bg_color'])
ax1.set_title('チーム別レースペース推移\n(燃料補正済 中央値)', color=STYLE['text_color'], fontsize=11)

teams_sorted = out_df.sort_values('TotalPoints', ascending=False)['Team'].dropna().tolist()
for team in teams_sorted:
    color = TEAM_COLORS.get(team, '#aaaaaa')
    row = out_df[out_df['Team'] == team]
    if row.empty:
        continue
    paces = [
        row['R01_Pace'].values[0],
        row['R02_Pace'].values[0],
        row['R03_Pace'].values[0],
    ]
    # NaNスキップしてプロット
    valid_x = [i for i, p in zip(gp_x, paces) if not np.isnan(p)]
    valid_p = [p for p in paces if not np.isnan(p)]
    if len(valid_p) >= 2:
        ax1.plot(valid_x, valid_p, marker='o', color=color,
                 label=team, linewidth=1.8, markersize=5)
    # チーム名を最後のデータポイントに表示
    if valid_p:
        ax1.annotate(
            team.replace(' Racing', '').replace(' F1 Team', ''),
            (valid_x[-1], valid_p[-1]),
            xytext=(4, 0), textcoords='offset points',
            fontsize=6.5, color=color, va='center'
        )

ax1.set_xticks(gp_x)
ax1.set_xticklabels(gp_labels_short, color=STYLE['text_color'], fontsize=9)
ax1.set_ylabel('ペース（秒）', color=STYLE['text_color'], fontsize=9)
ax1.tick_params(colors=STYLE['text_color'])
ax1.grid(True, color=STYLE['grid_color'], alpha=0.5, linestyle='--')
for spine in ax1.spines.values():
    spine.set_edgecolor(STYLE['grid_color'])

# -------- Panel 2: ドライバー別正規化ペース成長率 --------
ax2.set_facecolor(STYLE['bg_color'])
ax2.set_title('ドライバー別正規化ペース推移\n(リーダーとの差 ％)', color=STYLE['text_color'], fontsize=11)

# 全3GP参加のドライバーのみ表示
for driver in driver_gp_norm.index:
    row = driver_gp_norm.loc[driver]
    team = row['Team'] if 'Team' in row else 'Unknown'
    color = TEAM_COLORS.get(team, '#aaaaaa')
    paces = [
        row.get('R01_Australia', np.nan),
        row.get('R02_China', np.nan),
        row.get('R03_Japan', np.nan),
    ]
    valid_x = [i for i, p in zip(gp_x, paces) if not np.isnan(p)]
    valid_p = [p for p in paces if not np.isnan(p)]
    if len(valid_p) >= 2:
        ax2.plot(valid_x, valid_p, marker='o', color=color,
                 linewidth=1.5, markersize=4, alpha=0.85)
    if valid_p:
        ax2.annotate(
            driver,
            (valid_x[-1], valid_p[-1]),
            xytext=(4, 0), textcoords='offset points',
            fontsize=6, color=color, va='center'
        )

ax2.axhline(0, color='#ffffff', linewidth=0.8, linestyle='--', alpha=0.5)
ax2.set_xticks(gp_x)
ax2.set_xticklabels(gp_labels_short, color=STYLE['text_color'], fontsize=9)
ax2.set_ylabel('リーダー比 (%)', color=STYLE['text_color'], fontsize=9)
ax2.tick_params(colors=STYLE['text_color'])
ax2.grid(True, color=STYLE['grid_color'], alpha=0.5, linestyle='--')
for spine in ax2.spines.values():
    spine.set_edgecolor(STYLE['grid_color'])

# -------- Panel 3: コンストラクターポイント累計推移 --------
ax3.set_facecolor(STYLE['bg_color'])
ax3.set_title('コンストラクターポイント累計推移', color=STYLE['text_color'], fontsize=11)

gp_keys_list = ['R01', 'R02', 'R03']

# ポイント累計を全チームについてプロット
teams_by_total = sorted(all_teams, key=lambda t: cumulative_by_gp['R03'].get(t, 0), reverse=True)
for team in teams_by_total:
    color = TEAM_COLORS.get(team, '#aaaaaa')
    pts = [cumulative_by_gp[k].get(team, 0) for k in gp_keys_list]
    if max(pts) > 0:
        ax3.plot(gp_x, pts, marker='o', color=color,
                 label=team, linewidth=1.8, markersize=5)
        ax3.annotate(
            team.replace(' Racing', '').replace(' F1 Team', ''),
            (2, pts[-1]),
            xytext=(4, 0), textcoords='offset points',
            fontsize=6.5, color=color, va='center'
        )

ax3.set_xticks(gp_x)
ax3.set_xticklabels(gp_labels_short, color=STYLE['text_color'], fontsize=9)
ax3.set_ylabel('累計ポイント', color=STYLE['text_color'], fontsize=9)
ax3.tick_params(colors=STYLE['text_color'])
ax3.grid(True, color=STYLE['grid_color'], alpha=0.5, linestyle='--')
for spine in ax3.spines.values():
    spine.set_edgecolor(STYLE['grid_color'])

# -------- Panel 4: HARDタイヤ デグレートGP間比較 --------
ax4.set_facecolor(STYLE['bg_color'])
ax4.set_title('HARDタイヤ デグレート比較\n(チーム平均、正値のみ)', color=STYLE['text_color'], fontsize=11)

# 各GP×チームのHARDデグレートを横並びで表示
gp_deg_pivot = hard_team_deg.pivot_table(
    index='Team', columns='GP', values='HardDegRate'
).reset_index()

# GPごとに異なるスタイルでプロット
gp_cols = ['R01_Australia', 'R02_China', 'R03_Japan']
gp_colors = ['#FF6B6B', '#FFD700', '#98FB98']
markers = ['o', 's', '^']

bar_width = 0.25
x = np.arange(len(gp_deg_pivot))

for i, (gp_col, gp_label, bar_color) in enumerate(zip(gp_cols, gp_labels_short, gp_colors)):
    if gp_col in gp_deg_pivot.columns:
        vals = gp_deg_pivot[gp_col].fillna(0).values
        bars = ax4.bar(
            x + i * bar_width, vals, bar_width,
            label=gp_label.replace('\n', ' '), color=bar_color, alpha=0.8
        )

ax4.set_xticks(x + bar_width)
ax4.set_xticklabels(
    [t.replace(' Racing', '').replace(' F1 Team', '') for t in gp_deg_pivot['Team']],
    color=STYLE['text_color'], fontsize=6.5, rotation=35, ha='right'
)
ax4.set_ylabel('デグレート（秒/ラップ）', color=STYLE['text_color'], fontsize=9)
ax4.tick_params(colors=STYLE['text_color'])
ax4.legend(fontsize=8, facecolor=STYLE['bg_color'], labelcolor=STYLE['text_color'],
           loc='upper left')
ax4.grid(True, color=STYLE['grid_color'], alpha=0.5, linestyle='--', axis='y')
for spine in ax4.spines.values():
    spine.set_edgecolor(STYLE['grid_color'])

# グラフ保存
png_path = os.path.join(OUTPUT_DIR, 'cross_gp_trends.png')
plt.savefig(png_path, dpi=150, bbox_inches='tight',
            facecolor=STYLE['bg_color'], edgecolor='none')
plt.close()
print(f'  -> {png_path}')

# ============================================================
# Step 9: サマリー表示
# ============================================================
print('\n=== 分析サマリー ===')
print(f'\n【チーム一貫性スコア（低い=安定）】')
for team, score in team_consistency.items():
    print(f'  {team}: {score:.3f}%')

print(f'\n【R03時点コンストラクターポイント順位】')
r03_pts = {t: cumulative_by_gp['R03'].get(t, 0) for t in all_teams}
for i, (team, pts) in enumerate(sorted(r03_pts.items(), key=lambda x: -x[1]), 1):
    print(f'  {i:2d}. {team}: {pts:.0f}pt')

print(f'\n完了: cross_gp_team_trends.csv + cross_gp_trends.png を出力しました')
