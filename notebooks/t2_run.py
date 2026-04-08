#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
t2_run.py — R01-R03 クリーンロングラン抽出スクリプト

ロングラン識別ロジック（CLAUDE.md定義に準拠）:
1. アウトラップ（PitOutTime_secが非NaN）を除外
2. インラップ（PitInTime_secが非NaN）を除外
3. 同一ドライバー・同一Stint・同一Compoundの連続ラップをグループ化
4. グループ内ラップ数 >= 5 → ロングラン
5. 各ラップが当該GPセッション最速の107%以内（異常値除外フィルタ）
6. TrackStatus == '1'（グリーンフラグ）のラップのみ
"""

import matplotlib
matplotlib.use('Agg')  # GUIなし環境用バックエンド

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import os
import sys

# ==============================
# 設定
# ==============================
BASE_DIR = '/Volumes/lyssr_workspace/2026_1_4/Motorsports-Visualised'
OUTPUT_DIR = os.path.join(BASE_DIR, 'notebooks', 'output')

# GP設定: (ラベル, CSVパス)
GP_FILES = [
    ('R01_Australia', os.path.join(BASE_DIR, 'data', '2026_R01_Australia', 'export', 'race_laps.csv')),
    ('R02_China',     os.path.join(BASE_DIR, 'data', '2026_R02_China',     'export', 'race_laps.csv')),
    ('R03_Japan',     os.path.join(BASE_DIR, 'data', '2026_R03_Japan',     'export', 'race_laps.csv')),
]

LONGRUN_MIN_LAPS = 5      # ロングランの最低ラップ数
FILTER_PCT = 1.07          # セッション最速ラップの107%以内フィルタ
GREEN_FLAG = '1'           # TrackStatus グリーンフラグ値（文字列）

# スタイル設定
STYLE = {
    'bg_color':   '#1a1a2e',
    'text_color': '#ffffff',
    'grid_color': '#333355',
    'figsize':    (12, 6.75),
    'title_size': 18,
    'label_size': 12,
}

COMPOUND_COLORS = {
    'SOFT':         '#FF3333',
    'MEDIUM':       '#FFD700',
    'HARD':         '#FFFFFF',
    'INTERMEDIATE': '#39B54A',
    'WET':          '#0072CE',
}

# ==============================
# 出力ディレクトリ作成
# ==============================
os.makedirs(OUTPUT_DIR, exist_ok=True)
print(f"出力先ディレクトリ: {OUTPUT_DIR}")


# ==============================
# ヘルパー関数
# ==============================

def load_race_laps(gp_label, csv_path):
    """race_laps.csvを読み込み、型変換して返す"""
    if not os.path.exists(csv_path):
        print(f"[WARNING] {gp_label}: ファイルが見つかりません → {csv_path}")
        return None

    df = pd.read_csv(csv_path, dtype={'TrackStatus': str})  # TrackStatusは文字列で読む

    # GP列を追加
    df['GP'] = gp_label

    # 数値変換
    for col in ['LapTime_sec', 'Sector1Time_sec', 'Sector2Time_sec', 'Sector3Time_sec',
                'Stint', 'TyreLife', 'LapNumber', 'PitOutTime_sec', 'PitInTime_sec']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # FreshTyre: 文字列 'True'/'False' → bool
    if 'FreshTyre' in df.columns:
        df['FreshTyre'] = df['FreshTyre'].astype(str).str.strip().str.lower() == 'true'

    print(f"[OK] {gp_label}: {len(df)}行読み込み完了 (ドライバー数: {df['Driver'].nunique()})")
    return df


def extract_clean_longruns(df, gp_label):
    """
    クリーンなロングランを抽出する。
    戻り値: (clean_df, stats_dict)
    """
    stats = {
        'gp': gp_label,
        'total_laps': len(df),
        'after_green_filter': 0,
        'after_pit_filter': 0,
        'longrun_laps': 0,
        'after_107_filter': 0,
        'excluded_by_107': 0,
        'longrun_count': 0,
        'clean_lap_count': 0,
    }

    # ----- ステップ6: TrackStatus == '1'（グリーンフラグ）のみ -----
    # TrackStatusが文字列であることを確認した上でフィルタ
    df_green = df[df['TrackStatus'].astype(str).str.strip() == GREEN_FLAG].copy()
    stats['after_green_filter'] = len(df_green)
    print(f"  グリーンフラグフィルタ後: {len(df_green)}行 ({len(df) - len(df_green)}行除外)")

    # ----- ステップ1,2: アウトラップ・インラップ除外 -----
    df_clean = df_green[
        df_green['PitOutTime_sec'].isna() &   # アウトラップ除外
        df_green['PitInTime_sec'].isna()       # インラップ除外
    ].copy()
    stats['after_pit_filter'] = len(df_clean)
    print(f"  ピットラップ除外後: {len(df_clean)}行 ({len(df_green) - len(df_clean)}行除外)")

    # LapTimeが有効なラップのみ（NaNを除く）
    df_clean = df_clean.dropna(subset=['LapTime_sec'])

    # ----- ステップ3,4: 同一ドライバー・Stint・Compoundでグループ化し5周以上 -----
    # グループキー: (GP, Driver, Stint, Compound)
    group_cols = ['GP', 'Driver', 'Stint', 'Compound']
    group_sizes = df_clean.groupby(group_cols)['LapNumber'].count().reset_index()
    group_sizes.columns = group_cols + ['StintLapCount']

    # 5周以上のグループのみ抽出（ロングランの候補）
    longrun_groups = group_sizes[group_sizes['StintLapCount'] >= LONGRUN_MIN_LAPS]
    df_longrun = df_clean.merge(longrun_groups[group_cols], on=group_cols, how='inner').copy()
    stats['longrun_laps'] = len(df_longrun)
    print(f"  ロングラン候補（>=5周）: {len(df_longrun)}行")

    # ----- ステップ5: 107%フィルタ -----
    # セッション全体（グリーンフラグ・ピット除外後）の最速ラップタイム
    session_fastest = df_clean['LapTime_sec'].min()
    threshold_107 = session_fastest * FILTER_PCT

    df_filtered = df_longrun[df_longrun['LapTime_sec'] <= threshold_107].copy()
    excluded_107 = len(df_longrun) - len(df_filtered)
    stats['after_107_filter'] = len(df_filtered)
    stats['excluded_by_107'] = excluded_107
    print(f"  107%フィルタ（>{threshold_107:.3f}秒を除外）: {excluded_107}行除外、残り{len(df_filtered)}行")

    # ----- LongRunID を付与 -----
    # グループ番号を連番で振る
    if len(df_filtered) == 0:
        print(f"  [WARNING] {gp_label}: クリーンなロングランが0件")
        return pd.DataFrame(), stats

    # ソート
    df_filtered = df_filtered.sort_values(['Driver', 'Stint', 'LapNumber']).copy()

    # LongRunID: "{GP}_{Driver}_S{Stint}" 形式
    df_filtered['LongRunID'] = (
        df_filtered['GP'] + '_' +
        df_filtered['Driver'].astype(str) + '_S' +
        df_filtered['Stint'].astype(int).astype(str)
    )

    # CleanLapCount: そのLongRunID内のラップ数を付与
    df_filtered['CleanLapCount'] = df_filtered.groupby('LongRunID')['LapNumber'].transform('count')

    # ロングランID数とラップ数を集計
    stats['longrun_count'] = df_filtered['LongRunID'].nunique()
    stats['clean_lap_count'] = len(df_filtered)

    print(f"  → クリーンロングラン: {stats['longrun_count']}スティント、{stats['clean_lap_count']}ラップ")

    return df_filtered, stats


def select_output_columns(df):
    """出力カラムを契約仕様に合わせて選択・整形"""
    out_cols = [
        'GP', 'Driver', 'Team', 'Stint', 'Compound',
        'TyreLife', 'LapNumber', 'LapTime_sec',
        'Sector1Time_sec', 'Sector2Time_sec', 'Sector3Time_sec',
        'FreshTyre', 'LongRunID', 'CleanLapCount'
    ]
    # 存在するカラムのみ選択
    available = [c for c in out_cols if c in df.columns]
    return df[available].copy()


# ==============================
# メイン処理
# ==============================

def main():
    all_dfs = []
    all_stats = []

    for gp_label, csv_path in GP_FILES:
        print(f"\n{'='*50}")
        print(f"処理中: {gp_label}")
        print(f"{'='*50}")

        # データ読み込み
        df = load_race_laps(gp_label, csv_path)
        if df is None:
            continue

        # クリーンロングラン抽出
        df_clean, stats = extract_clean_longruns(df, gp_label)
        all_stats.append(stats)

        if len(df_clean) > 0:
            df_out = select_output_columns(df_clean)
            all_dfs.append(df_out)

    # ----- 全GP統合CSV出力 -----
    print(f"\n{'='*50}")
    print("全GP統合 CSV出力")
    print(f"{'='*50}")

    if all_dfs:
        df_final = pd.concat(all_dfs, ignore_index=True)
        output_csv = os.path.join(OUTPUT_DIR, 'clean_longruns.csv')
        df_final.to_csv(output_csv, index=False, encoding='utf-8')
        print(f"保存: {output_csv} ({len(df_final)}行)")
    else:
        print("[WARNING] 出力データが空です")
        df_final = pd.DataFrame()

    # ----- 統計サマリー表示 -----
    print("\n\n【GPごとの統計サマリー】")
    stats_df = pd.DataFrame(all_stats)
    print(stats_df.to_string(index=False))

    # ----- 可視化1: GPごとのロングラン数・クリーンラップ数 -----
    if len(df_final) > 0:
        plot_gp_summary(all_stats)
        plot_compound_distribution(df_final)
        plot_longrun_table(df_final)

    print("\n完了！")
    return df_final, all_stats


def plot_gp_summary(all_stats):
    """GPごとのロングラン数・クリーンラップ数・107%除外数のバーチャート"""
    fig, axes = plt.subplots(1, 3, figsize=(STYLE['figsize'][0], STYLE['figsize'][1]))
    fig.patch.set_facecolor(STYLE['bg_color'])
    fig.suptitle('GPごとのロングラン統計 (R01-R03)', color=STYLE['text_color'],
                 fontsize=STYLE['title_size'], fontweight='bold', y=1.01)

    gp_labels = [s['gp'] for s in all_stats]
    x = range(len(gp_labels))

    # ① ロングラン数
    ax = axes[0]
    ax.set_facecolor(STYLE['bg_color'])
    vals = [s['longrun_count'] for s in all_stats]
    bars = ax.bar(x, vals, color='#4488ff', alpha=0.85)
    ax.set_xticks(list(x))
    ax.set_xticklabels(gp_labels, color=STYLE['text_color'], fontsize=9, rotation=15, ha='right')
    ax.set_title('ロングランスティント数', color=STYLE['text_color'], fontsize=STYLE['label_size'])
    ax.set_ylabel('件数', color=STYLE['text_color'])
    ax.tick_params(colors=STYLE['text_color'])
    ax.spines[['top','right']].set_visible(False)
    for spine in ['left','bottom']:
        ax.spines[spine].set_color(STYLE['grid_color'])
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                str(val), ha='center', va='bottom', color=STYLE['text_color'], fontsize=10)

    # ② クリーンラップ数
    ax = axes[1]
    ax.set_facecolor(STYLE['bg_color'])
    vals = [s['clean_lap_count'] for s in all_stats]
    bars = ax.bar(x, vals, color='#44cc88', alpha=0.85)
    ax.set_xticks(list(x))
    ax.set_xticklabels(gp_labels, color=STYLE['text_color'], fontsize=9, rotation=15, ha='right')
    ax.set_title('クリーンラップ数', color=STYLE['text_color'], fontsize=STYLE['label_size'])
    ax.set_ylabel('ラップ数', color=STYLE['text_color'])
    ax.tick_params(colors=STYLE['text_color'])
    ax.spines[['top','right']].set_visible(False)
    for spine in ['left','bottom']:
        ax.spines[spine].set_color(STYLE['grid_color'])
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                str(val), ha='center', va='bottom', color=STYLE['text_color'], fontsize=10)

    # ③ 107%フィルタ除外ラップ数
    ax = axes[2]
    ax.set_facecolor(STYLE['bg_color'])
    vals = [s['excluded_by_107'] for s in all_stats]
    bars = ax.bar(x, vals, color='#ff6644', alpha=0.85)
    ax.set_xticks(list(x))
    ax.set_xticklabels(gp_labels, color=STYLE['text_color'], fontsize=9, rotation=15, ha='right')
    ax.set_title('107%フィルタ除外ラップ数', color=STYLE['text_color'], fontsize=STYLE['label_size'])
    ax.set_ylabel('ラップ数', color=STYLE['text_color'])
    ax.tick_params(colors=STYLE['text_color'])
    ax.spines[['top','right']].set_visible(False)
    for spine in ['left','bottom']:
        ax.spines[spine].set_color(STYLE['grid_color'])
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                str(val), ha='center', va='bottom', color=STYLE['text_color'], fontsize=10)

    plt.tight_layout()
    out_path = os.path.join(OUTPUT_DIR, 'gp_summary.png')
    plt.savefig(out_path, dpi=150, bbox_inches='tight', facecolor=STYLE['bg_color'])
    plt.close()
    print(f"グラフ保存: {out_path}")


def plot_compound_distribution(df_final):
    """コンパウンド別ロングラン分布（GPごとにスタック棒グラフ）"""
    # GP×Compoundのクロス集計（LongRunIDでカウント）
    pivot = (df_final
             .drop_duplicates(subset=['GP', 'Driver', 'Stint', 'Compound'])
             .groupby(['GP', 'Compound'])
             .size()
             .unstack(fill_value=0))

    # コンパウンド順を固定
    compound_order = ['SOFT', 'MEDIUM', 'HARD', 'INTERMEDIATE', 'WET']
    ordered_cols = [c for c in compound_order if c in pivot.columns]
    pivot = pivot[ordered_cols]

    fig, ax = plt.subplots(figsize=STYLE['figsize'])
    fig.patch.set_facecolor(STYLE['bg_color'])
    ax.set_facecolor(STYLE['bg_color'])

    bottom = [0] * len(pivot)
    for compound in ordered_cols:
        vals = pivot[compound].values
        color = COMPOUND_COLORS.get(compound, '#888888')
        bars = ax.bar(pivot.index, vals, bottom=bottom, label=compound,
                      color=color, alpha=0.85,
                      edgecolor='#555555', linewidth=0.5)
        # ラベル表示（0より大きい部分のみ）
        for i, (bar, val) in enumerate(zip(bars, vals)):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bottom[i] + val / 2,
                        str(val),
                        ha='center', va='center',
                        color='#000000' if compound == 'MEDIUM' else STYLE['text_color'],
                        fontsize=9, fontweight='bold')
        bottom = [b + v for b, v in zip(bottom, vals)]

    ax.set_title('コンパウンド別ロングランスティント分布 (R01-R03)',
                 color=STYLE['text_color'], fontsize=STYLE['title_size'], fontweight='bold')
    ax.set_xlabel('GP', color=STYLE['text_color'], fontsize=STYLE['label_size'])
    ax.set_ylabel('ロングランスティント数', color=STYLE['text_color'], fontsize=STYLE['label_size'])
    ax.tick_params(colors=STYLE['text_color'])
    ax.spines[['top','right']].set_visible(False)
    for spine in ['left','bottom']:
        ax.spines[spine].set_color(STYLE['grid_color'])

    legend = ax.legend(title='Compound', title_fontsize=10,
                       facecolor='#2a2a4e', edgecolor=STYLE['grid_color'],
                       labelcolor=STYLE['text_color'])
    legend.get_title().set_color(STYLE['text_color'])

    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))

    plt.tight_layout()
    out_path = os.path.join(OUTPUT_DIR, 'compound_distribution.png')
    plt.savefig(out_path, dpi=150, bbox_inches='tight', facecolor=STYLE['bg_color'])
    plt.close()
    print(f"グラフ保存: {out_path}")


def plot_longrun_table(df_final):
    """ドライバー×スティントのロングラン一覧テーブル（GP別）"""
    for gp_label in df_final['GP'].unique():
        df_gp = df_final[df_final['GP'] == gp_label]

        # ドライバー・スティントごとにサマリー
        summary = (df_gp
                   .groupby(['Driver', 'Team', 'Stint', 'Compound'])
                   .agg(
                       CleanLaps=('LapNumber', 'count'),
                       MinLapTime=('LapTime_sec', 'min'),
                       MaxLapTime=('LapTime_sec', 'max'),
                       AvgLapTime=('LapTime_sec', 'mean'),
                       TyreLifeStart=('TyreLife', 'min'),
                   )
                   .reset_index()
                   .sort_values(['Driver', 'Stint']))

        # テーブル描画
        n_rows = len(summary)
        fig_height = max(4, n_rows * 0.35 + 2)
        fig, ax = plt.subplots(figsize=(14, fig_height))
        fig.patch.set_facecolor(STYLE['bg_color'])
        ax.set_facecolor(STYLE['bg_color'])
        ax.axis('off')

        # カラム名
        col_names = ['Driver', 'Team', 'Stint', 'Compound',
                     'CleanLaps', 'MinLapTime', 'MaxLapTime', 'AvgLapTime', 'TyreLifeStart']
        col_labels = ['Driver', 'Team', 'Stint', 'Compound',
                      'Clean\nLaps', 'Min\nLapTime', 'Max\nLapTime', 'Avg\nLapTime', 'TyreLife\nStart']

        cell_data = []
        for _, row in summary.iterrows():
            cell_data.append([
                row['Driver'],
                row['Team'],
                int(row['Stint']),
                row['Compound'],
                int(row['CleanLaps']),
                f"{row['MinLapTime']:.3f}",
                f"{row['MaxLapTime']:.3f}",
                f"{row['AvgLapTime']:.3f}",
                int(row['TyreLifeStart']),
            ])

        table = ax.table(
            cellText=cell_data,
            colLabels=col_labels,
            cellLoc='center',
            loc='center',
        )
        table.auto_set_font_size(False)
        table.set_fontsize(8)
        table.scale(1.0, 1.4)

        # テーブルスタイリング
        for (row_idx, col_idx), cell in table.get_celld().items():
            if row_idx == 0:
                cell.set_facecolor('#2a2a5e')
                cell.set_text_props(color=STYLE['text_color'], fontweight='bold')
            else:
                # Compoundカラム（index 3）に色付け
                compound_val = cell_data[row_idx - 1][3] if col_idx == 3 else None
                if compound_val and col_idx == 3:
                    cell.set_facecolor(COMPOUND_COLORS.get(compound_val, '#333355'))
                    text_color = '#000000' if compound_val == 'MEDIUM' else STYLE['text_color']
                    cell.set_text_props(color=text_color, fontweight='bold')
                else:
                    bg = '#1e1e38' if row_idx % 2 == 0 else '#15152a'
                    cell.set_facecolor(bg)
                    cell.set_text_props(color=STYLE['text_color'])
            cell.set_edgecolor(STYLE['grid_color'])

        ax.set_title(f'{gp_label} — ドライバー×スティント ロングラン一覧',
                     color=STYLE['text_color'], fontsize=STYLE['title_size'],
                     fontweight='bold', pad=12)

        plt.tight_layout()
        out_path = os.path.join(OUTPUT_DIR, f'longrun_table_{gp_label}.png')
        plt.savefig(out_path, dpi=150, bbox_inches='tight', facecolor=STYLE['bg_color'])
        plt.close()
        print(f"グラフ保存: {out_path}")


# ==============================
# エントリーポイント
# ==============================
if __name__ == '__main__':
    df_result, stats_result = main()
