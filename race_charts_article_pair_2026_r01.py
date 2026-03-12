"""
============================================================
2026 オーストラリアGP — 記事用チャート ペア別一括生成（ライトテーマ）
============================================================
使い方:
  python race_charts_article_pair_2026_r01.py LEC ANT
  python race_charts_article_pair_2026_r01.py LEC HAM
  python race_charts_article_pair_2026_r01.py          # → LEC vs ANT, LEC vs HAM 一括

出力（各ペアごとにサブフォルダ）:
  art_laptime_delta.png   — ラップタイム / デルタ / スピードトラップ
  art_speed_boxplot.png   — スピード分布（箱ひげ図・全ラップ）
  art_speed_boxplot_L26.png — スピード分布（L26以降）
  art_sector_compare.png  — セクター比較 (S1 / S2 / S3)
  art_sector_table.png    — セクター比較テーブル
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
import colorsys
import sys
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# GP設定
# ============================================================
YEAR = 2026
GP_NAME = 'Australia'
ROUND_NUMBER = 1

BASE_DIR = Path(f'./data/{YEAR}_R{ROUND_NUMBER:02d}_{GP_NAME}/article')

# ============================================================
# ライトテーマ
# ============================================================
LT = {
    'bg': '#FFFFFF', 'card_bg': '#F7F7FA', 'text': '#1a1a2e',
    'axis': '#444444', 'grid_maj': '#CCCCCC', 'grid_min': '#E8E8E8',
    'spine': '#AAAAAA', 'vsc': '#FFD700', 'vsc_alpha': 0.20,
    'title_size': 18, 'label_size': 13, 'tick_size': 11,
    'line_w': 2.8, 'marker_s': 35, 'marker_s_sm': 20,
}

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
# データ読み込み（1回）
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


# ============================================================
# ユーティリティ
# ============================================================
def get_pair_colors(drv1, drv2):
    """ドライバーペアの色を取得（同チームなら2nd暗め）"""
    c1 = TEAM_COLORS.get(drv_team.get(drv1, ''), '#444')
    c2 = TEAM_COLORS.get(drv_team.get(drv2, ''), '#444')
    if c1 == c2:
        r, g, b = int(c1[1:3], 16)/255, int(c1[3:5], 16)/255, int(c1[5:7], 16)/255
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        l2 = min(1.0, l * 0.55)
        r2, g2, b2 = colorsys.hls_to_rgb(h, l2, s)
        c2 = f'#{int(r2*255):02x}{int(g2*255):02x}{int(b2*255):02x}'
    return c1, c2


def setup_ax(ax, ylabel=None, title=None, xlabel=None):
    ax.set_facecolor(LT['bg'])
    ax.tick_params(colors=LT['axis'], labelsize=LT['tick_size'])
    ax.xaxis.set_major_locator(MultipleLocator(5))
    ax.grid(True, which='major', color=LT['grid_maj'], linewidth=0.6, alpha=0.8)
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
    for start, end in vsc_periods:
        ax.axvspan(start - 0.5, end + 0.5, alpha=LT['vsc_alpha'], color=LT['vsc'], zorder=0)
    if label_y is not None:
        for start, end in vsc_periods:
            ax.text((start + end) / 2, label_y, 'VSC', ha='center', va='bottom',
                    fontsize=10, color='#B8960A', fontweight='bold', alpha=0.9)


def save_fig(fig, path):
    fig.savefig(path, dpi=180, facecolor=LT['bg'], bbox_inches='tight')
    size_kb = path.stat().st_size / 1024
    print(f'  保存: {path.name} ({size_kb:.0f} KB)')
    plt.close(fig)


def draw_boxplot_legend(ax_leg):
    """箱ひげ図の読み方パネル"""
    ax_leg.set_facecolor('white')
    ax_leg.set_xlim(0, 10); ax_leg.set_ylim(0, 10)
    ax_leg.set_xticks([]); ax_leg.set_yticks([])
    for spine in ax_leg.spines.values():
        spine.set_color(LT['spine']); spine.set_linewidth(0.5)

    bx, bw = 2.8, 1.8
    q1, med, q3 = 2.5, 4.5, 6.2
    whi_lo, whi_hi = 1.2, 8.0
    outlier_y = 9.2
    lc = '#444444'
    ax_leg.plot([bx, bx], [whi_lo, q1], color=lc, linewidth=1.2)
    ax_leg.plot([bx, bx], [q3, whi_hi], color=lc, linewidth=1.2)
    ax_leg.plot([bx-0.4, bx+0.4], [whi_lo, whi_lo], color=lc, linewidth=1.2)
    ax_leg.plot([bx-0.4, bx+0.4], [whi_hi, whi_hi], color=lc, linewidth=1.2)
    box_rect = plt.Rectangle((bx-bw/2, q1), bw, q3-q1,
                               facecolor='#BBCCDD', edgecolor=lc, linewidth=1.2, alpha=0.7)
    ax_leg.add_patch(box_rect)
    ax_leg.plot([bx-bw/2, bx+bw/2], [med, med], color='#CC3333', linewidth=2)
    ax_leg.plot(bx, outlier_y, 'o', color=lc, markersize=5, markerfacecolor='none')

    tx = 5.5
    annot = dict(fontsize=8, color=LT['text'], va='center', ha='left')
    arrow = dict(arrowstyle='-', color='#888', lw=0.5)
    ax_leg.annotate('外れ値', xy=(bx+0.3, outlier_y), xytext=(tx, outlier_y), arrowprops=arrow, **annot)
    ax_leg.annotate('上ひげ(最大値*)', xy=(bx+0.5, whi_hi), xytext=(tx, whi_hi), arrowprops=arrow, **annot)
    ax_leg.annotate('Q3 (75%)', xy=(bx+bw/2+0.1, q3), xytext=(tx, q3), arrowprops=arrow, **annot)
    ax_leg.annotate('中央値', xy=(bx+bw/2+0.1, med), xytext=(tx, med),
                    arrowprops=dict(arrowstyle='-', color='#CC3333', lw=0.5),
                    fontsize=8, color='#CC3333', va='center', ha='left')
    ax_leg.annotate('Q1 (25%)', xy=(bx+bw/2+0.1, q1), xytext=(tx, q1), arrowprops=arrow, **annot)
    ax_leg.annotate('下ひげ(最小値*)', xy=(bx+0.5, whi_lo), xytext=(tx, whi_lo), arrowprops=arrow, **annot)
    ax_leg.text(5.0, 0.3, '*Q1/Q3から箱の1.5倍以内', fontsize=7, color='#888', ha='center')
    ax_leg.set_title('箱ひげ図の見方', fontsize=10, color=LT['text'], pad=6)


# ============================================================
# ペア別チャート生成
# ============================================================
def generate_pair_charts(drv1, drv2):
    """drv1 vs drv2 の記事用チャート5枚を生成"""
    tag = f'{drv1.lower()}_vs_{drv2.lower()}'
    out_dir = BASE_DIR / tag
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f'\n{"="*60}')
    print(f'{drv1} vs {drv2} 記事用チャート生成')
    print(f'{"="*60}')

    c1, c2 = get_pair_colors(drv1, drv2)
    colors = {drv1: c1, drv2: c2}
    DRIVERS = [drv1, drv2]

    dd = {d: all_driver_data[d] for d in DRIVERS}
    pl = {d: all_pit_laps[d] for d in DRIVERS}
    cd = {d: all_clean_data[d] for d in DRIVERS}
    both_clean = set(cd[drv1]['LapNum']) & set(cd[drv2]['LapNum'])

    # LECのピットイン周を基準にL26以降のクリーンデータ
    # (LEC基準: 最初のピットイン+1以降)
    lec_first_pit = all_pit_laps.get('LEC', [25])[0]
    l26_start = lec_first_pit + 1  # L26
    cd_l26 = {}
    for d in DRIVERS:
        cd_l26[d] = cd[d][cd[d]['LapNum'] >= l26_start]
    both_clean_l26 = set(cd_l26[drv1]['LapNum']) & set(cd_l26[drv2]['LapNum'])

    team1, team2 = drv_team.get(drv1, ''), drv_team.get(drv2, '')

    # ============================
    # 1. ラップタイム / デルタ / スピードトラップ
    # ============================
    print(f'  [1/5] ラップタイム / デルタ / スピードトラップ...')
    fig, (axa, axb, axc) = plt.subplots(3, 1, figsize=(16, 14),
                                          height_ratios=[3, 1, 1.5],
                                          gridspec_kw={'hspace': 0.08},
                                          facecolor=LT['bg'])
    for ax in [axa, axb, axc]:
        setup_ax(ax)
        add_vsc(ax)

    for drv in DRIVERS:
        df = dd[drv]
        valid = df[df['LapTimeSec'].notna() & (df['LapTimeSec'] < 200)]
        clean_set = set(cd[drv]['LapNum'].tolist())
        for stint in valid['Stint'].unique():
            sdf = valid[valid['Stint'] == stint]
            sc = sdf[sdf['LapNum'].isin(clean_set)]
            axa.plot(sc['LapNum'], sc['LapTimeSec'], color=colors[drv],
                     linewidth=LT['line_w'], alpha=0.9,
                     label=drv if stint == valid['Stint'].min() else None, zorder=3)
            axa.scatter(sc['LapNum'], sc['LapTimeSec'],
                        c=[TYRE_COLORS.get(c, '#888') for c in sc['Compound']],
                        s=LT['marker_s'], edgecolors=colors[drv], linewidths=1.0, zorder=4)
            dirty = sdf[~sdf['LapNum'].isin(clean_set)]
            if len(dirty) > 0:
                axa.scatter(dirty['LapNum'], dirty['LapTimeSec'],
                            marker='x', c=colors[drv], s=LT['marker_s_sm'], alpha=0.35, zorder=2)

    # ピット線
    for drv in DRIVERS:
        for ax in [axa, axb, axc]:
            for p in pl[drv]:
                ax.axvline(p, color=colors[drv], linestyle='--', alpha=0.6, linewidth=1.5, zorder=1)

    all_ct = pd.concat([cd[d]['LapTimeSec'].dropna() for d in DRIVERS])
    axa.set_ylim(max(all_ct.min() - 1, 75), all_ct.quantile(0.98) + 2)
    axa.set_ylabel('ラップタイム (秒)', color=LT['text'], fontsize=LT['label_size'])
    axa.legend(loc='upper right', fontsize=11, framealpha=0.9, facecolor='white',
               edgecolor=LT['spine'], labelcolor=LT['text'])
    axa.tick_params(labelbottom=False)

    # ピットラベル
    y_bottom, y_top = axa.get_ylim()
    y_range = y_top - y_bottom
    for i, drv in enumerate(DRIVERS):
        for p in pl[drv]:
            y_pos = y_top - y_range * (0.03 + 0.08 * i)
            axa.text(p, y_pos, f'{drv} PIT L{p}', ha='center', va='top',
                     fontsize=9, fontweight='bold', color=colors[drv], alpha=0.9,
                     bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                               edgecolor=colors[drv], alpha=0.85, linewidth=1.0))

    axa.set_title(f'{drv1} vs {drv2} ラップタイム / デルタ / スピードトラップ\n'
                  f'(丸=クリーン, x=VSC/ピット, 黄帯=VSC, 破線=ピットイン)',
                  color=LT['text'], fontsize=LT['title_size'], fontweight='bold', pad=14)

    # ギャップサマリー表（パネル1右上）
    # リーダーとの差からdrv1-drv2間ギャップを計算
    leader_drv = results.iloc[0]['Abbreviation']
    leader_laps_df = laps_all[laps_all['Driver'] == leader_drv].sort_values('LapNumber')
    leader_times = {}
    for _, lr in leader_laps_df.iterrows():
        lnum = int(lr['LapNumber'])
        lt = lr['Time']
        if pd.notna(lt):
            leader_times[lnum] = lt.total_seconds()

    gap_d = {}
    for drv in DRIVERS:
        drv_laps_df = laps_all[laps_all['Driver'] == drv].sort_values('LapNumber')
        g = {}
        for _, lr in drv_laps_df.iterrows():
            lnum = int(lr['LapNumber'])
            lt = lr['Time']
            if pd.notna(lt) and lnum in leader_times:
                g[lnum] = lt.total_seconds() - leader_times[lnum]
        gap_d[drv] = g

    g1_l26 = gap_d.get(drv1, {}).get(l26_start, None)
    g2_l26 = gap_d.get(drv2, {}).get(l26_start, None)
    last_lap = max(max(gap_d.get(drv1, {}).keys(), default=0),
                   max(gap_d.get(drv2, {}).keys(), default=0))
    g1_fin = gap_d.get(drv1, {}).get(last_lap, None)
    g2_fin = gap_d.get(drv2, {}).get(last_lap, None)

    if g1_l26 is not None and g2_l26 is not None:
        pair_gap_l26 = g2_l26 - g1_l26  # drv2がdrv1より何秒遅いか（正=drv2が後方）
        pair_gap_fin = (g2_fin or 0) - (g1_fin or 0)
        pair_gap_diff = pair_gap_fin - pair_gap_l26

        tbl_data = [
            [f'L{l26_start}', f'{pair_gap_l26:+.3f}s'],
            [f'L{last_lap}', f'{pair_gap_fin:+.3f}s'],
            ['差分', f'{pair_gap_diff:+.3f}s'],
        ]
        tbl = axa.table(cellText=tbl_data,
                         colLabels=[f'{drv1}-{drv2}', 'Gap'],
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
            elif row == len(tbl_data):
                cell.set_facecolor('#3D5A99')
                cell.set_text_props(fontweight='bold', color='white')
            else:
                cell.set_facecolor('#E8EDF5')
                cell.set_text_props(color=LT['text'])

    # デルタ
    merged = pd.merge(
        dd[drv1][['LapNum', 'LapTimeSec']].rename(columns={'LapTimeSec': f'{drv1}_s'}),
        dd[drv2][['LapNum', 'LapTimeSec']].rename(columns={'LapTimeSec': f'{drv2}_s'}),
        on='LapNum', how='inner')
    merged['delta'] = merged[f'{drv1}_s'] - merged[f'{drv2}_s']
    merged['is_clean'] = merged['LapNum'].isin(both_clean)
    mc = merged[merged['is_clean']]

    axb.bar(mc['LapNum'], mc['delta'],
            color=[colors[drv1] if d < 0 else colors[drv2] for d in mc['delta']],
            alpha=0.75, width=0.8, zorder=3)
    axb.axhline(0, color=LT['axis'], linewidth=1.0, alpha=0.5)
    axb.set_ylabel(f'Delta (秒)\n{drv1} < 0 < {drv2}', color=LT['text'],
                   fontsize=LT['label_size'] - 1)
    if len(mc) > 0:
        d_max = max(abs(mc['delta'].min()), abs(mc['delta'].max())) + 0.5
        axb.set_ylim(-d_max, d_max)
    axb.tick_params(labelbottom=False)

    # スピードトラップ
    for drv in DRIVERS:
        clean = cd[drv]
        cs = clean[clean['SpeedST'].notna()].sort_values('LapNum')
        for stint in sorted(cs['Stint'].unique()):
            sc = cs[cs['Stint'] == stint]
            axc.plot(sc['LapNum'], sc['SpeedST'], color=colors[drv],
                     linewidth=LT['line_w'] - 0.5, alpha=0.85, zorder=3,
                     label=drv if stint == sorted(cs['Stint'].unique())[0] else None)
            axc.scatter(sc['LapNum'], sc['SpeedST'],
                        c=[TYRE_COLORS.get(c, '#888') for c in sc['Compound']],
                        s=LT['marker_s_sm'], edgecolors=colors[drv], linewidths=0.8, zorder=4)

    all_st = pd.concat([cd[d]['SpeedST'].dropna() for d in DRIVERS])
    st_m = (all_st.max() - all_st.min()) * 0.12 + 3
    axc.set_ylim(all_st.min() - st_m, all_st.max() + st_m)
    axc.set_xlabel('ラップ数', color=LT['text'], fontsize=LT['label_size'])
    axc.set_ylabel('スピードトラップ (km/h)', color=LT['text'], fontsize=LT['label_size'])
    axc.legend(loc='lower right', fontsize=10, framealpha=0.9, facecolor='white',
               edgecolor=LT['spine'], labelcolor=LT['text'])

    # L26以降のスピードトラップ傾向を点線四角形で強調
    # drv1のST中央値がdrv2より高いか判定
    st1_l26 = cd_l26[drv1]['SpeedST'].dropna()
    st2_l26 = cd_l26[drv2]['SpeedST'].dropna()
    if len(st1_l26) > 0 and len(st2_l26) > 0:
        faster_st = drv1 if st1_l26.median() > st2_l26.median() else drv2
        slower_st = drv2 if faster_st == drv1 else drv1
        st_y_lo, st_y_hi = axc.get_ylim()
        rect = plt.Rectangle((l26_start - 0.5, st_y_lo + (st_y_hi - st_y_lo) * 0.05),
                              last_lap - l26_start + 1, (st_y_hi - st_y_lo) * 0.88,
                              linewidth=2, edgecolor=colors[faster_st], facecolor='none',
                              linestyle='--', alpha=0.8, zorder=8)
        axc.add_patch(rect)
        axc.text(last_lap + 0.5, st_y_hi - (st_y_hi - st_y_lo) * 0.08,
                 f'L{l26_start}以降: {faster_st}が{slower_st}より\n安定して高い速度を記録',
                 fontsize=10, color=colors[faster_st], fontweight='bold',
                 ha='right', va='top',
                 bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                           edgecolor=colors[faster_st], alpha=0.9, linewidth=1.2))

    save_fig(fig, out_dir / 'art_laptime_delta.png')

    # ============================
    # 2. スピード分布（全ラップ）
    # ============================
    print(f'  [2/5] スピード分布（全ラップ）...')
    fig_bp = plt.figure(figsize=(14, 7), facecolor=LT['bg'])
    gs_bp = GridSpec(1, 5, figure=fig_bp, wspace=0.4)
    ax_bp = fig_bp.add_subplot(gs_bp[0, :3])
    ax_bp_leg = fig_bp.add_subplot(gs_bp[0, 3])

    ax_bp.set_facecolor('white')
    ax_bp.tick_params(colors=LT['axis'], labelsize=LT['tick_size'])
    ax_bp.grid(True, axis='y', color=LT['grid_maj'], linewidth=0.6, alpha=0.8)
    for spine in ax_bp.spines.values():
        spine.set_color(LT['spine'])

    bp1 = ax_bp.boxplot([cd[drv1][col].dropna().values for col in SPEED_COLS],
                         positions=np.arange(4)*3, widths=0.8, patch_artist=True,
                         showfliers=True, flierprops={'markersize': 4})
    bp2 = ax_bp.boxplot([cd[drv2][col].dropna().values for col in SPEED_COLS],
                         positions=np.arange(4)*3+1, widths=0.8, patch_artist=True,
                         showfliers=True, flierprops={'markersize': 4})
    for p in bp1['boxes']: p.set_facecolor(c1); p.set_alpha(0.5); p.set_edgecolor(c1)
    for p in bp2['boxes']: p.set_facecolor(c2); p.set_alpha(0.5); p.set_edgecolor(c2)
    for e in ['whiskers','caps']:
        for l in bp1[e]: l.set_color(LT['axis'])
        for l in bp2[e]: l.set_color(LT['axis'])
    for l in bp1['medians']: l.set_color(c1); l.set_linewidth(2)
    for l in bp2['medians']: l.set_color(c2); l.set_linewidth(2)

    ax_bp.set_xticks(np.arange(4)*3+0.5)
    ax_bp.set_xticklabels(SPEED_SHORT, fontsize=LT['label_size'])
    ax_bp.set_ylabel('速度 (km/h)', color=LT['text'], fontsize=LT['label_size'])
    ax_bp.set_title(f'{drv1} vs {drv2} スピード分布比較 (クリーンラップ)',
                    color=LT['text'], fontsize=LT['title_size'], fontweight='bold', pad=14)
    ax_bp.legend([bp1['boxes'][0], bp2['boxes'][0]], [drv1, drv2],
                 loc='upper left', fontsize=11, framealpha=0.9, facecolor='white',
                 edgecolor=LT['spine'], labelcolor=LT['text'])
    ax_bp.text(0.5, -0.10,
               'S1末端=Sector1終点の通過速度  S2末端=Sector2終点の通過速度\n'
               'FL=フィニッシュライン通過速度  ST=スピードトラップ(FIA最高速計測点)',
               transform=ax_bp.transAxes, fontsize=9, color='#666', ha='center', va='top', style='italic')
    draw_boxplot_legend(ax_bp_leg)
    save_fig(fig_bp, out_dir / 'art_speed_boxplot.png')

    # ============================
    # 3. スピード分布（L26以降）
    # ============================
    print(f'  [3/5] スピード分布（L26以降）...')
    fig_bp2 = plt.figure(figsize=(14, 7), facecolor=LT['bg'])
    gs_bp2 = GridSpec(1, 5, figure=fig_bp2, wspace=0.4)
    ax_bp2 = fig_bp2.add_subplot(gs_bp2[0, :3])
    ax_bp2_leg = fig_bp2.add_subplot(gs_bp2[0, 3])

    ax_bp2.set_facecolor('white')
    ax_bp2.tick_params(colors=LT['axis'], labelsize=LT['tick_size'])
    ax_bp2.grid(True, axis='y', color=LT['grid_maj'], linewidth=0.6, alpha=0.8)
    for spine in ax_bp2.spines.values():
        spine.set_color(LT['spine'])

    bp1_l26 = ax_bp2.boxplot([cd_l26[drv1][col].dropna().values for col in SPEED_COLS],
                              positions=np.arange(4)*3, widths=0.8, patch_artist=True,
                              showfliers=True, flierprops={'markersize': 4})
    bp2_l26 = ax_bp2.boxplot([cd_l26[drv2][col].dropna().values for col in SPEED_COLS],
                              positions=np.arange(4)*3+1, widths=0.8, patch_artist=True,
                              showfliers=True, flierprops={'markersize': 4})
    for p in bp1_l26['boxes']: p.set_facecolor(c1); p.set_alpha(0.5); p.set_edgecolor(c1)
    for p in bp2_l26['boxes']: p.set_facecolor(c2); p.set_alpha(0.5); p.set_edgecolor(c2)
    for e in ['whiskers','caps']:
        for l in bp1_l26[e]: l.set_color(LT['axis'])
        for l in bp2_l26[e]: l.set_color(LT['axis'])
    for l in bp1_l26['medians']: l.set_color(c1); l.set_linewidth(2)
    for l in bp2_l26['medians']: l.set_color(c2); l.set_linewidth(2)

    ax_bp2.set_xticks(np.arange(4)*3+0.5)
    ax_bp2.set_xticklabels(SPEED_SHORT, fontsize=LT['label_size'])
    ax_bp2.set_ylabel('速度 (km/h)', color=LT['text'], fontsize=LT['label_size'])
    ax_bp2.set_title(f'{drv1} vs {drv2} スピード分布比較 (L{l26_start}以降・クリーンラップ)',
                     color=LT['text'], fontsize=LT['title_size'], fontweight='bold', pad=14)
    ax_bp2.legend([bp1_l26['boxes'][0], bp2_l26['boxes'][0]], [drv1, drv2],
                  loc='upper left', fontsize=11, framealpha=0.9, facecolor='white',
                  edgecolor=LT['spine'], labelcolor=LT['text'])
    ax_bp2.text(0.5, -0.12,
                'S1末端=Sector1終点の通過速度  S2末端=Sector2終点の通過速度\n'
                'FL=フィニッシュライン通過速度  ST=スピードトラップ(FIA最高速計測点)\n'
                f'L{l26_start}以降=LECピットイン後、両者HARDタイヤ',
                transform=ax_bp2.transAxes, fontsize=9, color='#666', ha='center', va='top', style='italic')
    draw_boxplot_legend(ax_bp2_leg)
    save_fig(fig_bp2, out_dir / 'art_speed_boxplot_L26.png')

    # ============================
    # 4. セクター比較 (S1 / S2 / S3)
    # ============================
    print(f'  [4/5] セクター比較...')
    sectors = [('S1', 'S1Sec', 'Sector 1 (秒)'),
               ('S2', 'S2Sec', 'Sector 2 (秒)'),
               ('S3', 'S3Sec', 'Sector 3 (秒)')]

    fig_sec, axes_sec = plt.subplots(6, 1, figsize=(16, 20),
                                      height_ratios=[3, 1, 3, 1, 3, 1],
                                      gridspec_kw={'hspace': 0.06},
                                      facecolor=LT['bg'])
    for si, (sname, scol, sylabel) in enumerate(sectors):
        ax_m = axes_sec[si * 2]
        ax_d = axes_sec[si * 2 + 1]

        for ax in [ax_m, ax_d]:
            setup_ax(ax)
            add_vsc(ax)

        for drv in DRIVERS:
            df = dd[drv]
            valid = df[df[scol].notna()]
            clean_set = set(cd[drv]['LapNum'].tolist())
            for stint in valid['Stint'].unique():
                sdf = valid[valid['Stint'] == stint]
                sc = sdf[sdf['LapNum'].isin(clean_set)]
                ax_m.plot(sc['LapNum'], sc[scol], color=colors[drv],
                          linewidth=LT['line_w'], alpha=0.9,
                          label=drv if stint == valid['Stint'].min() else None, zorder=3)
                ax_m.scatter(sc['LapNum'], sc[scol],
                             c=[TYRE_COLORS.get(c, '#888') for c in sc['Compound']],
                             s=LT['marker_s'], edgecolors=colors[drv], linewidths=1.0, zorder=4)
                dirty = sdf[~sdf['LapNum'].isin(clean_set)]
                if len(dirty) > 0:
                    ax_m.scatter(dirty['LapNum'], dirty[scol],
                                 marker='x', c=colors[drv], s=LT['marker_s_sm'], alpha=0.35, zorder=2)

        for drv in DRIVERS:
            for ax in [ax_m, ax_d]:
                for p in pl[drv]:
                    ax.axvline(p, color=colors[drv], linestyle='--', alpha=0.6, linewidth=1.5, zorder=1)

        acv = pd.concat([cd[d][scol].dropna() for d in DRIVERS])
        margin = (acv.max() - acv.min()) * 0.12 + 0.2
        ax_m.set_ylim(acv.min() - margin, acv.max() + margin)
        ax_m.set_ylabel(sylabel, color=LT['text'], fontsize=LT['label_size'])
        ax_m.tick_params(labelbottom=False)

        if si == 0:
            yb, yt = ax_m.get_ylim()
            yr = yt - yb
            for i, drv in enumerate(DRIVERS):
                for p in pl[drv]:
                    yp = yt - yr * (0.03 + 0.08 * i)
                    ax_m.text(p, yp, f'{drv} PIT L{p}', ha='center', va='top',
                              fontsize=9, fontweight='bold', color=colors[drv], alpha=0.9,
                              bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                                        edgecolor=colors[drv], alpha=0.85, linewidth=1.0))
            ax_m.legend(loc='upper right', fontsize=11, framealpha=0.9, facecolor='white',
                        edgecolor=LT['spine'], labelcolor=LT['text'])
            ax_m.set_title(f'{drv1} vs {drv2} セクター比較 (S1 / S2 / S3)\n'
                           f'(丸=クリーン, x=VSC/ピット, 黄帯=VSC, 破線=ピットイン)',
                           color=LT['text'], fontsize=LT['title_size'], fontweight='bold', pad=14)

        sec_mg = pd.merge(
            dd[drv1][['LapNum', scol]].rename(columns={scol: f'{drv1}_s'}),
            dd[drv2][['LapNum', scol]].rename(columns={scol: f'{drv2}_s'}),
            on='LapNum', how='inner')
        sec_mg['delta'] = sec_mg[f'{drv1}_s'] - sec_mg[f'{drv2}_s']
        sec_mg['is_clean'] = sec_mg['LapNum'].isin(both_clean)
        smc = sec_mg[sec_mg['is_clean']]

        ax_d.bar(smc['LapNum'], smc['delta'],
                 color=[colors[drv1] if d < 0 else colors[drv2] for d in smc['delta']],
                 alpha=0.75, width=0.8, zorder=3)
        ax_d.axhline(0, color=LT['axis'], linewidth=1.0, alpha=0.5)
        ax_d.set_ylabel(f'{sname} Delta', color=LT['text'], fontsize=LT['label_size'] - 2)
        if len(smc) > 0:
            dm = max(abs(smc['delta'].min()), abs(smc['delta'].max())) + 0.2
            ax_d.set_ylim(-dm, dm)
        if si < 2:
            ax_d.tick_params(labelbottom=False)
        else:
            ax_d.set_xlabel('ラップ数', color=LT['text'], fontsize=LT['label_size'])
        ax_d.text(1.01, 0.5, f'{drv1}<0<{drv2}', transform=ax_d.transAxes,
                  fontsize=8, color='#888', va='center', ha='left', rotation=90)

    save_fig(fig_sec, out_dir / 'art_sector_compare.png')

    # ============================
    # 5. セクターテーブル（L26以降）
    # ============================
    print(f'  [5/5] セクターテーブル...')
    fig_tbl, ax_tbl = plt.subplots(figsize=(10, 4), facecolor='white')
    ax_tbl.set_facecolor('white')
    ax_tbl.axis('off')

    ax_tbl.text(0.5, 0.95, f'L{l26_start}以降 {drv1} vs {drv2} セクター別比較（クリーンラップ）',
                transform=ax_tbl.transAxes, fontsize=14, fontweight='bold', color=LT['text'],
                ha='center', va='top')
    ax_tbl.text(0.5, 0.87, '両者ともHARDタイヤ、VSC/ピット周を除外。',
                transform=ax_tbl.transAxes, fontsize=10, color='#555', ha='center', va='top')

    col_labels = ['セクター', f'{drv1}平均', f'{drv2}平均', '差', f'{drv1}勝ち', f'{drv2}勝ち']
    cell_data = []
    for sname, scol in [('S1', 'S1Sec'), ('S2', 'S2Sec'), ('S3', 'S3Sec')]:
        v1 = cd_l26[drv1][scol].dropna()
        v2 = cd_l26[drv2][scol].dropna()
        ci = v1.index[v1.index.isin(cd_l26[drv1].index)].intersection(
             v2.index[v2.index.isin(cd_l26[drv2].index)])
        # ラップ番号ベースで結合
        d1_sec = cd_l26[drv1].set_index('LapNum')[scol].dropna()
        d2_sec = cd_l26[drv2].set_index('LapNum')[scol].dropna()
        common = d1_sec.index.intersection(d2_sec.index)
        r_v, l_v = d1_sec[common], d2_sec[common]
        diff = r_v - l_v
        r_mean, l_mean = r_v.mean(), l_v.mean()
        d1_wins = int((diff < 0).sum())
        d2_wins = int((diff > 0).sum())
        gap = r_mean - l_mean
        winner = drv1 if gap < 0 else drv2
        cell_data.append([sname, f'{r_mean:.3f}s', f'{l_mean:.3f}s',
                          f'{gap:+.3f}s ({winner})', str(d1_wins), str(d2_wins)])

    table = ax_tbl.table(cellText=cell_data, colLabels=col_labels,
                          cellLoc='center', loc='center',
                          bbox=[0.05, 0.05, 0.90, 0.70])
    table.auto_set_font_size(False)
    table.set_fontsize(11)

    for j in range(len(col_labels)):
        cell = table[0, j]
        cell.set_facecolor('#2B3045')
        cell.set_text_props(color='white', fontweight='bold', fontsize=11)
        cell.set_edgecolor('#AAAAAA')
        cell.set_linewidth(0.8)

    for i in range(len(cell_data)):
        for j in range(len(col_labels)):
            cell = table[i + 1, j]
            cell.set_edgecolor('#CCCCCC')
            cell.set_linewidth(0.8)
            cell.set_text_props(fontsize=11)
            cell.set_facecolor('#F7F7FA' if i % 2 == 0 else '#FFFFFF')
            cell.set_height(0.22)

            if j == 3:
                cell.set_text_props(fontweight='bold', fontsize=11)
                if drv1 in cell_data[i][j]:
                    cell.set_text_props(color=c1, fontweight='bold', fontsize=11)
                elif drv2 in cell_data[i][j]:
                    cell.set_text_props(color=c2, fontweight='bold', fontsize=11)
            if j == 4:
                val = int(cell_data[i][j])
                other = int(cell_data[i][5])
                if val > other:
                    cell.set_text_props(fontweight='bold', color=c1, fontsize=12)
                    cell.set_facecolor('#E6F7F3' if c1 == '#00B89F' else '#F0F0FF')
            if j == 5:
                val = int(cell_data[i][j])
                other = int(cell_data[i][4])
                if val > other:
                    cell.set_text_props(fontweight='bold', color=c2, fontsize=12)
                    cell.set_facecolor('#FCE8E8' if c2 == '#DC0000' else '#F0F0FF')

        table[i + 1, 0].set_height(0.22)

    save_fig(fig_tbl, out_dir / 'art_sector_table.png')

    print(f'  === {drv1} vs {drv2} 完了: {out_dir} ===')


# ============================================================
# メイン
# ============================================================
if __name__ == '__main__':
    if len(sys.argv) == 3:
        d1, d2 = sys.argv[1].upper(), sys.argv[2].upper()
        generate_pair_charts(d1, d2)
    else:
        for d1, d2 in [('ANT', 'LEC'), ('LEC', 'HAM')]:
            generate_pair_charts(d1, d2)
    print('\n=== 全ペア完了 ===')
