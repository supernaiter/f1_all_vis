#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T4: 燃料補正後レースペース比較
R01-R03のクリーンロングランに燃料補正を適用し、真のレースペースを比較する。

燃料補正モデル（CLAUDE.md準拠、概算値）:
  - 燃料1kgあたり約0.035秒/ラップ遅くなる
  - 1ラップあたり約1.75kg消費
  - → 1ラップあたり約0.06秒の燃料軽量化効果
  - 補正: FuelCorrectedTime = LapTime_sec + (LapNumber * 0.06)
    ラップが進むほど燃料が軽くなるため、その分を足し戻して「スタート時の燃料搭載量換算」に統一する。

注意: 燃料補正値は概算であり、チームごとの燃料搭載量差・エンジン出力差は未考慮。
      常に「燃料補正前/後」を明記すること。
"""

import matplotlib
matplotlib.use('Agg')  # GUIなし環境でのバックエンド設定

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy import stats
import os
import sys
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# パス設定
# ============================================================
BASE_DIR = '/Volumes/lyssr_workspace/2026_1_4/Motorsports-Visualised'
INPUT_CSV = os.path.join(BASE_DIR, 'notebooks/output/clean_longruns.csv')
OUTPUT_DIR = os.path.join(BASE_DIR, 'notebooks/output')

# レース結果CSV
RACE_RESULTS = {
    'R01_Australia': os.path.join(BASE_DIR, 'data/2026_R01_Australia/export/race_results.csv'),
    'R02_China':     os.path.join(BASE_DIR, 'data/2026_R02_China/export/race_results.csv'),
    'R03_Japan':     os.path.join(BASE_DIR, 'data/2026_R03_Japan/export/race_results.csv'),
}

# ============================================================
# グラフスタイル設定（CLAUDE.md準拠）
# ============================================================
STYLE = {
    'bg_color':    '#1a1a2e',
    'card_color':  '#1c1c25',
    'text_color':  '#ffffff',
    'dim_color':   '#aaaaaa',
    'grid_color':  '#333355',
    'accent_color': '#e10600',  # F1 Red
    'figsize':     (14, 10),
    'title_size':  18,
    'label_size':  12,
    'tick_size':   10,
}

# 日本語フォント設定（Hiragino Sans: /usr/bin/python3のmatplotlibで使用可能）
import matplotlib.font_manager as fm
JP_FONT = None
for font in fm.fontManager.ttflist:
    if 'Hiragino' in font.name:
        JP_FONT = font.name
        break
if JP_FONT:
    plt.rcParams['font.family'] = JP_FONT

# GP表示名マッピング
GP_LABELS = {
    'R01_Australia': 'R01 オーストラリア',
    'R02_China':     'R02 中国',
    'R03_Japan':     'R03 日本（鈴鹿）',
}

# チームカラー（F1 2026）
TEAM_COLORS = {
    'McLaren':      '#F47600',
    'Ferrari':      '#E8002D',
    'Red Bull':     '#3671C6',
    'Mercedes':     '#00D7B6',
    'Aston Martin': '#229971',
    'Williams':     '#0093CC',
    'Racing Bulls': '#6692FF',
    'Alpine':       '#0090FF',
    'Haas':         '#B6BABD',
    'Kick Sauber':  '#52E252',
}

# ============================================================
# 燃料補正定数（CLAUDE.md準拠、概算）
# ============================================================
FUEL_CORRECTION_PER_LAP = 0.06  # 秒/ラップ（燃料軽量化効果）


def apply_fuel_correction(df):
    """
    燃料補正を各ラップに適用する。
    FuelCorrectedTime = LapTime_sec + (LapNumber * FUEL_CORRECTION_PER_LAP)
    LapNumberが大きいほど燃料が軽くなっているため、その分を足し戻す。
    """
    df = df.copy()
    df['FuelCorrectedTime'] = df['LapTime_sec'] + df['LapNumber'] * FUEL_CORRECTION_PER_LAP
    return df


def load_race_results():
    """レース結果CSVを全GP分読み込み、GPカラムを追加して結合する。"""
    dfs = []
    for gp_key, path in RACE_RESULTS.items():
        if not os.path.exists(path):
            print(f"  [警告] レース結果CSVが見つかりません: {path}", file=sys.stderr)
            continue
        df = pd.read_csv(path)
        df['GP'] = gp_key
        dfs.append(df)
    if not dfs:
        raise FileNotFoundError("レース結果CSVが1件も見つかりません。")
    return pd.concat(dfs, ignore_index=True)


def compute_driver_summary(laps_df, results_df):
    """
    ドライバー別・GP別のペースサマリーを計算する。
    出力カラム: GP, Driver, Team, RawMedianPace, FuelCorrectedMedianPace, CleanLaps, RacePosition
    """
    rows = []
    for (gp, driver), grp in laps_df.groupby(['GP', 'Driver']):
        team = grp['Team'].iloc[0]
        raw_median = grp['LapTime_sec'].median()
        fuel_median = grp['FuelCorrectedTime'].median()
        clean_laps = len(grp)

        # レース結果から最終順位を取得
        mask = (results_df['GP'] == gp) & (results_df['Abbreviation'] == driver)
        race_pos_series = results_df.loc[mask, 'Position']
        race_position = int(race_pos_series.iloc[0]) if len(race_pos_series) > 0 else None

        rows.append({
            'GP':                    gp,
            'Driver':                driver,
            'Team':                  team,
            'RawMedianPace':         round(raw_median, 4),
            'FuelCorrectedMedianPace': round(fuel_median, 4),
            'CleanLaps':             clean_laps,
            'RacePosition':          race_position,
        })

    summary = pd.DataFrame(rows)
    return summary


def compute_team_ranking(summary_df):
    """
    チーム別の平均燃料補正ペース（補正前・補正後）を計算し、
    GPごとにチームランキングを算出する。
    """
    team_rows = []
    for (gp, team), grp in summary_df.groupby(['GP', 'Team']):
        # チームの代表ペース = ベストドライバーの中央値（2台の中の速い方）
        raw_best = grp['RawMedianPace'].min()
        fuel_best = grp['FuelCorrectedMedianPace'].min()
        team_rows.append({
            'GP':   gp,
            'Team': team,
            'RawBestPace':  round(raw_best, 4),
            'FuelBestPace': round(fuel_best, 4),
        })
    team_df = pd.DataFrame(team_rows)
    # 各GP内でランキング付け
    team_df['RawRank'] = team_df.groupby('GP')['RawBestPace'].rank(method='min')
    team_df['FuelRank'] = team_df.groupby('GP')['FuelBestPace'].rank(method='min')
    team_df['RankChange'] = team_df['RawRank'] - team_df['FuelRank']  # 正=補正後に上昇
    return team_df


def plot_fuel_pace_comparison(summary_df, team_df, output_path):
    """
    燃料補正前後のペース比較グラフを描画・保存する。
    4パネル構成:
      [0] ドライバー別補正後ペース散布図（GP別）
      [1] 燃料補正前後のチームランキング変動（全GP集計）
      [2] 補正効果量の統計（補正前後のペース差分布）
      [3] 補正後ペース vs レース結果順位の相関
    """
    fig = plt.figure(figsize=(16, 12))
    fig.patch.set_facecolor(STYLE['bg_color'])

    gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.45, wspace=0.35)
    axes = [fig.add_subplot(gs[i, j]) for i in range(2) for j in range(2)]

    for ax in axes:
        ax.set_facecolor(STYLE['card_color'])
        ax.tick_params(colors=STYLE['text_color'], labelsize=STYLE['tick_size'])
        ax.xaxis.label.set_color(STYLE['text_color'])
        ax.yaxis.label.set_color(STYLE['text_color'])
        ax.title.set_color(STYLE['text_color'])
        for spine in ax.spines.values():
            spine.set_edgecolor(STYLE['grid_color'])
        ax.grid(True, color=STYLE['grid_color'], linewidth=0.5, alpha=0.7)

    # ---- [0] ドライバー別燃料補正後ペース散布図（GP別） ----
    ax0 = axes[0]
    gp_list = sorted(summary_df['GP'].unique())
    gp_offsets = {gp: i for i, gp in enumerate(gp_list)}
    marker_styles = ['o', 's', '^']

    for i, gp in enumerate(gp_list):
        gp_data = summary_df[summary_df['GP'] == gp].copy()
        # チームカラーで着色
        for _, row in gp_data.iterrows():
            color = TEAM_COLORS.get(row['Team'], '#888888')
            x = i + np.random.uniform(-0.15, 0.15)  # ジッター
            ax0.scatter(x, row['FuelCorrectedMedianPace'],
                        color=color, marker=marker_styles[i],
                        s=60, alpha=0.85, zorder=3)

    ax0.set_xticks(range(len(gp_list)))
    ax0.set_xticklabels([GP_LABELS.get(g, g) for g in gp_list],
                        color=STYLE['text_color'], fontsize=9)
    ax0.set_ylabel('燃料補正後ペース中央値（秒）', color=STYLE['text_color'], fontsize=10)
    ax0.set_title('ドライバー別 燃料補正後ペース（GP別）\n※補正後: LapTime + LapNumber×0.06秒（概算）',
                  color=STYLE['text_color'], fontsize=11, pad=8)

    # チームカラー凡例
    legend_handles = [
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=c, markersize=7, label=t)
        for t, c in TEAM_COLORS.items() if t in summary_df['Team'].values
    ]
    ax0.legend(handles=legend_handles, loc='upper right',
               facecolor=STYLE['bg_color'], edgecolor=STYLE['grid_color'],
               labelcolor=STYLE['text_color'], fontsize=7, ncol=2)

    # ---- [1] 燃料補正前後チームランキング変動 ----
    ax1 = axes[1]
    # 全GP平均のランキングを計算（上位チーム優先）
    team_avg = team_df.groupby('Team')[['RawRank', 'FuelRank']].mean().reset_index()
    team_avg = team_avg.sort_values('FuelRank')

    bar_w = 0.35
    x = np.arange(len(team_avg))
    bars_raw  = ax1.bar(x - bar_w/2, team_avg['RawRank'],  bar_w,
                        label='補正前ランク', color='#6688cc', alpha=0.8)
    bars_fuel = ax1.bar(x + bar_w/2, team_avg['FuelRank'], bar_w,
                        label='補正後ランク', color=STYLE['accent_color'], alpha=0.8)

    ax1.set_xticks(x)
    ax1.set_xticklabels(team_avg['Team'], rotation=40, ha='right',
                        color=STYLE['text_color'], fontsize=8)
    ax1.set_ylabel('平均ランキング（小=速い）', color=STYLE['text_color'], fontsize=10)
    ax1.set_title('チーム別 燃料補正前後のランキング（全GP平均）\n※補正前: 生ラップタイム、補正後: 燃料補正済み（概算）',
                  color=STYLE['text_color'], fontsize=11, pad=8)
    ax1.invert_yaxis()  # 1位が上に来るよう反転
    ax1.legend(facecolor=STYLE['bg_color'], edgecolor=STYLE['grid_color'],
               labelcolor=STYLE['text_color'], fontsize=9)

    # ---- [2] 燃料補正効果量の統計（補正前後のペース差分布） ----
    ax2 = axes[2]
    summary_df['PaceDiff'] = summary_df['FuelCorrectedMedianPace'] - summary_df['RawMedianPace']

    for i, gp in enumerate(gp_list):
        gp_data = summary_df[summary_df['GP'] == gp]['PaceDiff']
        color = ['#6688cc', STYLE['accent_color'], '#66cc88'][i]
        ax2.hist(gp_data, bins=8, alpha=0.6, color=color,
                 label=GP_LABELS.get(gp, gp), edgecolor=STYLE['grid_color'])

    # 理論値ライン（レース中盤ラップ番号での補正量）
    # ラップ数の中央値を使って代表値を計算
    median_lap = summary_df.groupby('GP').apply(
        lambda g: g['CleanLaps'].sum() / len(g)
    ).mean()
    # ペース差はLapNumber依存。中央値は各ドライバーの分布の中央
    ax2.axvline(0, color=STYLE['text_color'], linestyle='--', alpha=0.5, linewidth=1)
    ax2.set_xlabel('補正後 − 補正前 ペース（秒）', color=STYLE['text_color'], fontsize=10)
    ax2.set_ylabel('ドライバー数', color=STYLE['text_color'], fontsize=10)
    ax2.set_title('燃料補正効果量の分布\n※正の値=補正後に遅く見える（早いラップを使用していた）',
                  color=STYLE['text_color'], fontsize=11, pad=8)
    ax2.legend(facecolor=STYLE['bg_color'], edgecolor=STYLE['grid_color'],
               labelcolor=STYLE['text_color'], fontsize=9)

    # ---- [3] 補正後ペース vs レース結果順位の相関 ----
    ax3 = axes[3]
    valid = summary_df.dropna(subset=['RacePosition', 'FuelCorrectedMedianPace']).copy()

    for i, gp in enumerate(gp_list):
        gp_data = valid[valid['GP'] == gp]
        color = ['#6688cc', STYLE['accent_color'], '#66cc88'][i]
        ax3.scatter(gp_data['FuelCorrectedMedianPace'], gp_data['RacePosition'],
                    color=color, s=60, alpha=0.8, zorder=3,
                    label=GP_LABELS.get(gp, gp))
        # ドライバーラベル
        for _, row in gp_data.iterrows():
            ax3.annotate(row['Driver'],
                         (row['FuelCorrectedMedianPace'], row['RacePosition']),
                         textcoords='offset points', xytext=(4, 0),
                         color=STYLE['dim_color'], fontsize=6)

    # 全GP通算の相関係数（Spearman）
    if len(valid) > 2:
        rho, pval = stats.spearmanr(valid['FuelCorrectedMedianPace'], valid['RacePosition'])
        corr_text = f'Spearman ρ = {rho:.3f} (p={pval:.3f})'
        ax3.text(0.05, 0.92, corr_text, transform=ax3.transAxes,
                 color=STYLE['text_color'], fontsize=9,
                 bbox=dict(facecolor=STYLE['bg_color'], alpha=0.7, edgecolor='none'))

    ax3.set_xlabel('燃料補正後ペース中央値（秒）', color=STYLE['text_color'], fontsize=10)
    ax3.set_ylabel('レース最終順位', color=STYLE['text_color'], fontsize=10)
    ax3.invert_yaxis()  # 1位が上に
    ax3.set_title('燃料補正後ペース vs レース最終順位\n（燃料補正前の値も参考値、概算補正）',
                  color=STYLE['text_color'], fontsize=11, pad=8)
    ax3.legend(facecolor=STYLE['bg_color'], edgecolor=STYLE['grid_color'],
               labelcolor=STYLE['text_color'], fontsize=8)

    # ---- タイトル・フッター ----
    fig.suptitle('F1 2026 R01-R03 燃料補正後レースペース分析\n'
                 '（燃料補正値は概算: +0.06秒/ラップ。チームごとの燃料搭載量差は未考慮）',
                 color=STYLE['text_color'], fontsize=STYLE['title_size'],
                 y=0.98, fontweight='bold')

    plt.savefig(output_path, dpi=150, bbox_inches='tight',
                facecolor=STYLE['bg_color'])
    plt.close()
    print(f"  [保存] {output_path}")


def main():
    print("=" * 60)
    print("T4: 燃料補正後レースペース分析 開始")
    print("=" * 60)

    # ---- データ読み込み ----
    print("\n[1] クリーンロングランCSVを読み込み中...")
    if not os.path.exists(INPUT_CSV):
        print(f"  [エラー] clean_longruns.csvが見つかりません: {INPUT_CSV}", file=sys.stderr)
        sys.exit(1)
    laps_df = pd.read_csv(INPUT_CSV)
    print(f"  読み込み: {len(laps_df)}行 / GP={laps_df['GP'].nunique()} / ドライバー={laps_df['Driver'].nunique()}")

    print("\n[2] レース結果CSVを読み込み中...")
    try:
        results_df = load_race_results()
        print(f"  読み込み: {len(results_df)}行 / GP={results_df['GP'].nunique()}")
    except FileNotFoundError as e:
        print(f"  [エラー] {e}", file=sys.stderr)
        sys.exit(1)

    # ---- 燃料補正の適用 ----
    print("\n[3] 燃料補正を適用中（+0.06秒/ラップ、概算）...")
    laps_df = apply_fuel_correction(laps_df)
    fuel_diff = laps_df['FuelCorrectedTime'] - laps_df['LapTime_sec']
    print(f"  補正量: min={fuel_diff.min():.2f}秒, max={fuel_diff.max():.2f}秒, "
          f"mean={fuel_diff.mean():.2f}秒")

    # ---- ドライバーサマリー計算 ----
    print("\n[4] ドライバー別サマリーを計算中...")
    summary_df = compute_driver_summary(laps_df, results_df)
    print(f"  サマリー行数: {len(summary_df)}")

    # ---- チームランキング計算 ----
    print("\n[5] チーム別ランキングを計算中...")
    team_df = compute_team_ranking(summary_df)

    # ---- 燃料補正前後のランキング変動を表示 ----
    print("\n  --- 燃料補正前後のランキング変動（全GP平均） ---")
    team_avg_display = team_df.groupby('Team')[['RawRank', 'FuelRank', 'RankChange']].mean()
    team_avg_display = team_avg_display.sort_values('FuelRank')
    for team, row in team_avg_display.iterrows():
        change_str = f"+{row['RankChange']:.1f}" if row['RankChange'] > 0 else f"{row['RankChange']:.1f}"
        print(f"  {team:<20} 補正前ランク={row['RawRank']:.1f}  補正後ランク={row['FuelRank']:.1f}  変動={change_str}")

    # ---- 相関係数（補正後ペース vs レース順位） ----
    valid = summary_df.dropna(subset=['RacePosition', 'FuelCorrectedMedianPace'])
    if len(valid) > 2:
        rho, pval = stats.spearmanr(valid['FuelCorrectedMedianPace'], valid['RacePosition'])
        print(f"\n  補正後ペース vs レース順位 Spearmanρ = {rho:.3f} (p={pval:.4f})")
        # 補正前も比較
        rho_raw, pval_raw = stats.spearmanr(valid['RawMedianPace'], valid['RacePosition'])
        print(f"  補正前ペース vs レース順位 Spearmanρ = {rho_raw:.3f} (p={pval_raw:.4f})")

    # ---- CSV出力 ----
    print("\n[6] 結果CSVを出力中...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_csv = os.path.join(OUTPUT_DIR, 'fuel_corrected_pace.csv')
    summary_df.to_csv(output_csv, index=False, encoding='utf-8')
    print(f"  [保存] {output_csv}")

    # ---- グラフ出力 ----
    print("\n[7] グラフを生成中...")
    output_png = os.path.join(OUTPUT_DIR, 'fuel_pace_comparison.png')
    plot_fuel_pace_comparison(summary_df, team_df, output_png)

    # ---- 完了 ----
    print("\n" + "=" * 60)
    print("T4: 燃料補正後レースペース分析 完了")
    print(f"  出力CSV : {output_csv}")
    print(f"  出力PNG : {output_png}")
    print("  注意: 燃料補正値（0.06秒/ラップ）は概算です。")
    print("        チームごとの実際の燃料搭載量は非公開のため未考慮。")
    print("=" * 60)


if __name__ == '__main__':
    main()
