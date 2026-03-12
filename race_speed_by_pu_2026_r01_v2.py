"""
============================================================
2026 オーストラリアGP — PUサプライヤー別スピード分布比較 (v2)
============================================================
フォーマット改善版:
  - 2x2グリッドレイアウト
  - パネル別Y軸最適化
  - フォントサイズ拡大
  - X軸ラベル簡素化（ドライバー略称のみ）
  - テーブル簡素化（Med + SD の2行）
  - Haas視認性改善（エッジ濃く・alpha調整）
  - PU背景帯を濃く（alpha=0.10）
  - PU平均破線マーカー追加
  - 小PUグループの最小幅確保
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

# Haasなど薄い色のチームはエッジを濃くする
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

# 全クリーンラップデータ（Lap制限なし）
clean_all = {}
for _, r in results.iterrows():
    drv = r['Abbreviation']
    df = laps_all[laps_all['Driver'] == drv].copy().sort_values('LapNumber')
    if len(df) == 0:
        continue
    df['LapNum'] = df['LapNumber'].astype(int)
    pit_in = set(df[df['PitInTime'].notna()]['LapNum'])
    pit_out = set(df[df['PitOutTime'].notna()]['LapNum'])
    exclude = vsc_set | pit_in | pit_out | {1}
    c = df[~df['LapNum'].isin(exclude)]
    if len(c) > 3:
        clean_all[drv] = c

# PUグループ別にドライバー整理（ポジション順）
pu_drivers = {pu: [] for pu in PU_ORDER}
for drv in results['Abbreviation'].tolist():
    team = drv_team.get(drv, '')
    pu = PU_MAP.get(team, '?')
    if pu in pu_drivers and drv in clean_all:
        pu_drivers[pu].append(drv)

print('PUグループ:')
for pu in PU_ORDER:
    drivers = pu_drivers[pu]
    if drivers:
        print(f'  {pu}: {", ".join(drivers)}')

# テーマ
LT = {'bg': '#FFFFFF', 'text': '#1a1a2e', 'axis': '#444444',
      'grid_maj': '#DDDDDD', 'spine': '#AAAAAA'}

SPEED_COLS = ['SpeedST', 'SpeedFL', 'SpeedI1', 'SpeedI2']
SPEED_LABELS = ['ST (スピードトラップ)', 'FL (フィニッシュライン)', 'S1末端', 'S2末端']

# ==========================================================
# パネル別Y軸範囲を事前計算
# ==========================================================
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
    # マージン付きで丸める（5km/h単位）
    y_lo = max(220, int(p_min / 5) * 5 - 5)
    y_hi = int(p_max / 5) * 5 + 10
    panel_ylims[scol] = (y_lo, y_hi)
    print(f'  {slabel}: {y_lo} - {y_hi} km/h')

# ==========================================================
# チャート: 2x2グリッド（各セル = 箱ひげ図 + テーブル2行）
# ==========================================================
print('\nチャート生成中...')

fig = plt.figure(figsize=(28, 22), facecolor='white')

# 外側2x2、内側それぞれ箱ひげ図(高さ3)+テーブル(高さ0.8)
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

    # テーブル用データ収集
    drv_stats = {}

    x_pos = 0
    tick_positions = []
    tick_labels_list = []
    group_labels_pos = []
    pu_gap_positions = []
    # PU平均の中央値を箱ひげ図上に破線表示するためのデータ
    pu_avg_lines = []  # (x_start, x_end, avg_med, pu_color)

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

            # 統計値を記録（SDは外れ値除外: IQR*1.5の範囲内のみ）
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

            # チームカラーで箱ひげ図を着色
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
            # X軸ラベル（リタイアはDNF表記付き）
            label = f'{drv}\n(DNF)' if is_retired else drv
            tick_labels_list.append(label)
            x_pos += 1

        group_end = x_pos - 1

        if group_start <= group_end:
            gc = (group_start + group_end) / 2
            group_labels_pos.append((gc, pu, pu_color, group_start - 0.5, group_end + 0.5))

            # PU平均線用データ
            # PU平均にはリタイアドライバーを含めない
            pu_meds = [drv_stats[d]['med'] for d in drivers if d in drv_stats and d not in RETIRED_DRIVERS]
            if pu_meds:
                avg_med = np.mean(pu_meds)
                pu_avg_lines.append((group_start - 0.4, group_end + 0.4, avg_med, pu_color))

        # PU平均を表示するための空白位置を記録
        # Honda(2名)やAudi(1名)には最小ギャップ幅を確保
        gap_width = 1.2
        pu_gap_positions.append((x_pos + gap_width / 2, pu, pu_color))
        x_pos += gap_width + 0.3

    # Y軸をパネル個別に設定
    y_lo, y_hi = panel_ylims[scol]
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels_list, fontsize=11, fontweight='bold', rotation=0)
    ax.set_ylim(y_lo, y_hi)
    ax.set_ylabel(f'{slabel} (km/h)', color=LT['text'], fontsize=14, fontweight='bold')

    # パネルタイトル
    ax.set_title(slabel, color=LT['text'], fontsize=16, fontweight='bold', pad=10)

    # PUグループのラベル+背景帯（alpha=0.10に強化）
    y_min_ax, y_max_ax = ax.get_ylim()
    for gc, pu, color, x_start, x_end in group_labels_pos:
        ax.axvspan(x_start, x_end, alpha=0.10, color=color, zorder=0)
        ax.text(gc, y_max_ax - (y_max_ax - y_min_ax) * 0.03, pu,
                ha='center', va='top', fontsize=12, fontweight='bold',
                color=color, alpha=0.9,
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                          edgecolor=color, alpha=0.85, linewidth=1.2))

    # PU平均破線（箱ひげ図上にグループ範囲内で水平破線）
    for x_s, x_e, avg_med, pu_color in pu_avg_lines:
        ax.hlines(avg_med, x_s, x_e, colors=pu_color, linestyles='dashed',
                  linewidths=1.8, alpha=0.7, zorder=5)

    # ====================================================
    # テーブル（簡素化: Med + SD の2行のみ）
    # ====================================================
    ax_tbl.set_xlim(ax.get_xlim())
    ax_tbl.set_ylim(-0.3, 2.3)
    ax_tbl.axis('off')

    row_labels = ['Med', 'SD']
    row_y = [1.5, 0.5]

    # 行ラベル（左端）
    x_left = ax.get_xlim()[0] + 0.1
    for rl, ry in zip(row_labels, row_y):
        ax_tbl.text(x_left, ry, rl, ha='right', va='center',
                    fontsize=10, fontweight='bold', color='#666666')

    # 横罫線
    for y_line in [2.0, 1.0, 0.0]:
        ax_tbl.axhline(y_line, color='#E0E0E0', linewidth=0.5, zorder=0)

    # PUグループ背景帯（テーブルにも適用）
    for gc, pu, color, x_start, x_end in group_labels_pos:
        ax_tbl.axvspan(x_start, x_end, alpha=0.06, color=color, zorder=0)

    # 各ドライバーの統計値を配置
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

    # PU平均値をグループ間の空白位置に配置
    for gap_x, pu, pu_color in pu_gap_positions:
        drivers = pu_drivers[pu]
        # PU平均にはリタイアドライバーを含めない
        pu_data_all = [drv_stats[d] for d in drivers if d in drv_stats and d not in RETIRED_DRIVERS]
        if not pu_data_all:
            continue

        avg_med = np.mean([s['med'] for s in pu_data_all])
        avg_sd = np.mean([s['sd'] for s in pu_data_all])
        n_drivers = len(pu_data_all)

        # PU名ヘッダー + ドライバー数
        ax_tbl.text(gap_x, 2.1, f'Avg\n(n={n_drivers})', ha='center', va='center',
                    fontsize=8, fontweight='bold', color=pu_color, alpha=0.8)

        avg_vals = [f'{avg_med:.0f}', f'{avg_sd:.1f}']
        for ri, (val, ry) in enumerate(zip(avg_vals, row_y)):
            fw = 'bold' if ri == 0 else 'normal'
            ax_tbl.text(gap_x, ry, val, ha='center', va='center',
                        fontsize=10, fontweight=fw, color=pu_color, alpha=0.85)

# 全体タイトル
fig.suptitle('PUサプライヤー別 スピード分布比較 — 2026 オーストラリアGP\n'
             '全クリーンラップ (VSC/ピット周除外)',
             fontsize=20, fontweight='bold', color=LT['text'], y=0.98)

# 脚注
retired_str = ', '.join(sorted(RETIRED_DRIVERS))
fig.text(0.5, 0.005,
         'PU供給: Mercedes = Mercedes, McLaren, Williams, Alpine  /  Ferrari = Ferrari, Haas, Cadillac  /  '
         'Red Bull PT = Red Bull, Racing Bulls  /  Honda = Aston Martin  /  Audi\n'
         '破線 = PUグループ内の中央値平均  |  箱ひげ図の色 = チームカラー  |  背景帯 = PUサプライヤー\n'
         f'グレー表示 = DNFドライバー ({retired_str}) — 参考値。PU平均には含まず\n'
         '※ SD(標準偏差)の計算には IQR x 1.5 基準で外れ値を除外',
         ha='center', va='bottom', fontsize=10, color='#666', style='italic')

out = Path('./data/2026_R01_Australia/article/art_speed_by_pu_v2.png')
out.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(out, dpi=180, facecolor='white', bbox_inches='tight', pad_inches=0.5)
size_kb = out.stat().st_size / 1024
print(f'\n保存: {out} ({size_kb:.0f} KB)')
plt.close(fig)

# サマリー
print('\n=== ST (スピードトラップ) PU別中央値 ===')
pu_medians = {}
for pu in PU_ORDER:
    drivers = pu_drivers[pu]
    if not drivers:
        continue
    meds = []
    for drv in drivers:
        v = clean_all[drv]['SpeedST'].dropna()
        med = v.median()
        meds.append(med)
        print(f'  {pu:12s} {drv:3s}: median={med:.1f} km/h (n={len(v)})')
    avg_med = np.mean(meds)
    pu_medians[pu] = avg_med
    print(f'  {pu:12s} >>> PU平均: {avg_med:.1f} km/h\n')

print('=== PUランキング (ST中央値の平均) ===')
for rank, (pu, val) in enumerate(sorted(pu_medians.items(), key=lambda x: -x[1]), 1):
    print(f'  {rank}. {pu}: {val:.1f} km/h')
