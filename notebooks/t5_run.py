#!/usr/bin/env python3
"""
T5: チームメイト比較分析
全10チーム × 3GP のペースデルタ・セクター・スピード・タイヤ劣化・最終順位差を集計する。
出力: notebooks/output/teammate_comparison.csv
      notebooks/output/teammate_heatmap.png
"""

import matplotlib
matplotlib.use('Agg')  # GUIなし環境対応

import csv
import os
import sys
import math
import statistics
from collections import defaultdict

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np

# ─────────────────────────────────────────────
# パス設定
# ─────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

LONGRUNS_CSV   = os.path.join(OUTPUT_DIR, 'clean_longruns.csv')
FUEL_CSV       = os.path.join(OUTPUT_DIR, 'fuel_corrected_pace.csv')

GP_META = {
    'R01': {
        'label': 'Australia',
        'results': os.path.join(ROOT_DIR, 'data/2026_R01_Australia/export/race_results.csv'),
        'laps':    os.path.join(ROOT_DIR, 'data/2026_R01_Australia/export/race_laps.csv'),
    },
    'R02': {
        'label': 'China',
        'results': os.path.join(ROOT_DIR, 'data/2026_R02_China/export/race_results.csv'),
        'laps':    os.path.join(ROOT_DIR, 'data/2026_R02_China/export/race_laps.csv'),
    },
    'R03': {
        'label': 'Japan',
        'results': os.path.join(ROOT_DIR, 'data/2026_R03_Japan/export/race_results.csv'),
        'laps':    os.path.join(ROOT_DIR, 'data/2026_R03_Japan/export/race_laps.csv'),
    },
}

# ─────────────────────────────────────────────
# チームメイトペア定義（2026シーズン）
# GP名: None = 全GP共通
# ─────────────────────────────────────────────
TEAMMATE_PAIRS = {
    'McLaren':       ('NOR', 'PIA'),
    'Ferrari':       ('LEC', 'HAM'),
    'Red Bull Racing': ('VER', 'HAD'),   # TSU → HAD 移籍済み
    'Mercedes':      ('RUS', 'ANT'),
    'Aston Martin':  ('ALO', 'STR'),
    'Williams':      ('ALB', 'SAI'),
    'Racing Bulls':  ('LAW', 'LIN'),
    'Alpine':        ('GAS', 'COL'),
    'Haas F1 Team':  ('OCO', 'BEA'),
    'Audi':          ('HUL', 'BOR'),   # Kick Sauber → Audi
}

# ─────────────────────────────────────────────
# ユーティリティ: NaN を安全に扱う中央値
# ─────────────────────────────────────────────
def safe_median(vals):
    """数値リストから NaN を除き中央値を返す。空の場合は None"""
    clean = [v for v in vals if v is not None and not math.isnan(v)]
    if not clean:
        return None
    return statistics.median(clean)


def to_float(s):
    """文字列 → float。変換不可なら None"""
    try:
        v = float(s)
        return None if math.isnan(v) else v
    except (TypeError, ValueError):
        return None


# ─────────────────────────────────────────────
# Step 1: 燃料補正済みペース読み込み
# ─────────────────────────────────────────────
def load_fuel_corrected():
    """fuel_corrected_pace.csv を読み込み、{(GP, Driver): FuelCorrectedMedianPace} を返す"""
    result = {}
    with open(FUEL_CSV, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            gp_key = row['GP'].split('_')[0]   # "R01_Australia" → "R01"
            pace   = to_float(row['FuelCorrectedMedianPace'])
            result[(gp_key, row['Driver'])] = pace
    print(f'[燃料補正ペース] {len(result)} レコード読み込み')
    return result


# ─────────────────────────────────────────────
# Step 2: ロングランからセクター・ラップタイムを読み込み
# ─────────────────────────────────────────────
def load_longruns():
    """clean_longruns.csv を読み込み
    {(GP, Driver): {'s1': [..], 's2': [..], 's3': [..], 'laps': [(TyreLife, LapTime)]}} を返す"""
    data = defaultdict(lambda: {'s1': [], 's2': [], 's3': [], 'laps': []})
    with open(LONGRUNS_CSV, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            gp_key = row['GP'].split('_')[0]
            key    = (gp_key, row['Driver'])
            s1 = to_float(row['Sector1Time_sec'])
            s2 = to_float(row['Sector2Time_sec'])
            s3 = to_float(row['Sector3Time_sec'])
            lt = to_float(row['LapTime_sec'])
            tl = to_float(row['TyreLife'])
            if s1 is not None: data[key]['s1'].append(s1)
            if s2 is not None: data[key]['s2'].append(s2)
            if s3 is not None: data[key]['s3'].append(s3)
            if lt is not None and tl is not None:
                data[key]['laps'].append((tl, tl))  # (TyreLife, LapTime) ※後で tl を使う
                # 上書き: タプルを正しく格納
    # 再読み込みでタプルを修正
    data2 = defaultdict(lambda: {'s1': [], 's2': [], 's3': [], 'laps': []})
    with open(LONGRUNS_CSV, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            gp_key = row['GP'].split('_')[0]
            key    = (gp_key, row['Driver'])
            s1 = to_float(row['Sector1Time_sec'])
            s2 = to_float(row['Sector2Time_sec'])
            s3 = to_float(row['Sector3Time_sec'])
            lt = to_float(row['LapTime_sec'])
            tl = to_float(row['TyreLife'])
            if s1 is not None: data2[key]['s1'].append(s1)
            if s2 is not None: data2[key]['s2'].append(s2)
            if s3 is not None: data2[key]['s3'].append(s3)
            if lt is not None and tl is not None:
                data2[key]['laps'].append((tl, tl))
    print(f'[ロングラン] {len(data2)} ドライバー×GPキー読み込み')
    return data2


def load_longruns_v2():
    """clean_longruns.csv を読み込み、正しい (TyreLife, LapTime) タプルで返す"""
    data = defaultdict(lambda: {'s1': [], 's2': [], 's3': [], 'laps': []})
    with open(LONGRUNS_CSV, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            gp_key = row['GP'].split('_')[0]
            key    = (gp_key, row['Driver'])
            for col, lst in [('Sector1Time_sec', 's1'),
                              ('Sector2Time_sec', 's2'),
                              ('Sector3Time_sec', 's3')]:
                v = to_float(row[col])
                if v is not None:
                    data[key][lst].append(v)
            lt = to_float(row['LapTime_sec'])
            tl = to_float(row['TyreLife'])
            if lt is not None and tl is not None:
                data[key]['laps'].append((tl, lt))
    print(f'[ロングラン] {len(data)} ドライバー×GPキー読み込み')
    return data


# ─────────────────────────────────────────────
# Step 3: SpeedST を race_laps.csv から読み込み
# ─────────────────────────────────────────────
def load_speed_st():
    """各GP の race_laps.csv から SpeedST 中央値を {(GP, Driver): median_speed} で返す"""
    result = {}
    for gp_key, meta in GP_META.items():
        laps_path = meta['laps']
        if not os.path.exists(laps_path):
            print(f'[警告] {laps_path} が見つかりません')
            continue
        driver_speeds = defaultdict(list)
        with open(laps_path, newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                drv = row['Driver']
                spd = to_float(row.get('SpeedST'))
                if spd is not None and spd > 0:
                    driver_speeds[drv].append(spd)
        for drv, speeds in driver_speeds.items():
            result[(gp_key, drv)] = safe_median(speeds)
    print(f'[SpeedST] {len(result)} レコード読み込み')
    return result


# ─────────────────────────────────────────────
# Step 4: レース最終順位を race_results.csv から読み込み
# ─────────────────────────────────────────────
def load_race_positions():
    """{(GP, Driver): position} を返す。DNF等は None"""
    result = {}
    for gp_key, meta in GP_META.items():
        path = meta['results']
        if not os.path.exists(path):
            print(f'[警告] {path} が見つかりません')
            continue
        with open(path, newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                drv = row['Abbreviation']
                pos = to_float(row.get('Position'))
                result[(gp_key, drv)] = pos  # DNFなどで None の場合あり
    print(f'[レース順位] {len(result)} レコード読み込み')
    return result


# ─────────────────────────────────────────────
# Step 5: タイヤ劣化デルタ（ロングラン後半ペースドロップ）計算
# laps の後半50%の平均 - 前半50%の平均
# ─────────────────────────────────────────────
def tyre_deg_delta(laps):
    """
    (TyreLife, LapTime) のリストから後半ペースドロップを計算。
    TyreLife でソートして前半/後半に分割。
    正 → 後半が遅い（タイヤ劣化）, 負 → 後半が速い（燃料効果優勢）
    """
    if len(laps) < 4:
        return None
    sorted_laps = sorted(laps, key=lambda x: x[0])  # TyreLife でソート
    mid = len(sorted_laps) // 2
    first_half  = [lt for _, lt in sorted_laps[:mid]]
    second_half = [lt for _, lt in sorted_laps[mid:]]
    return safe_median(second_half) - safe_median(first_half)


# ─────────────────────────────────────────────
# Step 6: チームメイト比較の中核計算
# ─────────────────────────────────────────────
def compute_teammate_comparison(fuel_pace, longruns, speed_st, race_pos):
    """
    全チーム × 全GP でチームメイトペアのデルタを計算する。
    Delta = Driver1 - Driver2（負 = Driver1 が速い）
    """
    rows = []
    gp_labels = ['R01', 'R02', 'R03']

    for team, (d1, d2) in TEAMMATE_PAIRS.items():
        for gp in gp_labels:
            gp_label = GP_META[gp]['label']

            # 燃料補正済みペース中央値差
            p1 = fuel_pace.get((gp, d1))
            p2 = fuel_pace.get((gp, d2))
            pace_delta = (p1 - p2) if (p1 is not None and p2 is not None) else None

            # セクター別中央値差
            lr1 = longruns.get((gp, d1), {'s1': [], 's2': [], 's3': [], 'laps': []})
            lr2 = longruns.get((gp, d2), {'s1': [], 's2': [], 's3': [], 'laps': []})

            m1s1, m2s1 = safe_median(lr1['s1']), safe_median(lr2['s1'])
            m1s2, m2s2 = safe_median(lr1['s2']), safe_median(lr2['s2'])
            m1s3, m2s3 = safe_median(lr1['s3']), safe_median(lr2['s3'])

            s1_delta = (m1s1 - m2s1) if (m1s1 is not None and m2s1 is not None) else None
            s2_delta = (m1s2 - m2s2) if (m1s2 is not None and m2s2 is not None) else None
            s3_delta = (m1s3 - m2s3) if (m1s3 is not None and m2s3 is not None) else None

            # SpeedST 中央値差
            sp1 = speed_st.get((gp, d1))
            sp2 = speed_st.get((gp, d2))
            speed_delta = (sp1 - sp2) if (sp1 is not None and sp2 is not None) else None

            # レース最終順位差
            pos1 = race_pos.get((gp, d1))
            pos2 = race_pos.get((gp, d2))
            pos_delta = (pos1 - pos2) if (pos1 is not None and pos2 is not None) else None

            # タイヤ劣化デルタ
            deg1 = tyre_deg_delta(lr1['laps'])
            deg2 = tyre_deg_delta(lr2['laps'])
            tyre_deg_delta_val = (deg1 - deg2) if (deg1 is not None and deg2 is not None) else None

            rows.append({
                'GP':           gp_label,
                'Team':         team,
                'Driver1':      d1,
                'Driver2':      d2,
                'PaceDelta_sec':   round(pace_delta, 4)      if pace_delta  is not None else '',
                'S1Delta':         round(s1_delta, 4)         if s1_delta    is not None else '',
                'S2Delta':         round(s2_delta, 4)         if s2_delta    is not None else '',
                'S3Delta':         round(s3_delta, 4)         if s3_delta    is not None else '',
                'SpeedDelta':      round(speed_delta, 2)      if speed_delta is not None else '',
                'PositionDelta':   round(pos_delta, 0)        if pos_delta   is not None else '',
                'TyreDegDelta':    round(tyre_deg_delta_val, 4) if tyre_deg_delta_val is not None else '',
            })
            # デバッグ出力
            status = f"PaceDelta={pace_delta:.3f}" if pace_delta is not None else "PaceDelta=NaN"
            print(f'  {gp} {team:20s} {d1} vs {d2}: {status}')

    return rows


# ─────────────────────────────────────────────
# Step 7: CSV 出力
# ─────────────────────────────────────────────
def save_csv(rows, out_path):
    fieldnames = ['GP', 'Team', 'Driver1', 'Driver2',
                  'PaceDelta_sec', 'S1Delta', 'S2Delta', 'S3Delta',
                  'SpeedDelta', 'PositionDelta', 'TyreDegDelta']
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f'[CSV] 保存: {out_path} ({len(rows)} 行)')


# ─────────────────────────────────────────────
# Step 8: ヒートマップ描画（チーム × GP のペース差）
# ─────────────────────────────────────────────
def save_heatmap(rows, out_path):
    """PaceDelta_sec をヒートマップで可視化。負（青）= Driver1 が速い"""

    gp_order   = ['Australia', 'China', 'Japan']
    team_order = list(TEAMMATE_PAIRS.keys())

    # 行列作成
    matrix = np.full((len(team_order), len(gp_order)), np.nan)
    pair_labels = {}  # team → "D1 vs D2" 文字列
    for team, (d1, d2) in TEAMMATE_PAIRS.items():
        pair_labels[team] = f'{d1} vs {d2}'
        ti = team_order.index(team)
        for row in rows:
            if row['Team'] == team and row['PaceDelta_sec'] != '':
                gi = gp_order.index(row['GP'])
                matrix[ti, gi] = float(row['PaceDelta_sec'])

    # ─── プロット ───
    fig, ax = plt.subplots(figsize=(10, 8))
    fig.patch.set_facecolor('#1a1a2e')
    ax.set_facecolor('#1a1a2e')

    # ゼロ中心のカラーマップ
    abs_max = np.nanmax(np.abs(matrix)) if not np.all(np.isnan(matrix)) else 1.0
    norm = mcolors.TwoSlopeNorm(vmin=-abs_max, vcenter=0, vmax=abs_max)
    cmap = plt.cm.RdBu_r  # 青=Driver1速い, 赤=Driver2速い

    im = ax.imshow(matrix, cmap=cmap, norm=norm, aspect='auto')

    # カラーバー
    cbar = fig.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label('ペース差 [秒]\n(負 = Driver1 が速い)', color='white', fontsize=10)
    cbar.ax.yaxis.set_tick_params(color='white')
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color='white')

    # 軸ラベル
    ax.set_xticks(range(len(gp_order)))
    ax.set_xticklabels(gp_order, color='white', fontsize=11)
    ax.set_yticks(range(len(team_order)))
    ax.set_yticklabels(
        [f'{t}\n({pair_labels[t]})' for t in team_order],
        color='white', fontsize=9
    )
    ax.tick_params(colors='white')

    # セル内に数値を表示
    for ti in range(len(team_order)):
        for gi in range(len(gp_order)):
            val = matrix[ti, gi]
            if not np.isnan(val):
                text_color = 'white' if abs(val) > abs_max * 0.5 else '#cccccc'
                ax.text(gi, ti, f'{val:+.3f}', ha='center', va='center',
                        color=text_color, fontsize=9, fontweight='bold')
            else:
                ax.text(gi, ti, 'N/A', ha='center', va='center',
                        color='#666688', fontsize=8)

    ax.set_title('チームメイトペース差ヒートマップ（2026 R01-R03）\nDriver1 - Driver2 [秒、燃料補正済み]',
                 color='white', fontsize=13, pad=15)
    ax.spines[:].set_color('#333355')

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
    plt.close()
    print(f'[PNG] 保存: {out_path}')


# ─────────────────────────────────────────────
# メイン
# ─────────────────────────────────────────────
def main():
    print('=' * 60)
    print('T5 チームメイト比較分析')
    print('=' * 60)

    # データ読み込み
    fuel_pace = load_fuel_corrected()
    longruns  = load_longruns_v2()
    speed_st  = load_speed_st()
    race_pos  = load_race_positions()

    print()
    print('[チームメイトデルタ計算中...]')
    rows = compute_teammate_comparison(fuel_pace, longruns, speed_st, race_pos)

    # CSV 出力
    csv_path = os.path.join(OUTPUT_DIR, 'teammate_comparison.csv')
    save_csv(rows, csv_path)

    # ヒートマップ出力
    heatmap_path = os.path.join(OUTPUT_DIR, 'teammate_heatmap.png')
    save_heatmap(rows, heatmap_path)

    print()
    print('=' * 60)
    print('完了！')
    print(f'  CSV     : {csv_path}')
    print(f'  ヒートマップ: {heatmap_path}')
    print('=' * 60)


if __name__ == '__main__':
    main()
