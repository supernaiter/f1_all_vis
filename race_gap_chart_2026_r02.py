"""
============================================================
2026 R2 中国GP — ANT起点 全ドライバー ギャップ推移チャート
============================================================
ANTの累積タイムを基準に、全ドライバーのギャップをラップごとにプロット。

出力:
  data/2026_R02_China/article/art_gap_all_drivers.png
"""

import fastf1
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
from matplotlib.patches import Patch
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# GP設定
# ============================================================
YEAR = 2026
GP_NAME = 'China'
ROUND_NUMBER = 2
REF_DRIVER = 'ANT'  # 基準ドライバー

OUT_DIR = Path(f'./data/{YEAR}_R{ROUND_NUMBER:02d}_{GP_NAME}/article')
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# ライトテーマ（R01準拠）
# ============================================================
LT = {
    'bg':       '#FFFFFF',
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

# チームカラー（ライト背景用）
TEAM_COLORS = {
    'McLaren': '#E07800', 'Ferrari': '#DC0000', 'Red Bull Racing': '#2B5DAB',
    'Mercedes': '#00B89F', 'Aston Martin': '#1B7A5A', 'Williams': '#3BA3E0',
    'Racing Bulls': '#4A72CC', 'Alpine': '#0078AA', 'Haas F1 Team': '#7A7A7A',
    'Audi': '#3AAA3A', 'Cadillac': '#888888',
}

# チームメイト（2番手ドライバー）→破線
TEAMMATE_DASH = {
    'ANT': (5, 2.5), 'HAM': (5, 2.5), 'VER': (5, 2.5),
    'BEA': (5, 2.5), 'COL': (5, 2.5), 'SAI': (5, 2.5),
    'LAW': (5, 2.5), 'BOR': (5, 2.5), 'BOT': (5, 2.5),
    'STR': (5, 2.5), 'HAD': (5, 2.5), 'LIN': (5, 2.5),
    'PER': (5, 2.5),
}

# 日本語フォント
for font_name in ['Yu Gothic', 'Meiryo', 'MS Gothic']:
    try:
        matplotlib.font_manager.FontProperties(family=font_name)
        plt.rcParams['font.family'] = font_name
        break
    except:
        continue

# ============================================================
# データ読み込み
# ============================================================
print('FastF1からデータを読み込み中...')
fastf1.Cache.enable_cache('~/f1_cache')
session = fastf1.get_session(YEAR, GP_NAME, 'R')
session.load(telemetry=False, laps=True, weather=False)

laps_all = session.laps
results = session.results.sort_values('Position')
race_laps = int(laps_all['LapNumber'].max())

drv_team = dict(zip(results['Abbreviation'], results['TeamName']))
drv_pos = dict(zip(results['Abbreviation'], results['Position'].astype(int)))
drv_status = dict(zip(results['Abbreviation'], results['Status']))

# SC/VSC検出
rcm = session.race_control_messages
sc_periods = []   # セーフティカー期間
vsc_periods = []  # VSC期間
current_sc_start = None
current_vsc_start = None

if rcm is not None:
    for _, row in rcm.iterrows():
        msg = str(row.get('Message', ''))
        lap = row.get('Lap', None)
        if lap is not None:
            lap = int(lap)
            # SC
            if 'SAFETY CAR DEPLOYED' in msg:
                current_sc_start = lap
            elif 'SAFETY CAR IN THIS LAP' in msg and current_sc_start is not None:
                sc_periods.append((current_sc_start, lap))
                current_sc_start = None
            # VSC
            if 'VSC DEPLOYED' in msg:
                current_vsc_start = lap
            elif 'VSC ENDING' in msg and current_vsc_start is not None:
                vsc_periods.append((current_vsc_start, lap))
                current_vsc_start = None
    if current_sc_start is not None:
        sc_periods.append((current_sc_start, current_sc_start + 2))
    if current_vsc_start is not None:
        vsc_periods.append((current_vsc_start, current_vsc_start + 1))

print(f'レース: {race_laps}周, SC: {sc_periods}, VSC: {vsc_periods}')

# ============================================================
# ギャップ計算（ANT基準）
# ============================================================
print(f'ギャップ計算中（基準: {REF_DRIVER}）...')

# 基準ドライバーの累積タイム
ref_laps = laps_all[laps_all['Driver'] == REF_DRIVER].sort_values('LapNumber')
ref_times = {}
for _, row in ref_laps.iterrows():
    lap = int(row['LapNumber'])
    t = row['Time']
    if pd.notna(t):
        ref_times[lap] = t.total_seconds()

# 全ドライバーのギャップ計算
driver_gaps = {}
driver_order = results['Abbreviation'].tolist()
all_pit_laps = {}

for drv in driver_order:
    drv_laps = laps_all[laps_all['Driver'] == drv].sort_values('LapNumber')
    if len(drv_laps) == 0:
        continue

    # ピットラップ
    all_pit_laps[drv] = drv_laps[drv_laps['PitInTime'].notna()]['LapNumber'].astype(int).tolist()

    # ギャップ
    gaps = {}
    for _, row in drv_laps.iterrows():
        lap = int(row['LapNumber'])
        t = row['Time']
        if pd.notna(t) and lap in ref_times:
            gaps[lap] = t.total_seconds() - ref_times[lap]
    if gaps:
        driver_gaps[drv] = gaps

# 1ラップしか走っていないドライバーを除外（プロット不可）
min_laps_for_plot = 2
plotted_drivers = [drv for drv in driver_order
                   if drv in driver_gaps and len(driver_gaps[drv]) >= min_laps_for_plot]

print(f'プロット対象: {len(plotted_drivers)}ドライバー')
for drv in plotted_drivers:
    gaps = driver_gaps[drv]
    last_lap = max(gaps.keys())
    last_gap = gaps[last_lap]
    print(f'  {drv:3s} ({drv_team.get(drv, ""):18s}) L{last_lap:2d}  gap: {last_gap:+.1f}s')

# ============================================================
# プロット
# ============================================================
print('\nチャート描画中...')

fig, ax = plt.subplots(figsize=(18, 10), facecolor=LT['bg'])

# 軸設定
ax.set_facecolor(LT['bg'])
ax.tick_params(colors=LT['axis'], labelsize=LT['tick_size'])
ax.xaxis.set_major_locator(MultipleLocator(5))
ax.xaxis.set_minor_locator(MultipleLocator(1))
ax.grid(True, which='major', color=LT['grid_maj'], linewidth=0.6, alpha=0.8)
ax.grid(True, which='minor', color=LT['grid_min'], linewidth=0.3, alpha=0.5)
for spine in ax.spines.values():
    spine.set_color(LT['spine'])

ax.set_title(f'{YEAR} R{ROUND_NUMBER} {GP_NAME} GP -- {REF_DRIVER}とのギャップ推移 (全ドライバー)',
             color=LT['text'], fontsize=LT['title_size'], fontweight='bold', pad=14)
ax.set_ylabel(f'Gap to {REF_DRIVER} (秒)', color=LT['text'], fontsize=LT['label_size'])
ax.set_xlabel('ラップ数', color=LT['text'], fontsize=LT['label_size'])

# SC/VSC帯
for start, end in sc_periods:
    ax.axvspan(start - 0.5, end + 0.5, alpha=LT['sc_alpha'], color=LT['sc'], zorder=0)
for start, end in vsc_periods:
    ax.axvspan(start - 0.5, end + 0.5, alpha=LT['sc_alpha'], color=LT['sc'], zorder=0)

# Y軸範囲計算（全ドライバー）
all_gaps_vals = []
for drv in plotted_drivers:
    all_gaps_vals.extend(driver_gaps[drv].values())
if all_gaps_vals:
    y_max = max(all_gaps_vals) * 1.05 + 5
    y_min = min(all_gaps_vals) - 5
    ax.set_ylim(y_max, y_min)  # 反転（正=後方が下）
ax.set_xlim(0, race_laps + 6)  # 右に余白（ラベル用）

# 基準線（ANT = 0）
ax.axhline(0, color=TEAM_COLORS.get(drv_team.get(REF_DRIVER, ''), '#888'),
           linewidth=1.5, alpha=0.5, linestyle='-', zorder=5)

# 各ドライバーをプロット
for drv in plotted_drivers:
    gaps = driver_gaps[drv]
    team = drv_team.get(drv, '')
    color = TEAM_COLORS.get(team, '#888')
    dashes = TEAMMATE_DASH.get(drv, None)
    lap_nums = sorted(gaps.keys())
    gap_vals = [gaps[l] for l in lap_nums]

    # ライン幅: 主要ドライバーは太く、その他は細め
    lw = LT['line_w'] if drv == REF_DRIVER else 2.2

    kwargs = dict(color=color, linewidth=lw, alpha=0.90, zorder=10,
                  solid_capstyle='round')
    if dashes:
        kwargs['dashes'] = dashes

    ax.plot(lap_nums, gap_vals, **kwargs)

    # ピットマーカー
    for pl in all_pit_laps.get(drv, []):
        if pl in gaps:
            ax.plot(pl, gaps[pl], 'v', color=color, markersize=6, alpha=0.8, zorder=11)

    # リタイアマーカー
    status_str = str(drv_status.get(drv, ''))
    if 'Retired' in status_str or '+' in status_str:
        last_lap = max(gaps.keys())
        last_gap = gaps[last_lap]
        # 完走者以外にXマーク
        total_laps = len(laps_all[laps_all['Driver'] == drv])
        if total_laps < race_laps - 2:
            ax.plot(last_lap, last_gap, 'x', color=color, markersize=9,
                    markeredgewidth=2.5, zorder=12)

# ============================================================
# 末尾ドライバー名ラベル（重複回避）
# ============================================================
fig.canvas.draw()

# 各ドライバーの最終ラップ位置を収集
end_labels = []
for drv in plotted_drivers:
    gaps = driver_gaps[drv]
    last_lap = max(gaps.keys())
    last_gap = gaps[last_lap]
    team = drv_team.get(drv, '')
    color = TEAM_COLORS.get(team, '#888')
    end_labels.append((drv, last_lap, last_gap, color))

# display座標でY位置をソート → 重複回避
end_labels_disp = []
for drv, last_lap, real_y, color in end_labels:
    disp_y = ax.transData.transform((0, real_y))[1]
    end_labels_disp.append((drv, last_lap, real_y, color, disp_y))
# display Y大=画面上（gap小=前方）が先
end_labels_disp.sort(key=lambda x: -x[4])

min_disp_gap = 14  # ピクセル単位の最小間隔
placed_disp_y = []

for drv, last_lap, real_y, color, orig_disp_y in end_labels_disp:
    # 配置位置を調整（上から詰めていく）
    target_disp_y = orig_disp_y
    for prev_dy in placed_disp_y:
        if prev_dy - target_disp_y < min_disp_gap:
            target_disp_y = prev_dy - min_disp_gap
    placed_disp_y.append(target_disp_y)
    oy = target_disp_y - orig_disp_y  # offset in display pixels

    ax.annotate(drv, (last_lap, real_y), xytext=(10, oy),
                textcoords='offset points', fontsize=9, fontweight='bold',
                color=color, va='center', ha='left', zorder=15,
                arrowprops=dict(arrowstyle='-', color=color, alpha=0.3, lw=0.5)
                if abs(oy) > 4 else None)

# ============================================================
# 凡例
# ============================================================
handles, lbls = [], []

# SC/VSC
if sc_periods:
    handles.append(Patch(facecolor=LT['sc'], alpha=0.4, edgecolor='none'))
    lbls.append('SC')
if vsc_periods:
    handles.append(Patch(facecolor=LT['sc'], alpha=0.4, edgecolor='none'))
    lbls.append('VSC')

# ピットマーカー
handles.append(plt.Line2D([0], [0], marker='v', color='#888', markersize=7, linewidth=0))
lbls.append('Pit Stop')

# リタイアマーカー
handles.append(plt.Line2D([0], [0], marker='x', color='#888', markersize=7,
               markeredgewidth=2, linewidth=0))
lbls.append('Retired/+Laps')

# チーム別凡例（実線=Driver1, 破線=Driver2）
teams_plotted = []
for drv in plotted_drivers:
    team = drv_team.get(drv, '')
    if team not in teams_plotted:
        teams_plotted.append(team)
        color = TEAM_COLORS.get(team, '#888')
        # チーム名の短縮
        short_name = team.replace(' Racing', '').replace(' F1 Team', '')
        handles.append(plt.Line2D([0], [0], color=color, linewidth=2.5, linestyle='-'))
        lbls.append(short_name)

ax.legend(handles, lbls, loc='lower left', fontsize=9, facecolor='white',
          edgecolor=LT['spine'], labelcolor=LT['text'], ncol=4, framealpha=0.95)

# ============================================================
# 保存
# ============================================================
path = OUT_DIR / 'art_gap_all_drivers.png'
fig.savefig(path, dpi=180, facecolor=LT['bg'], bbox_inches='tight')
size_kb = path.stat().st_size / 1024
print(f'\n保存: {path} ({size_kb:.0f} KB)')
plt.close(fig)

# CSVエクスポート
csv_dir = OUT_DIR / 'csv'
csv_dir.mkdir(parents=True, exist_ok=True)
rows = []
for drv in plotted_drivers:
    team = drv_team.get(drv, '')
    pos = drv_pos.get(drv, '')
    for lap, gap in sorted(driver_gaps[drv].items()):
        rows.append({
            'Driver': drv, 'Team': team, 'Position': pos,
            'LapNumber': lap, 'GapToANT_sec': round(gap, 3),
        })
csv_path = csv_dir / 'chart_gap_all_drivers.csv'
pd.DataFrame(rows).to_csv(csv_path, index=False)
print(f'CSV保存: {csv_path} ({len(rows)} rows)')

print('\n完了')
