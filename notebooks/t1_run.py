#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# t1_run.py — R01〜R03 データ品質監査スクリプト
# このファイルはt1_data_quality_audit.ipynbの全Pythonセルを抽出したもの

# ライブラリのインポート
import os
import warnings
warnings.filterwarnings('ignore')

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

try:
    from IPython.display import display, HTML
except ImportError:
    def display(x):
        print(x)

# 日本語フォント設定
import matplotlib.font_manager as fm
jp_fonts = [f.name for f in fm.fontManager.ttflist if 'Noto' in f.name or 'Hiragino' in f.name or 'Yu Gothic' in f.name]
jp_font = jp_fonts[0] if jp_fonts else 'DejaVu Sans'
plt.rcParams['font.family'] = jp_font
print(f'使用フォント: {jp_font}')

# スタイル設定
BG_COLOR = '#1a1a2e'
TEXT_COLOR = '#ffffff'
GRID_COLOR = '#333355'
ACCENT = '#e94560'
OK_COLOR = '#39B54A'
WARN_COLOR = '#FFD700'
ERR_COLOR = '#FF3333'

plt.rcParams.update({
    'figure.facecolor': BG_COLOR,
    'axes.facecolor': BG_COLOR,
    'axes.edgecolor': GRID_COLOR,
    'axes.labelcolor': TEXT_COLOR,
    'xtick.color': TEXT_COLOR,
    'ytick.color': TEXT_COLOR,
    'text.color': TEXT_COLOR,
    'grid.color': GRID_COLOR,
})

print('設定完了')

# ─── データパスの定義 ──────────────────────────────────────────────────────────
BASE = '/Volumes/lyssr_workspace/2026_1_4/Motorsports-Visualised/data'

GP_CONFIGS = {
    'R01_Australia': {
        'path': os.path.join(BASE, '2026_R01_Australia', 'export'),
        'files': [
            'fp_laps.csv',
            'fp_session_summary.csv',
            'fp_weather.csv',
            'race_laps.csv',
            'race_results.csv',
            'race_weather.csv',
            'race_control_messages.csv',
        ],
        'has_sprint': False,
        'has_quali': False,
    },
    'R02_China': {
        'path': os.path.join(BASE, '2026_R02_China', 'export'),
        'files': [
            'fp_laps.csv',
            'fp_session_summary.csv',
            'fp_weather.csv',
            'quali_laps.csv',
            'sprint_laps.csv',
            'sprint_results.csv',
            'sq_laps.csv',
            'race_laps.csv',
            'race_results.csv',
            'race_weather.csv',
            'race_control_messages.csv',
        ],
        'has_sprint': True,
        'has_quali': True,
    },
    'R03_Japan': {
        'path': os.path.join(BASE, '2026_R03_Japan', 'export'),
        'files': [
            'fp_laps.csv',
            'fp1_summary.csv',
            'fp2_summary.csv',
            'race_laps.csv',
            'race_results.csv',
            'race_weather.csv',
            'race_control_messages.csv',
        ],
        'has_sprint': False,
        'has_quali': False,
    },
}

print('GPコンフィグ定義完了')
for gp, cfg in GP_CONFIGS.items():
    print(f'  {gp}: {len(cfg["files"])}ファイル')

# ─── 1. 各CSVのshape・カラム・欠損値 ──────────────────────────────────────────

# 全CSVを読み込み、基本情報を収集する関数
def audit_csv(filepath):
    """CSVを読み込み、shape・カラム・欠損値を返す"""
    result = {
        'exists': False,
        'shape': None,
        'columns': [],
        'missing': {},
        'missing_total': 0,
        'df': None,
        'error': None,
    }
    if not os.path.exists(filepath):
        result['error'] = 'ファイルなし'
        return result
    try:
        df = pd.read_csv(filepath)
        result['exists'] = True
        result['shape'] = df.shape
        result['columns'] = list(df.columns)
        missing = df.isnull().sum()
        result['missing'] = missing[missing > 0].to_dict()
        result['missing_total'] = int(missing.sum())
        result['df'] = df
    except Exception as e:
        result['error'] = str(e)
    return result

# 全GP・全ファイルを読み込む
all_data = {}
for gp, cfg in GP_CONFIGS.items():
    all_data[gp] = {}
    for fname in cfg['files']:
        fpath = os.path.join(cfg['path'], fname)
        all_data[gp][fname] = audit_csv(fpath)

print('全CSV読み込み完了')

# 各GPのCSV情報を表示
for gp, files in all_data.items():
    print('\n' + '='*60)
    print(f'  {gp}')
    print('='*60)

    rows = []
    for fname, info in files.items():
        if info['error']:
            status = f'[警告] {info["error"]}'
            shape_str = '-'
            missing_str = '-'
        else:
            status = '[OK]'
            shape_str = f'{info["shape"][0]}行 x {info["shape"][1]}列'
            if info['missing_total'] > 0:
                missing_str = f'{info["missing_total"]}セル欠損'
            else:
                missing_str = '欠損なし'
        rows.append({'ファイル': fname, 'ステータス': status, 'サイズ': shape_str, '欠損': missing_str})

    summary_df = pd.DataFrame(rows)
    display(summary_df.to_string(index=False))

    # 欠損カラムの詳細表示
    for fname, info in files.items():
        if info['exists'] and info['missing']:
            print(f'\n  [{fname}] 欠損カラム詳細:')
            for col, cnt in info['missing'].items():
                pct = cnt / info['shape'][0] * 100
                print(f'    {col}: {cnt}件 ({pct:.1f}%)')

# カラム一覧の詳細表示（主要テーブルのみ）
KEY_FILES = ['race_laps.csv', 'fp_laps.csv', 'race_results.csv']

for gp, files in all_data.items():
    print(f'\n--- {gp} カラム一覧 ---')
    for fname in KEY_FILES:
        if fname in files and files[fname]['exists']:
            cols = files[fname]['columns']
            print(f'  {fname} ({len(cols)}列): {cols}')

# ─── 2. ドライバー別ラップ数の整合性チェック ──────────────────────────────────

def check_lap_consistency(gp, files):
    """race_lapsとrace_resultsのLaps列を比較し、不整合を報告する"""
    print(f'\n=== {gp} ラップ数整合性チェック ===')

    rl_info = files.get('race_laps.csv', {})
    rr_info = files.get('race_results.csv', {})

    if not rl_info.get('exists') or not rr_info.get('exists'):
        print('  [警告] race_laps.csv または race_results.csv が存在しません')
        return None

    rl_df = rl_info['df']
    rr_df = rr_info['df']

    # race_lapsからドライバー別ラップ数を集計（IsAccurateに関係なく全ラップ）
    # LapNumberの最大値をそのドライバーの完走ラップ数とみなす
    laps_from_rl = rl_df.groupby('Driver')['LapNumber'].max().reset_index()
    laps_from_rl.columns = ['Driver', 'Laps_race_laps']

    # race_resultsのLapsをAbbreviationで取得
    rr_sub = rr_df[['Abbreviation', 'Laps', 'Status', 'Position']].copy()
    rr_sub.columns = ['Driver', 'Laps_results', 'Status', 'Position']
    rr_sub['Laps_results'] = pd.to_numeric(rr_sub['Laps_results'], errors='coerce')

    # マージ
    merged = pd.merge(laps_from_rl, rr_sub, on='Driver', how='outer')
    merged['Laps_race_laps'] = pd.to_numeric(merged['Laps_race_laps'], errors='coerce')
    merged['差分'] = merged['Laps_race_laps'] - merged['Laps_results']
    merged['整合'] = merged['差分'].abs() <= 2  # ±2ラップまで許容

    # 表示
    display_df = merged.sort_values('Position').reset_index(drop=True)
    display_df['Laps_race_laps'] = display_df['Laps_race_laps'].astype('Int64')
    display_df['Laps_results'] = display_df['Laps_results'].astype('Int64')
    display_df['差分'] = display_df['差分'].astype('Int64')

    print(display_df[['Driver', 'Position', 'Status', 'Laps_race_laps', 'Laps_results', '差分', '整合']].to_string(index=False))

    # 不整合サマリー
    n_mismatch = (~merged['整合']).sum()
    n_total = len(merged)
    if n_mismatch == 0:
        print(f'\n  [OK] 全{n_total}ドライバーで整合 (±2ラップ許容)')
    else:
        print(f'\n  [警告] {n_mismatch}/{n_total}ドライバーで不整合')

    return merged

# 全GPで実行
lap_consistency = {}
for gp, files in all_data.items():
    lap_consistency[gp] = check_lap_consistency(gp, files)

# ─── 3. FPラップ数のセッション別集計 ─────────────────────────────────────────

def audit_fp_laps(gp, files):
    """fp_laps.csvのセッション別・ドライバー別ラップ数を集計する"""
    print(f'\n=== {gp} FPラップ数集計 ===')

    fp_info = files.get('fp_laps.csv', {})
    if not fp_info.get('exists'):
        print('  [警告] fp_laps.csv が存在しません')
        return

    df = fp_info['df']

    if 'Session' not in df.columns:
        print('  [警告] Sessionカラムなし')
        return

    # セッション別ラップ数集計
    session_summary = df.groupby('Session').agg(
        ドライバー数=('Driver', 'nunique'),
        総ラップ数=('LapNumber', 'count'),
        有効ラップ=('IsAccurate', lambda x: (pd.to_numeric(x, errors='coerce') == 1).sum()),
    ).reset_index()

    print('\nセッション別サマリー:')
    print(session_summary.to_string(index=False))

    # ドライバー別・セッション別ラップ数
    driver_session = df.groupby(['Session', 'Driver'])['LapNumber'].count().unstack(level=0, fill_value=0)
    driver_session.columns.name = None
    driver_session = driver_session.reset_index()

    print('\nドライバー別・セッション別ラップ数:')
    print(driver_session.to_string(index=False))

    return session_summary

# 全GPで実行
for gp, files in all_data.items():
    audit_fp_laps(gp, files)

# FPラップ数の可視化
fig, axes = plt.subplots(1, 3, figsize=(18, 6), facecolor=BG_COLOR)
fig.suptitle('FPラップ数 — セッション別・ドライバー別', fontsize=16, color=TEXT_COLOR, y=1.02)

gp_list = list(GP_CONFIGS.keys())
colors_cycle = ['#e94560', '#0f3460', '#533483', '#00b4d8', '#90e0ef']

for ax, gp in zip(axes, gp_list):
    ax.set_facecolor(BG_COLOR)
    fp_info = all_data[gp].get('fp_laps.csv', {})
    if not fp_info.get('exists'):
        ax.text(0.5, 0.5, 'データなし', ha='center', va='center', color=TEXT_COLOR)
        ax.set_title(gp, color=TEXT_COLOR)
        continue

    df = fp_info['df']
    if 'Session' not in df.columns:
        ax.text(0.5, 0.5, 'Sessionカラムなし', ha='center', va='center', color=TEXT_COLOR)
        ax.set_title(gp, color=TEXT_COLOR)
        continue

    sessions = sorted(df['Session'].unique())
    driver_counts = df.groupby(['Session', 'Driver'])['LapNumber'].count().unstack(level=0, fill_value=0)

    x = np.arange(len(driver_counts))
    width = 0.8 / max(len(sessions), 1)

    for i, sess in enumerate(sessions):
        if sess in driver_counts.columns:
            vals = driver_counts[sess].values
            bars = ax.bar(x + i * width - (len(sessions)-1)*width/2, vals,
                          width=width*0.9, label=sess,
                          color=colors_cycle[i % len(colors_cycle)], alpha=0.85)

    ax.set_xticks(x)
    ax.set_xticklabels(driver_counts.index, rotation=90, fontsize=7, color=TEXT_COLOR)
    ax.set_ylabel('ラップ数', color=TEXT_COLOR)
    ax.set_title(gp.replace('_', ' '), color=TEXT_COLOR, fontsize=11)
    ax.legend(fontsize=7, facecolor='#333355', labelcolor=TEXT_COLOR)
    ax.grid(axis='y', color=GRID_COLOR, alpha=0.5)
    ax.tick_params(colors=TEXT_COLOR)
    for spine in ax.spines.values():
        spine.set_edgecolor(GRID_COLOR)

plt.tight_layout()
plt.savefig('/tmp/fp_laps_by_session.png', dpi=120, bbox_inches='tight', facecolor=BG_COLOR)
plt.close()
print('グラフ保存: /tmp/fp_laps_by_session.png')

# ─── 4. 異常値検出 ────────────────────────────────────────────────────────────

# 異常値検出の設定
LAP_TIME_MIN = 60.0   # 秒 — これより短いラップは異常とみなす
LAP_TIME_MAX = 200.0  # 秒 — これより長いラップは異常とみなす（SC/安全上問題のある周回は除外）
SECTOR_MIN = 0.0       # 負のセクタータイムは異常

# ラップデータを含む可能性があるファイル名のリスト
LAP_FILES = ['race_laps.csv', 'fp_laps.csv', 'quali_laps.csv', 'sprint_laps.csv', 'sq_laps.csv']
SECTOR_COLS = ['Sector1Time_sec', 'Sector2Time_sec', 'Sector3Time_sec']

anomaly_summary = []  # 全GPの異常値まとめ

for gp, files in all_data.items():
    print(f'\n=== {gp} 異常値検出 ===')

    for fname in LAP_FILES:
        info = files.get(fname)
        if info is None or not info.get('exists'):
            continue
        df = info['df'].copy()

        # LapTime_sec列の確認
        if 'LapTime_sec' not in df.columns:
            print(f'  [{fname}] LapTime_secカラムなし — スキップ')
            continue

        lap_col = pd.to_numeric(df['LapTime_sec'], errors='coerce')
        n_total = len(df)

        # LapTime異常値（非NaN・範囲外）
        mask_too_fast = lap_col.notna() & (lap_col < LAP_TIME_MIN)
        mask_too_slow = lap_col.notna() & (lap_col > LAP_TIME_MAX)
        mask_nan = lap_col.isna()

        n_fast = mask_too_fast.sum()
        n_slow = mask_too_slow.sum()
        n_nan = mask_nan.sum()

        # セクタータイム負値
        neg_sector_counts = {}
        for sc in SECTOR_COLS:
            if sc in df.columns:
                sc_col = pd.to_numeric(df[sc], errors='coerce')
                neg_cnt = (sc_col.notna() & (sc_col < SECTOR_MIN)).sum()
                if neg_cnt > 0:
                    neg_sector_counts[sc] = neg_cnt

        # 結果表示
        print(f'\n  [{fname}] 総行数: {n_total}')
        print(f'    LapTime NaN: {n_nan}件 ({n_nan/n_total*100:.1f}%)')
        print(f'    LapTime < {LAP_TIME_MIN}秒: {n_fast}件')
        print(f'    LapTime > {LAP_TIME_MAX}秒: {n_slow}件')

        if n_fast > 0:
            print(f'    [警告] 高速異常ラップ:')
            fast_df = df[mask_too_fast][['Driver', 'LapNumber', 'LapTime_sec']].head(10)
            print(fast_df.to_string(index=False))

        if neg_sector_counts:
            print(f'    [警告] 負セクタータイム: {neg_sector_counts}')
        else:
            print(f'    セクタータイム負値: なし')

        # サマリー集計用
        anomaly_summary.append({
            'GP': gp,
            'ファイル': fname,
            '総行数': n_total,
            'LapTime_NaN': n_nan,
            'LapTime_高速異常': n_fast,
            'LapTime_低速異常': n_slow,
            '負セクター件数': sum(neg_sector_counts.values()),
        })

print('\n異常値検出完了')

# LapTime分布の可視化（race_lapsに絞る）
gp_list_valid = [gp for gp in GP_CONFIGS.keys() if all_data[gp].get('race_laps.csv', {}).get('exists')]
n_plots = len(gp_list_valid)

if n_plots > 0:
    fig, axes = plt.subplots(1, n_plots, figsize=(6 * n_plots, 5), facecolor=BG_COLOR)
    if n_plots == 1:
        axes = [axes]

    fig.suptitle('LapTime分布 (race_laps) — 異常値ライン付き', fontsize=14, color=TEXT_COLOR)

    for ax, gp in zip(axes, gp_list_valid):
        ax.set_facecolor(BG_COLOR)
        df = all_data[gp]['race_laps.csv']['df']
        lap_times = pd.to_numeric(df['LapTime_sec'], errors='coerce').dropna()

        ax.hist(lap_times, bins=50, color='#0f3460', edgecolor=GRID_COLOR, alpha=0.8)
        ax.axvline(LAP_TIME_MIN, color=ERR_COLOR, linestyle='--', linewidth=1.5, label=f'下限 {LAP_TIME_MIN}s')
        ax.axvline(LAP_TIME_MAX, color=WARN_COLOR, linestyle='--', linewidth=1.5, label=f'上限 {LAP_TIME_MAX}s')

        ax.set_title(gp.replace('_', ' '), color=TEXT_COLOR)
        ax.set_xlabel('LapTime (秒)', color=TEXT_COLOR)
        ax.set_ylabel('ラップ数', color=TEXT_COLOR)
        ax.legend(fontsize=8, facecolor='#333355', labelcolor=TEXT_COLOR)
        ax.grid(axis='y', color=GRID_COLOR, alpha=0.4)
        ax.tick_params(colors=TEXT_COLOR)
        for spine in ax.spines.values():
            spine.set_edgecolor(GRID_COLOR)

    plt.tight_layout()
    plt.savefig('/tmp/laptime_distribution.png', dpi=120, bbox_inches='tight', facecolor=BG_COLOR)
    plt.close()
    print('グラフ保存: /tmp/laptime_distribution.png')

# ─── 5. 全GPの総合サマリーテーブル ───────────────────────────────────────────

# 全GP・全CSVのサマリーを一つのDataFrameにまとめる
summary_rows = []

for gp, files in all_data.items():
    for fname, info in files.items():
        row = {
            'GP': gp,
            'ファイル': fname,
            '存在': '[OK]' if info['exists'] else '[NG]',
            '行数': info['shape'][0] if info['exists'] else 0,
            '列数': info['shape'][1] if info['exists'] else 0,
            '欠損セル数': info['missing_total'] if info['exists'] else 0,
            'エラー': info['error'] or '',
        }
        summary_rows.append(row)

summary_df = pd.DataFrame(summary_rows)

print('=== 全GP 総合CSVサマリーテーブル ===')
print(summary_df.to_string(index=False))

# 異常値サマリーテーブル
print('\n=== 異常値サマリー ===')
anomaly_df = pd.DataFrame(anomaly_summary)
if not anomaly_df.empty:
    print(anomaly_df.to_string(index=False))

    # 異常あり・なしの集計
    anomaly_df['異常フラグ'] = (
        (anomaly_df['LapTime_高速異常'] > 0) |
        (anomaly_df['負セクター件数'] > 0)
    )
    n_anomaly = anomaly_df['異常フラグ'].sum()
    n_total = len(anomaly_df)
    print(f'\n異常ありファイル: {n_anomaly}/{n_total}')
else:
    print('データなし')

# ラップ数整合性サマリー
print('\n=== ラップ数整合性サマリー ===')
consistency_rows = []
for gp, merged in lap_consistency.items():
    if merged is None:
        consistency_rows.append({'GP': gp, '整合': '-', '不整合': '-', '計': '-', '備考': 'データなし'})
        continue
    n_ok = merged['整合'].sum()
    n_ng = (~merged['整合']).sum()
    n_total = len(merged)
    consistency_rows.append({
        'GP': gp,
        '整合': n_ok,
        '不整合': n_ng,
        '計': n_total,
        '備考': '[OK] 全整合' if n_ng == 0 else f'[警告] {n_ng}件不整合'
    })

consistency_summary_df = pd.DataFrame(consistency_rows)
print(consistency_summary_df.to_string(index=False))

# 総合品質スコアの計算と可視化
score_rows = []
for gp, files in all_data.items():
    total_files = len(files)
    existing = sum(1 for f in files.values() if f['exists'])
    missing_total = sum(f['missing_total'] for f in files.values() if f['exists'])
    total_cells = sum(f['shape'][0] * f['shape'][1] for f in files.values() if f['exists'])
    missing_rate = missing_total / total_cells * 100 if total_cells > 0 else 0

    # 異常値カウント（このGPのみ）
    gp_anomalies = anomaly_df[anomaly_df['GP'] == gp] if not anomaly_df.empty else pd.DataFrame()
    n_laptime_anomaly = gp_anomalies['LapTime_高速異常'].sum() if not gp_anomalies.empty else 0
    n_sector_anomaly = gp_anomalies['負セクター件数'].sum() if not gp_anomalies.empty else 0

    # ラップ数整合性
    lc = lap_consistency.get(gp)
    if lc is not None:
        lap_ok_rate = lc['整合'].mean() * 100
    else:
        lap_ok_rate = None

    score_rows.append({
        'GP': gp,
        'ファイル存在率(%)': round(existing / total_files * 100, 1),
        '欠損セル率(%)': round(missing_rate, 2),
        'LapTime異常数': int(n_laptime_anomaly),
        'セクター異常数': int(n_sector_anomaly),
        'ラップ数整合率(%)': round(lap_ok_rate, 1) if lap_ok_rate is not None else 'N/A',
    })

score_df = pd.DataFrame(score_rows)
print('=== 総合品質スコア ===')
print(score_df.to_string(index=False))

# 可視化
fig, axes = plt.subplots(2, 2, figsize=(14, 10), facecolor=BG_COLOR)
fig.suptitle('R01〜R03 データ品質 総合ダッシュボード', fontsize=16, color=TEXT_COLOR, y=1.01)

gps = score_df['GP'].str.replace('R0', 'R').values
x = np.arange(len(gps))

# ファイル存在率
ax = axes[0, 0]
ax.set_facecolor(BG_COLOR)
bars = ax.bar(x, score_df['ファイル存在率(%)'], color=['#39B54A' if v == 100 else '#FFD700' for v in score_df['ファイル存在率(%)']])
ax.set_xticks(x); ax.set_xticklabels(gps, color=TEXT_COLOR)
ax.set_ylim(0, 110)
ax.set_title('ファイル存在率 (%)', color=TEXT_COLOR)
ax.set_ylabel('%', color=TEXT_COLOR)
ax.axhline(100, color=GRID_COLOR, linestyle='--', linewidth=1)
for bar, val in zip(bars, score_df['ファイル存在率(%)']):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, f'{val}%', ha='center', color=TEXT_COLOR, fontsize=10)
ax.grid(axis='y', color=GRID_COLOR, alpha=0.4)
ax.tick_params(colors=TEXT_COLOR)
for spine in ax.spines.values(): spine.set_edgecolor(GRID_COLOR)

# 欠損セル率
ax = axes[0, 1]
ax.set_facecolor(BG_COLOR)
missing_vals = score_df['欠損セル率(%)'].values
bars = ax.bar(x, missing_vals, color=['#39B54A' if v < 10 else '#FFD700' if v < 30 else '#FF3333' for v in missing_vals])
ax.set_xticks(x); ax.set_xticklabels(gps, color=TEXT_COLOR)
ax.set_title('欠損セル率 (%)', color=TEXT_COLOR)
ax.set_ylabel('%', color=TEXT_COLOR)
for bar, val in zip(bars, missing_vals):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1, f'{val}%', ha='center', color=TEXT_COLOR, fontsize=10)
ax.grid(axis='y', color=GRID_COLOR, alpha=0.4)
ax.tick_params(colors=TEXT_COLOR)
for spine in ax.spines.values(): spine.set_edgecolor(GRID_COLOR)

# LapTime・セクター異常数
ax = axes[1, 0]
ax.set_facecolor(BG_COLOR)
w = 0.35
b1 = ax.bar(x - w/2, score_df['LapTime異常数'], width=w, color=ERR_COLOR, label='LapTime異常', alpha=0.85)
b2 = ax.bar(x + w/2, score_df['セクター異常数'], width=w, color=WARN_COLOR, label='セクター異常', alpha=0.85)
ax.set_xticks(x); ax.set_xticklabels(gps, color=TEXT_COLOR)
ax.set_title('異常値件数', color=TEXT_COLOR)
ax.set_ylabel('件数', color=TEXT_COLOR)
ax.legend(facecolor='#333355', labelcolor=TEXT_COLOR, fontsize=9)
ax.grid(axis='y', color=GRID_COLOR, alpha=0.4)
ax.tick_params(colors=TEXT_COLOR)
for spine in ax.spines.values(): spine.set_edgecolor(GRID_COLOR)

# ラップ数整合率
ax = axes[1, 1]
ax.set_facecolor(BG_COLOR)
lap_rates = []
for v in score_df['ラップ数整合率(%)']:
    try:
        lap_rates.append(float(v))
    except Exception:
        lap_rates.append(0.0)
bars = ax.bar(x, lap_rates, color=['#39B54A' if v >= 95 else '#FFD700' if v >= 80 else '#FF3333' for v in lap_rates])
ax.set_xticks(x); ax.set_xticklabels(gps, color=TEXT_COLOR)
ax.set_ylim(0, 110)
ax.set_title('ラップ数整合率 (%)', color=TEXT_COLOR)
ax.set_ylabel('%', color=TEXT_COLOR)
ax.axhline(100, color=GRID_COLOR, linestyle='--', linewidth=1)
for bar, val, orig in zip(bars, lap_rates, score_df['ラップ数整合率(%)']):
    label = f'{orig}%' if str(orig) != 'N/A' else 'N/A'
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, label, ha='center', color=TEXT_COLOR, fontsize=10)
ax.grid(axis='y', color=GRID_COLOR, alpha=0.4)
ax.tick_params(colors=TEXT_COLOR)
for spine in ax.spines.values(): spine.set_edgecolor(GRID_COLOR)

plt.tight_layout()
plt.savefig('/tmp/quality_dashboard.png', dpi=120, bbox_inches='tight', facecolor=BG_COLOR)
plt.close()
print('グラフ保存: /tmp/quality_dashboard.png')

# ─── 最終サマリー出力 ─────────────────────────────────────────────────────────

print('=' * 70)
print('  R01〜R03 データ品質監査 — 完了サマリー')
print('=' * 70)

total_files_checked = sum(len(f) for f in all_data.values())
total_existing = sum(sum(1 for fi in f.values() if fi['exists']) for f in all_data.values())
total_missing_files = total_files_checked - total_existing

print(f'\n検査対象ファイル数: {total_files_checked}')
print(f'存在: {total_existing} / 不在: {total_missing_files}')

total_anomaly_laptime = int(anomaly_df['LapTime_高速異常'].sum()) if not anomaly_df.empty else 0
total_anomaly_sector = int(anomaly_df['負セクター件数'].sum()) if not anomaly_df.empty else 0
print(f'\nLapTime異常 (< {LAP_TIME_MIN}秒): {total_anomaly_laptime}件')
print(f'セクター異常 (負値): {total_anomaly_sector}件')

print('\n各GPラップ数整合性:')
print(consistency_summary_df.to_string(index=False))

print('\n注意事項:')
print('  - LapTime NaN（アウトラップ・インラップ等）は正常欠損として許容')
print('  - LapTime > 200秒はSC/VSC介入ラップの可能性あり — 個別確認推奨')
print('  - ラップ数整合性は ±2ラップの誤差を許容（記録方法の違い）')
print('  - FP1リザーブドライバーは分析前に除外すること')
print('=' * 70)
