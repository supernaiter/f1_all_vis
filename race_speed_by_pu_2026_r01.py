"""
============================================================
2026 オーストラリアGP — PUサプライヤー別スピード分布比較
============================================================
L26以降クリーンラップ。4計測ポイント×全ドライバー、PUグループ別。
"""

import fastf1
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import colorsys
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
    'Ferrari': 'Ferrari', 'Haas F1 Team': 'Ferrari', 'Cadillac': 'Ferrari',
    'Red Bull Racing': 'Red Bull PT', 'Racing Bulls': 'Red Bull PT',
    'Aston Martin': 'Honda', 'Alpine': 'Renault', 'Audi': 'Audi',
}

PU_ORDER = ['Mercedes', 'Ferrari', 'Red Bull PT', 'Honda', 'Audi', 'Renault']
PU_COLORS = {
    'Mercedes': '#00B89F', 'Ferrari': '#DC0000', 'Red Bull PT': '#2B5DAB',
    'Honda': '#1B7A5A', 'Audi': '#3AAA3A', 'Renault': '#0078AA',
}

drv_team = dict(zip(results['Abbreviation'], results['TeamName']))

def lighten(hex_color, factor):
    r, g, b = int(hex_color[1:3], 16)/255, int(hex_color[3:5], 16)/255, int(hex_color[5:7], 16)/255
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    l2 = min(1.0, l + (1.0 - l) * factor)
    r2, g2, b2 = colorsys.hls_to_rgb(h, l2, s)
    return f'#{int(r2*255):02x}{int(g2*255):02x}{int(b2*255):02x}'

# L26以降のクリーンデータ
clean_l26 = {}
for _, r in results.iterrows():
    drv = r['Abbreviation']
    df = laps_all[laps_all['Driver'] == drv].copy().sort_values('LapNumber')
    if len(df) == 0:
        continue
    df['LapNum'] = df['LapNumber'].astype(int)
    pit_in = set(df[df['PitInTime'].notna()]['LapNum'])
    pit_out = set(df[df['PitOutTime'].notna()]['LapNum'])
    exclude = vsc_set | pit_in | pit_out | {1}
    c = df[(~df['LapNum'].isin(exclude)) & (df['LapNum'] >= 26)]
    if len(c) > 3:
        clean_l26[drv] = c

# PUグループ別にドライバー整理（ポジション順）
pu_drivers = {pu: [] for pu in PU_ORDER}
for drv in results['Abbreviation'].tolist():
    team = drv_team.get(drv, '')
    pu = PU_MAP.get(team, '?')
    if pu in pu_drivers and drv in clean_l26:
        pu_drivers[pu].append(drv)

print('PUグループ:')
for pu in PU_ORDER:
    drivers = pu_drivers[pu]
    if drivers:
        print(f'  {pu}: {", ".join(drivers)}')

# テーマ
LT = {'bg': '#FFFFFF', 'text': '#1a1a2e', 'axis': '#444444',
      'grid_maj': '#DDDDDD', 'spine': '#AAAAAA'}

SPEED_COLS = ['SpeedI1', 'SpeedI2', 'SpeedFL', 'SpeedST']
SPEED_LABELS = ['S1末端', 'S2末端', 'FL', 'ST (スピードトラップ)']

# ==========================================================
# チャート: 4段パネル
# ==========================================================
print('\nチャート生成中...')
fig, axes = plt.subplots(4, 1, figsize=(20, 24), facecolor='white',
                          gridspec_kw={'hspace': 0.28})

for panel_idx, (scol, slabel) in enumerate(zip(SPEED_COLS, SPEED_LABELS)):
    ax = axes[panel_idx]
    ax.set_facecolor('white')
    ax.tick_params(colors=LT['axis'], labelsize=10)
    ax.grid(True, axis='y', color=LT['grid_maj'], linewidth=0.5, alpha=0.8)
    for spine in ax.spines.values():
        spine.set_color(LT['spine'])

    x_pos = 0
    tick_positions = []
    tick_labels_list = []
    group_labels_pos = []

    for pu_idx, pu in enumerate(PU_ORDER):
        drivers = pu_drivers[pu]
        if not drivers:
            continue
        pu_color = PU_COLORS[pu]
        group_start = x_pos

        for di, drv in enumerate(drivers):
            data = clean_l26[drv][scol].dropna().values
            if len(data) == 0:
                x_pos += 1
                continue

            shade = lighten(pu_color, di * 0.12)

            bp = ax.boxplot([data], positions=[x_pos], widths=0.7,
                            patch_artist=True, showfliers=True,
                            flierprops={'markersize': 3, 'markerfacecolor': 'none',
                                        'markeredgecolor': '#888'})
            for p in bp['boxes']:
                p.set_facecolor(shade)
                p.set_alpha(0.6)
                p.set_edgecolor(pu_color)
            for e in ['whiskers', 'caps']:
                for line in bp[e]:
                    line.set_color(LT['axis'])
            for line in bp['medians']:
                line.set_color(pu_color)
                line.set_linewidth(2)

            # 中央値テキスト
            med_val = np.median(data)
            ax.text(x_pos, med_val + 0.6, f'{med_val:.0f}', ha='center', va='bottom',
                    fontsize=7, color=pu_color, fontweight='bold', alpha=0.8)

            tick_positions.append(x_pos)
            team = drv_team.get(drv, '')
            # チーム名を短縮
            team_short = {'Mercedes': 'MER', 'McLaren': 'MCL', 'Williams': 'WIL',
                          'Ferrari': 'FER', 'Haas F1 Team': 'HAA', 'Cadillac': 'CAD',
                          'Red Bull Racing': 'RBR', 'Racing Bulls': 'RCB',
                          'Aston Martin': 'AMR', 'Alpine': 'ALP', 'Audi': 'AUD'}.get(team, team[:3])
            tick_labels_list.append(f'{drv}\n({team_short})')
            x_pos += 1

        group_end = x_pos - 1
        if group_start <= group_end:
            gc = (group_start + group_end) / 2
            group_labels_pos.append((gc, pu, pu_color, group_start - 0.5, group_end + 0.5))

        # PUグループ間スペース
        x_pos += 1.5

    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels_list, fontsize=9, rotation=0)
    ax.set_ylabel(f'{slabel} (km/h)', color=LT['text'], fontsize=12, fontweight='bold')

    if panel_idx == 0:
        ax.set_title('PUサプライヤー別 スピード分布比較\n'
                      '(L26以降 クリーンラップ・全ドライバー)',
                      color=LT['text'], fontsize=18, fontweight='bold', pad=16)

    # PUグループのラベル+背景帯
    y_min_ax, y_max_ax = ax.get_ylim()
    for gc, pu, color, x_start, x_end in group_labels_pos:
        ax.axvspan(x_start, x_end, alpha=0.06, color=color, zorder=0)
        ax.text(gc, y_max_ax - (y_max_ax - y_min_ax) * 0.02, pu,
                ha='center', va='top', fontsize=11, fontweight='bold',
                color=color, alpha=0.9,
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                          edgecolor=color, alpha=0.8, linewidth=1.0))

# 脚注
fig.text(0.5, 0.005,
         'S1末端=Sector1終点  S2末端=Sector2終点  FL=フィニッシュライン  '
         'ST=スピードトラップ(FIA最高速計測点)\n'
         'L26以降=LECピットイン後(HARD区間)  VSC/ピット周を除外\n'
         'PU供給: Mercedes=Mercedes,McLaren,Williams / Ferrari=Ferrari,Haas,Cadillac / '
         'Red Bull PT=Red Bull,Racing Bulls / Honda=Aston Martin / Audi / Renault=Alpine',
         ha='center', va='bottom', fontsize=9, color='#666', style='italic')

out = Path('./data/2026_R01_Australia/article/art_speed_by_pu.png')
out.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(out, dpi=180, facecolor='white', bbox_inches='tight', pad_inches=0.4)
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
        v = clean_l26[drv]['SpeedST'].dropna()
        med = v.median()
        meds.append(med)
        print(f'  {pu:12s} {drv:3s}: median={med:.1f} km/h (n={len(v)})')
    avg_med = np.mean(meds)
    pu_medians[pu] = avg_med
    print(f'  {pu:12s} >>> PU平均: {avg_med:.1f} km/h\n')

print('=== PUランキング (ST中央値の平均) ===')
for rank, (pu, val) in enumerate(sorted(pu_medians.items(), key=lambda x: -x[1]), 1):
    print(f'  {rank}. {pu}: {val:.1f} km/h')
