"""
============================================================
2026 オーストラリアGP — PUサプライヤー別スピード分布比較 (v3)
============================================================
v2フォーマット + オーバーテイクモード影響除外版:
  F/L通過時に前車とのギャップが1秒以内だった場合、
  次のラップ（OTモード使用可能ラップ）を除外。
"""

import fastf1
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
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
print('FastF1からデータを読み込み中...')
fastf1.Cache.enable_cache('~/f1_cache')
session = fastf1.get_session(2026, 'Australia', 'R')
session.load(telemetry=False, laps=True, weather=False)
laps_all = session.laps
results = session.results.sort_values('Position')

# VSC
rcm = session.race_control_messages
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

# ============================================================
# オーバーテイクモード対象ラップを特定
# F/L通過時に前車との差が1秒以内 → 次のラップを除外
# ============================================================
print('\nオーバーテイクモード対象ラップを特定中...')
overtake_laps = set()  # (driver, lap_number) のセット
max_lap = int(laps_all['LapNumber'].max())
one_sec = pd.Timedelta(seconds=1)

for lap_num in range(1, max_lap + 1):
    lap_data = laps_all[laps_all['LapNumber'] == lap_num][['Driver', 'Position', 'Time']].dropna(subset=['Time'])
    if len(lap_data) < 2:
        continue
    lap_data = lap_data.sort_values('Time')
    times = lap_data['Time'].values
    drivers = lap_data['Driver'].values

    for i in range(1, len(drivers)):
        gap = times[i] - times[i - 1]
        if gap <= one_sec:
            # 次のラップでOTモード使用可能 → 除外対象
            overtake_laps.add((drivers[i], lap_num + 1))

# ドライバー別OT除外ラップ数を集計
from collections import Counter
ot_counts_by_drv = Counter(drv for drv, _ in overtake_laps)
print(f'OTモード対象ラップ総数: {len(overtake_laps)}')
for drv, cnt in sorted(ot_counts_by_drv.items(), key=lambda x: -x[1]):
    print(f'  {drv}: {cnt} laps')

# PUマッピング
PU_MAP = {
    'Mercedes': 'Mercedes', 'McLaren': 'Mercedes', 'Williams': 'Mercedes',
    'Alpine': 'Mercedes',
    'Ferrari': 'Ferrari', 'Haas F1 Team': 'Ferrari', 'Cadillac': 'Ferrari',
    'Red Bull Racing': 'Red Bull PT', 'Racing Bulls': 'Red Bull PT',
    'Aston Martin': 'Honda', 'Audi': 'Audi',
}

PU_ORDER = ['Mercedes', 'Ferrari', 'Red Bull PT', 'Honda', 'Audi']
PU_COLORS = {
    'Mercedes': '#00B89F', 'Ferrari': '#DC0000', 'Red Bull PT': '#2B5DAB',
    'Honda': '#1B7A5A', 'Audi': '#C92D39',
}

# チームカラー（F1公式準拠）
TEAM_COLORS = {
    'Mercedes': '#27F4D2', 'McLaren': '#FF8700', 'Williams': '#64C4FF',
    'Alpine': '#00A1E8',
    'Ferrari': '#E8002D', 'Haas F1 Team': '#B6BABD', 'Cadillac': '#1E1E1E',
    'Red Bull Racing': '#3671C6', 'Racing Bulls': '#6692FF',
    'Aston Martin': '#229971', 'Audi': '#C92D39',
}

TEAM_EDGE_COLORS = {
    'Haas F1 Team': '#666666',
    'Cadillac': '#555555',
}

drv_team = dict(zip(results['Abbreviation'], results['TeamName']))

# リタイアドライバー（グレーアウト表示、PU平均には含めない）
RETIRED_DRIVERS = set()
for _, r in results.iterrows():
    status = str(r.get('Status', ''))
    if status in ('Retired', 'Did not finish', 'Disqualified') or 'Retired' in status:
        RETIRED_DRIVERS.add(r['Abbreviation'])
print(f'リタイアドライバー: {RETIRED_DRIVERS}')

GREY_COLOR = '#BBBBBB'
GREY_EDGE = '#999999'

# 全クリーンラップデータ（VSC/ピット/Lap1 + OTモードラップを除外）
clean_all = {}
clean_all_with_ot = {}  # 比較用: OT除外なし
excluded_ot_counts = {}  # ドライバー別の実際のOT除外数（クリーンラップからの除外）
for _, r in results.iterrows():
    drv = r['Abbreviation']
    df = laps_all[laps_all['Driver'] == drv].copy().sort_values('LapNumber')
    if len(df) == 0:
        continue
    df['LapNum'] = df['LapNumber'].astype(int)
    pit_in = set(df[df['PitInTime'].notna()]['LapNum'])
    pit_out = set(df[df['PitOutTime'].notna()]['LapNum'])
    base_exclude = vsc_set | pit_in | pit_out | {1}

    # OTなし版（ベースのクリーンラップ）
    c_base = df[~df['LapNum'].isin(base_exclude)]
    if len(c_base) > 3:
        clean_all_with_ot[drv] = c_base

    # OT除外版
    ot_laps_for_drv = {l for d, l in overtake_laps if d == drv}
    ot_exclude = base_exclude | ot_laps_for_drv
    c = df[~df['LapNum'].isin(ot_exclude)]

    # クリーンラップのうちOTで追加除外された数
    ot_actually_excluded = len(c_base) - len(c) if drv in clean_all_with_ot else 0
    excluded_ot_counts[drv] = ot_actually_excluded

    if len(c) > 3:
        clean_all[drv] = c

# 除外サマリー
total_base = sum(len(v) for v in clean_all_with_ot.values())
total_after = sum(len(v) for v in clean_all.values())
total_ot_excluded = sum(excluded_ot_counts.values())
print(f'\nクリーンラップ(OT込み): {total_base}')
print(f'OTモード除外数: {total_ot_excluded}')
print(f'クリーンラップ(OT除外後): {total_after}')

# PUグループ別にドライバー整理（ポジション順）
pu_drivers = {pu: [] for pu in PU_ORDER}
for drv in results['Abbreviation'].tolist():
    team = drv_team.get(drv, '')
    pu = PU_MAP.get(team, '?')
    if pu in pu_drivers and drv in clean_all:
        pu_drivers[pu].append(drv)

print('\nPUグループ:')
for pu in PU_ORDER:
    drivers = pu_drivers[pu]
    if drivers:
        drv_info = [f'{d}({excluded_ot_counts.get(d,0)}除外)' for d in drivers]
        print(f'  {pu}: {", ".join(drv_info)}')

# テーマ
LT = {'bg': '#FFFFFF', 'text': '#1a1a2e', 'axis': '#444444',
      'grid_maj': '#DDDDDD', 'spine': '#AAAAAA'}

SPEED_COLS = ['SpeedST', 'SpeedFL', 'SpeedI1', 'SpeedI2']
SPEED_LABELS = ['ST (スピードトラップ)', 'FL (フィニッシュライン)', 'S1末端', 'S2末端']

# パネル別Y軸範囲を事前計算
print('\nパネル別Y軸範囲を計算中...')
panel_ylims = {}
for scol, slabel in zip(SPEED_COLS, SPEED_LABELS):
    p_min, p_max = 999, 0
    for drv in clean_all:
        data = clean_all[drv][scol].dropna().values
        if len(data) == 0:
            continue
        q1_v = np.percentile(data, 25)
        q3_v = np.percentile(data, 75)
        iqr = q3_v - q1_v
        whisker_lo = data[data >= q1_v - 1.5 * iqr]
        whisker_hi = data[data <= q3_v + 1.5 * iqr]
        if len(whisker_lo) > 0:
            p_min = min(p_min, whisker_lo.min())
        if len(whisker_hi) > 0:
            p_max = max(p_max, whisker_hi.max())
    y_lo = max(220, int(p_min / 5) * 5 - 5)
    y_hi = int(p_max / 5) * 5 + 10
    panel_ylims[scol] = (y_lo, y_hi)
    print(f'  {slabel}: {y_lo} - {y_hi} km/h')

# ==========================================================
# チャート: 2x2グリッド
# ==========================================================
print('\nチャート生成中...')

fig = plt.figure(figsize=(28, 22), facecolor='white')
outer_gs = GridSpec(2, 2, figure=fig, hspace=0.28, wspace=0.15)

for panel_idx, (scol, slabel) in enumerate(zip(SPEED_COLS, SPEED_LABELS)):
    row, col = divmod(panel_idx, 2)
    inner_gs = outer_gs[row, col].subgridspec(2, 1, height_ratios=[3, 0.7], hspace=0.05)
    ax = fig.add_subplot(inner_gs[0])
    ax_tbl = fig.add_subplot(inner_gs[1])

    ax.set_facecolor('white')
    ax.tick_params(colors=LT['axis'], labelsize=11)
    ax.grid(True, axis='y', color=LT['grid_maj'], linewidth=0.5, alpha=0.8)
    for spine in ax.spines.values():
        spine.set_color(LT['spine'])

    drv_stats = {}
    x_pos = 0
    tick_positions = []
    tick_labels_list = []
    group_labels_pos = []
    pu_gap_positions = []
    pu_avg_lines = []

    for pu_idx, pu in enumerate(PU_ORDER):
        drivers = pu_drivers[pu]
        if not drivers:
            continue
        pu_color = PU_COLORS[pu]
        group_start = x_pos

        for di, drv in enumerate(drivers):
            data = clean_all[drv][scol].dropna().values
            if len(data) == 0:
                x_pos += 1
                continue

            q1_v = np.percentile(data, 25)
            q3_v = np.percentile(data, 75)
            iqr = q3_v - q1_v
            inliers = data[(data >= q1_v - 1.5 * iqr) & (data <= q3_v + 1.5 * iqr)]
            drv_stats[drv] = {
                'q1': q1_v,
                'med': np.median(data),
                'q3': q3_v,
                'sd': np.std(inliers, ddof=1) if len(inliers) > 1 else 0,
                'n': len(data),
            }

            team = drv_team.get(drv, '')
            is_retired = drv in RETIRED_DRIVERS

            if is_retired:
                box_color = GREY_COLOR
                edge_color = GREY_EDGE
                box_alpha = 0.35
            else:
                box_color = TEAM_COLORS.get(team, '#888888')
                edge_color = TEAM_EDGE_COLORS.get(team, box_color)
                box_alpha = 0.45 if team in ('Haas F1 Team',) else 0.55

            bp = ax.boxplot([data], positions=[x_pos], widths=0.7,
                            patch_artist=True, showfliers=True,
                            flierprops={'markersize': 3, 'markerfacecolor': 'none',
                                        'markeredgecolor': '#999'})
            for p in bp['boxes']:
                p.set_facecolor(box_color)
                p.set_alpha(box_alpha)
                p.set_edgecolor(edge_color)
                p.set_linewidth(1.5)
            for e in ['whiskers', 'caps']:
                for line in bp[e]:
                    line.set_color(GREY_EDGE if is_retired else LT['axis'])
            for line in bp['medians']:
                line.set_color(GREY_EDGE if is_retired else '#222222')
                line.set_linewidth(2.5)

            tick_positions.append(x_pos)
            label = f'{drv}\n(DNF)' if is_retired else drv
            tick_labels_list.append(label)
            x_pos += 1

        group_end = x_pos - 1
        if group_start <= group_end:
            gc = (group_start + group_end) / 2
            group_labels_pos.append((gc, pu, pu_color, group_start - 0.5, group_end + 0.5))

            # PU平均にはリタイアドライバーを含めない
            pu_meds = [drv_stats[d]['med'] for d in drivers if d in drv_stats and d not in RETIRED_DRIVERS]
            if pu_meds:
                avg_med = np.mean(pu_meds)
                pu_avg_lines.append((group_start - 0.4, group_end + 0.4, avg_med, pu_color))

        gap_width = 1.2
        pu_gap_positions.append((x_pos + gap_width / 2, pu, pu_color))
        x_pos += gap_width + 0.3

    y_lo, y_hi = panel_ylims[scol]
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels_list, fontsize=11, fontweight='bold', rotation=0)
    ax.set_ylim(y_lo, y_hi)
    ax.set_ylabel(f'{slabel} (km/h)', color=LT['text'], fontsize=14, fontweight='bold')
    ax.set_title(slabel, color=LT['text'], fontsize=16, fontweight='bold', pad=10)

    y_min_ax, y_max_ax = ax.get_ylim()
    for gc, pu, color, x_start, x_end in group_labels_pos:
        ax.axvspan(x_start, x_end, alpha=0.10, color=color, zorder=0)
        ax.text(gc, y_max_ax - (y_max_ax - y_min_ax) * 0.03, pu,
                ha='center', va='top', fontsize=12, fontweight='bold',
                color=color, alpha=0.9,
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                          edgecolor=color, alpha=0.85, linewidth=1.2))

    for x_s, x_e, avg_med, pu_color in pu_avg_lines:
        ax.hlines(avg_med, x_s, x_e, colors=pu_color, linestyles='dashed',
                  linewidths=1.8, alpha=0.7, zorder=5)

    # テーブル（Med + SD）
    ax_tbl.set_xlim(ax.get_xlim())
    ax_tbl.set_ylim(-0.3, 2.3)
    ax_tbl.axis('off')

    row_labels = ['Med', 'SD']
    row_y = [1.5, 0.5]

    x_left = ax.get_xlim()[0] + 0.1
    for rl, ry in zip(row_labels, row_y):
        ax_tbl.text(x_left, ry, rl, ha='right', va='center',
                    fontsize=10, fontweight='bold', color='#666666')

    for y_line in [2.0, 1.0, 0.0]:
        ax_tbl.axhline(y_line, color='#E0E0E0', linewidth=0.5, zorder=0)

    for gc, pu, color, x_start, x_end in group_labels_pos:
        ax_tbl.axvspan(x_start, x_end, alpha=0.06, color=color, zorder=0)

    drv_order_flat = []
    for pu in PU_ORDER:
        for d in pu_drivers[pu]:
            if d in drv_stats:
                drv_order_flat.append(d)

    for xi, xp in enumerate(tick_positions):
        if xi >= len(drv_order_flat):
            break
        drv = drv_order_flat[xi]
        if drv not in drv_stats:
            continue

        s = drv_stats[drv]
        is_ret = drv in RETIRED_DRIVERS
        vals = [f'{s["med"]:.0f}', f'{s["sd"]:.1f}']
        for ri, (val, ry) in enumerate(zip(vals, row_y)):
            fw = 'bold' if ri == 0 and not is_ret else 'normal'
            clr = '#BBBBBB' if is_ret else (LT['text'] if ri == 0 else '#555555')
            ax_tbl.text(xp, ry, val, ha='center', va='center',
                        fontsize=10, fontweight=fw, color=clr)

    for gap_x, pu, pu_color in pu_gap_positions:
        drivers = pu_drivers[pu]
        # PU平均にはリタイアドライバーを含めない
        pu_data_all = [drv_stats[d] for d in drivers if d in drv_stats and d not in RETIRED_DRIVERS]
        if not pu_data_all:
            continue

        avg_med = np.mean([s['med'] for s in pu_data_all])
        avg_sd = np.mean([s['sd'] for s in pu_data_all])
        n_drivers = len(pu_data_all)

        ax_tbl.text(gap_x, 2.1, f'Avg\n(n={n_drivers})', ha='center', va='center',
                    fontsize=8, fontweight='bold', color=pu_color, alpha=0.8)

        avg_vals = [f'{avg_med:.0f}', f'{avg_sd:.1f}']
        for ri, (val, ry) in enumerate(zip(avg_vals, row_y)):
            fw = 'bold' if ri == 0 else 'normal'
            ax_tbl.text(gap_x, ry, val, ha='center', va='center',
                        fontsize=10, fontweight=fw, color=pu_color, alpha=0.85)

# 全体タイトル
fig.suptitle('PUサプライヤー別 スピード分布比較 — 2026 オーストラリアGP\n'
             'オーバーテイクモード影響除外 (F/L通過時 前車差1秒以内 → 次周を除外)',
             fontsize=20, fontweight='bold', color=LT['text'], y=0.98)

# 脚注（除外ラップ数を明記）
# ドライバー別除外数の文字列を構築
ot_detail_parts = []
for pu in PU_ORDER:
    for drv in pu_drivers[pu]:
        cnt = excluded_ot_counts.get(drv, 0)
        if cnt > 0:
            ot_detail_parts.append(f'{drv}:{cnt}')
ot_detail_str = ', '.join(ot_detail_parts)

retired_str = ', '.join(sorted(RETIRED_DRIVERS))
fig.text(0.5, 0.005,
         f'OTモード除外: クリーンラップ {total_base} 中 {total_ot_excluded} ラップ除外 '
         f'(残 {total_after}, {total_after/total_base*100:.0f}%)  '
         f'[{ot_detail_str}]\n'
         'PU供給: Mercedes = Mercedes, McLaren, Williams, Alpine  /  Ferrari = Ferrari, Haas, Cadillac  /  '
         'Red Bull PT = Red Bull, Racing Bulls  /  Honda = Aston Martin  /  Audi\n'
         '破線 = PUグループ内の中央値平均  |  箱ひげ図の色 = チームカラー  |  背景帯 = PUサプライヤー\n'
         f'グレー表示 = DNFドライバー ({retired_str}) — 参考値。PU平均には含まず\n'
         '※ SD(標準偏差)の計算には IQR x 1.5 基準で外れ値を除外  |  '
         'OTモード判定: F/L通過時に前車とのギャップが1秒以内 → 次のラップを除外',
         ha='center', va='bottom', fontsize=9, color='#666', style='italic')

out = Path('./data/2026_R01_Australia/article/art_speed_by_pu_v3_no_ot.png')
out.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(out, dpi=180, facecolor='white', bbox_inches='tight', pad_inches=0.5)
size_kb = out.stat().st_size / 1024
print(f'\n保存: {out} ({size_kb:.0f} KB)')
plt.close(fig)

# サマリー: v2 vs v3 の中央値比較
print('\n=== OTモード除外による中央値変化 ===')
for scol, slabel in zip(SPEED_COLS, SPEED_LABELS):
    print(f'\n--- {slabel} ---')
    for pu in PU_ORDER:
        for drv in pu_drivers[pu]:
            if drv in clean_all and drv in clean_all_with_ot:
                med_with = clean_all_with_ot[drv][scol].dropna().median()
                med_without = clean_all[drv][scol].dropna().median()
                diff = med_without - med_with
                n_ot = excluded_ot_counts.get(drv, 0)
                if n_ot > 0:
                    print(f'  {drv:3s} ({pu:12s}): {med_with:.1f} -> {med_without:.1f} ({diff:+.1f} km/h, {n_ot} laps removed)')
