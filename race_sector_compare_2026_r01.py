"""
============================================================
2026 オーストラリアGP 決勝 — RUS vs LEC セクター比較チャート
============================================================
Chart 1と同じ形式で S1 / S2 / S3 を3段で比較。
各段にデルタバーを内蔵。
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
GP_NAME = 'Australia'
ROUND_NUMBER = 1
DRV1, DRV2 = 'RUS', 'LEC'

OUT_DIR = Path(f'./data/{YEAR}_R{ROUND_NUMBER:02d}_{GP_NAME}')
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_PNG = OUT_DIR / f'race_sector_{DRV1.lower()}_vs_{DRV2.lower()}_{YEAR}_r{ROUND_NUMBER:02d}.png'

TEAM_COLORS = {
    'McLaren': '#FF8700', 'Ferrari': '#E8002D', 'Red Bull Racing': '#3671C6',
    'Mercedes': '#27F4D2', 'Aston Martin': '#229971', 'Williams': '#64C4FF',
    'Racing Bulls': '#6692FF', 'Alpine': '#0093CC', 'Haas F1 Team': '#B6BABD',
    'Audi': '#52E252', 'Cadillac': '#C0C0C0',
}

TYRE_COLORS = {
    'SOFT': '#FF3333', 'MEDIUM': '#FFD700', 'HARD': '#FFFFFF',
    'INTERMEDIATE': '#39B54A', 'WET': '#0072CE',
}

STYLE = {
    'bg_color': '#1a1a2e', 'text_color': '#ffffff', 'grid_color': '#333355',
    'title_size': 16, 'label_size': 11, 'tick_size': 9,
}

# 日本語フォント
for font_name in ['Yu Gothic', 'Meiryo', 'MS Gothic']:
    try:
        matplotlib.font_manager.FontProperties(family=font_name)
        plt.rcParams['font.family'] = font_name
        break
    except:
        continue

plt.rcParams['axes.facecolor'] = STYLE['bg_color']
plt.rcParams['figure.facecolor'] = STYLE['bg_color']
plt.rcParams['text.color'] = STYLE['text_color']
plt.rcParams['axes.labelcolor'] = STYLE['text_color']
plt.rcParams['xtick.color'] = STYLE['text_color']
plt.rcParams['ytick.color'] = STYLE['text_color']

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

# ドライバーデータ構築
DRIVERS = [DRV1, DRV2]
driver_data = {}
pit_laps = {}
clean_data = {}

for drv in DRIVERS:
    df = laps_all[laps_all['Driver'] == drv].copy().sort_values('LapNumber')
    df['LapTimeSec'] = df['LapTime'].dt.total_seconds()
    df['S1Sec'] = df['Sector1Time'].dt.total_seconds()
    df['S2Sec'] = df['Sector2Time'].dt.total_seconds()
    df['S3Sec'] = df['Sector3Time'].dt.total_seconds()
    df['LapNum'] = df['LapNumber'].astype(int)
    driver_data[drv] = df
    pit_laps[drv] = df[df['PitInTime'].notna()]['LapNum'].tolist()

    pit_in_set = set(pit_laps[drv])
    pit_out_set = set(df[df['PitOutTime'].notna()]['LapNum'].tolist())
    exclude = vsc_lap_set | pit_in_set | pit_out_set | {1}
    clean_data[drv] = df[~df['LapNum'].isin(exclude)].copy()

color1 = TEAM_COLORS.get(drv_team.get(DRV1, ''), '#888')
color2 = TEAM_COLORS.get(drv_team.get(DRV2, ''), '#888')
colors = {DRV1: color1, DRV2: color2}

# ============================================================
# チャート生成: S1 / S2 / S3 各2段（値 + デルタ）= 6段
# ============================================================
print('セクター比較チャート生成中...')

sectors = [('S1', 'S1Sec', 'Sector 1 (秒)'),
           ('S2', 'S2Sec', 'Sector 2 (秒)'),
           ('S3', 'S3Sec', 'Sector 3 (秒)')]

fig, axes = plt.subplots(6, 1, figsize=(16, 18),
                          height_ratios=[3, 1, 3, 1, 3, 1],
                          gridspec_kw={'hspace': 0.06})

# 共通クリーンラップセット
both_clean = set(clean_data[DRV1]['LapNum']) & set(clean_data[DRV2]['LapNum'])

for si, (sec_name, sec_col, sec_ylabel) in enumerate(sectors):
    ax_main = axes[si * 2]
    ax_delta = axes[si * 2 + 1]

    # VSC帯
    for ax in [ax_main, ax_delta]:
        for start, end in vsc_periods:
            ax.axvspan(start - 0.5, end + 0.5, alpha=0.2, color='#FFD700', zorder=0)

    # セクタータイム折れ線
    for drv in DRIVERS:
        df = driver_data[drv]
        valid = df[df[sec_col].notna()]
        clean_set = set(clean_data[drv]['LapNum'].tolist())

        for stint in valid['Stint'].unique():
            stint_df = valid[valid['Stint'] == stint]
            stint_clean = stint_df[stint_df['LapNum'].isin(clean_set)]
            ax_main.plot(stint_clean['LapNum'], stint_clean[sec_col],
                         color=colors[drv], linewidth=1.8, alpha=0.9,
                         label=drv if stint == valid['Stint'].min() else None, zorder=3)
            ax_main.scatter(stint_clean['LapNum'], stint_clean[sec_col],
                            c=[TYRE_COLORS.get(c, '#888') for c in stint_clean['Compound']],
                            s=20, edgecolors=colors[drv], linewidths=0.8, zorder=4)
            stint_dirty = stint_df[~stint_df['LapNum'].isin(clean_set)]
            if len(stint_dirty) > 0:
                ax_main.scatter(stint_dirty['LapNum'], stint_dirty[sec_col],
                                marker='x', c=colors[drv], s=18, alpha=0.3, zorder=2)

    # ピットイン線（全6段に描画）
    for drv in DRIVERS:
        for pl in pit_laps[drv]:
            for ax in [ax_main, ax_delta]:
                ax.axvline(pl, color=colors[drv], linestyle='--', alpha=0.7, linewidth=1.2)

    # Y軸: クリーンラップに合わせる
    all_clean_vals = pd.concat([clean_data[d][sec_col].dropna() for d in DRIVERS])
    margin = (all_clean_vals.max() - all_clean_vals.min()) * 0.12 + 0.2
    ax_main.set_ylim(all_clean_vals.min() - margin, all_clean_vals.max() + margin)
    ax_main.set_ylabel(sec_ylabel, fontsize=STYLE['label_size'])
    ax_main.xaxis.set_major_locator(MultipleLocator(5))
    ax_main.grid(True, color=STYLE['grid_color'], alpha=0.5, linewidth=0.5)
    ax_main.tick_params(labelbottom=False)

    # ピットインラベル（最上段のみ）
    if si == 0:
        y_bottom, y_top = ax_main.get_ylim()
        y_range = y_top - y_bottom
        for i, drv in enumerate(DRIVERS):
            for pl in pit_laps[drv]:
                y_pos = y_top - y_range * (0.03 + 0.08 * i)
                ax_main.text(pl, y_pos, f'{drv} PIT L{pl}',
                             ha='center', va='top', fontsize=8, fontweight='bold',
                             color=colors[drv], alpha=0.9,
                             bbox=dict(boxstyle='round,pad=0.2', facecolor=STYLE['bg_color'],
                                       edgecolor=colors[drv], alpha=0.7, linewidth=0.8))
        ax_main.legend(loc='upper right', fontsize=10, framealpha=0.3)
        ax_main.set_title(f'{DRV1} vs {DRV2} セクター比較 (S1 / S2 / S3)\n'
                          f'(丸=クリーン, x=VSC/ピット, 黄帯=VSC, 破線=ピットイン)',
                          fontsize=STYLE['title_size'], pad=12)

    # デルタバー
    merged = pd.merge(
        driver_data[DRV1][['LapNum', sec_col]].rename(columns={sec_col: f'{DRV1}_sec'}),
        driver_data[DRV2][['LapNum', sec_col]].rename(columns={sec_col: f'{DRV2}_sec'}),
        on='LapNum', how='inner')
    merged['delta'] = merged[f'{DRV1}_sec'] - merged[f'{DRV2}_sec']
    merged['is_clean'] = merged['LapNum'].isin(both_clean)
    mc = merged[merged['is_clean']]

    ax_delta.bar(mc['LapNum'], mc['delta'],
                 color=[colors[DRV1] if d < 0 else colors[DRV2] for d in mc['delta']],
                 alpha=0.7, width=0.8, zorder=3)
    ax_delta.axhline(0, color='#fff', linewidth=0.8, alpha=0.5)
    ax_delta.set_ylabel(f'{sec_name} Delta', fontsize=STYLE['label_size'] - 2)
    if len(mc) > 0:
        d_max = max(abs(mc['delta'].min()), abs(mc['delta'].max())) + 0.2
        ax_delta.set_ylim(-d_max, d_max)
    ax_delta.xaxis.set_major_locator(MultipleLocator(5))
    ax_delta.grid(True, color=STYLE['grid_color'], alpha=0.5, linewidth=0.5)

    # 最下段以外はX軸ラベル非表示
    if si < 2:
        ax_delta.tick_params(labelbottom=False)
    else:
        ax_delta.set_xlabel('ラップ数', fontsize=STYLE['label_size'])

    # デルタ軸の右に説明
    ax_delta.text(1.01, 0.5, f'{DRV1}<0<{DRV2}', transform=ax_delta.transAxes,
                  fontsize=7, color='#888', va='center', ha='left', rotation=90)

# 保存
fig.savefig(OUT_PNG, dpi=150, facecolor=STYLE['bg_color'], bbox_inches='tight')
print(f'保存: {OUT_PNG} ({OUT_PNG.stat().st_size / 1024:.0f} KB)')
plt.close(fig)
print('完了!')
