"""
============================================================
2026 R2 中国GP — ANT起点 Top10+VER ギャップ推移（X投稿用 v4）
============================================================
"""

import fastf1
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
# 設定
# ============================================================
YEAR = 2026
GP_NAME = 'China'
ROUND_NUMBER = 2
REF_DRIVER = 'ANT'

OUT_DIR = Path(f'./data/{YEAR}_R{ROUND_NUMBER:02d}_{GP_NAME}/article')
OUT_DIR.mkdir(parents=True, exist_ok=True)

GROUPS = [
    {'drivers': ['ANT', 'RUS']},
    {'drivers': ['HAM', 'LEC']},
    {'drivers': ['BEA', 'GAS']},
    {'drivers': ['LAW', 'HAD']},
    {'drivers': ['SAI', 'COL']},
]
SPECIAL_DRIVERS = ['VER']
TARGET_DRIVERS = [d for g in GROUPS for d in g['drivers']] + SPECIAL_DRIVERS

# ============================================================
# ダークテーマ
# ============================================================
BG       = '#0f0f1a'
TEXT     = '#EEEEEE'
TEXT_DIM = '#8899AA'
GRID_MAJ = '#252540'
GRID_MIN = '#1a1a30'
SPINE    = '#333355'
SC_COLOR = '#FFD700'

# ドライバー別カラー（全員区別可能）
COLORS = {
    'ANT': '#00E8C8',   # Mercedes - ターコイズ
    'RUS': '#00E8C8',   # Mercedes（破線で区別）
    'LEC': '#FF4444',   # Ferrari - 赤
    'HAM': '#FF4444',   # Ferrari（破線で区別）
    'GAS': '#FF88CC',   # Alpine - ピンク
    'BEA': '#BBBBBB',   # Haas - シルバー
    'LAW': '#8877EE',   # Racing Bulls - パープル
    'HAD': '#2266CC',   # Red Bull 2nd - ダークブルー
    'SAI': '#55CCFF',   # Williams - ライトブルー
    'COL': '#FF88CC',   # Alpine（GASと同色・破線で区別）
    'VER': '#2266CC',   # Red Bull（HADと同色・一点鎖線で区別）
}

GROUP_BAND_COLORS = ['#00E8C8', '#FF4444', '#99AACC', '#8877EE', '#55CCFF']

LINE_STYLES = {
    'ANT': {'dash': None,   'lw': 3.5},
    'RUS': {'dash': (7, 3), 'lw': 3.0},
    'LEC': {'dash': None,   'lw': 3.0},
    'HAM': {'dash': (7, 3), 'lw': 3.0},
    'GAS': {'dash': None,   'lw': 2.8},
    'BEA': {'dash': (7, 3), 'lw': 2.8},
    'LAW': {'dash': None,   'lw': 2.8},
    'HAD': {'dash': (7, 3), 'lw': 2.8},
    'SAI': {'dash': None,   'lw': 2.4},
    'COL': {'dash': (7, 3), 'lw': 2.4},
    'VER': {'dash': (3, 2, 7, 2), 'lw': 2.8},
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

# SC検出
rcm = session.race_control_messages
sc_periods = []
current_sc_start = None
if rcm is not None:
    for _, row in rcm.iterrows():
        msg = str(row.get('Message', ''))
        lap = row.get('Lap', None)
        if lap is not None:
            lap = int(lap)
            if 'SAFETY CAR DEPLOYED' in msg:
                current_sc_start = lap
            elif 'SAFETY CAR IN THIS LAP' in msg and current_sc_start is not None:
                sc_periods.append((current_sc_start, lap))
                current_sc_start = None
    if current_sc_start is not None:
        sc_periods.append((current_sc_start, current_sc_start + 2))

print(f'レース: {race_laps}周, SC: {sc_periods}')

# ============================================================
# ギャップ計算
# ============================================================
ref_laps = laps_all[laps_all['Driver'] == REF_DRIVER].sort_values('LapNumber')
ref_times = {}
for _, row in ref_laps.iterrows():
    lap = int(row['LapNumber'])
    t = row['Time']
    if pd.notna(t):
        ref_times[lap] = t.total_seconds()

driver_gaps = {}
all_pit_laps = {}

for drv in TARGET_DRIVERS:
    drv_laps = laps_all[laps_all['Driver'] == drv].sort_values('LapNumber')
    if len(drv_laps) == 0:
        continue
    all_pit_laps[drv] = drv_laps[drv_laps['PitInTime'].notna()]['LapNumber'].astype(int).tolist()
    gaps = {}
    for _, row in drv_laps.iterrows():
        lap = int(row['LapNumber'])
        t = row['Time']
        if pd.notna(t) and lap in ref_times:
            gaps[lap] = t.total_seconds() - ref_times[lap]
    if gaps:
        driver_gaps[drv] = gaps

for drv in TARGET_DRIVERS:
    if drv in driver_gaps:
        g = driver_gaps[drv]
        last = max(g.keys())
        print(f'  {drv}: L{last} gap={g[last]:+.1f}s  pits={all_pit_laps.get(drv, [])}')

# ============================================================
# プロット
# ============================================================
print('\nチャート描画中...')

fig, ax = plt.subplots(figsize=(12, 6.75), facecolor=BG)
ax.set_facecolor(BG)

ax.tick_params(colors=TEXT_DIM, labelsize=11, length=4)
ax.xaxis.set_major_locator(MultipleLocator(5))
ax.xaxis.set_minor_locator(MultipleLocator(1))
ax.grid(True, which='major', color=GRID_MAJ, linewidth=0.7, alpha=1.0)
ax.grid(True, which='minor', color=GRID_MIN, linewidth=0.3, alpha=0.7)
for spine in ax.spines.values():
    spine.set_color(SPINE)

ax.set_ylabel(f'Gap to {REF_DRIVER} (秒)', color=TEXT_DIM, fontsize=13)
ax.set_xlabel('Lap', color=TEXT_DIM, fontsize=13)

# Y軸範囲
stable_gaps = []
for drv in TARGET_DRIVERS:
    if drv in driver_gaps:
        for lap, gap in driver_gaps[drv].items():
            if lap >= 14:
                stable_gaps.append(gap)
y_top = -3
y_bot = max(stable_gaps) + 8 if stable_gaps else 120
ax.set_ylim(y_bot, y_top)
ax.set_xlim(0.5, race_laps + 8)

# SC帯
for start, end in sc_periods:
    ax.axvspan(start - 0.5, end + 0.5, alpha=0.15, color=SC_COLOR, zorder=0)

# ANT = 0 基準線
ax.axhline(0, color=COLORS['ANT'], linewidth=1.0, alpha=0.25, zorder=1)

# --- グループ内ドライバーライン ---
for drv in TARGET_DRIVERS:
    if drv not in driver_gaps or drv in SPECIAL_DRIVERS:
        continue
    gaps = driver_gaps[drv]
    color = COLORS[drv]
    style = LINE_STYLES[drv]

    lap_nums = sorted(gaps.keys())
    gap_vals = [gaps[l] for l in lap_nums]

    kwargs = dict(color=color, linewidth=style['lw'], alpha=0.92, zorder=10,
                  solid_capstyle='round', clip_on=True)
    if style['dash']:
        kwargs['dashes'] = style['dash']

    ax.plot(lap_nums, gap_vals, **kwargs)

    for pl in all_pit_laps.get(drv, []):
        if pl in gaps and y_top <= gaps[pl] <= y_bot:
            ax.plot(pl, gaps[pl], 'v', color=color, markersize=7, alpha=0.9, zorder=11)

# --- VER（特別描画） ---
if 'VER' in driver_gaps:
    gaps = driver_gaps['VER']
    color = COLORS['VER']
    style = LINE_STYLES['VER']
    lap_nums = sorted(gaps.keys())
    gap_vals = [gaps[l] for l in lap_nums]

    kwargs = dict(color=color, linewidth=style['lw'], alpha=0.85, zorder=9,
                  solid_capstyle='round', clip_on=True)
    if style['dash']:
        kwargs['dashes'] = style['dash']
    ax.plot(lap_nums, gap_vals, **kwargs)

    for pl in all_pit_laps.get('VER', []):
        if pl in gaps and y_top <= gaps[pl] <= y_bot:
            ax.plot(pl, gaps[pl], 'v', color=color, markersize=7, alpha=0.9, zorder=11)

    # リタイアマーカー
    last_lap = max(gaps.keys())
    last_gap = gaps[last_lap]
    ax.plot(last_lap, last_gap, 'X', color=color, markersize=12,
            markeredgewidth=2.5, markeredgecolor='white', zorder=12)

    # VERリタイア注釈
    ax.annotate(f'VER DNF L{last_lap}', (last_lap, last_gap),
                xytext=(-12, 14), textcoords='offset points',
                fontsize=11, fontweight='bold', color=color,
                va='bottom', ha='center', zorder=15,
                bbox=dict(boxstyle='round,pad=0.3', facecolor=BG,
                          edgecolor=color, alpha=0.9, linewidth=1.2),
                arrowprops=dict(arrowstyle='->', color=color, lw=1.5))

# --- 末尾ラベル + グループブラケット ---
fig.canvas.draw()

# 全ドライバーの末尾ラベル情報を収集（display座標で重複回避）
all_end_labels = []  # (drv, last_lap, last_gap, color, pos, group_idx)
for gi, grp in enumerate(GROUPS):
    for drv in grp['drivers']:
        if drv not in driver_gaps:
            continue
        gaps = driver_gaps[drv]
        last_lap = max(gaps.keys())
        last_gap = gaps[last_lap]
        color = COLORS[drv]
        pos = drv_pos.get(drv, '')
        all_end_labels.append((drv, last_lap, last_gap, color, pos, gi))

# display座標でソート（画面上 → 下）
all_end_disp = []
for drv, last_lap, real_y, color, pos, gi in all_end_labels:
    disp_y = ax.transData.transform((0, real_y))[1]
    all_end_disp.append((drv, last_lap, real_y, color, pos, gi, disp_y))
all_end_disp.sort(key=lambda x: -x[6])  # display Y大 = 画面上が先

# 重複回避して配置
min_disp_gap = 18
placed_disp_y = []

for drv, last_lap, real_y, color, pos, gi, orig_disp_y in all_end_disp:
    target_disp_y = orig_disp_y
    for prev_dy in placed_disp_y:
        if prev_dy - target_disp_y < min_disp_gap:
            target_disp_y = prev_dy - min_disp_gap
    placed_disp_y.append(target_disp_y)
    oy = target_disp_y - orig_disp_y

    # ラベルテキスト: "P2 RUS +6s" 形式
    if drv == REF_DRIVER:
        label_text = f'P{pos} {drv}'
    else:
        gap_sec = real_y
        label_text = f'P{pos} {drv} +{gap_sec:.0f}s'

    ax.annotate(label_text, (last_lap, real_y),
                xytext=(12, oy), textcoords='offset points',
                fontsize=13, fontweight='bold', color=color,
                va='center', ha='left', zorder=15,
                arrowprops=dict(arrowstyle='-', color=color, alpha=0.3, lw=0.5)
                if abs(oy) > 4 else None)

# グループ帯（薄いハイライトのみ、ブラケットなし）
for gi, grp in enumerate(GROUPS):
    band_color = GROUP_BAND_COLORS[gi]
    g_gaps = []
    for drv in grp['drivers']:
        if drv in driver_gaps:
            gaps = driver_gaps[drv]
            g_gaps.append(gaps[max(gaps.keys())])
    if not g_gaps:
        continue

    g_top = min(g_gaps) - 2.0
    g_bot = max(g_gaps) + 2.0
    ax.axhspan(g_top, g_bot, alpha=0.03, color=band_color, zorder=0)

# SC ラベル
for start, end in sc_periods:
    ax.text((start + end) / 2, y_top + 0.5, 'SC', ha='center', va='bottom',
            fontsize=11, color='#DDAA22', fontweight='bold', alpha=0.9)

# --- タイトル（シンプル） ---
ax.set_title(
    f'2026 R2 China GP -- Gap to {REF_DRIVER} (Top 10 Drivers + VER)',
    color=TEXT, fontsize=20, fontweight='bold', pad=14, loc='center'
)

# ============================================================
# 保存
# ============================================================
plt.tight_layout()
path = OUT_DIR / 'x_gap_4groups.png'
fig.savefig(path, dpi=180, facecolor=BG, bbox_inches='tight')
size_kb = path.stat().st_size / 1024
print(f'\n保存: {path} ({size_kb:.0f} KB)')
plt.close(fig)
print('完了')
