"""
============================================================
2026 オーストラリアGP — 記事用チャート一括生成（ライトテーマ）
============================================================
Google Docs / PDF 記事向けに視認性を最適化したチャートを生成。

出力:
  1. art_gap_top6.png      — Top 6 ギャップ推移
  2. art_laptime_delta.png  — RUS vs LEC ラップタイム / デルタ / スピードトラップ
  3. art_speed_boxplot.png  — RUS vs LEC スピード分布（箱ひげ図）
  4. art_sector_compare.png — RUS vs LEC セクター比較 (S1 / S2 / S3)
"""

import fastf1
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
from matplotlib.gridspec import GridSpec
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# GP設定
# ============================================================
YEAR = 2026
GP_NAME = 'Australia'
ROUND_NUMBER = 1
DRV1, DRV2 = 'RUS', 'LEC'

OUT_DIR = Path(f'./data/{YEAR}_R{ROUND_NUMBER:02d}_{GP_NAME}/article')
OUT_DIR.mkdir(parents=True, exist_ok=True)

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
    'vsc':      '#FFD700',
    'vsc_alpha': 0.20,
    'title_size': 18,
    'label_size': 13,
    'tick_size':  11,
    'line_w':     2.8,
    'line_w_thin': 1.5,
    'marker_s':   35,
    'marker_s_sm': 20,
}

# チームカラー（ライト背景用に調整）
TEAM_COLORS = {
    'McLaren': '#E07800', 'Ferrari': '#DC0000', 'Red Bull Racing': '#2B5DAB',
    'Mercedes': '#00B89F', 'Aston Martin': '#1B7A5A', 'Williams': '#3BA3E0',
    'Racing Bulls': '#4A72CC', 'Alpine': '#0078AA', 'Haas F1 Team': '#7A7A7A',
    'Audi': '#3AAA3A', 'Cadillac': '#888888',
}

TYRE_COLORS = {
    'SOFT': '#DD2222', 'MEDIUM': '#CCAA00', 'HARD': '#555555',
    'INTERMEDIATE': '#2E9440', 'WET': '#0060B0',
}

TEAMMATE_DASH = {
    'ANT': (5, 2.5), 'HAM': (5, 2.5), 'VER': (5, 2.5),
    'BEA': (5, 2.5), 'COL': (5, 2.5), 'SAI': (5, 2.5),
    'LAW': (5, 2.5), 'BOR': (5, 2.5), 'BOT': (5, 2.5),
    'STR': (5, 2.5), 'HAD': (5, 2.5),
}

SPEED_COLS = ['SpeedI1', 'SpeedI2', 'SpeedFL', 'SpeedST']
SPEED_SHORT = ['S1末端', 'S2末端', 'FL', 'ST']

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

# VSC検出
rcm = session.race_control_messages
vsc_periods = []
current_vsc_start = None
if rcm is not None:
    for _, row in rcm.iterrows():
        msg = str(row.get('Message', ''))
        lap = row.get('Lap', None)
        if lap is not None:
            lap = int(lap)
            if 'VSC DEPLOYED' in msg:
                current_vsc_start = lap
            elif 'VSC ENDING' in msg and current_vsc_start is not None:
                vsc_periods.append((current_vsc_start, lap))
                current_vsc_start = None
    if current_vsc_start is not None:
        vsc_periods.append((current_vsc_start, current_vsc_start + 1))

vsc_lap_set = set()
for start, end in vsc_periods:
    for l in range(start, end + 2):
        vsc_lap_set.add(l)

print(f'レース: {race_laps}周, VSC: {vsc_periods}')

# 全ドライバーデータ構築
all_driver_data = {}
all_pit_laps = {}
all_clean_data = {}

for _, r in results.iterrows():
    drv = r['Abbreviation']
    df = laps_all[laps_all['Driver'] == drv].copy().sort_values('LapNumber')
    if len(df) == 0:
        continue
    df['LapTimeSec'] = df['LapTime'].dt.total_seconds()
    df['S1Sec'] = df['Sector1Time'].dt.total_seconds()
    df['S2Sec'] = df['Sector2Time'].dt.total_seconds()
    df['S3Sec'] = df['Sector3Time'].dt.total_seconds()
    df['LapNum'] = df['LapNumber'].astype(int)
    all_driver_data[drv] = df
    all_pit_laps[drv] = df[df['PitInTime'].notna()]['LapNum'].tolist()

    pit_in_set = set(all_pit_laps[drv])
    pit_out_set = set(df[df['PitOutTime'].notna()]['LapNum'].tolist())
    exclude = vsc_lap_set | pit_in_set | pit_out_set | {1}
    all_clean_data[drv] = df[~df['LapNum'].isin(exclude)].copy()

# ギャップ計算（Top6用）
leader_drv = results.iloc[0]['Abbreviation']
leader_laps = laps_all[laps_all['Driver'] == leader_drv].sort_values('LapNumber')
leader_times = {}
for _, row in leader_laps.iterrows():
    lap = int(row['LapNumber'])
    t = row['Time']
    if pd.notna(t):
        leader_times[lap] = t.total_seconds()

driver_gaps = {}
driver_order = results['Abbreviation'].tolist()
for drv in driver_order:
    drv_laps = laps_all[laps_all['Driver'] == drv].sort_values('LapNumber')
    gaps = {}
    for _, row in drv_laps.iterrows():
        lap = int(row['LapNumber'])
        t = row['Time']
        if pd.notna(t) and lap in leader_times:
            gaps[lap] = t.total_seconds() - leader_times[lap]
    if gaps:
        driver_gaps[drv] = gaps

# 比較ドライバーの色
color1 = TEAM_COLORS.get(drv_team.get(DRV1, ''), '#444')
color2 = TEAM_COLORS.get(drv_team.get(DRV2, ''), '#444')
colors = {DRV1: color1, DRV2: color2}

# ============================================================
# 共通ユーティリティ
# ============================================================
def setup_ax_light(ax, ylabel=None, title=None, xlabel=None):
    """ライトテーマの軸設定"""
    ax.set_facecolor(LT['bg'])
    ax.tick_params(colors=LT['axis'], labelsize=LT['tick_size'])
    ax.xaxis.set_major_locator(MultipleLocator(5))
    ax.grid(True, which='major', color=LT['grid_maj'], linewidth=0.6, alpha=0.8)
    ax.grid(True, which='minor', color=LT['grid_min'], linewidth=0.3, alpha=0.5)
    for spine in ax.spines.values():
        spine.set_color(LT['spine'])
    if ylabel:
        ax.set_ylabel(ylabel, color=LT['text'], fontsize=LT['label_size'])
    if title:
        ax.set_title(title, color=LT['text'], fontsize=LT['title_size'],
                      fontweight='bold', pad=14)
    if xlabel:
        ax.set_xlabel(xlabel, color=LT['text'], fontsize=LT['label_size'])


def add_vsc(ax, label_y=None):
    """VSC帯"""
    for start, end in vsc_periods:
        ax.axvspan(start - 0.5, end + 0.5, alpha=LT['vsc_alpha'], color=LT['vsc'], zorder=0)
    if label_y is not None:
        for start, end in vsc_periods:
            ax.text((start + end) / 2, label_y, 'VSC', ha='center', va='bottom',
                    fontsize=10, color='#B8960A', fontweight='bold', alpha=0.9)


def add_pit_lines(ax, drv, color, label=False, y_pos=None):
    """ピットイン破線"""
    for pl in all_pit_laps.get(drv, []):
        ax.axvline(pl, color=color, linestyle='--', alpha=0.6, linewidth=1.5, zorder=1)
        if label and y_pos is not None:
            ax.text(pl, y_pos, f'{drv} PIT L{pl}', ha='center', va='top',
                    fontsize=9, fontweight='bold', color=color, alpha=0.9,
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                              edgecolor=color, alpha=0.85, linewidth=1.0))


def save_fig(fig, name):
    path = OUT_DIR / name
    fig.savefig(path, dpi=180, facecolor=LT['bg'], bbox_inches='tight')
    size_kb = path.stat().st_size / 1024
    print(f'  保存: {path} ({size_kb:.0f} KB)')
    plt.close(fig)


def adjust_label_positions(labels, min_gap=3.5):
    labels.sort(key=lambda x: x[1])
    adjusted = []
    for item in labels:
        drv, y, color, alpha = item
        if adjusted and (y - adjusted[-1][1]) < min_gap:
            y = adjusted[-1][1] + min_gap
        adjusted.append((drv, y, color, alpha))
    return adjusted


# ============================================================
# Chart 1: Top 6 ギャップ推移
# ============================================================
print('\n[1/4] Top 6 ギャップ推移...')
fig1, ax1 = plt.subplots(figsize=(16, 8), facecolor=LT['bg'])
setup_ax_light(ax1, ylabel='Gap to RUS (秒)',
               title=f'{YEAR} R{ROUND_NUMBER} {GP_NAME} GP -- リーダーとのギャップ推移 (Top 6)')

top6 = driver_order[:6]

all_gaps_top6 = []
for drv in top6:
    if drv in driver_gaps:
        all_gaps_top6.extend(driver_gaps[drv].values())
if all_gaps_top6:
    y_max = max(all_gaps_top6) * 1.1 + 3
    y_min = min(all_gaps_top6) - 2
    ax1.set_ylim(y_max, y_min)  # 反転
ax1.set_xlim(0, race_laps + 4)
ax1.xaxis.set_minor_locator(MultipleLocator(1))

add_vsc(ax1)  # VSC帯のみ（テキストラベルなし）

for drv in top6:
    if drv not in driver_gaps:
        continue
    gaps = driver_gaps[drv]
    team = drv_team.get(drv, '')
    color = TEAM_COLORS.get(team, '#888')
    dashes = TEAMMATE_DASH.get(drv, None)
    lap_nums = sorted(gaps.keys())
    gap_vals = [gaps[l] for l in lap_nums]
    kwargs = dict(color=color, linewidth=LT['line_w'], alpha=0.95, zorder=10,
                  solid_capstyle='round')
    if dashes:
        kwargs['dashes'] = dashes
    ax1.plot(lap_nums, gap_vals, **kwargs)
    for pl in all_pit_laps.get(drv, []):
        if pl in gaps:
            ax1.plot(pl, gaps[pl], 'v', color=color, markersize=8, alpha=0.9, zorder=11)

# ピットイン縦線 + ラベル（Top6全員分）
# 全PITラベルを(lap, drv, color)で収集し、fig座標で重複回避
pit_labels_all = []
for drv in top6:
    team = drv_team.get(drv, '')
    color = TEAM_COLORS.get(team, '#888')
    for pl in all_pit_laps.get(drv, []):
        ax1.axvline(pl, color=color, linestyle=':', alpha=0.4, linewidth=1.0, zorder=2)
        pit_labels_all.append((pl, drv, color))

# PITラベルをX位置でソートし、重複回避（transform経由でfig座標比較）
pit_labels_all.sort(key=lambda x: (x[0], x[1]))
placed_fig_coords = []  # (fig_x, fig_y) of placed labels
fig1.canvas.draw()  # transformを有効化
trans = ax1.transData + fig1.transFigure.inverted()

for pl, drv, clr in pit_labels_all:
    # 基本Y位置（反転軸: y_minが上端）
    base_y = y_min + 1.0
    # fig座標に変換して既存ラベルとの重複チェック
    row = 0
    while True:
        test_y = base_y + row * 3.5
        fx, fy = trans.transform((pl, test_y))
        collision = False
        for pfx, pfy in placed_fig_coords:
            if abs(fx - pfx) < 0.04 and abs(fy - pfy) < 0.025:
                collision = True
                break
        if not collision:
            break
        row += 1
    placed_fig_coords.append((fx, fy))
    ax1.text(pl, test_y, f'{drv} PIT', ha='center', va='bottom',
             fontsize=7.5, fontweight='bold', color=clr, alpha=0.9,
             bbox=dict(boxstyle='round,pad=0.15', facecolor='white',
                       edgecolor=clr, alpha=0.85, linewidth=0.7))

# 末尾ラベル（display座標で重複回避）
end_labels = []
for drv in top6:
    if drv in driver_gaps:
        gaps = driver_gaps[drv]
        last_lap = max(gaps.keys())
        last_gap = gaps[last_lap]
        team = drv_team.get(drv, '')
        color = TEAM_COLORS.get(team, '#888')
        end_labels.append((drv, last_gap, color))

fig1.canvas.draw()
# display座標のY位置を取得してソート（画面上の上→下順）
end_labels_disp = []
for drv, real_y, color in end_labels:
    disp_y = ax1.transData.transform((0, real_y))[1]
    end_labels_disp.append((drv, real_y, color, disp_y))
end_labels_disp.sort(key=lambda x: -x[3])  # display Y大=画面上が先

min_disp_gap = 16  # ピクセル単位の最小間隔
placed_disp_y = []
for drv, real_y, color, orig_disp_y in end_labels_disp:
    gaps = driver_gaps[drv]
    last_lap = max(gaps.keys())
    status_str = str(drv_status.get(drv, ''))
    if 'Retired' in status_str:
        ax1.plot(last_lap, real_y, 'x', color=color, markersize=9,
                 markeredgewidth=2.5, zorder=12)
    # 配置位置を調整（上から詰めていく）
    target_disp_y = orig_disp_y
    for prev_dy in placed_disp_y:
        if prev_dy - target_disp_y < min_disp_gap:
            target_disp_y = prev_dy - min_disp_gap
    placed_disp_y.append(target_disp_y)
    oy = target_disp_y - orig_disp_y  # display座標の差 = offset points相当
    ax1.annotate(drv, (last_lap, real_y), xytext=(12, oy),
                 textcoords='offset points', fontsize=11, fontweight='bold',
                 color=color, va='center', ha='left', zorder=15,
                 arrowprops=dict(arrowstyle='-', color=color, alpha=0.4, lw=0.6)
                 if abs(oy) > 4 else None)

# 凡例
handles, lbls = [], []
from matplotlib.patches import Patch
handles.append(Patch(facecolor=LT['vsc'], alpha=0.4, edgecolor='none'))
lbls.append('VSC')
handles.append(plt.Line2D([0], [0], marker='v', color='#888', markersize=7, linewidth=0))
lbls.append('Pit Stop')
for drv in top6:
    team = drv_team.get(drv, '')
    color = TEAM_COLORS.get(team, '#888')
    dashes = TEAMMATE_DASH.get(drv, None)
    ls = '--' if dashes else '-'
    handles.append(plt.Line2D([0], [0], color=color, linewidth=2.5, linestyle=ls))
    lbls.append(drv)
ax1.legend(handles, lbls, loc='lower left', fontsize=10, facecolor='white',
           edgecolor=LT['spine'], labelcolor=LT['text'], ncol=4, framealpha=0.95)

save_fig(fig1, 'art_gap_top6.png')

# ============================================================
# Chart 2: RUS vs LEC ラップタイム / デルタ / スピードトラップ
# ============================================================
print('[2/4] RUS vs LEC ラップタイム / デルタ / スピードトラップ...')

fig2, (ax2a, ax2b, ax2c) = plt.subplots(3, 1, figsize=(16, 14),
                                          height_ratios=[3, 1, 1.5],
                                          gridspec_kw={'hspace': 0.08},
                                          facecolor=LT['bg'])

DRIVERS = [DRV1, DRV2]
driver_data = {d: all_driver_data[d] for d in DRIVERS}
pit_laps = {d: all_pit_laps[d] for d in DRIVERS}
clean_data = {d: all_clean_data[d] for d in DRIVERS}
both_clean = set(clean_data[DRV1]['LapNum']) & set(clean_data[DRV2]['LapNum'])

for ax in [ax2a, ax2b, ax2c]:
    setup_ax_light(ax)
    add_vsc(ax)

# ラップタイム
for drv in DRIVERS:
    df = driver_data[drv]
    valid = df[df['LapTimeSec'].notna() & (df['LapTimeSec'] < 200)]
    clean_set = set(clean_data[drv]['LapNum'].tolist())
    for stint in valid['Stint'].unique():
        stint_df = valid[valid['Stint'] == stint]
        sc = stint_df[stint_df['LapNum'].isin(clean_set)]
        ax2a.plot(sc['LapNum'], sc['LapTimeSec'], color=colors[drv],
                  linewidth=LT['line_w'], alpha=0.9,
                  label=drv if stint == valid['Stint'].min() else None, zorder=3)
        ax2a.scatter(sc['LapNum'], sc['LapTimeSec'],
                     c=[TYRE_COLORS.get(c, '#888') for c in sc['Compound']],
                     s=LT['marker_s'], edgecolors=colors[drv], linewidths=1.0, zorder=4)
        dirty = stint_df[~stint_df['LapNum'].isin(clean_set)]
        if len(dirty) > 0:
            ax2a.scatter(dirty['LapNum'], dirty['LapTimeSec'],
                         marker='x', c=colors[drv], s=LT['marker_s_sm'], alpha=0.35, zorder=2)

# ピット線
for drv in DRIVERS:
    for axx in [ax2a, ax2b, ax2c]:
        add_pit_lines(axx, drv, colors[drv])

# Y軸フィット
all_ct = pd.concat([clean_data[d]['LapTimeSec'].dropna() for d in DRIVERS])
ax2a.set_ylim(max(all_ct.min() - 1, 75), all_ct.quantile(0.98) + 2)
ax2a.set_ylabel('ラップタイム (秒)', color=LT['text'], fontsize=LT['label_size'])
ax2a.legend(loc='upper right', fontsize=11, framealpha=0.9, facecolor='white',
            edgecolor=LT['spine'], labelcolor=LT['text'])
ax2a.tick_params(labelbottom=False)

# ピットインラベル
y_bottom, y_top = ax2a.get_ylim()
y_range = y_top - y_bottom
for i, drv in enumerate(DRIVERS):
    y_pos = y_top - y_range * (0.03 + 0.08 * i)
    add_pit_lines(ax2a, drv, colors[drv])  # 既に描画済みだがラベルのみ追加
    for pl in pit_laps[drv]:
        ax2a.text(pl, y_pos, f'{drv} PIT L{pl}', ha='center', va='top',
                  fontsize=9, fontweight='bold', color=colors[drv], alpha=0.9,
                  bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                            edgecolor=colors[drv], alpha=0.85, linewidth=1.0))

ax2a.set_title(f'{DRV1} vs {DRV2} ラップタイム / デルタ / スピードトラップ\n'
               f'(丸=クリーン, x=VSC/ピット, 黄帯=VSC, 破線=ピットイン)',
               color=LT['text'], fontsize=LT['title_size'], fontweight='bold', pad=14)

# ギャップサマリー表（パネル1右上）
# RUS-LECのギャップをL26時点とフィニッシュ時点で計算
gap_rus = driver_gaps.get(DRV1, {})
gap_lec = driver_gaps.get(DRV2, {})
# 両者のリーダーとの差の差分 = RUS-LEC間ギャップ
gap_at_l26 = gap_lec.get(26, None)
gap_at_l26_rus = gap_rus.get(26, None)
last_lap_num = max(max(gap_rus.keys(), default=0), max(gap_lec.keys(), default=0))
gap_at_finish = gap_lec.get(last_lap_num, None)
gap_at_finish_rus = gap_rus.get(last_lap_num, None)

if gap_at_l26 is not None and gap_at_l26_rus is not None:
    rus_lec_gap_l26 = gap_at_l26 - gap_at_l26_rus
    rus_lec_gap_finish = (gap_at_finish or 0) - (gap_at_finish_rus or 0)
    gap_diff = rus_lec_gap_finish - rus_lec_gap_l26

    # テーブルデータ
    table_data = [
        ['L26', f'{rus_lec_gap_l26:+.3f}s'],
        [f'L{last_lap_num}', f'{rus_lec_gap_finish:+.3f}s'],
        ['差分', f'{gap_diff:+.3f}s'],
    ]
    tbl = ax2a.table(cellText=table_data,
                     colLabels=[f'{DRV1}-{DRV2}', 'Gap'],
                     loc='upper right',
                     bbox=[0.72, 0.52, 0.27, 0.34])
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(10)
    for (row, col), cell in tbl.get_celld().items():
        cell.set_edgecolor('white')
        cell.set_linewidth(1.0)
        cell.PAD = 0.03
        if row == 0:
            cell.set_facecolor('#2B3A67')
            cell.set_text_props(fontweight='bold', color='white')
        elif row == len(table_data):
            cell.set_facecolor('#3D5A99')
            cell.set_text_props(fontweight='bold', color='white')
        else:
            cell.set_facecolor('#E8EDF5')
            cell.set_text_props(color=LT['text'])

# デルタ
merged = pd.merge(
    driver_data[DRV1][['LapNum', 'LapTimeSec']].rename(columns={'LapTimeSec': f'{DRV1}_sec'}),
    driver_data[DRV2][['LapNum', 'LapTimeSec']].rename(columns={'LapTimeSec': f'{DRV2}_sec'}),
    on='LapNum', how='inner')
merged['delta'] = merged[f'{DRV1}_sec'] - merged[f'{DRV2}_sec']
merged['is_clean'] = merged['LapNum'].isin(both_clean)
mc = merged[merged['is_clean']]

ax2b.bar(mc['LapNum'], mc['delta'],
         color=[colors[DRV1] if d < 0 else colors[DRV2] for d in mc['delta']],
         alpha=0.75, width=0.8, zorder=3)
ax2b.axhline(0, color=LT['axis'], linewidth=1.0, alpha=0.5)
ax2b.set_ylabel(f'Delta (秒)\n{DRV1} < 0 < {DRV2}', color=LT['text'],
                fontsize=LT['label_size'] - 1)
if len(mc) > 0:
    d_max = max(abs(mc['delta'].min()), abs(mc['delta'].max())) + 0.5
    ax2b.set_ylim(-d_max, d_max)
ax2b.tick_params(labelbottom=False)

# スピードトラップ
for drv in DRIVERS:
    clean = clean_data[drv]
    cs = clean[clean['SpeedST'].notna()].sort_values('LapNum')
    for stint in sorted(cs['Stint'].unique()):
        sc = cs[cs['Stint'] == stint]
        ax2c.plot(sc['LapNum'], sc['SpeedST'], color=colors[drv],
                  linewidth=LT['line_w'] - 0.5, alpha=0.85, zorder=3,
                  label=drv if stint == sorted(cs['Stint'].unique())[0] else None)
        ax2c.scatter(sc['LapNum'], sc['SpeedST'],
                     c=[TYRE_COLORS.get(c, '#888') for c in sc['Compound']],
                     s=LT['marker_s_sm'], edgecolors=colors[drv], linewidths=0.8, zorder=4)

all_st = pd.concat([clean_data[d]['SpeedST'].dropna() for d in DRIVERS])
st_m = (all_st.max() - all_st.min()) * 0.12 + 3
ax2c.set_ylim(all_st.min() - st_m, all_st.max() + st_m)
ax2c.set_xlabel('ラップ数', color=LT['text'], fontsize=LT['label_size'])
ax2c.set_ylabel('スピードトラップ (km/h)', color=LT['text'], fontsize=LT['label_size'])
ax2c.legend(loc='lower right', fontsize=10, framealpha=0.9, facecolor='white',
            edgecolor=LT['spine'], labelcolor=LT['text'])

# L26以降のRUSスピードトラップ優位を点線四角形で強調
from matplotlib.patches import FancyBboxPatch
st_y_lo, st_y_hi = ax2c.get_ylim()
rect = plt.Rectangle((25.5, st_y_lo + (st_y_hi - st_y_lo) * 0.05),
                      last_lap_num - 25, (st_y_hi - st_y_lo) * 0.88,
                      linewidth=2, edgecolor=colors[DRV1], facecolor='none',
                      linestyle='--', alpha=0.8, zorder=8)
ax2c.add_patch(rect)
# キャプション
ax2c.text(last_lap_num + 0.5, st_y_hi - (st_y_hi - st_y_lo) * 0.08,
          f'L26以降: {DRV1}が{DRV2}より\n安定して高い速度を記録',
          fontsize=10, color=colors[DRV1], fontweight='bold',
          ha='right', va='top',
          bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                    edgecolor=colors[DRV1], alpha=0.9, linewidth=1.2))

save_fig(fig2, 'art_laptime_delta.png')

# ============================================================
# Chart 3: スピード分布（箱ひげ図）+ 凡例 + 脚注
# ============================================================
print('[3/4] スピード分布（箱ひげ図）...')

fig3 = plt.figure(figsize=(14, 7), facecolor=LT['bg'])
gs3 = GridSpec(1, 5, figure=fig3, wspace=0.4)
ax3 = fig3.add_subplot(gs3[0, :3])
ax3_leg = fig3.add_subplot(gs3[0, 3])
# 4列目は空白（余白）

ax3.set_facecolor(LT['bg'])
ax3.tick_params(colors=LT['axis'], labelsize=LT['tick_size'])
ax3.grid(True, axis='y', color=LT['grid_maj'], linewidth=0.6, alpha=0.8)
for spine in ax3.spines.values():
    spine.set_color(LT['spine'])

bp1_data = [all_clean_data[DRV1][col].dropna().values for col in SPEED_COLS]
bp2_data = [all_clean_data[DRV2][col].dropna().values for col in SPEED_COLS]
pos1 = np.arange(len(SPEED_COLS)) * 3
pos2 = pos1 + 1

bp1 = ax3.boxplot(bp1_data, positions=pos1, widths=0.8, patch_artist=True,
                   showfliers=True, flierprops={'markersize': 4})
bp2 = ax3.boxplot(bp2_data, positions=pos2, widths=0.8, patch_artist=True,
                   showfliers=True, flierprops={'markersize': 4})
for patch in bp1['boxes']:
    patch.set_facecolor(color1); patch.set_alpha(0.5); patch.set_edgecolor(color1)
for patch in bp2['boxes']:
    patch.set_facecolor(color2); patch.set_alpha(0.5); patch.set_edgecolor(color2)
for elem in ['whiskers', 'caps']:
    for line in bp1[elem]: line.set_color(LT['axis'])
    for line in bp2[elem]: line.set_color(LT['axis'])
for line in bp1['medians']: line.set_color(color1); line.set_linewidth(2)
for line in bp2['medians']: line.set_color(color2); line.set_linewidth(2)

ax3.set_xticks(pos1 + 0.5)
ax3.set_xticklabels(SPEED_SHORT, fontsize=LT['label_size'])
ax3.set_ylabel('速度 (km/h)', color=LT['text'], fontsize=LT['label_size'])
ax3.set_title('スピード分布比較 (クリーンラップ)', color=LT['text'],
              fontsize=LT['title_size'], fontweight='bold', pad=14)
ax3.legend([bp1['boxes'][0], bp2['boxes'][0]], [DRV1, DRV2],
           loc='upper left', fontsize=11, framealpha=0.9, facecolor='white',
           edgecolor=LT['spine'], labelcolor=LT['text'])

# 脚注
footnote = ('S1末端=Sector1終点の通過速度  S2末端=Sector2終点の通過速度\n'
            'FL=フィニッシュライン通過速度  ST=スピードトラップ(FIA最高速計測点)')
ax3.text(0.5, -0.10, footnote, transform=ax3.transAxes, fontsize=9,
         color='#666', ha='center', va='top', style='italic')

# 箱ひげ図の読み方（独立パネル）
ax3_leg.set_facecolor(LT['bg'])
ax3_leg.set_xlim(0, 10)
ax3_leg.set_ylim(0, 10)
ax3_leg.set_xticks([])
ax3_leg.set_yticks([])
for spine in ax3_leg.spines.values():
    spine.set_color(LT['spine'])
    spine.set_linewidth(0.5)

bx, bw = 2.8, 1.8
q1, med, q3 = 2.5, 4.5, 6.2
whi_lo, whi_hi = 1.2, 8.0
outlier_y = 9.2

lc = '#444444'
ax3_leg.plot([bx, bx], [whi_lo, q1], color=lc, linewidth=1.2)
ax3_leg.plot([bx, bx], [q3, whi_hi], color=lc, linewidth=1.2)
ax3_leg.plot([bx - 0.4, bx + 0.4], [whi_lo, whi_lo], color=lc, linewidth=1.2)
ax3_leg.plot([bx - 0.4, bx + 0.4], [whi_hi, whi_hi], color=lc, linewidth=1.2)
box_rect = plt.Rectangle((bx - bw/2, q1), bw, q3 - q1,
                           facecolor='#BBCCDD', edgecolor=lc, linewidth=1.2, alpha=0.7)
ax3_leg.add_patch(box_rect)
ax3_leg.plot([bx - bw/2, bx + bw/2], [med, med], color='#CC3333', linewidth=2)
ax3_leg.plot(bx, outlier_y, 'o', color=lc, markersize=5, markerfacecolor='none')

tx = 5.5
annot = dict(fontsize=8, color=LT['text'], va='center', ha='left')
arrow = dict(arrowstyle='-', color='#888', lw=0.5)
ax3_leg.annotate('外れ値', xy=(bx + 0.3, outlier_y), xytext=(tx, outlier_y),
                  arrowprops=arrow, **annot)
ax3_leg.annotate('上ひげ(最大値*)', xy=(bx + 0.5, whi_hi), xytext=(tx, whi_hi),
                  arrowprops=arrow, **annot)
ax3_leg.annotate('Q3 (75%)', xy=(bx + bw/2 + 0.1, q3), xytext=(tx, q3),
                  arrowprops=arrow, **annot)
ax3_leg.annotate('中央値', xy=(bx + bw/2 + 0.1, med), xytext=(tx, med),
                  arrowprops=dict(arrowstyle='-', color='#CC3333', lw=0.5),
                  fontsize=8, color='#CC3333', va='center', ha='left')
ax3_leg.annotate('Q1 (25%)', xy=(bx + bw/2 + 0.1, q1), xytext=(tx, q1),
                  arrowprops=arrow, **annot)
ax3_leg.annotate('下ひげ(最小値*)', xy=(bx + 0.5, whi_lo), xytext=(tx, whi_lo),
                  arrowprops=arrow, **annot)
ax3_leg.text(5.0, 0.3, '*Q1/Q3から箱の1.5倍以内', fontsize=7, color='#888', ha='center')
ax3_leg.set_title('箱ひげ図の見方', fontsize=10, color=LT['text'], pad=6)

save_fig(fig3, 'art_speed_boxplot.png')

# ============================================================
# Chart 4: セクター比較 (S1 / S2 / S3)
# ============================================================
print('[4/4] セクター比較 (S1 / S2 / S3)...')

sectors = [('S1', 'S1Sec', 'Sector 1 (秒)'),
           ('S2', 'S2Sec', 'Sector 2 (秒)'),
           ('S3', 'S3Sec', 'Sector 3 (秒)')]

fig4, axes4 = plt.subplots(6, 1, figsize=(16, 20),
                             height_ratios=[3, 1, 3, 1, 3, 1],
                             gridspec_kw={'hspace': 0.06},
                             facecolor=LT['bg'])

for si, (sec_name, sec_col, sec_ylabel) in enumerate(sectors):
    ax_main = axes4[si * 2]
    ax_delta = axes4[si * 2 + 1]

    for ax in [ax_main, ax_delta]:
        setup_ax_light(ax)
        add_vsc(ax)

    # セクタータイム
    for drv in DRIVERS:
        df = driver_data[drv]
        valid = df[df[sec_col].notna()]
        clean_set = set(clean_data[drv]['LapNum'].tolist())
        for stint in valid['Stint'].unique():
            stint_df = valid[valid['Stint'] == stint]
            sc = stint_df[stint_df['LapNum'].isin(clean_set)]
            ax_main.plot(sc['LapNum'], sc[sec_col], color=colors[drv],
                         linewidth=LT['line_w'], alpha=0.9,
                         label=drv if stint == valid['Stint'].min() else None, zorder=3)
            ax_main.scatter(sc['LapNum'], sc[sec_col],
                            c=[TYRE_COLORS.get(c, '#888') for c in sc['Compound']],
                            s=LT['marker_s'], edgecolors=colors[drv], linewidths=1.0, zorder=4)
            dirty = stint_df[~stint_df['LapNum'].isin(clean_set)]
            if len(dirty) > 0:
                ax_main.scatter(dirty['LapNum'], dirty[sec_col],
                                marker='x', c=colors[drv], s=LT['marker_s_sm'], alpha=0.35, zorder=2)

    # ピット線
    for drv in DRIVERS:
        for ax in [ax_main, ax_delta]:
            add_pit_lines(ax, drv, colors[drv])

    # Y軸
    all_clean_vals = pd.concat([clean_data[d][sec_col].dropna() for d in DRIVERS])
    margin = (all_clean_vals.max() - all_clean_vals.min()) * 0.12 + 0.2
    ax_main.set_ylim(all_clean_vals.min() - margin, all_clean_vals.max() + margin)
    ax_main.set_ylabel(sec_ylabel, color=LT['text'], fontsize=LT['label_size'])
    ax_main.tick_params(labelbottom=False)

    # ピットラベル・凡例（最上段のみ）
    if si == 0:
        y_bottom, y_top = ax_main.get_ylim()
        y_range = y_top - y_bottom
        for i, drv in enumerate(DRIVERS):
            for pl in pit_laps[drv]:
                y_pos = y_top - y_range * (0.03 + 0.08 * i)
                ax_main.text(pl, y_pos, f'{drv} PIT L{pl}', ha='center', va='top',
                             fontsize=9, fontweight='bold', color=colors[drv], alpha=0.9,
                             bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                                       edgecolor=colors[drv], alpha=0.85, linewidth=1.0))
        ax_main.legend(loc='upper right', fontsize=11, framealpha=0.9, facecolor='white',
                       edgecolor=LT['spine'], labelcolor=LT['text'])
        ax_main.set_title(f'{DRV1} vs {DRV2} セクター比較 (S1 / S2 / S3)\n'
                          f'(丸=クリーン, x=VSC/ピット, 黄帯=VSC, 破線=ピットイン)',
                          color=LT['text'], fontsize=LT['title_size'],
                          fontweight='bold', pad=14)

    # デルタ
    sec_merged = pd.merge(
        driver_data[DRV1][['LapNum', sec_col]].rename(columns={sec_col: f'{DRV1}_sec'}),
        driver_data[DRV2][['LapNum', sec_col]].rename(columns={sec_col: f'{DRV2}_sec'}),
        on='LapNum', how='inner')
    sec_merged['delta'] = sec_merged[f'{DRV1}_sec'] - sec_merged[f'{DRV2}_sec']
    sec_merged['is_clean'] = sec_merged['LapNum'].isin(both_clean)
    smc = sec_merged[sec_merged['is_clean']]

    ax_delta.bar(smc['LapNum'], smc['delta'],
                 color=[colors[DRV1] if d < 0 else colors[DRV2] for d in smc['delta']],
                 alpha=0.75, width=0.8, zorder=3)
    ax_delta.axhline(0, color=LT['axis'], linewidth=1.0, alpha=0.5)
    ax_delta.set_ylabel(f'{sec_name} Delta', color=LT['text'], fontsize=LT['label_size'] - 2)
    if len(smc) > 0:
        d_max = max(abs(smc['delta'].min()), abs(smc['delta'].max())) + 0.2
        ax_delta.set_ylim(-d_max, d_max)

    if si < 2:
        ax_delta.tick_params(labelbottom=False)
    else:
        ax_delta.set_xlabel('ラップ数', color=LT['text'], fontsize=LT['label_size'])

    ax_delta.text(1.01, 0.5, f'{DRV1}<0<{DRV2}', transform=ax_delta.transAxes,
                  fontsize=8, color='#888', va='center', ha='left', rotation=90)

save_fig(fig4, 'art_sector_compare.png')

print(f'\n=== 完了: 記事用チャート4枚を {OUT_DIR} に出力 ===')
