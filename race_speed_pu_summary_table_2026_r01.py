"""
2026 オーストラリアGP — PU平均スピード サマリーテーブル画像
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

RETIRED = {'HAD', 'BOT', 'ALO'}
PU_MAP = {
    'Mercedes': 'Mercedes', 'McLaren': 'Mercedes', 'Williams': 'Mercedes', 'Alpine': 'Mercedes',
    'Ferrari': 'Ferrari', 'Haas F1 Team': 'Ferrari', 'Cadillac': 'Ferrari',
    'Red Bull Racing': 'Red Bull PT', 'Racing Bulls': 'Red Bull PT',
    'Aston Martin': 'Honda', 'Audi': 'Audi',
}
PU_ORDER = ['Mercedes', 'Ferrari', 'Red Bull PT', 'Honda', 'Audi']
PU_COLORS = {
    'Mercedes': '#00B89F',
    'Ferrari': '#DC0000',
    'Red Bull PT': '#2B5DAB',
    'Honda': '#1B7A5A',
    'Audi': '#C92D39',
}
# 背景用の薄い色（PUカラーベース）
PU_BG_COLORS = {
    'Mercedes': '#D5F5EE',
    'Ferrari': '#FADEDE',
    'Red Bull PT': '#D8E4F5',
    'Honda': '#D2EDE4',
    'Audi': '#F5D8DC',
}

drv_team = dict(zip(results['Abbreviation'], results['TeamName']))
SPEED_COLS = ['SpeedST', 'SpeedFL', 'SpeedI1', 'SpeedI2']
COL_LABELS = ['ST\n(スピードトラップ)', 'FL\n(フィニッシュライン)', 'S1末端', 'S2末端']

# クリーンラップ(OT除外)
clean = {}
for _, r in results.iterrows():
    drv = r['Abbreviation']
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

# PUグループ（DNF除外）
pu_drivers = {pu: [] for pu in PU_ORDER}
for drv in results['Abbreviation'].tolist():
    team = drv_team.get(drv, '')
    pu = PU_MAP.get(team, '?')
    if pu in pu_drivers and drv in clean and drv not in RETIRED:
        pu_drivers[pu].append(drv)

# PU平均を算出
table_data = []  # [(pu, [st, fl, s1, s2], n, teams)]
for pu in PU_ORDER:
    drivers = pu_drivers[pu]
    if not drivers:
        continue
    avgs = []
    for scol in SPEED_COLS:
        meds = [clean[d][scol].dropna().median() for d in drivers]
        avgs.append(np.mean(meds))
    teams = sorted(set(drv_team[d] for d in drivers))
    team_short = {
        'Mercedes': 'MER', 'McLaren': 'MCL', 'Williams': 'WIL', 'Alpine': 'ALP',
        'Ferrari': 'FER', 'Haas F1 Team': 'HAA', 'Cadillac': 'CAD',
        'Red Bull Racing': 'RBR', 'Racing Bulls': 'RCB',
        'Aston Martin': 'AMR', 'Audi': 'AUD',
    }
    team_str = ', '.join(team_short.get(t, t[:3]) for t in teams)
    table_data.append((pu, avgs, len(drivers), team_str))

# 各列の最大値・最小値を特定（ハイライト用）
max_per_col = [max(row[1][ci] for row in table_data) for ci in range(4)]
min_per_col = [min(row[1][ci] for row in table_data) for ci in range(4)]

FASTEST_COLOR = '#0055CC'  # 青字（最速）
SLOWEST_COLOR = '#CC2200'  # 赤字（最遅）

# ==========================================================
# テーブル画像生成
# ==========================================================
print('テーブル画像生成中...')

n_rows = len(table_data)
n_cols = 6  # PU, ST, FL, S1末端, S2末端, チーム

fig, ax = plt.subplots(figsize=(14, 5), facecolor='white')
ax.set_facecolor('white')
ax.axis('off')
ax.set_xlim(0, 14)
ax.set_ylim(-0.5, n_rows + 2.0)

# 列のX座標
col_x = [1.2, 4.0, 6.0, 8.0, 10.0, 12.5]
col_widths = [2.4, 1.8, 1.8, 1.8, 1.8, 2.8]  # 各列の幅

# ヘッダー行
header_y = n_rows + 1.0
header_labels = ['PU'] + COL_LABELS + ['供給チーム']
header_x = [1.2, 4.0, 6.0, 8.0, 10.0, 12.5]

# ヘッダー背景
ax.fill_between([0, 14], header_y - 0.45, header_y + 0.55, color='#2C2C4A', zorder=1)

for xi, label in zip(header_x, header_labels):
    ax.text(xi, header_y, label, ha='center', va='center',
            fontsize=12, fontweight='bold', color='white', zorder=2)

# データ行
for ri, (pu, avgs, n, team_str) in enumerate(table_data):
    y = n_rows - ri - 0.2
    pu_color = PU_COLORS[pu]
    bg_color = PU_BG_COLORS[pu]

    # 行背景
    ax.fill_between([0, 14], y - 0.45, y + 0.45, color=bg_color, alpha=0.7, zorder=0)

    # 行罫線（下端）
    ax.axhline(y - 0.45, color='#E0E0E0', linewidth=0.5, zorder=1)

    # PU名（左寄せ、PUカラー）
    ax.text(col_x[0], y, pu, ha='center', va='center',
            fontsize=13, fontweight='bold', color=pu_color, zorder=2)

    # 速度値（最速=青字、最遅=赤字）
    for ci in range(4):
        val = avgs[ci]
        is_max = abs(val - max_per_col[ci]) < 0.01
        is_min = abs(val - min_per_col[ci]) < 0.01
        if is_max:
            clr = FASTEST_COLOR
            fw = 'bold'
            fs = 14
        elif is_min:
            clr = SLOWEST_COLOR
            fw = 'bold'
            fs = 14
        else:
            clr = '#333333'
            fw = 'normal'
            fs = 12
        ax.text(col_x[ci + 1], y, f'{val:.1f}', ha='center', va='center',
                fontsize=fs, fontweight=fw, color=clr, zorder=2)

    # チーム名 + n
    note = f'* n={n}' if n <= 1 else f'n={n}'
    ax.text(col_x[5], y, f'{team_str}\n({note})', ha='center', va='center',
            fontsize=9, color='#666666', zorder=2, linespacing=1.3)

# 上端罫線
ax.axhline(header_y - 0.45, color='#2C2C4A', linewidth=1.5, zorder=1)
# 下端罫線
ax.axhline(n_rows - len(table_data) + 0.35, color='#AAAAAA', linewidth=1.0, zorder=1)

# タイトル
ax.text(7.0, n_rows + 1.8, 'PU平均スピード (中央値の平均, km/h) — 2026 オーストラリアGP',
        ha='center', va='center', fontsize=16, fontweight='bold', color='#1a1a2e')

# 脚注
ax.text(7.0, -0.3,
        'OTモード影響除外 (F/L通過時 前車差1秒以内 → 次周除外)  |  DNFドライバー (ALO, BOT, HAD) 除外  |  '
        '青字 = 各列最速  |  赤字 = 各列最遅  |  * n=1 は参考値',
        ha='center', va='center', fontsize=8.5, color='#888888', style='italic')

plt.subplots_adjust(left=0.02, right=0.98, top=0.88, bottom=0.08)

out = Path('./data/2026_R01_Australia/article/art_speed_pu_summary_table.png')
out.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(out, dpi=200, facecolor='white', bbox_inches='tight', pad_inches=0.3)
size_kb = out.stat().st_size / 1024
print(f'保存: {out} ({size_kb:.0f} KB)')
plt.close(fig)
