#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T3: タイヤデグラデーション分析スクリプト
入力: notebooks/output/clean_longruns.csv
出力: notebooks/output/deg_rates_clean.csv
        notebooks/output/deg_heatmap.png
比較: data/cross_gp_analysis/csv/cross_gp_deg_rates.csv（107%フィルタ前後の差）
"""

import matplotlib
matplotlib.use('Agg')  # GUIなし環境向け

import os
import sys
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from scipy.stats import linregress

warnings.filterwarnings('ignore')

# ─────────────────────────────────────────────
# パス設定
# ─────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)

INPUT_CSV       = os.path.join(BASE_DIR, 'output', 'clean_longruns.csv')
OLD_CSV         = os.path.join(PROJECT_DIR, 'data', 'cross_gp_analysis', 'csv', 'cross_gp_deg_rates.csv')
OUTPUT_DIR      = os.path.join(BASE_DIR, 'output')
OUTPUT_CSV      = os.path.join(OUTPUT_DIR, 'deg_rates_clean.csv')
OUTPUT_HEATMAP  = os.path.join(OUTPUT_DIR, 'deg_heatmap.png')

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─────────────────────────────────────────────
# グラフスタイル設定（CLAUDE.md準拠）
# ─────────────────────────────────────────────
STYLE = {
    'bg_color':   '#1a1a2e',
    'text_color': '#ffffff',
    'grid_color': '#333355',
    'figsize':    (14, 8),
    'title_size': 16,
    'label_size': 11,
}

# 日本語フォント設定（Hiragino Sans利用可能）
import matplotlib.font_manager as fm
available = {f.name for f in fm.fontManager.ttflist}
JP_FONT = 'Hiragino Sans' if 'Hiragino Sans' in available else None
if JP_FONT:
    plt.rcParams['font.family'] = JP_FONT

COMPOUND_COLORS = {
    'SOFT':         '#FF3333',
    'MEDIUM':       '#FFD700',
    'HARD':         '#FFFFFF',
    'INTERMEDIATE': '#39B54A',
    'WET':          '#0072CE',
}

# デグレート区分（CLAUDE.md基準値）
DEG_THRESHOLDS = {
    'low':    0.05,   # < 0.05 → 低デグ
    'medium': 0.10,   # 0.05–0.10 → 中デグ
                      # > 0.10 → 高デグ
}

def classify_deg(rate: float) -> str:
    """デグレートを3段階に分類する"""
    abs_rate = abs(rate)
    if abs_rate < DEG_THRESHOLDS['low']:
        return '低デグ'
    elif abs_rate < DEG_THRESHOLDS['medium']:
        return '中デグ'
    else:
        return '高デグ'

# ─────────────────────────────────────────────
# 1. データ読み込み
# ─────────────────────────────────────────────
print("=" * 60)
print("T3 タイヤデグラデーション分析")
print("=" * 60)

print(f"\n[1/5] データ読み込み中...")

try:
    df = pd.read_csv(INPUT_CSV)
    print(f"  クリーンロングランデータ: {len(df)}行, {df['LongRunID'].nunique()}ロングラン")
except FileNotFoundError:
    print(f"  ERROR: {INPUT_CSV} が見つかりません")
    print(f"  先にT2ノートブック(t2_clean_longruns.ipynb)を実行してください")
    sys.exit(1)

# 既存データ（比較用）
try:
    df_old = pd.read_csv(OLD_CSV, encoding='utf-8-sig')
    print(f"  既存デグレートデータ: {len(df_old)}行（107%フィルタ前）")
    has_old = True
except FileNotFoundError:
    print(f"  注意: 比較用CSV {OLD_CSV} が見つかりません（比較はスキップ）")
    has_old = False

# ─────────────────────────────────────────────
# 2. ロングラン単位で線形回帰（TyreLife vs LapTime_sec）
# ─────────────────────────────────────────────
print(f"\n[2/5] 線形回帰計算中...")

MIN_LAPS = 5  # ロングランの最小周回数

results = []
skipped = 0

for run_id, group in df.groupby('LongRunID'):
    # 5周以上のみ回帰対象
    if len(group) < MIN_LAPS:
        skipped += 1
        continue

    # TyreLife と LapTime_sec を取得
    x = group['TyreLife'].values.astype(float)
    y = group['LapTime_sec'].values.astype(float)

    # NaN除外
    mask = ~(np.isnan(x) | np.isnan(y))
    x, y = x[mask], y[mask]
    if len(x) < MIN_LAPS:
        skipped += 1
        continue

    # 線形回帰
    slope, intercept, r_value, p_value, std_err = linregress(x, y)
    r2 = r_value ** 2

    # メタデータ（最初の行から取得）
    meta = group.iloc[0]

    results.append({
        'GP':         meta['GP'],
        'Driver':     meta['Driver'],
        'Team':       meta['Team'],
        'Stint':      meta['Stint'],
        'Compound':   meta['Compound'],
        'DegRate':    round(slope, 6),       # 秒/ラップ（正=劣化、負=燃料効果優勢）
        'Intercept':  round(intercept, 3),
        'R2':         round(r2, 4),
        'PValue':     round(p_value, 4),
        'CleanLaps':  len(x),
        'MeanPace':   round(np.mean(y), 4),
        'MinTyreLife': int(x.min()),
        'MaxTyreLife': int(x.max()),
        'LongRunID':  run_id,
    })

df_result = pd.DataFrame(results)
print(f"  回帰完了: {len(df_result)}ロングラン（スキップ: {skipped}件 ＜{MIN_LAPS}周）")

# デグレート分類列追加
df_result['DegClass']  = df_result['DegRate'].apply(classify_deg)
df_result['GPShort']   = df_result['GP'].str.extract(r'(R\d+)')[0]  # R01/R02/R03

# ─────────────────────────────────────────────
# 3. 出力: deg_rates_clean.csv
# ─────────────────────────────────────────────
print(f"\n[3/5] CSVエクスポート中...")

# 仕様通りのカラム構成
out_cols = ['GP', 'Driver', 'Team', 'Stint', 'Compound',
            'DegRate', 'R2', 'CleanLaps', 'MeanPace']
df_out = df_result[out_cols].copy()
df_out.to_csv(OUTPUT_CSV, index=False, encoding='utf-8')
print(f"  保存完了: {OUTPUT_CSV}")
print(f"  行数: {len(df_out)}")

# ─────────────────────────────────────────────
# 4. サマリー表示（コンパウンド別×チーム別×GP別）
# ─────────────────────────────────────────────
print(f"\n[4/5] サマリー分析...")

# 4-A: コンパウンド別サマリー
print("\n  [コンパウンド別デグレート（全GP合計）]")
comp_summary = (df_result.groupby('Compound')['DegRate']
                .agg(['mean', 'std', 'count'])
                .round(4)
                .rename(columns={'mean': '平均(秒/lap)', 'std': '標準偏差', 'count': '件数'}))
print(comp_summary.to_string())

# 4-B: GP×コンパウンド別
print("\n  [GP×コンパウンド別平均デグレート]")
gp_comp = (df_result.groupby(['GPShort', 'Compound'])['DegRate']
           .mean()
           .round(4)
           .unstack(fill_value=np.nan))
print(gp_comp.to_string())

# 4-C: デグ分類の分布
print("\n  [デグレート分類の分布]")
print(df_result['DegClass'].value_counts().to_string())

# 4-D: 負のデグレート（燃料効果が勝っている）の分析
neg_deg = df_result[df_result['DegRate'] < 0]
print(f"\n  [負のデグレート（燃料効果優勢）: {len(neg_deg)}件]")
if len(neg_deg) > 0:
    print(f"  うち初期スティント（TyreLife min<=5）: {(neg_deg['MinTyreLife'] <= 5).sum()}件")
    print(f"  平均デグレート: {neg_deg['DegRate'].mean():.4f} 秒/ラップ")
    print(f"  典型例:")
    top_neg = neg_deg.nsmallest(5, 'DegRate')[
        ['GP', 'Driver', 'Team', 'Compound', 'DegRate', 'CleanLaps', 'R2']
    ]
    print(top_neg.to_string(index=False))

# 4-E: チーム別タイヤマネジメント評価（ロングラン後半のペースドロップ）
print(f"\n  [チーム別タイヤマネジメント評価（Hardコンパウンド中心）]")
hard_runs = df_result[df_result['Compound'] == 'HARD'].copy()
if len(hard_runs) > 0:
    team_hard = (hard_runs.groupby('Team')['DegRate']
                 .agg(['mean', 'count'])
                 .round(4)
                 .rename(columns={'mean': 'HARD平均デグレート', 'count': '件数'})
                 .sort_values('HARD平均デグレート'))
    print(team_hard.to_string())

# 4-F: 既存データとの比較（107%フィルタ前後の差）
if has_old:
    print(f"\n  [107%フィルタ前後のデグレート比較]")
    # GPカラムを短縮して結合
    df_old_cmp = df_old.copy()
    df_old_cmp['GPShort'] = df_old_cmp['GP'].str.extract(r'(R\d+)')[0] if \
        df_old_cmp['GP'].str.contains('R0').any() else df_old_cmp['GP'].apply(
            lambda x: f"R{df_old_cmp['GP'].unique().tolist().index(x)+1:02d}" if x in df_old_cmp['GP'].unique() else x
        )

    # フィルタ後（T3）の平均
    t3_summary = (df_result.groupby(['GPShort', 'Compound'])['DegRate']
                  .mean().round(4).reset_index()
                  .rename(columns={'DegRate': 'DegRate_T3（107%フィルタ後）'}))

    # フィルタ前（既存）の平均 — GP短縮名を合わせる
    df_old['GPShort'] = df_old['GP'].str.replace('R0', 'R0', regex=False)
    # cross_gp_deg_rates.csvのGPはR01/R02/R03形式
    old_summary = (df_old.groupby(['GP', 'Compound'])['DegRate_sec_per_lap']
                   .mean().round(4).reset_index()
                   .rename(columns={'GP': 'GPShort', 'DegRate_sec_per_lap': 'DegRate_Old（フィルタ前）'}))

    merged_cmp = pd.merge(
        t3_summary, old_summary,
        on=['GPShort', 'Compound'], how='inner'
    )
    if len(merged_cmp) > 0:
        merged_cmp['差（T3-Old）'] = (merged_cmp['DegRate_T3（107%フィルタ後）'] -
                                     merged_cmp['DegRate_Old（フィルタ前）']).round(4)
        print(merged_cmp.to_string(index=False))
    else:
        print("  GPShort形式が一致しないため比較をスキップ")

# ─────────────────────────────────────────────
# 5. ヒートマップ生成（チーム×コンパウンド）
# ─────────────────────────────────────────────
print(f"\n[5/5] ヒートマップ生成中...")

# チーム×コンパウンドの平均デグレートピボット
pivot = (df_result.pivot_table(
    values='DegRate',
    index='Team',
    columns='Compound',
    aggfunc='mean'
))

# 行・列の順序を整理
compound_order = [c for c in ['SOFT', 'MEDIUM', 'HARD'] if c in pivot.columns]
pivot = pivot[compound_order]
# チームをMEDIUM平均でソート（なければ全体平均）
sort_col = 'MEDIUM' if 'MEDIUM' in pivot.columns else pivot.columns[0]
pivot = pivot.sort_values(sort_col, ascending=True)

fig, axes = plt.subplots(1, 2, figsize=(16, 8),
                          gridspec_kw={'width_ratios': [2, 1]})
fig.patch.set_facecolor(STYLE['bg_color'])

# ── サブプロット1: ヒートマップ ──
ax1 = axes[0]
ax1.set_facecolor(STYLE['bg_color'])

# カラーマップ: 赤（高デグ）→白（0）→青（燃料効果）
from matplotlib.colors import TwoSlopeNorm
data = pivot.values.astype(float)
vmax = max(abs(np.nanmax(data)), abs(np.nanmin(data)))
norm = TwoSlopeNorm(vmin=-vmax, vcenter=0, vmax=vmax)
cmap = plt.cm.RdBu_r

im = ax1.imshow(data, cmap=cmap, norm=norm, aspect='auto')

# 軸ラベル
ax1.set_xticks(range(len(compound_order)))
ax1.set_xticklabels(compound_order, color=STYLE['text_color'],
                    fontsize=STYLE['label_size'], fontweight='bold')
ax1.set_yticks(range(len(pivot.index)))
ax1.set_yticklabels(pivot.index, color=STYLE['text_color'],
                    fontsize=STYLE['label_size'])
ax1.tick_params(colors=STYLE['text_color'])

# セル内に数値を表示
for i in range(len(pivot.index)):
    for j in range(len(compound_order)):
        val = data[i, j]
        if not np.isnan(val):
            cls = classify_deg(val)
            cell_text = f"{val:+.3f}\n({cls})"
            txt_color = '#000000' if abs(val) < 0.05 else STYLE['text_color']
            ax1.text(j, i, cell_text, ha='center', va='center',
                     color=txt_color, fontsize=9, fontweight='bold')

# カラーバー
cbar = plt.colorbar(im, ax=ax1, shrink=0.8, pad=0.02)
cbar.set_label('デグレート (秒/ラップ)', color=STYLE['text_color'],
               fontsize=STYLE['label_size'])
cbar.ax.yaxis.set_tick_params(color=STYLE['text_color'])
plt.setp(cbar.ax.yaxis.get_ticklabels(), color=STYLE['text_color'])

ax1.set_title('チーム別タイヤデグレートヒートマップ\n（全GP平均、赤=高デグ 青=燃料効果優勢）',
              color=STYLE['text_color'], fontsize=STYLE['title_size'], pad=12)

# グリッド線（セル区切り）
for x in np.arange(-0.5, len(compound_order), 1):
    ax1.axvline(x, color=STYLE['grid_color'], linewidth=0.5)
for y in np.arange(-0.5, len(pivot.index), 1):
    ax1.axhline(y, color=STYLE['grid_color'], linewidth=0.5)

# ── サブプロット2: デグレート分布（コンパウンド別箱ひげ図） ──
ax2 = axes[1]
ax2.set_facecolor(STYLE['bg_color'])

box_data  = []
box_labels = []
box_colors = []

for comp in compound_order:
    vals = df_result[df_result['Compound'] == comp]['DegRate'].dropna()
    if len(vals) > 0:
        box_data.append(vals.values)
        box_labels.append(comp)
        box_colors.append(COMPOUND_COLORS.get(comp, '#aaaaaa'))

bp = ax2.boxplot(box_data, patch_artist=True, vert=True,
                  widths=0.5,
                  medianprops=dict(color='#000000', linewidth=2),
                  whiskerprops=dict(color=STYLE['text_color']),
                  capprops=dict(color=STYLE['text_color']),
                  flierprops=dict(marker='o', markerfacecolor='#aaaaaa',
                                  markersize=4, alpha=0.6))
for patch, color in zip(bp['boxes'], box_colors):
    patch.set_facecolor(color)
    patch.set_alpha(0.8)

# 基準線
for threshold, label, linestyle in [
    (0.05,  '低/中デグ境界', '--'),
    (0.10,  '中/高デグ境界', ':'),
    (-0.05, '低/中デグ境界(負)', '--'),
]:
    ax2.axhline(threshold, color='#ffaa00', linewidth=1,
                linestyle=linestyle, alpha=0.7, label=label)
ax2.axhline(0, color='#888888', linewidth=0.8, linestyle='-', alpha=0.5)

ax2.set_xticks(range(1, len(box_labels) + 1))
ax2.set_xticklabels(box_labels, color=STYLE['text_color'],
                     fontsize=STYLE['label_size'])
ax2.set_ylabel('デグレート (秒/ラップ)', color=STYLE['text_color'],
               fontsize=STYLE['label_size'])
ax2.tick_params(colors=STYLE['text_color'])
for spine in ax2.spines.values():
    spine.set_edgecolor(STYLE['grid_color'])
ax2.set_facecolor(STYLE['bg_color'])
ax2.yaxis.set_tick_params(labelcolor=STYLE['text_color'])
ax2.set_title('コンパウンド別デグレート分布', color=STYLE['text_color'],
              fontsize=14, pad=8)
ax2.grid(True, color=STYLE['grid_color'], alpha=0.4, linewidth=0.5)
ax2.set_axisbelow(True)

# 凡例（デグ分類）
legend_patches = [
    mpatches.Patch(color='#4CAF50', label='低デグ (<0.05)'),
    mpatches.Patch(color='#FF9800', label='中デグ (0.05–0.10)'),
    mpatches.Patch(color='#F44336', label='高デグ (>0.10)'),
]
ax2.legend(handles=legend_patches, loc='upper right',
           facecolor=STYLE['bg_color'], edgecolor=STYLE['grid_color'],
           labelcolor=STYLE['text_color'], fontsize=9)

# 全体タイトル
fig.suptitle('F1 2026 タイヤデグラデーション分析（R01–R03）',
             color=STYLE['text_color'], fontsize=18, fontweight='bold', y=0.98)

plt.tight_layout(rect=[0, 0, 1, 0.96])
plt.savefig(OUTPUT_HEATMAP, dpi=150, bbox_inches='tight',
            facecolor=STYLE['bg_color'], edgecolor='none')
plt.close()
print(f"  ヒートマップ保存: {OUTPUT_HEATMAP}")

# ─────────────────────────────────────────────
# 完了サマリー
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("完了サマリー")
print("=" * 60)
print(f"  分析ロングラン数: {len(df_result)}")
print(f"  使用GP: {', '.join(df_result['GP'].unique())}")
print(f"  平均R²値: {df_result['R2'].mean():.3f}（回帰信頼性）")
print(f"  R²<0.3（信頼性低）: {(df_result['R2'] < 0.3).sum()}件")
print(f"  負のデグレート（燃料効果優勢）: {(df_result['DegRate'] < 0).sum()}件")
print(f"  出力CSV: {OUTPUT_CSV}")
print(f"  ヒートマップ: {OUTPUT_HEATMAP}")
print()

# 燃料効果の考察
print("■ 燃料効果の考察")
print("  初期スティントで負のデグレートが出る理由:")
print("  1. 燃料搭載量が多い序盤は1周あたり約0.05-0.08秒のタイム改善効果がある")
print("  2. タイヤ劣化が軽微なうちは、燃料消費による重量減の効果が勝る")
print("  3. TyreLifeが浅い（5周以下）のデータは回帰の信頼性が低い（R²要確認）")
print()
print("■ デグレート解釈の注意")
print("  ・正の値 = タイヤ劣化効果が優勢（1周ごとにNsec遅くなる）")
print("  ・負の値 = 燃料軽量化効果が優勢（見かけ上タイヤは劣化していない）")
print("  ・全て「燃料補正前」の値。実際のタイヤ劣化は過小評価の可能性あり")
