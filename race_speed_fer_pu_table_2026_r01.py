"""
2026 オーストラリアGP — Ferrari PU使用チーム スピード比較テーブル
OTモード除外・DNF除外
"""

import fastf1
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

for fn in ['Yu Gothic', 'Meiryo', 'MS Gothic']:
    try:
        matplotlib.font_manager.FontProperties(family=fn)
        plt.rcParams['font.family'] = fn
        break
    except:
        continue

# データ読み込み
print('データ読み込み中...')
fastf1.Cache.enable_cache('~/f1_cache')
s = fastf1.get_session(2026, 'Australia', 'R')
s.load(telemetry=False, laps=True, weather=False)
laps_all = s.laps
results = s.results.sort_values('Position')

# VSC
rcm = s.race_control_messages
vsc_set = set()
cs = None
for _, row in rcm.iterrows():
    msg = str(row.get('Message', ''))
    lap = row.get('Lap', None)
    if lap is not None:
        lap = int(lap)
        if 'VSC DEPLOYED' in msg:
            cs = lap
        elif 'VSC ENDING' in msg and cs is not None:
            for l in range(cs, lap + 2):
                vsc_set.add(l)
            cs = None

# OTラップ
one_sec = pd.Timedelta(seconds=1)
overtake_laps = set()
for lap_num in range(1, int(laps_all['LapNumber'].max()) + 1):
    ld = laps_all[laps_all['LapNumber'] == lap_num][['Driver', 'Time']].dropna(subset=['Time']).sort_values('Time')
    if len(ld) < 2:
        continue
    times, drivers = ld['Time'].values, ld['Driver'].values
    for i in range(1, len(drivers)):
        if times[i] - times[i - 1] <= one_sec:
            overtake_laps.add((drivers[i], lap_num + 1))

drv_team = dict(zip(results['Abbreviation'], results['TeamName']))

# リタイアドライバー
RETIRED = set()
for _, r in results.iterrows():
    status = str(r.get('Status', ''))
    if 'Retired' in status:
        RETIRED.add(r['Abbreviation'])
print(f'リタイアドライバー: {RETIRED}')

# Ferrari PUチームのみ
FER_TEAMS = {'Ferrari', 'Haas F1 Team', 'Cadillac'}

TEAM_COLORS = {
    'Ferrari': '#E8002D', 'Haas F1 Team': '#B6BABD', 'Cadillac': '#1E1E1E',
}
TEAM_BG_COLORS = {
    'Ferrari': '#FADEDE', 'Haas F1 Team': '#F0F0F0', 'Cadillac': '#E8E8E8',
}
TEAM_SHORT = {
    'Ferrari': 'FER', 'Haas F1 Team': 'HAA', 'Cadillac': 'CAD',
}

# Haasのテキストカラー（背景が薄いので少し濃く）
TEAM_TEXT_COLORS = {
    'Ferrari': '#E8002D', 'Haas F1 Team': '#777777', 'Cadillac': '#333333',
}

SPEED_COLS = ['SpeedST', 'SpeedFL', 'SpeedI1', 'SpeedI2']
COL_LABELS = ['ST\n(スピードトラップ)', 'FL\n(フィニッシュライン)', 'S1末端', 'S2末端']

GREY_COLOR = '#BBBBBB'

# クリーンラップ(OT除外)
clean = {}
for _, r in results.iterrows():
    drv = r['Abbreviation']
    team = r['TeamName']
    if team not in FER_TEAMS:
        continue
    df = laps_all[laps_all['Driver'] == drv].copy().sort_values('LapNumber')
    if len(df) == 0:
        continue
    df['LapNum'] = df['LapNumber'].astype(int)
    pit_in = set(df[df['PitInTime'].notna()]['LapNum'])
    pit_out = set(df[df['PitOutTime'].notna()]['LapNum'])
    ot_for = {l for d, l in overtake_laps if d == drv}
    exclude = vsc_set | pit_in | pit_out | {1} | ot_for
    c = df[~df['LapNum'].isin(exclude)]
    if len(c) > 3:
        clean[drv] = c

# ドライバー別中央値を算出
drv_data = {}
for drv in results['Abbreviation'].tolist():
    team = drv_team.get(drv, '')
    if team not in FER_TEAMS or drv not in clean:
        continue
    meds = [clean[drv][scol].dropna().median() for scol in SPEED_COLS]
    n = len(clean[drv])
    drv_data[drv] = (team, meds, n)

# チーム順: Ferrari, Haas, Cadillac（v3チャートと整合）
TEAM_ORDER = ['Ferrari', 'Haas F1 Team', 'Cadillac']
table_data = []
for team in TEAM_ORDER:
    for drv in results['Abbreviation'].tolist():
        if drv in drv_data and drv_data[drv][0] == team:
            t, meds, n = drv_data[drv]
            is_retired = drv in RETIRED
            table_data.append((drv, t, meds, n, is_retired))

print(f'Ferrari PUドライバー: {len(table_data)}名')
for drv, team, meds, n, ret in table_data:
    tag = ' (DNF)' if ret else ''
    print(f'  {drv} ({TEAM_SHORT[team]}){tag}: ST={meds[0]:.1f} FL={meds[1]:.1f} S1={meds[2]:.1f} S2={meds[3]:.1f} n={n}')

# 各列の最大値・最小値（DNF除外で計算）
active_data = [row for row in table_data if not row[4]]
max_per_col = [max(row[2][ci] for row in active_data) for ci in range(4)]
min_per_col = [min(row[2][ci] for row in active_data) for ci in range(4)]

FASTEST_COLOR = '#0055CC'
SLOWEST_COLOR = '#CC2200'

# PU平均（DNF除外）
pu_avg_meds = []
for ci in range(4):
    pu_avg_meds.append(np.mean([row[2][ci] for row in active_data]))
pu_avg_n = sum(row[3] for row in active_data)

# ==========================================================
# テーブル画像生成
# ==========================================================
print('\nテーブル画像生成中...')

n_rows = len(table_data)
total_rows = n_rows + 1  # データ行 + PU平均行

fig, ax = plt.subplots(figsize=(14, 7), facecolor='white')
ax.set_facecolor('white')
ax.axis('off')
ax.set_xlim(0, 14)
ax.set_ylim(-1.2, total_rows + 2.2)

col_x = [0.8, 2.2, 4.5, 6.5, 8.5, 10.5, 12.5]

# ヘッダー行
header_y = total_rows + 1.0
header_labels = ['Driver', 'Team'] + COL_LABELS + ['Laps']

# ヘッダー背景（Ferrariカラー）
ax.fill_between([0, 14], header_y - 0.45, header_y + 0.55, color='#DC0000', zorder=1)

for xi, label in zip(col_x, header_labels):
    ax.text(xi, header_y, label, ha='center', va='center',
            fontsize=11, fontweight='bold', color='white', zorder=2)

# データ行
prev_team = None
for ri, (drv, team, meds, n, is_retired) in enumerate(table_data):
    y = total_rows - ri - 0.2
    bg_color = TEAM_BG_COLORS[team]

    # 行背景
    bg_alpha = 0.7 if ri % 2 == 0 else 0.45
    ax.fill_between([0, 14], y - 0.45, y + 0.45, color=bg_color, alpha=bg_alpha, zorder=0)

    # チーム境界線
    if prev_team is not None and team != prev_team:
        ax.axhline(y + 0.45, color='#BBBBBB', linewidth=1.2, zorder=1)
    else:
        ax.axhline(y + 0.45, color='#E0E0E0', linewidth=0.5, zorder=1)
    prev_team = team

    ax.axhline(y - 0.45, color='#E0E0E0', linewidth=0.5, zorder=1)

    # ドライバー名（DNFはグレー + (DNF)表記）
    if is_retired:
        drv_label = f'{drv} (DNF)'
        drv_color = GREY_COLOR
    else:
        drv_label = drv
        drv_color = '#1a1a2e'
    ax.text(col_x[0], y, drv_label, ha='center', va='center',
            fontsize=13, fontweight='bold', color=drv_color, zorder=2)

    # チーム名
    team_text_color = GREY_COLOR if is_retired else TEAM_TEXT_COLORS[team]
    ax.text(col_x[1], y, TEAM_SHORT[team], ha='center', va='center',
            fontsize=12, fontweight='bold', color=team_text_color, zorder=2)

    # 速度値
    for ci in range(4):
        val = meds[ci]
        if is_retired:
            clr = GREY_COLOR
            fw = 'normal'
            fs = 12
        else:
            is_max = abs(val - max_per_col[ci]) < 0.01
            is_min = abs(val - min_per_col[ci]) < 0.01
            if is_max:
                clr = FASTEST_COLOR
                fw = 'bold'
                fs = 13
            elif is_min:
                clr = SLOWEST_COLOR
                fw = 'bold'
                fs = 13
            else:
                clr = '#333333'
                fw = 'normal'
                fs = 12
        ax.text(col_x[ci + 2], y, f'{val:.1f}', ha='center', va='center',
                fontsize=fs, fontweight=fw, color=clr, zorder=2)

    # ラップ数
    laps_color = GREY_COLOR if is_retired else '#666666'
    ax.text(col_x[6], y, str(n), ha='center', va='center',
            fontsize=11, color=laps_color, zorder=2)

# PU平均行
avg_y = total_rows - n_rows - 0.2
ax.axhline(avg_y + 0.45, color='#DC0000', linewidth=1.8, zorder=2)
ax.fill_between([0, 14], avg_y - 0.45, avg_y + 0.45, color='#FDF0F0', alpha=0.9, zorder=0)
ax.axhline(avg_y - 0.45, color='#DC0000', linewidth=1.0, zorder=1)

PU_ACCENT = '#DC0000'
ax.text(col_x[0], avg_y, 'PU Avg', ha='center', va='center',
        fontsize=13, fontweight='bold', color=PU_ACCENT, zorder=2)
ax.text(col_x[1], avg_y, f'n={len(active_data)}', ha='center', va='center',
        fontsize=10, fontweight='bold', color=PU_ACCENT, zorder=2)

for ci in range(4):
    ax.text(col_x[ci + 2], avg_y, f'{pu_avg_meds[ci]:.1f}', ha='center', va='center',
            fontsize=13, fontweight='bold', color=PU_ACCENT, zorder=2)

ax.text(col_x[6], avg_y, str(pu_avg_n), ha='center', va='center',
        fontsize=11, fontweight='bold', color=PU_ACCENT, zorder=2)

# 上端罫線
ax.axhline(header_y - 0.45, color='#DC0000', linewidth=1.5, zorder=1)

# タイトル
ax.text(7.0, total_rows + 1.9,
        'Ferrari PU使用チーム スピード比較 (中央値, km/h) — 2026 オーストラリアGP',
        ha='center', va='center', fontsize=16, fontweight='bold', color='#1a1a2e')

# 脚注
retired_str = ', '.join(sorted(drv for drv, _, _, _, ret in table_data if ret))
ax.text(7.0, avg_y - 0.85,
        'OTモード影響除外 (F/L通過時 前車差1秒以内 → 次周除外)  |  VSC/ピット周除外  |  '
        '青字 = 各列最速  |  赤字 = 各列最遅\n'
        f'Ferrari PU供給: Ferrari, Haas, Cadillac  |  グレー = DNF ({retired_str}) — 参考値、PU平均に含まず',
        ha='center', va='center', fontsize=8.5, color='#888888', style='italic')

plt.subplots_adjust(left=0.02, right=0.98, top=0.86, bottom=0.08)

out = Path('./data/2026_R01_Australia/article/art_speed_fer_pu_comparison.png')
out.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(out, dpi=200, facecolor='white', bbox_inches='tight', pad_inches=0.3)
size_kb = out.stat().st_size / 1024
print(f'保存: {out} ({size_kb:.0f} KB)')
plt.close(fig)
