"""
============================================================
2026 オーストラリアGP 決勝 — ドライバー Head-to-Head レースペース分析
============================================================
任意の2ドライバーの比較レポートを生成する汎用スクリプト。

使い方:
  python race_h2h_2026_r01.py RUS LEC
  python race_h2h_2026_r01.py RUS ANT
  python race_h2h_2026_r01.py LEC HAM
  python race_h2h_2026_r01.py ANT HAM
  python race_h2h_2026_r01.py          # → 4ペア一括生成
"""

import fastf1
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
from pathlib import Path
from datetime import datetime
import base64
from io import BytesIO
import sys
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# GP設定
# ============================================================
YEAR = 2026
GP_NAME = 'Australia'
ROUND_NUMBER = 1

OUT_DIR = Path(f'./data/{YEAR}_R{ROUND_NUMBER:02d}_{GP_NAME}')
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 全ドライバー情報（レース結果から自動取得もするが、チームカラーは手動定義）
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

# スピード計測ポイントの正式名
SPEED_COLS = ['SpeedI1', 'SpeedI2', 'SpeedFL', 'SpeedST']
SPEED_LABELS = ['Sector1末端', 'Sector2末端', 'フィニッシュライン', 'スピードトラップ']
SPEED_SHORT = ['S1末端', 'S2末端', 'FL', 'ST']

# グラフスタイル
STYLE = {
    'bg_color': '#1a1a2e', 'text_color': '#ffffff', 'grid_color': '#333355',
    'title_size': 16, 'label_size': 11, 'tick_size': 9,
}

# 日本語フォント設定
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
# データ読み込み（1回だけ）
# ============================================================
print('FastF1からレースデータを読み込み中...')
fastf1.Cache.enable_cache('~/f1_cache')
session = fastf1.get_session(YEAR, GP_NAME, 'R')
session.load(telemetry=False, laps=True, weather=False)

laps_all = session.laps
results = session.results.sort_values('Position')
race_laps = int(laps_all['LapNumber'].max())

# ドライバー情報マップ構築
drv_team = dict(zip(results['Abbreviation'], results['TeamName']))
drv_full = dict(zip(results['Abbreviation'], results['FullName']))
drv_pos = dict(zip(results['Abbreviation'], results['Position'].astype(int)))
drv_grid = dict(zip(results['Abbreviation'], results['GridPosition'].astype(int)))
drv_status = dict(zip(results['Abbreviation'], results['Status']))

def drv_color(drv):
    team = drv_team.get(drv, '')
    return TEAM_COLORS.get(team, '#888888')

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

print(f'レース: {race_laps}周, VSC期間: {vsc_periods}')

# 全ドライバーのデータを事前に構築
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

    # クリーンラップ
    pit_in_set = set(all_pit_laps[drv])
    pit_out_set = set(df[df['PitOutTime'].notna()]['LapNum'].tolist())
    exclude = vsc_lap_set | pit_in_set | pit_out_set | {1}
    all_clean_data[drv] = df[~df['LapNum'].isin(exclude)].copy()


# ============================================================
# ユーティリティ
# ============================================================
def fig_to_base64(fig, dpi=150):
    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight',
                facecolor=fig.get_facecolor(), edgecolor='none')
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return b64

def format_time(val):
    if pd.isna(val):
        return '-'
    return f'{val:.3f}'

def make_table_html(headers, rows):
    html = '<div class="table-scroll"><table><thead><tr>'
    for h in headers:
        html += f'<th>{h}</th>'
    html += '</tr></thead><tbody>'
    for row in rows:
        html += '<tr>'
        for cell in row:
            html += f'<td>{cell}</td>'
        html += '</tr>'
    html += '</tbody></table></div>'
    return html


# ============================================================
# レポート生成関数
# ============================================================
def generate_h2h_report(drv1, drv2):
    """drv1 vs drv2 のHTMLレポートを生成"""
    DRIVERS = [drv1, drv2]
    print(f'\n{"="*60}')
    print(f'{drv1} vs {drv2} レポート生成中...')
    print(f'{"="*60}')

    d1_data = all_driver_data[drv1]
    d2_data = all_driver_data[drv2]
    driver_data = {drv1: d1_data, drv2: d2_data}
    pit_laps = {drv1: all_pit_laps[drv1], drv2: all_pit_laps[drv2]}
    clean_data = {drv1: all_clean_data[drv1], drv2: all_clean_data[drv2]}

    color1, color2 = drv_color(drv1), drv_color(drv2)
    team1, team2 = drv_team[drv1], drv_team[drv2]

    # 同じチームの場合、2ndドライバーの色を調整
    if color1 == color2:
        # 明度を変えて区別
        color2 = color1 + '99'  # 透明度で区別（フォールバック）
        # より良い方法: 明るさを変える
        import colorsys
        r, g, b = int(color1[1:3], 16)/255, int(color1[3:5], 16)/255, int(color1[5:7], 16)/255
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        l2 = min(1.0, l * 0.6)  # 暗めにする
        r2, g2, b2 = colorsys.hls_to_rgb(h, l2, s)
        color2 = f'#{int(r2*255):02x}{int(g2*255):02x}{int(b2*255):02x}'

    colors = {drv1: color1, drv2: color2}

    # スティント情報の取得
    def get_stint_info(drv):
        df = driver_data[drv]
        info = []
        for stint in sorted(df['Stint'].dropna().unique()):
            s = df[df['Stint'] == stint]
            compound = s['Compound'].iloc[0]
            l_min, l_max = int(s['LapNum'].min()), int(s['LapNum'].max())
            n = len(s)
            info.append({'stint': int(stint), 'compound': compound,
                         'laps': f'L{l_min}-{l_max}', 'n': n,
                         'l_min': l_min, 'l_max': l_max})
        return info

    stints = {drv: get_stint_info(drv) for drv in DRIVERS}

    print(f'  {drv1}: ピットL{pit_laps[drv1]}, {len(stints[drv1])}スティント')
    print(f'  {drv2}: ピットL{pit_laps[drv2]}, {len(stints[drv2])}スティント')

    # ================================================================
    # Chart 1: ラップタイム + デルタ + トップスピード（3段）
    # ================================================================
    print('  Chart 1: ラップタイム推移...')

    fig1, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 12),
                                          height_ratios=[3, 1, 1.5],
                                          gridspec_kw={'hspace': 0.08})

    # VSC帯
    for ax in [ax1, ax2, ax3]:
        for start, end in vsc_periods:
            ax.axvspan(start - 0.5, end + 0.5, alpha=0.2, color='#FFD700', zorder=0)

    # ラップタイム折れ線
    for drv in DRIVERS:
        df = driver_data[drv]
        valid = df[df['LapTimeSec'].notna() & (df['LapTimeSec'] < 200)]
        clean_set = set(clean_data[drv]['LapNum'].tolist())
        for stint in valid['Stint'].unique():
            stint_df = valid[valid['Stint'] == stint]
            compound = stint_df['Compound'].iloc[0]
            stint_clean = stint_df[stint_df['LapNum'].isin(clean_set)]
            ax1.plot(stint_clean['LapNum'], stint_clean['LapTimeSec'],
                     color=colors[drv], linewidth=1.8, alpha=0.9,
                     label=drv if stint == valid['Stint'].min() else None, zorder=3)
            ax1.scatter(stint_clean['LapNum'], stint_clean['LapTimeSec'],
                        c=TYRE_COLORS.get(compound, '#888'), s=20,
                        edgecolors=colors[drv], linewidths=0.8, zorder=4)
            stint_dirty = stint_df[~stint_df['LapNum'].isin(clean_set)]
            if len(stint_dirty) > 0:
                ax1.scatter(stint_dirty['LapNum'], stint_dirty['LapTimeSec'],
                            marker='x', c=colors[drv], s=18, alpha=0.3, zorder=2)
        for pl in pit_laps[drv]:
            for ax in [ax1, ax2, ax3]:
                ax.axvline(pl, color=colors[drv], linestyle=':', alpha=0.4, linewidth=0.8)

    # Y軸
    all_ct = pd.concat([clean_data[d]['LapTimeSec'].dropna() for d in DRIVERS])
    ax1.set_ylim(max(all_ct.min() - 1, 75), all_ct.quantile(0.98) + 2)
    ax1.set_ylabel('ラップタイム (秒)', fontsize=STYLE['label_size'])
    ax1.xaxis.set_major_locator(MultipleLocator(5))
    ax1.grid(True, color=STYLE['grid_color'], alpha=0.5, linewidth=0.5)
    ax1.legend(loc='upper right', fontsize=10, framealpha=0.3)
    ax1.set_title(f'{drv1} vs {drv2} ラップタイム / デルタ / スピードトラップ\n'
                  f'(丸=クリーン, x=VSC/ピット, 黄帯=VSC, 点線=ピットイン)',
                  fontsize=STYLE['title_size'], pad=12)
    ax1.tick_params(labelbottom=False)

    # デルタ
    both_clean = set(clean_data[drv1]['LapNum']) & set(clean_data[drv2]['LapNum'])
    merged = pd.merge(
        driver_data[drv1][['LapNum', 'LapTimeSec']].rename(columns={'LapTimeSec': f'{drv1}_sec'}),
        driver_data[drv2][['LapNum', 'LapTimeSec']].rename(columns={'LapTimeSec': f'{drv2}_sec'}),
        on='LapNum', how='inner')
    merged['delta'] = merged[f'{drv1}_sec'] - merged[f'{drv2}_sec']
    merged['is_clean'] = merged['LapNum'].isin(both_clean)
    mc = merged[merged['is_clean']]

    ax2.bar(mc['LapNum'], mc['delta'],
            color=[colors[drv1] if d < 0 else colors[drv2] for d in mc['delta']],
            alpha=0.7, width=0.8, zorder=3)
    ax2.axhline(0, color='#fff', linewidth=0.8, alpha=0.5)
    ax2.set_ylabel(f'Delta (秒)\n{drv1} < 0 < {drv2}', fontsize=STYLE['label_size'] - 1)
    if len(mc) > 0:
        d_max = max(abs(mc['delta'].min()), abs(mc['delta'].max())) + 0.5
        ax2.set_ylim(-d_max, d_max)
    ax2.xaxis.set_major_locator(MultipleLocator(5))
    ax2.grid(True, color=STYLE['grid_color'], alpha=0.5, linewidth=0.5)
    ax2.tick_params(labelbottom=False)

    # トップスピード
    for drv in DRIVERS:
        clean = clean_data[drv]
        cs = clean[clean['SpeedST'].notna()].sort_values('LapNum')
        for stint in sorted(cs['Stint'].unique()):
            sc = cs[cs['Stint'] == stint]
            ax3.plot(sc['LapNum'], sc['SpeedST'], color=colors[drv],
                     linewidth=1.4, alpha=0.85, zorder=3,
                     label=drv if stint == sorted(cs['Stint'].unique())[0] else None)
            ax3.scatter(sc['LapNum'], sc['SpeedST'],
                        c=[TYRE_COLORS.get(c, '#888') for c in sc['Compound']],
                        s=18, edgecolors=colors[drv], linewidths=0.6, zorder=4)

    all_st = pd.concat([clean_data[d]['SpeedST'].dropna() for d in DRIVERS])
    st_m = (all_st.max() - all_st.min()) * 0.12 + 3
    ax3.set_ylim(all_st.min() - st_m, all_st.max() + st_m)
    ax3.set_xlabel('ラップ数', fontsize=STYLE['label_size'])
    ax3.set_ylabel('スピードトラップ (km/h)', fontsize=STYLE['label_size'])
    ax3.xaxis.set_major_locator(MultipleLocator(5))
    ax3.grid(True, color=STYLE['grid_color'], alpha=0.5, linewidth=0.5)
    ax3.legend(loc='lower right', fontsize=9, framealpha=0.3)

    chart1_b64 = fig_to_base64(fig1)

    # Chart 1 テーブル
    chart1_rows = []
    for lap_num in range(1, race_laps + 1):
        row = {'Lap': lap_num, 'VSC': 'Y' if lap_num in vsc_lap_set else ''}
        for drv in DRIVERS:
            df = driver_data[drv]
            lr = df[df['LapNum'] == lap_num]
            if len(lr) > 0:
                lt = lr['LapTimeSec'].values[0]
                comp = lr['Compound'].values[0]
                tl = int(lr['TyreLife'].values[0]) if pd.notna(lr['TyreLife'].values[0]) else ''
                st_val = lr['SpeedST'].values[0]
                row[f'{drv}_Time'] = f'{lt:.3f}' if pd.notna(lt) else ''
                row[f'{drv}_Tyre'] = f'{comp}({tl})'
                row[f'{drv}_ST'] = f'{st_val:.0f}' if pd.notna(st_val) else ''
                row[f'{drv}_Pos'] = int(lr['Position'].values[0]) if pd.notna(lr['Position'].values[0]) else ''
            else:
                row[f'{drv}_Time'] = row[f'{drv}_Tyre'] = row[f'{drv}_ST'] = row[f'{drv}_Pos'] = ''
        m = merged[merged['LapNum'] == lap_num]
        row['Delta'] = f'{m["delta"].values[0]:+.3f}' if len(m) > 0 and pd.notna(m['delta'].values[0]) else ''
        chart1_rows.append(row)

    c1_html = '<div class="table-scroll"><table><thead><tr>'
    c1_html += f'<th>Lap</th><th>{drv1} Time</th><th>{drv1} Tyre</th><th>{drv1} ST</th><th>{drv1} Pos</th>'
    c1_html += f'<th>{drv2} Time</th><th>{drv2} Tyre</th><th>{drv2} ST</th><th>{drv2} Pos</th><th>Delta</th><th>VSC</th>'
    c1_html += '</tr></thead><tbody>'
    for r in chart1_rows:
        cls = ' class="vsc-row"' if r['VSC'] == 'Y' else ''
        c1_html += f'<tr{cls}><td>{r["Lap"]}</td>'
        for drv in DRIVERS:
            c1_html += f'<td>{r[f"{drv}_Time"]}</td><td>{r[f"{drv}_Tyre"]}</td><td>{r[f"{drv}_ST"]}</td><td>{r[f"{drv}_Pos"]}</td>'
        c1_html += f'<td>{r["Delta"]}</td><td>{r["VSC"]}</td></tr>'
    c1_html += '</tbody></table></div>'

    # ================================================================
    # Chart 2/3: 各ドライバーのセクター一貫性
    # ================================================================
    def create_sector_chart(drv):
        print(f'  Chart: {drv} セクター分析...')
        df = driver_data[drv]
        clean = clean_data[drv]
        color = colors[drv]
        clean_set = set(clean['LapNum'].tolist())

        fig, axes = plt.subplots(4, 1, figsize=(14, 12), height_ratios=[1, 1, 1, 1],
                                  gridspec_kw={'hspace': 0.15})
        for ax in axes:
            for start, end in vsc_periods:
                ax.axvspan(start - 0.5, end + 0.5, alpha=0.15, color='#FFD700', zorder=0)

        def plot_sector(ax, col, ylabel, title=None):
            all_valid = df[df[col].notna()].copy()
            clean_sec = all_valid[all_valid['LapNum'].isin(clean_set)]
            dirty_sec = all_valid[~all_valid['LapNum'].isin(clean_set)]
            for stint in sorted(clean_sec['Stint'].unique()):
                sc = clean_sec[clean_sec['Stint'] == stint].sort_values('LapNum')
                ax.plot(sc['LapNum'], sc[col], color=color, linewidth=1.3, alpha=0.85, zorder=3)
                ax.scatter(sc['LapNum'], sc[col],
                           c=[TYRE_COLORS.get(c, '#888') for c in sc['Compound']],
                           s=20, edgecolors=color, linewidths=0.5, zorder=4)
            if len(dirty_sec) > 0:
                ax.scatter(dirty_sec['LapNum'], dirty_sec[col],
                           marker='x', c='#666666', s=15, alpha=0.35, zorder=1,
                           label='VSC/Pit' if ylabel.startswith('S1') else None)
            for stint in clean['Stint'].unique():
                sc = clean[(clean['Stint'] == stint) & clean[col].notna()]
                if len(sc) >= 3:
                    mean_val = sc[col].mean()
                    lr = (sc['LapNum'].min(), sc['LapNum'].max())
                    ax.hlines(mean_val, lr[0], lr[1], color=color, linestyle='--', alpha=0.5, linewidth=0.8)
                    ax.text(lr[1] + 0.5, mean_val, f'{mean_val:.2f}', fontsize=7, color=color, alpha=0.7, va='center')
            if len(clean_sec) > 0:
                cv = clean_sec[col].dropna()
                margin = (cv.max() - cv.min()) * 0.15 + 0.1
                ax.set_ylim(cv.min() - margin, cv.max() + margin)
            ax.set_ylabel(ylabel, fontsize=STYLE['label_size'])
            if title:
                ax.set_title(title, fontsize=STYLE['title_size'], pad=10)
            ax.grid(True, color=STYLE['grid_color'], alpha=0.4, linewidth=0.5)

        plot_sector(axes[0], 'S1Sec', 'S1 (秒)',
                    title=f'{drv} ({drv_team[drv]}) セクタータイム & スピードトラップ推移\n(x=VSC/ピット周, 破線=スティント平均)')
        axes[0].tick_params(labelbottom=False)
        plot_sector(axes[1], 'S2Sec', 'S2 (秒)')
        axes[1].tick_params(labelbottom=False)
        plot_sector(axes[2], 'S3Sec', 'S3 (秒)')
        axes[2].tick_params(labelbottom=False)

        # スピードトラップ
        ax_st = axes[3]
        all_st_data = df[df['SpeedST'].notna()].copy()
        cs = all_st_data[all_st_data['LapNum'].isin(clean_set)]
        ds = all_st_data[~all_st_data['LapNum'].isin(clean_set)]
        for stint in sorted(cs['Stint'].unique()):
            sc = cs[cs['Stint'] == stint].sort_values('LapNum')
            ax_st.plot(sc['LapNum'], sc['SpeedST'], color=color, linewidth=1.3, alpha=0.85, zorder=3,
                       label='スピードトラップ' if stint == sorted(cs['Stint'].unique())[0] else None)
            ax_st.scatter(sc['LapNum'], sc['SpeedST'],
                          c=[TYRE_COLORS.get(c, '#888') for c in sc['Compound']],
                          s=20, edgecolors=color, linewidths=0.5, zorder=4)
        if len(ds) > 0:
            ax_st.scatter(ds['LapNum'], ds['SpeedST'], marker='x', c='#666', s=15, alpha=0.35, zorder=1)
        ci1 = df[df['SpeedI1'].notna() & df['LapNum'].isin(clean_set)]
        ax_st.plot(ci1['LapNum'], ci1['SpeedI1'], color=color, linewidth=0.8, alpha=0.4, linestyle='--', zorder=2, label='Sector1末端')
        if len(cs) > 0:
            sv = cs['SpeedST'].dropna()
            sm = (sv.max() - sv.min()) * 0.15 + 3
            ax_st.set_ylim(sv.min() - sm, sv.max() + sm)
        ax_st.set_xlabel('ラップ数', fontsize=STYLE['label_size'])
        ax_st.set_ylabel('速度 (km/h)', fontsize=STYLE['label_size'])
        ax_st.legend(loc='lower right', fontsize=9, framealpha=0.3)
        ax_st.grid(True, color=STYLE['grid_color'], alpha=0.4, linewidth=0.5)
        for ax in axes:
            ax.xaxis.set_major_locator(MultipleLocator(5))
        return fig

    def compute_sector_stats(drv):
        clean = clean_data[drv]
        stats = []
        for stint in sorted(clean['Stint'].unique()):
            sc = clean[clean['Stint'] == stint]
            compound = sc['Compound'].iloc[0] if len(sc) > 0 else '?'
            row = {'Stint': int(stint), 'Compound': compound,
                   'Laps': f"L{int(sc['LapNum'].min())}-{int(sc['LapNum'].max())}",
                   'N_clean': len(sc)}
            for sec_name, col in [('S1', 'S1Sec'), ('S2', 'S2Sec'), ('S3', 'S3Sec'),
                                   ('LapTime', 'LapTimeSec'), ('SpeedST', 'SpeedST')]:
                vals = sc[col].dropna()
                if len(vals) >= 2:
                    row[f'{sec_name}_mean'] = vals.mean()
                    row[f'{sec_name}_std'] = vals.std()
                else:
                    row[f'{sec_name}_mean'] = row[f'{sec_name}_std'] = np.nan
            stats.append(row)
        return pd.DataFrame(stats)

    fig2 = create_sector_chart(drv1)
    chart2_b64 = fig_to_base64(fig2)
    stats1 = compute_sector_stats(drv1)

    fig3 = create_sector_chart(drv2)
    chart3_b64 = fig_to_base64(fig3)
    stats2 = compute_sector_stats(drv2)

    # ================================================================
    # Chart 4: 直接比較サマリー（4パネル）
    # ================================================================
    print('  Chart 4: 直接比較サマリー...')
    fig4, axes4 = plt.subplots(2, 2, figsize=(14, 10), gridspec_kw={'hspace': 0.35, 'wspace': 0.3})

    # 4A: スティント別平均ペース
    ax4a = axes4[0, 0]
    bar_data = []
    for drv in DRIVERS:
        clean = clean_data[drv]
        for stint in sorted(clean['Stint'].unique()):
            sc = clean[clean['Stint'] == stint]
            compound = sc['Compound'].iloc[0]
            mean_pace = sc['LapTimeSec'].dropna().mean()
            bar_data.append({'Driver': drv, 'Stint': int(stint), 'Compound': compound,
                             'MeanPace': mean_pace, 'N': len(sc)})
    bar_df = pd.DataFrame(bar_data)
    if len(bar_df) > 0:
        x_pos = np.arange(len(bar_df))
        bars = ax4a.bar(x_pos, bar_df['MeanPace'],
                        color=[colors[d] for d in bar_df['Driver']], alpha=0.8, zorder=3)
        ax4a.set_xticks(x_pos)
        ax4a.set_xticklabels([f"{r['Driver']}\n{r['Compound'][:1]}(St{r['Stint']})\nn={r['N']}"
                               for _, r in bar_df.iterrows()], fontsize=8)
        for bar, val in zip(bars, bar_df['MeanPace']):
            ax4a.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                      f'{val:.2f}', ha='center', fontsize=8, color=STYLE['text_color'])
        all_pace = bar_df['MeanPace'].values
        ax4a.set_ylim(min(all_pace) - 1.5, max(all_pace) + 1.5)
    ax4a.set_ylabel('平均ラップタイム (秒)', fontsize=STYLE['label_size'] - 1)
    ax4a.set_title('4A: スティント別平均ペース\n(クリーンラップのみ)', fontsize=12)
    ax4a.grid(True, axis='y', color=STYLE['grid_color'], alpha=0.4)

    # 4B: セクター別累積タイム差（最長共通コンパウンド区間）
    ax4b = axes4[0, 1]
    # 共通クリーンラップのうち、同一コンパウンド(できればHARD)で比較
    common_clean = set(clean_data[drv1]['LapNum']) & set(clean_data[drv2]['LapNum'])
    # HARDが両者にあればHARDで、なければ最も多い共通コンパウンドで
    d1_hard = clean_data[drv1][(clean_data[drv1]['Compound'] == 'HARD') & (clean_data[drv1]['LapNum'].isin(common_clean))]
    d2_hard = clean_data[drv2][(clean_data[drv2]['Compound'] == 'HARD') & (clean_data[drv2]['LapNum'].isin(common_clean))]
    hard_common = set(d1_hard['LapNum']) & set(d2_hard['LapNum'])

    if len(hard_common) >= 5:
        compare_laps = hard_common
        compare_compound = 'HARD'
    else:
        compare_laps = common_clean
        compare_compound = 'ALL'

    sector_cum = {}
    for sec, col in [('S1', 'S1Sec'), ('S2', 'S2Sec'), ('S3', 'S3Sec')]:
        v1 = clean_data[drv1][clean_data[drv1]['LapNum'].isin(compare_laps)].set_index('LapNum')[col]
        v2 = clean_data[drv2][clean_data[drv2]['LapNum'].isin(compare_laps)].set_index('LapNum')[col]
        ci = v1.dropna().index.intersection(v2.dropna().index)
        sector_cum[sec] = (v1[ci] - v2[ci]).sum() if len(ci) > 0 else 0

    sectors_list = list(sector_cum.keys())
    diffs_list = [sector_cum[s] for s in sectors_list]
    total_diff = sum(diffs_list)
    sectors_list.append('Total')
    diffs_list.append(total_diff)

    colors_4b = [colors[drv1] if d < 0 else colors[drv2] for d in diffs_list]
    bars_4b = ax4b.barh(sectors_list, diffs_list, color=colors_4b, alpha=0.8, zorder=3)
    ax4b.axvline(0, color='#fff', linewidth=0.8, alpha=0.5)
    for bar, val in zip(bars_4b, diffs_list):
        xp = val + (0.3 if val >= 0 else -0.3)
        ax4b.text(xp, bar.get_y() + bar.get_height()/2, f'{val:+.2f}s',
                  ha='left' if val >= 0 else 'right', va='center', fontsize=9, color=STYLE['text_color'])
    ax4b.set_xlabel(f'累積タイム差 (秒)\n{drv1} < 0 < {drv2}', fontsize=STYLE['label_size'] - 1)
    ax4b.set_title(f'4B: セクター別累積タイム差\n({compare_compound}共通ラップ n={len(compare_laps)})', fontsize=12)
    ax4b.grid(True, axis='x', color=STYLE['grid_color'], alpha=0.4)

    # 4C: スピード分布（箱ひげ図）— 正式名ラベル
    ax4c = axes4[1, 0]
    bp1_data = [clean_data[drv1][col].dropna().values for col in SPEED_COLS]
    bp2_data = [clean_data[drv2][col].dropna().values for col in SPEED_COLS]
    pos1 = np.arange(len(SPEED_COLS)) * 3
    pos2 = pos1 + 1
    bp1 = ax4c.boxplot(bp1_data, positions=pos1, widths=0.7, patch_artist=True, showfliers=True, flierprops={'markersize': 3})
    bp2 = ax4c.boxplot(bp2_data, positions=pos2, widths=0.7, patch_artist=True, showfliers=True, flierprops={'markersize': 3})
    for patch in bp1['boxes']:
        patch.set_facecolor(colors[drv1]); patch.set_alpha(0.6)
    for patch in bp2['boxes']:
        patch.set_facecolor(colors[drv2]); patch.set_alpha(0.6)
    for elem in ['whiskers', 'caps', 'medians']:
        for line in bp1[elem]: line.set_color(STYLE['text_color'])
        for line in bp2[elem]: line.set_color(STYLE['text_color'])
    ax4c.set_xticks(pos1 + 0.5)
    ax4c.set_xticklabels(SPEED_SHORT, fontsize=9)
    ax4c.set_ylabel('速度 (km/h)', fontsize=STYLE['label_size'] - 1)
    ax4c.set_title('4C: スピード分布比較\n(クリーンラップ)', fontsize=12)
    ax4c.grid(True, axis='y', color=STYLE['grid_color'], alpha=0.4)
    ax4c.legend([bp1['boxes'][0], bp2['boxes'][0]], [drv1, drv2], loc='lower right', fontsize=9, framealpha=0.3)

    # 4D: デグラデーション（最長スティントのコンパウンド）
    ax4d = axes4[1, 1]
    deg_results = {}
    for drv in DRIVERS:
        clean = clean_data[drv]
        hard = clean[clean['Compound'] == 'HARD']
        hard = hard[hard['LapTimeSec'].notna()]
        if len(hard) < 5:
            # HARDが少なければMEDIUMで
            hard = clean[clean['Compound'] == 'MEDIUM']
            hard = hard[hard['LapTimeSec'].notna()]
        if len(hard) >= 5:
            ax4d.scatter(hard['TyreLife'], hard['LapTimeSec'], c=colors[drv], s=15, alpha=0.5, zorder=3)
            x, y = hard['TyreLife'].values, hard['LapTimeSec'].values
            mask = np.isfinite(x) & np.isfinite(y)
            if mask.sum() >= 5:
                coeffs = np.polyfit(x[mask], y[mask], 1)
                xl = np.linspace(x[mask].min(), x[mask].max(), 50)
                ax4d.plot(xl, np.polyval(coeffs, xl), color=colors[drv], linewidth=2, alpha=0.8,
                          label=f'{drv}: {coeffs[0]:+.3f} s/lap ({hard["Compound"].iloc[0]})', zorder=4)
                deg_results[drv] = {'deg_rate': coeffs[0], 'n_laps': int(mask.sum()),
                                     'mean_pace': y[mask].mean(), 'compound': hard['Compound'].iloc[0]}

    ax4d.set_xlabel('TyreLife (周)', fontsize=STYLE['label_size'] - 1)
    ax4d.set_ylabel('ラップタイム (秒)', fontsize=STYLE['label_size'] - 1)
    ax4d.set_title('4D: ラップタイム推移\n(クリーンラップ、線形回帰、燃料補正なし)', fontsize=12)
    ax4d.legend(loc='upper left', fontsize=9, framealpha=0.3)
    ax4d.grid(True, color=STYLE['grid_color'], alpha=0.4)

    chart4_b64 = fig_to_base64(fig4)

    # ================================================================
    # 数値サマリー
    # ================================================================
    # スピード統計
    speed_summary = []
    for drv in DRIVERS:
        clean = clean_data[drv]
        row = {'Driver': drv}
        for col, label in zip(SPEED_COLS, SPEED_SHORT):
            vals = clean[col].dropna()
            row[f'{label}_mean'] = vals.mean() if len(vals) > 0 else np.nan
            row[f'{label}_std'] = vals.std() if len(vals) > 1 else np.nan
        speed_summary.append(row)
    speed_df = pd.DataFrame(speed_summary)

    # 一貫性
    consist_data = []
    for drv in DRIVERS:
        clean = clean_data[drv]
        for stint in sorted(clean['Stint'].unique()):
            sc = clean[clean['Stint'] == stint]
            comp = sc['Compound'].iloc[0] if len(sc) > 0 else '?'
            row = {'Driver': drv, 'Stint': int(stint), 'Compound': comp, 'N': len(sc)}
            for sec, col in [('S1', 'S1Sec'), ('S2', 'S2Sec'), ('S3', 'S3Sec'), ('Lap', 'LapTimeSec')]:
                vals = sc[col].dropna()
                row[f'{sec}_std'] = vals.std() if len(vals) >= 2 else np.nan
            consist_data.append(row)
    consist_df = pd.DataFrame(consist_data)

    # ================================================================
    # 考察テキスト自動生成
    # ================================================================
    # 戦略概要
    def stint_desc(drv):
        lines = []
        for s in stints[drv]:
            lines.append(f"{s['compound']}({s['laps']}, {s['n']}周)")
        return ' → '.join(lines)

    is_teammate = (team1 == team2)
    title_label = f'{team1}チームメイト比較' if is_teammate else f'{team1} vs {team2}'

    strategy_html = f"""<h3>戦略の概要</h3>
<ul>
<li><strong>{drv1}</strong>: {stint_desc(drv1)}。ピットイン: L{pit_laps[drv1] if pit_laps[drv1] else 'なし'}</li>
<li><strong>{drv2}</strong>: {stint_desc(drv2)}。ピットイン: L{pit_laps[drv2] if pit_laps[drv2] else 'なし'}</li>
<li><strong>VSC期間</strong>: {', '.join(f'L{s}-{e}' for s, e in vsc_periods)}</li>
</ul>"""

    # セクター一貫性の考察
    def sector_stats_text(drv):
        clean = clean_data[drv]
        hard = clean[clean['Compound'] == 'HARD']
        if len(hard) < 5:
            hard = clean  # HARDが不十分なら全クリーン
        stds = {}
        for sec, col in [('S1', 'S1Sec'), ('S2', 'S2Sec'), ('S3', 'S3Sec')]:
            v = hard[col].dropna()
            stds[sec] = v.std() if len(v) >= 2 else np.nan
        st_vals = hard['SpeedST'].dropna()
        st_std = st_vals.std() if len(st_vals) >= 2 else np.nan
        st_mean = st_vals.mean() if len(st_vals) > 0 else np.nan
        st_range = (st_vals.max() - st_vals.min()) if len(st_vals) > 0 else np.nan
        best = min(stds, key=lambda k: stds[k]) if all(np.isfinite(v) for v in stds.values()) else 'N/A'
        worst = max(stds, key=lambda k: stds[k]) if all(np.isfinite(v) for v in stds.values()) else 'N/A'
        text = f"""<h4>{drv} ({drv_team[drv]})</h4>
<ul>
<li><strong>最も安定</strong>: {best} (SD={stds.get(best, 0):.3f}s)</li>
<li><strong>最もバラつき</strong>: {worst} (SD={stds.get(worst, 0):.3f}s)</li>
<li><strong>スピードトラップ</strong>: 平均 {st_mean:.1f} km/h, SD={st_std:.1f} km/h, レンジ={st_range:.0f} km/h</li>
</ul>"""
        return text, stds, st_std, st_mean

    t1_text, t1_stds, t1_st_std, t1_st_mean = sector_stats_text(drv1)
    t2_text, t2_stds, t2_st_std, t2_st_mean = sector_stats_text(drv2)

    # デグ考察
    FUEL_EFFECT = -0.06
    deg_html = ""
    if drv1 in deg_results and drv2 in deg_results:
        d1d, d2d = deg_results[drv1], deg_results[drv2]
        d1c, d2c = d1d['deg_rate'] - FUEL_EFFECT, d2d['deg_rate'] - FUEL_EFFECT
        deg_html = f"""<li><strong>デグラデーション(生)</strong>: {drv1}={d1d['deg_rate']:+.3f} s/lap (n={d1d['n_laps']}, {d1d['compound']}) vs
    {drv2}={d2d['deg_rate']:+.3f} s/lap (n={d2d['n_laps']}, {d2d['compound']})。
    マイナス値=燃料軽量化効果が支配的。</li>
<li><strong>燃料補正後推定</strong>(0.06 s/lap補正): {drv1}≒{d1c:+.3f}, {drv2}≒{d2c:+.3f} s/lap。</li>"""

    # 全体考察
    pace_note = ""
    if len(mc) > 0:
        mean_delta = mc['delta'].mean()
        pace_note = f"クリーンラップ平均デルタ: <code>{mean_delta:+.3f}s</code> ({'{}が平均的に速い'.format(drv1) if mean_delta < 0 else '{}が平均的に速い'.format(drv2)})。"

    # ================================================================
    # HTMLテーブル生成
    # ================================================================
    def stats_table(sdf):
        headers = ['Stint', 'Compound', 'Laps', 'N',
                   'S1 mean', 'S1 SD', 'S2 mean', 'S2 SD', 'S3 mean', 'S3 SD',
                   'Lap mean', 'Lap SD', 'ST mean', 'ST SD']
        rows = []
        for _, r in sdf.iterrows():
            rows.append([
                int(r['Stint']), r['Compound'], r['Laps'], int(r['N_clean']),
                format_time(r.get('S1_mean')), format_time(r.get('S1_std')),
                format_time(r.get('S2_mean')), format_time(r.get('S2_std')),
                format_time(r.get('S3_mean')), format_time(r.get('S3_std')),
                format_time(r.get('LapTime_mean')), format_time(r.get('LapTime_std')),
                f"{r.get('SpeedST_mean', 0):.1f}" if pd.notna(r.get('SpeedST_mean')) else '-',
                f"{r.get('SpeedST_std', 0):.1f}" if pd.notna(r.get('SpeedST_std')) else '-',
            ])
        return make_table_html(headers, rows)

    speed_headers = ['Driver'] + [f'{l} mean' for l in SPEED_LABELS] + [f'{l} SD' for l in SPEED_LABELS]
    speed_rows = []
    for _, r in speed_df.iterrows():
        row = [r['Driver']]
        for l in SPEED_SHORT:
            row.append(f"{r.get(f'{l}_mean', 0):.1f}" if pd.notna(r.get(f'{l}_mean')) else '-')
        for l in SPEED_SHORT:
            row.append(f"{r.get(f'{l}_std', 0):.1f}" if pd.notna(r.get(f'{l}_std')) else '-')
        speed_rows.append(row)
    speed_tbl = make_table_html(speed_headers, speed_rows)

    deg_tbl_rows = []
    for drv in DRIVERS:
        if drv in deg_results:
            d = deg_results[drv]
            deg_tbl_rows.append([drv, d['compound'], f"{d['deg_rate']:+.4f}", d['n_laps'], f"{d['mean_pace']:.3f}"])
    deg_tbl = make_table_html(['Driver', 'Compound', 'Deg Rate (s/lap)', 'N', 'Mean Pace (s)'], deg_tbl_rows)

    consist_rows = []
    for _, r in consist_df.iterrows():
        consist_rows.append([r['Driver'], int(r['Stint']), r['Compound'], int(r['N']),
                             format_time(r['S1_std']), format_time(r['S2_std']),
                             format_time(r['S3_std']), format_time(r['Lap_std'])])
    consist_tbl = make_table_html(['Driver', 'Stint', 'Compound', 'N', 'S1 SD', 'S2 SD', 'S3 SD', 'Lap SD'], consist_rows)

    # ================================================================
    # HTML出力
    # ================================================================
    print('  HTML生成中...')
    accent1 = colors[drv1]
    accent2 = colors[drv2]

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>2026 R1 AUS — {drv1} vs {drv2}</title>
<style>
:root {{ --bg: #0f0f1a; --card-bg: #1a1a2e; --border: #333355; --text: #e0e0e0; --c1: {accent1}; --c2: {accent2}; }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:var(--bg); color:var(--text); font-family:'Yu Gothic','Meiryo','Segoe UI',sans-serif;
        line-height:1.6; padding:20px; max-width:1200px; margin:0 auto; }}
h1 {{ color:#fff; font-size:1.8em; margin:20px 0 5px; border-bottom:2px solid var(--border); padding-bottom:8px; }}
h2 {{ color:#fff; font-size:1.4em; margin:30px 0 10px; }}
h3 {{ color:#ccc; font-size:1.15em; margin:20px 0 8px; }}
h4 {{ color:#aaa; font-size:1.0em; margin:15px 0 5px; }}
p, li {{ font-size:0.95em; margin-bottom:6px; }}
ul, ol {{ padding-left:24px; }}
code {{ background:#2a2a3e; padding:2px 6px; border-radius:3px; font-size:0.9em; }}
.card {{ background:var(--card-bg); border:1px solid var(--border); border-radius:8px; padding:20px; margin:15px 0; }}
.chart-img {{ width:100%; border-radius:6px; margin:10px 0; }}
.table-scroll {{ overflow-x:auto; margin:10px 0; }}
table {{ border-collapse:collapse; width:100%; font-size:0.82em; background:var(--card-bg); }}
th, td {{ padding:5px 8px; border:1px solid var(--border); text-align:right; white-space:nowrap; }}
th {{ background:#252540; color:#fff; position:sticky; top:0; }}
td:first-child, th:first-child {{ text-align:center; }}
tr:hover {{ background:#252545; }}
.vsc-row {{ background:#3d3d1a !important; }}
.toc {{ background:var(--card-bg); border:1px solid var(--border); border-radius:8px; padding:15px 25px; margin:15px 0; }}
.toc a {{ color:var(--c1); text-decoration:none; }}
.toc a:hover {{ text-decoration:underline; }}
.tag1 {{ color:var(--c1); font-weight:bold; }}
.tag2 {{ color:var(--c2); font-weight:bold; }}
.note {{ background:#1e1e3a; border-left:3px solid #667; padding:10px 15px; margin:10px 0; font-size:0.9em; }}
.back-top {{ position:fixed; bottom:20px; right:20px; background:var(--card-bg);
    border:1px solid var(--border); padding:8px 12px; border-radius:5px; color:#fff;
    text-decoration:none; font-size:0.85em; }}
@media (max-width:768px) {{ body {{ padding:10px; }} h1 {{ font-size:1.4em; }} table {{ font-size:0.72em; }} }}
</style>
</head>
<body>

<h1>2026 R1 オーストラリアGP — <span class="tag1">{drv1} ({team1})</span> vs <span class="tag2">{drv2} ({team2})</span></h1>
<p style="color:#888;font-size:0.85em;">{title_label} | 生成日: {datetime.now().strftime('%Y-%m-%d %H:%M')} | FastF1 v3.8.1 | 燃料補正なし</p>

<div class="toc"><strong>目次</strong>
<ol>
<li><a href="#strategy">戦略概要</a></li>
<li><a href="#chart1">ラップタイム / デルタ / スピードトラップ</a></li>
<li><a href="#chart2">{drv1} セクター一貫性</a></li>
<li><a href="#chart3">{drv2} セクター一貫性</a></li>
<li><a href="#chart4">直接比較サマリー</a></li>
<li><a href="#overall">総合考察</a></li>
</ol></div>

<div class="card" id="strategy">
<h2>1. 戦略概要</h2>
{strategy_html}
<table>
<tr><th>項目</th><th class="tag1">{drv1} ({team1})</th><th class="tag2">{drv2} ({team2})</th></tr>
<tr><td>グリッド</td><td>P{drv_grid[drv1]}</td><td>P{drv_grid[drv2]}</td></tr>
<tr><td>フィニッシュ</td><td>P{drv_pos[drv1]}</td><td>P{drv_pos[drv2]}</td></tr>
<tr><td>戦略</td><td>{stint_desc(drv1)}</td><td>{stint_desc(drv2)}</td></tr>
<tr><td>ステータス</td><td>{drv_status[drv1]}</td><td>{drv_status[drv2]}</td></tr>
</table>
</div>

<div class="card" id="chart1">
<h2>2. ラップタイム / デルタ / スピードトラップ</h2>
<img class="chart-img" src="data:image/png;base64,{chart1_b64}" alt="Chart 1">
<h3>考察</h3>
<p>{pace_note}</p>
<h3>元データ</h3>
<div class="note">黄色行=VSC周。Delta: マイナス={drv1}が速い。ST=スピードトラップ(km/h)。</div>
{c1_html}
</div>

<div class="card" id="chart2">
<h2>3. {drv1} セクター一貫性 & スピードトラップ</h2>
<img class="chart-img" src="data:image/png;base64,{chart2_b64}" alt="{drv1} sectors">
{t1_text}
<h3>元データ: スティント別統計</h3>
{stats_table(stats1)}
</div>

<div class="card" id="chart3">
<h2>4. {drv2} セクター一貫性 & スピードトラップ</h2>
<img class="chart-img" src="data:image/png;base64,{chart3_b64}" alt="{drv2} sectors">
{t2_text}
<h3>元データ: スティント別統計</h3>
{stats_table(stats2)}
</div>

<div class="card">
<h3>セクター一貫性比較</h3>
<p class="note"><strong>注意</strong>: SDはスティント全体で計算。燃料消費(約0.06s/lap)の影響を含むため、
長スティントほどSDが大きくなる傾向あり。</p>
<ul>
<li><strong>S1</strong>: {drv1} SD={t1_stds.get('S1',0):.3f}s vs {drv2} SD={t2_stds.get('S2',0):.3f}s</li>
<li><strong>S2</strong>: {drv1} SD={t1_stds.get('S2',0):.3f}s vs {drv2} SD={t2_stds.get('S2',0):.3f}s</li>
<li><strong>S3</strong>: {drv1} SD={t1_stds.get('S3',0):.3f}s vs {drv2} SD={t2_stds.get('S3',0):.3f}s</li>
<li><strong>スピードトラップSD</strong>: {drv1}={t1_st_std:.1f} km/h vs {drv2}={t2_st_std:.1f} km/h</li>
</ul>
{consist_tbl}
</div>

<div class="card" id="chart4">
<h2>5. 直接比較サマリー</h2>
<img class="chart-img" src="data:image/png;base64,{chart4_b64}" alt="Chart 4">

<h3>考察</h3>
<ul>
{deg_html}
<li><strong>セクター累積差</strong> ({compare_compound}共通{len(compare_laps)}周):
    S1={sector_cum['S1']:+.2f}s, S2={sector_cum['S2']:+.2f}s, S3={sector_cum['S3']:+.2f}s,
    合計={total_diff:+.2f}s</li>
<li><strong>スピードトラップ平均</strong>: {drv1}={t1_st_mean:.1f} vs {drv2}={t2_st_mean:.1f} km/h
    (差={t1_st_mean - t2_st_mean:+.1f} km/h)</li>
</ul>

<h3>元データ: スピード分布 (km/h, クリーンラップ)</h3>
<p class="note">S1末端=Sector1末端速度, S2末端=Sector2末端速度, FL=フィニッシュライン通過速度, ST=スピードトラップ(最高速計測点)</p>
{speed_tbl}

<h3>元データ: デグラデーション</h3>
{deg_tbl}

<h3>元データ: セクター累積タイム差</h3>
<table>
<tr><th>セクター</th><th>累積差 (秒)</th><th>有利</th></tr>
<tr><td>S1</td><td>{sector_cum['S1']:+.3f}</td><td>{drv1 + '有利' if sector_cum['S1'] < 0 else drv2 + '有利'}</td></tr>
<tr><td>S2</td><td>{sector_cum['S2']:+.3f}</td><td>{drv1 + '有利' if sector_cum['S2'] < 0 else drv2 + '有利'}</td></tr>
<tr><td>S3</td><td>{sector_cum['S3']:+.3f}</td><td>{drv1 + '有利' if sector_cum['S3'] < 0 else drv2 + '有利'}</td></tr>
<tr><td><strong>Total</strong></td><td><strong>{total_diff:+.3f}</strong></td><td><strong>{drv1 + '有利' if total_diff < 0 else drv2 + '有利'}</strong></td></tr>
</table>
</div>

<div class="card" id="overall">
<h2>6. 総合考察</h2>
<ul>
<li><strong>結果</strong>: {drv1} P{drv_pos[drv1]} (Grid P{drv_grid[drv1]}) vs {drv2} P{drv_pos[drv2]} (Grid P{drv_grid[drv2]})</li>
<li>{pace_note}</li>
<li><strong>セクター特性</strong>: セクター累積差で最も大きい差がついたのは
    {'S1(低速セクション) → メカニカルグリップ差' if max(sector_cum, key=lambda k: abs(sector_cum[k])) == 'S1' else
     'S2(中高速セクション) → 高速コーナー性能差' if max(sector_cum, key=lambda k: abs(sector_cum[k])) == 'S2' else
     'S3(ストレート区間) → PUパワー/ドラッグ差'}を示唆。</li>
</ul>
<div class="note">
<strong>注意事項</strong>
<ul>
<li>全データは燃料補正前。</li>
<li>VSC周・ピットイン/アウトラップはクリーンラップ分析から除外済み。</li>
<li>2026年新規則（アクティブエアロ、Overtake Mode）の影響はデータから分離不可。</li>
<li>スピードトラップとエネルギーデプロイの関係は推定。</li>
</ul>
</div>
</div>

<a class="back-top" href="#">Top</a>
</body></html>"""

    # ファイル名生成
    tag = f'{drv1.lower()}_vs_{drv2.lower()}'
    out_path = OUT_DIR / f'race_h2h_{tag}_{YEAR}_r{ROUND_NUMBER:02d}.html'
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    size_kb = out_path.stat().st_size / 1024
    print(f'  出力: {out_path} ({size_kb:.0f} KB)')
    return out_path


# ============================================================
# メイン: コマンドライン引数 or 4ペア一括
# ============================================================
if __name__ == '__main__':
    if len(sys.argv) == 3:
        # 単一ペア: python race_h2h_2026_r01.py RUS LEC
        d1, d2 = sys.argv[1].upper(), sys.argv[2].upper()
        if d1 not in all_driver_data:
            print(f'エラー: {d1} のデータがありません')
            sys.exit(1)
        if d2 not in all_driver_data:
            print(f'エラー: {d2} のデータがありません')
            sys.exit(1)
        generate_h2h_report(d1, d2)
    else:
        # 4ペア一括生成
        pairs = [('RUS', 'LEC'), ('RUS', 'ANT'), ('LEC', 'HAM'), ('ANT', 'HAM')]
        outputs = []
        for d1, d2 in pairs:
            if d1 in all_driver_data and d2 in all_driver_data:
                out = generate_h2h_report(d1, d2)
                outputs.append(out)
            else:
                print(f'スキップ: {d1} or {d2} のデータなし')
        print(f'\n=== 完了: {len(outputs)}レポート生成 ===')
        for o in outputs:
            print(f'  {o}')
