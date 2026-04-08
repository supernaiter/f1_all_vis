#!/usr/bin/env python3
"""
T7: セーフティカー影響分析 — R03日本GP
SC期間前後のギャップ変動・戦略インパクトを定量化する
"""

import matplotlib
matplotlib.use('Agg')  # GUIなし環境対応

import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D

# ─── パス設定 ───────────────────────────────────────────────
BASE_DIR = '/Volumes/lyssr_workspace/2026_1_4/Motorsports-Visualised'
EXPORT_DIR = os.path.join(BASE_DIR, 'data/2026_R03_Japan/export')
OUT_DIR = os.path.join(BASE_DIR, 'notebooks/output')
os.makedirs(OUT_DIR, exist_ok=True)

# ─── グラフスタイル ──────────────────────────────────────────
STYLE = {
    'bg_color':   '#1a1a2e',
    'text_color': '#ffffff',
    'grid_color': '#333355',
    'figsize':    (14, 8),
    'title_size': 16,
    'label_size': 12,
}

TYRE_COLORS = {
    'SOFT':         '#FF3333',
    'MEDIUM':       '#FFD700',
    'HARD':         '#FFFFFF',
    'INTERMEDIATE': '#39B54A',
    'WET':          '#0072CE',
    'UNKNOWN':      '#888888',
}

# ─── 1. データ読み込み ───────────────────────────────────────
print("データ読み込み中...")

laps_path     = os.path.join(EXPORT_DIR, 'race_laps.csv')
rcm_path      = os.path.join(EXPORT_DIR, 'race_control_messages.csv')
results_path  = os.path.join(EXPORT_DIR, 'race_results.csv')

try:
    laps    = pd.read_csv(laps_path)
    rcm     = pd.read_csv(rcm_path)
    results = pd.read_csv(results_path)
except FileNotFoundError as e:
    print(f"エラー: ファイルが見つかりません — {e}")
    sys.exit(1)

print(f"  ラップ数: {len(laps)}行, ドライバー数: {laps['Driver'].nunique()}")
print(f"  レースコントロールメッセージ数: {len(rcm)}行")

# ─── 2. SC/VSC期間の特定 ────────────────────────────────────
print("\nSC/VSC期間を特定中...")

# SCイベント抽出
sc_deployed = rcm[rcm['Message'].str.contains('SAFETY CAR DEPLOYED', na=False)]['Lap'].tolist()
sc_in_lap   = rcm[rcm['Message'].str.contains('SAFETY CAR IN THIS LAP', na=False)]['Lap'].tolist()
vsc_deploy  = rcm[rcm['Message'].str.contains('VSC DEPLOYED', na=False)]['Lap'].tolist()
vsc_ending  = rcm[rcm['Message'].str.contains('VSC ENDING', na=False)]['Lap'].tolist()

# SC期間リスト: (deploy_lap, clear_lap) のペア
sc_periods = []
for dep in sc_deployed:
    # 対応する"IN THIS LAP"を探す（deployより後の最初のもの）
    clear = next((c for c in sc_in_lap if c >= dep), None)
    sc_periods.append((dep, clear))

# VSC期間リスト
vsc_periods = []
for dep in vsc_deploy:
    end = next((e for e in vsc_ending if e >= dep), None)
    vsc_periods.append((dep, end))

print(f"  SC期間: {sc_periods}")
print(f"  VSC期間: {vsc_periods}")

# メインSC期間を確定（最初のSCを使用）
if sc_periods:
    SC_START, SC_END = sc_periods[0]
else:
    # フォールバック: current.txtの情報
    SC_START, SC_END = 22, 27
    print(f"  警告: SCイベントが見つかりません。デフォルト値使用 ({SC_START}-{SC_END})")

# SC直前/直後の分析ウィンドウ定義
PRE_SC_START  = SC_START - 4   # SC前4周
PRE_SC_END    = SC_START - 1   # SC前1周
POST_SC_START = SC_END + 1     # SC明け最初の周
POST_SC_END   = SC_END + 4     # SC後4周

print(f"  SC期間: Lap {SC_START}–{SC_END}")
print(f"  分析ウィンドウ — SC前: Lap {PRE_SC_START}–{PRE_SC_END}, SC後: Lap {POST_SC_START}–{POST_SC_END}")

# ─── 3. データ前処理 ────────────────────────────────────────
print("\nデータ前処理中...")

# LapNumberをintに変換（float混在対応）
laps['LapNumber'] = laps['LapNumber'].astype(float).astype(int)

# TrackStatusを文字列化
laps['TrackStatus'] = laps['TrackStatus'].astype(str).str.strip()

# LapTime_secが0以下・NaNのラップを除外（クリーンラップのみ）
laps_clean = laps[laps['LapTime_sec'] > 60].copy()

# ─── 4. SC中にピットインしたドライバーの特定 ─────────────────
print("\nSC中ピット戦略を分析中...")

# SC期間中のラップ
sc_laps = laps[(laps['LapNumber'] >= SC_START) & (laps['LapNumber'] <= SC_END)].copy()

# PitInTime_sec が非NaN → そのラップでピットイン
pitted_during_sc = sc_laps[sc_laps['PitInTime_sec'].notna()]['Driver'].unique().tolist()
print(f"  SC中にピットしたドライバー: {pitted_during_sc}")

# ─── 5. SC前後のポジション取得 ──────────────────────────────
print("\nSC前後のポジション変動を計算中...")

def get_position_at_lap(df, lap_num):
    """指定ラップでのドライバーポジションをSeriesで返す"""
    subset = df[df['LapNumber'] == lap_num][['Driver', 'Position']].copy()
    subset = subset.dropna(subset=['Position'])
    subset['Position'] = subset['Position'].astype(float).astype(int)
    return subset.set_index('Driver')['Position']

pos_before_sc = get_position_at_lap(laps, PRE_SC_END)
pos_after_sc  = get_position_at_lap(laps, POST_SC_START)

# ─── 6. SC前後のコンパウンド取得 ────────────────────────────
def get_compound_at_lap(df, lap_num):
    """指定ラップでのドライバーコンパウンドをSeriesで返す"""
    subset = df[df['LapNumber'] == lap_num][['Driver', 'Compound']].copy()
    return subset.set_index('Driver')['Compound']

comp_before_sc = get_compound_at_lap(laps, PRE_SC_END)
comp_after_sc  = get_compound_at_lap(laps, POST_SC_START)

# ─── 7. SC前後のペース計算（クリーンラップ平均） ──────────────
def get_avg_pace(df, lap_start, lap_end):
    """
    指定範囲のラップタイム中央値をドライバー別に返す
    107%フィルタ適用（アウトラップ・インラップ除外済）
    """
    subset = df[(df['LapNumber'] >= lap_start) & (df['LapNumber'] <= lap_end)].copy()
    # アウトラップ除外: PitOutTime_sec非NaN
    subset = subset[subset['PitOutTime_sec'].isna()]
    # インラップ除外: PitInTime_sec非NaN
    subset = subset[subset['PitInTime_sec'].isna()]
    # 異常値除外: IsAccurateがTrue
    subset = subset[subset['IsAccurate'] == True]

    # ドライバー別中央値
    pace = subset.groupby('Driver')['LapTime_sec'].median()
    return pace

pace_before = get_avg_pace(laps_clean, PRE_SC_START, PRE_SC_END)
pace_after  = get_avg_pace(laps_clean, POST_SC_START, POST_SC_END)

# ─── 8. サマリーDataFrame構築 ────────────────────────────────
print("\nサマリーDataFrame構築中...")

# 全ドライバーリスト（results.csvから）
all_drivers = results['Abbreviation'].tolist()

summary_rows = []
for drv in all_drivers:
    row = {
        'Driver':           drv,
        'Team':             results.loc[results['Abbreviation'] == drv, 'TeamName'].values[0]
                            if drv in results['Abbreviation'].values else 'Unknown',
        'PositionBeforeSC': int(pos_before_sc[drv]) if drv in pos_before_sc else None,
        'PositionAfterSC':  int(pos_after_sc[drv])  if drv in pos_after_sc  else None,
        'PittedDuringSC':   drv in pitted_during_sc,
        'CompoundBeforeSC': comp_before_sc.get(drv, 'UNKNOWN'),
        'CompoundAfterSC':  comp_after_sc.get(drv, 'UNKNOWN'),
        'PaceBeforeSC_sec': round(float(pace_before[drv]), 3) if drv in pace_before else None,
        'PaceAfterSC_sec':  round(float(pace_after[drv]),  3) if drv in pace_after  else None,
    }
    # PositionChange: 負なら順位アップ（数値が小さくなる = 上位へ）
    if row['PositionBeforeSC'] is not None and row['PositionAfterSC'] is not None:
        row['PositionChange'] = row['PositionBeforeSC'] - row['PositionAfterSC']
    else:
        row['PositionChange'] = None

    summary_rows.append(row)

summary = pd.DataFrame(summary_rows)

# 戦略的勝者/敗者の判定
# PositionChange > 0: 順位上昇（勝者）, < 0: 順位下落（敗者）
summary['StrategicOutcome'] = summary['PositionChange'].apply(
    lambda x: '勝者(+)' if (x is not None and x > 0) else (
              '敗者(-)' if (x is not None and x < 0) else '変化なし')
)

# 出力用カラム順
output_cols = [
    'Driver', 'Team', 'PositionBeforeSC', 'PositionAfterSC',
    'PositionChange', 'PittedDuringSC', 'CompoundBeforeSC', 'CompoundAfterSC',
    'PaceBeforeSC_sec', 'PaceAfterSC_sec', 'StrategicOutcome'
]
summary = summary[output_cols]

print(summary.to_string(index=False))

# CSV保存
csv_path = os.path.join(OUT_DIR, 'sc_impact_summary.csv')
summary.to_csv(csv_path, index=False)
print(f"\nCSV保存: {csv_path}")

# ─── 9. グラフ描画 ──────────────────────────────────────────
print("\nグラフ描画中...")

fig, axes = plt.subplots(2, 2, figsize=(16, 12))
fig.patch.set_facecolor(STYLE['bg_color'])

# ── グラフ共通スタイル適用ヘルパー ──
def style_ax(ax, title):
    ax.set_facecolor(STYLE['bg_color'])
    ax.set_title(title, color=STYLE['text_color'], fontsize=14, fontweight='bold', pad=10)
    ax.tick_params(colors=STYLE['text_color'])
    ax.xaxis.label.set_color(STYLE['text_color'])
    ax.yaxis.label.set_color(STYLE['text_color'])
    for spine in ax.spines.values():
        spine.set_edgecolor(STYLE['grid_color'])
    ax.grid(color=STYLE['grid_color'], linestyle='--', alpha=0.5)

# ── パネル1: SC前後のラップタイム推移（上位10ドライバー） ──
ax1 = axes[0, 0]
style_ax(ax1, f'ラップタイム推移（Lap {PRE_SC_START}–{POST_SC_END}）')

# レース結果上位10ドライバー
top10_drivers = results.head(10)['Abbreviation'].tolist()

# カラーパレット（10色）
colors_palette = plt.cm.tab10.colors

for i, drv in enumerate(top10_drivers):
    drv_laps = laps_clean[
        (laps_clean['Driver'] == drv) &
        (laps_clean['LapNumber'] >= PRE_SC_START) &
        (laps_clean['LapNumber'] <= POST_SC_END) &
        (laps_clean['PitOutTime_sec'].isna()) &   # アウトラップ除外
        (laps_clean['PitInTime_sec'].isna())        # インラップ除外
    ].sort_values('LapNumber')

    if len(drv_laps) > 0:
        ax1.plot(
            drv_laps['LapNumber'], drv_laps['LapTime_sec'],
            marker='o', markersize=4, linewidth=1.5,
            color=colors_palette[i], label=drv, alpha=0.85
        )

# SC期間を灰色帯で表示
ax1.axvspan(SC_START, SC_END, color='#ffff00', alpha=0.12, label=f'SC (Lap {SC_START}–{SC_END})')
ax1.axvline(SC_START, color='#ffff00', linestyle='--', linewidth=1, alpha=0.7)
ax1.axvline(SC_END,   color='#ffff00', linestyle='--', linewidth=1, alpha=0.7)

ax1.set_xlabel('ラップ', fontsize=STYLE['label_size'])
ax1.set_ylabel('ラップタイム（秒）', fontsize=STYLE['label_size'])
ax1.legend(fontsize=8, loc='upper right', framealpha=0.3,
           labelcolor=STYLE['text_color'], facecolor=STYLE['bg_color'])
ax1.invert_yaxis()  # タイムが小さい方が上（速い）

# ── パネル2: SC前後のポジション変動バーチャート ──
ax2 = axes[0, 1]
style_ax(ax2, 'SC前後のポジション変動（ポジティブ = 順位上昇）')

# PositionChangeが有効なドライバーをSC前順位でソート
plot_df = summary.dropna(subset=['PositionChange', 'PositionBeforeSC']).copy()
plot_df = plot_df.sort_values('PositionBeforeSC')

bar_colors = []
for _, row in plot_df.iterrows():
    if row['PittedDuringSC']:
        bar_colors.append('#39B54A')  # ピット組: 緑
    elif row['PositionChange'] > 0:
        bar_colors.append('#3399FF')  # 順位上昇: 青
    elif row['PositionChange'] < 0:
        bar_colors.append('#FF6644')  # 順位下落: 赤
    else:
        bar_colors.append('#888888')  # 変化なし: グレー

bars = ax2.bar(plot_df['Driver'], plot_df['PositionChange'],
               color=bar_colors, edgecolor='none', alpha=0.9)

# ピット印（★）をバーの上に表示
for bar, (_, row) in zip(bars, plot_df.iterrows()):
    if row['PittedDuringSC']:
        ax2.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.1,
            '★', ha='center', va='bottom',
            color='#39B54A', fontsize=10
        )

ax2.axhline(0, color=STYLE['text_color'], linewidth=0.8)
ax2.set_xlabel('ドライバー', fontsize=STYLE['label_size'])
ax2.set_ylabel('ポジション変動（+:上昇）', fontsize=STYLE['label_size'])
ax2.tick_params(axis='x', rotation=45)

# 凡例
legend_elements = [
    mpatches.Patch(color='#39B54A', label='SC中ピット ★'),
    mpatches.Patch(color='#3399FF', label='順位上昇'),
    mpatches.Patch(color='#FF6644', label='順位下落'),
    mpatches.Patch(color='#888888', label='変化なし'),
]
ax2.legend(handles=legend_elements, fontsize=9, loc='upper right',
           framealpha=0.3, labelcolor=STYLE['text_color'], facecolor=STYLE['bg_color'])

# ── パネル3: SC前後ペース比較（散布図） ──
ax3 = axes[1, 0]
style_ax(ax3, 'SC前後ペース比較（中央値）')

pace_df = summary.dropna(subset=['PaceBeforeSC_sec', 'PaceAfterSC_sec']).copy()

scatter_colors = [
    ('#39B54A' if row['PittedDuringSC'] else '#FF6644'
     if row['PositionChange'] is not None and row['PositionChange'] < 0
     else '#3399FF')
    for _, row in pace_df.iterrows()
]

ax3.scatter(pace_df['PaceBeforeSC_sec'], pace_df['PaceAfterSC_sec'],
            c=scatter_colors, s=80, alpha=0.85, edgecolors='none', zorder=3)

# ドライバー名ラベル
for _, row in pace_df.iterrows():
    ax3.annotate(
        row['Driver'],
        (row['PaceBeforeSC_sec'], row['PaceAfterSC_sec']),
        textcoords='offset points', xytext=(6, 2),
        fontsize=7, color=STYLE['text_color'], alpha=0.85
    )

# 対角線: SC前後同ペース
all_vals = list(pace_df['PaceBeforeSC_sec']) + list(pace_df['PaceAfterSC_sec'])
min_v, max_v = min(all_vals) - 0.5, max(all_vals) + 0.5
ax3.plot([min_v, max_v], [min_v, max_v],
         color=STYLE['grid_color'], linestyle='--', linewidth=1, label='ペース変化なし')

ax3.set_xlabel(f'SC前ペース中央値（Lap {PRE_SC_START}–{PRE_SC_END}）[秒]',
               fontsize=STYLE['label_size'])
ax3.set_ylabel(f'SC後ペース中央値（Lap {POST_SC_START}–{POST_SC_END}）[秒]',
               fontsize=STYLE['label_size'])
ax3.legend(fontsize=9, framealpha=0.3, labelcolor=STYLE['text_color'],
           facecolor=STYLE['bg_color'])

# ── パネル4: タイヤ戦略（SC前後コンパウンド変化） ──
ax4 = axes[1, 1]
style_ax(ax4, 'タイヤ戦略 — SC前後コンパウンド')

# SC前順位でソート
strategy_df = summary.dropna(subset=['PositionBeforeSC']).copy()
strategy_df = strategy_df.sort_values('PositionBeforeSC').reset_index(drop=True)

n = len(strategy_df)
y_positions = range(n)

for idx, (_, row) in enumerate(strategy_df.iterrows()):
    c_before = str(row['CompoundBeforeSC']).upper()
    c_after  = str(row['CompoundAfterSC']).upper()
    col_before = TYRE_COLORS.get(c_before, TYRE_COLORS['UNKNOWN'])
    col_after  = TYRE_COLORS.get(c_after, TYRE_COLORS['UNKNOWN'])

    # SC前タイヤ（左側）
    ax4.barh(idx, 0.45, left=0.0, color=col_before, edgecolor='none', alpha=0.85, height=0.7)
    # SC後タイヤ（右側）
    ax4.barh(idx, 0.45, left=0.55, color=col_after, edgecolor='none', alpha=0.85, height=0.7)

    # コンパウンド名テキスト
    ax4.text(0.225, idx, c_before[:3], ha='center', va='center',
             fontsize=7, color='#000000' if c_before == 'HARD' else STYLE['text_color'],
             fontweight='bold')
    ax4.text(0.775, idx, c_after[:3], ha='center', va='center',
             fontsize=7, color='#000000' if c_after == 'HARD' else STYLE['text_color'],
             fontweight='bold')

    # ピット強調: 矢印
    if row['PittedDuringSC']:
        ax4.annotate('', xy=(0.55, idx), xytext=(0.45, idx),
                     arrowprops=dict(arrowstyle='->', color='#39B54A', lw=2))

ax4.set_yticks(range(n))
ax4.set_yticklabels(
    [f"P{int(r['PositionBeforeSC'])} {r['Driver']}" for _, r in strategy_df.iterrows()],
    fontsize=9, color=STYLE['text_color']
)
ax4.set_xlim(0, 1)
ax4.set_xticks([0.225, 0.775])
ax4.set_xticklabels(['SC前タイヤ', 'SC後タイヤ'], fontsize=STYLE['label_size'])
ax4.grid(False)
ax4.set_xlabel('')

# 凡例（コンパウンドカラー）
tyre_legend = [
    mpatches.Patch(color=TYRE_COLORS['SOFT'],   label='SOFT'),
    mpatches.Patch(color=TYRE_COLORS['MEDIUM'], label='MEDIUM'),
    mpatches.Patch(color=TYRE_COLORS['HARD'],   label='HARD'),
]
ax4.legend(handles=tyre_legend, fontsize=9, loc='lower right',
           framealpha=0.3, labelcolor=STYLE['text_color'], facecolor=STYLE['bg_color'])

# ── タイトル ──
fig.suptitle(
    f'2026 R03 日本GP — セーフティカー影響分析\nSC期間: Lap {SC_START}–{SC_END}',
    color=STYLE['text_color'], fontsize=STYLE['title_size'] + 2,
    fontweight='bold', y=0.98
)

plt.tight_layout(rect=[0, 0, 1, 0.96])

# 保存
png_path = os.path.join(OUT_DIR, 'sc_position_change.png')
fig.savefig(png_path, dpi=120, bbox_inches='tight', facecolor=STYLE['bg_color'])
plt.close()
print(f"グラフ保存: {png_path}")

# ─── 10. コンソール出力サマリー ────────────────────────────
print("\n" + "="*60)
print(f"=== SC分析サマリー (Lap {SC_START}–{SC_END}) ===")
print("="*60)
print(f"\nSC中ピット組 ({len(pitted_during_sc)}名): {', '.join(pitted_during_sc)}")

winners = summary[summary['PositionChange'] > 0].sort_values('PositionChange', ascending=False)
losers  = summary[summary['PositionChange'] < 0].sort_values('PositionChange')

print(f"\n■ 戦略的勝者（順位上昇）{len(winners)}名:")
for _, r in winners.iterrows():
    pit_mark = ' ★ピット' if r['PittedDuringSC'] else ''
    print(f"  {r['Driver']} ({r['Team']}): "
          f"P{r['PositionBeforeSC']}→P{r['PositionAfterSC']} (+{r['PositionChange']}){pit_mark}")

print(f"\n■ 戦略的敗者（順位下落）{len(losers)}名:")
for _, r in losers.iterrows():
    pit_mark = ' ★ピット' if r['PittedDuringSC'] else ''
    print(f"  {r['Driver']} ({r['Team']}): "
          f"P{r['PositionBeforeSC']}→P{r['PositionAfterSC']} ({r['PositionChange']}){pit_mark}")

print("\n" + "="*60)
print("T7 分析完了")
print(f"  CSV: {csv_path}")
print(f"  PNG: {png_path}")
