"""
============================================================
2026 オーストラリアGP — 記事データ正確性検証 + チャート別CSV出力
============================================================
記事に使用された全チャートの元データを検証し、
各チャートと紐づくCSVを出力する。

出力先: data/2026_R01_Australia/article/csv/
"""

import fastf1
import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# 設定
# ============================================================
YEAR = 2026
GP_NAME = 'Australia'
ROUND_NUMBER = 1

CSV_DIR = Path(f'./data/{YEAR}_R{ROUND_NUMBER:02d}_{GP_NAME}/article/csv')
CSV_DIR.mkdir(parents=True, exist_ok=True)

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
drv_pos = dict(zip(results['Abbreviation'], results['Position'].astype(int)))

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

# ギャップ計算
leader_drv = results.iloc[0]['Abbreviation']
leader_laps = laps_all[laps_all['Driver'] == leader_drv].sort_values('LapNumber')
leader_times = {}
for _, row in leader_laps.iterrows():
    lap = int(row['LapNumber'])
    t = row['Time']
    if pd.notna(t):
        leader_times[lap] = t.total_seconds()

driver_gaps = {}
driver_order = results['Abbreviation'].tolist()
for drv in driver_order:
    drv_laps = laps_all[laps_all['Driver'] == drv].sort_values('LapNumber')
    gaps = {}
    for _, row in drv_laps.iterrows():
        lap = int(row['LapNumber'])
        t = row['Time']
        if pd.notna(t) and lap in leader_times:
            gaps[lap] = t.total_seconds() - leader_times[lap]
    if gaps:
        driver_gaps[drv] = gaps

errors_found = []

# ============================================================
# 1. Top6 ギャップ推移 CSV
# ============================================================
print('\n--- [1] Top 6 ギャップ推移 ---')
top6 = driver_order[:6]
gap_rows = []
for drv in top6:
    if drv not in driver_gaps:
        continue
    gaps = driver_gaps[drv]
    for lap, gap in sorted(gaps.items()):
        gap_rows.append({
            'Driver': drv,
            'Team': drv_team.get(drv, ''),
            'Position': drv_pos.get(drv, ''),
            'LapNumber': lap,
            'GapToLeader_sec': round(gap, 3),
        })
df_gap = pd.DataFrame(gap_rows)
df_gap.to_csv(CSV_DIR / 'chart1_gap_top6.csv', index=False, encoding='utf-8-sig')
print(f'  出力: chart1_gap_top6.csv ({len(df_gap)}行)')

# 記事のデータ検証: ギャップ値チェック
# 記事: LECの1回目PIT後（L26）のRUSとの差 = +15.552秒、最終ラップ = +15.519秒
gap_rus = driver_gaps.get('RUS', {})
gap_lec = driver_gaps.get('LEC', {})
gap_ant = driver_gaps.get('ANT', {})
gap_ham = driver_gaps.get('HAM', {})

if gap_lec and gap_rus:
    lec_rus_gap_l26 = gap_lec.get(26, 0) - gap_rus.get(26, 0)
    last_lap = max(max(gap_rus.keys(), default=0), max(gap_lec.keys(), default=0))
    lec_rus_gap_finish = gap_lec.get(last_lap, 0) - gap_rus.get(last_lap, 0)
    lec_rus_diff = lec_rus_gap_finish - lec_rus_gap_l26
    print(f'  RUS-LEC Gap L26: +{lec_rus_gap_l26:.3f}s')
    print(f'  RUS-LEC Gap L{last_lap}: +{lec_rus_gap_finish:.3f}s')
    print(f'  差分: {lec_rus_diff:+.3f}s')
    # 記事記載値との比較
    article_l26 = 15.552
    article_finish = 15.519
    if abs(lec_rus_gap_l26 - article_l26) > 0.01:
        errors_found.append(f'LEC-RUS Gap L26: 記事={article_l26}, 実データ={lec_rus_gap_l26:.3f}')
    if abs(lec_rus_gap_finish - article_finish) > 0.01:
        errors_found.append(f'LEC-RUS Gap L{last_lap}: 記事={article_finish}, 実データ={lec_rus_gap_finish:.3f}')

# 記事: ANTはL26で+7.845秒差、最終ラップ(L58)では+2.974秒、4.871秒ANTが速い
if gap_ant and gap_rus:
    ant_rus_gap_l26 = gap_ant.get(26, 0) - gap_rus.get(26, 0)
    ant_last = max(gap_ant.keys(), default=0)
    ant_rus_gap_finish = gap_ant.get(ant_last, 0) - gap_rus.get(ant_last, 0)
    ant_diff = ant_rus_gap_finish - ant_rus_gap_l26
    print(f'\n  RUS-ANT Gap L26: +{ant_rus_gap_l26:.3f}s')
    print(f'  RUS-ANT Gap L{ant_last}: +{ant_rus_gap_finish:.3f}s')
    print(f'  差分: {ant_diff:+.3f}s')
    article_ant_l26 = 7.845
    article_ant_finish = 2.974
    if abs(ant_rus_gap_l26 - article_ant_l26) > 0.01:
        errors_found.append(f'ANT-RUS Gap L26: 記事={article_ant_l26}, 実データ={ant_rus_gap_l26:.3f}')
    if abs(ant_rus_gap_finish - article_ant_finish) > 0.01:
        errors_found.append(f'ANT-RUS Gap Finish: 記事={article_ant_finish}, 実データ={ant_rus_gap_finish:.3f}')

# 記事: HAMが1回目PIT後（L29）LEC差 +6.250→+0.625秒、5.625秒HAMが速い
if gap_ham and gap_lec:
    ham_lec_gap_l29 = gap_ham.get(29, 0) - gap_lec.get(29, 0)
    ham_last = max(gap_ham.keys(), default=0)
    ham_lec_gap_finish = gap_ham.get(ham_last, 0) - gap_lec.get(ham_last, 0)
    ham_diff = ham_lec_gap_finish - ham_lec_gap_l29
    print(f'\n  HAM-LEC Gap L29: +{ham_lec_gap_l29:.3f}s')
    print(f'  HAM-LEC Gap L{ham_last}: +{ham_lec_gap_finish:.3f}s')
    print(f'  差分: {ham_diff:+.3f}s')
    article_ham_l29 = 6.250
    article_ham_finish = 0.625
    if abs(ham_lec_gap_l29 - article_ham_l29) > 0.05:
        errors_found.append(f'HAM-LEC Gap L29: 記事={article_ham_l29}, 実データ={ham_lec_gap_l29:.3f}')
    if abs(ham_lec_gap_finish - article_ham_finish) > 0.05:
        errors_found.append(f'HAM-LEC Gap Finish: 記事={article_ham_finish}, 実データ={ham_lec_gap_finish:.3f}')

# ============================================================
# 2. RUS vs LEC ラップタイム / デルタ / スピードトラップ CSV
# ============================================================
print('\n--- [2] RUS vs LEC ラップタイム / デルタ / スピードトラップ ---')

for pair_name, drv1, drv2 in [('rus_vs_lec', 'RUS', 'LEC'),
                                ('ant_vs_lec', 'ANT', 'LEC')]:
    if drv1 not in all_driver_data or drv2 not in all_driver_data:
        continue

    d1 = all_driver_data[drv1]
    d2 = all_driver_data[drv2]
    c1 = all_clean_data[drv1]
    c2 = all_clean_data[drv2]

    # ラップタイム + デルタ
    merged = pd.merge(
        d1[['LapNum', 'LapTimeSec', 'Compound', 'SpeedST', 'SpeedI1', 'SpeedI2', 'SpeedFL']].rename(
            columns={col: f'{drv1}_{col}' for col in ['LapTimeSec', 'Compound', 'SpeedST', 'SpeedI1', 'SpeedI2', 'SpeedFL']}),
        d2[['LapNum', 'LapTimeSec', 'Compound', 'SpeedST', 'SpeedI1', 'SpeedI2', 'SpeedFL']].rename(
            columns={col: f'{drv2}_{col}' for col in ['LapTimeSec', 'Compound', 'SpeedST', 'SpeedI1', 'SpeedI2', 'SpeedFL']}),
        on='LapNum', how='outer')

    both_clean = set(c1['LapNum']) & set(c2['LapNum'])
    merged['IsCleanBoth'] = merged['LapNum'].isin(both_clean)
    merged[f'Delta_{drv1}_{drv2}_sec'] = merged[f'{drv1}_LapTimeSec'] - merged[f'{drv2}_LapTimeSec']
    merged[f'Delta_ST_{drv1}_{drv2}_kmh'] = merged[f'{drv1}_SpeedST'] - merged[f'{drv2}_SpeedST']
    merged = merged.sort_values('LapNum')

    fname = f'chart2_{pair_name}_laptime_delta.csv'
    merged.to_csv(CSV_DIR / fname, index=False, encoding='utf-8-sig', float_format='%.3f')
    print(f'  出力: {fname} ({len(merged)}行)')

# ============================================================
# 3. スピード分布（箱ひげ図）CSV
# ============================================================
print('\n--- [3] スピード分布（箱ひげ図）---')
SPEED_COLS = ['SpeedI1', 'SpeedI2', 'SpeedFL', 'SpeedST']
SPEED_LABELS = ['S1末端', 'S2末端', 'FL', 'ST']

for pair_name, drv1, drv2, lap_filter in [
    ('rus_vs_lec', 'RUS', 'LEC', None),
    ('rus_vs_lec_L26', 'RUS', 'LEC', 26),
    ('ant_vs_lec', 'ANT', 'LEC', None),
    ('ant_vs_lec_L26', 'ANT', 'LEC', 26),
]:
    if drv1 not in all_clean_data or drv2 not in all_clean_data:
        continue

    rows = []
    for drv in [drv1, drv2]:
        clean = all_clean_data[drv]
        if lap_filter:
            clean = clean[clean['LapNum'] >= lap_filter]
        for scol, slabel in zip(SPEED_COLS, SPEED_LABELS):
            vals = clean[scol].dropna()
            for v in vals:
                rows.append({
                    'Driver': drv,
                    'SpeedPoint': slabel,
                    'SpeedColumn': scol,
                    'Speed_kmh': round(float(v), 1),
                })

    df_speed = pd.DataFrame(rows)
    suffix = '_L26' if lap_filter else ''
    fname = f'chart3_{pair_name.replace("_L26","")}_speed_boxplot{suffix}.csv'
    df_speed.to_csv(CSV_DIR / fname, index=False, encoding='utf-8-sig')
    print(f'  出力: {fname} ({len(df_speed)}行)')

# ============================================================
# 4. セクター比較 CSV
# ============================================================
print('\n--- [4] セクター比較 ---')
SECTOR_COLS = [('S1', 'S1Sec'), ('S2', 'S2Sec'), ('S3', 'S3Sec')]

for pair_name, drv1, drv2 in [('rus_vs_lec', 'RUS', 'LEC'),
                                ('ant_vs_lec', 'ANT', 'LEC')]:
    if drv1 not in all_driver_data or drv2 not in all_driver_data:
        continue

    d1 = all_driver_data[drv1]
    d2 = all_driver_data[drv2]
    c1 = all_clean_data[drv1]
    c2 = all_clean_data[drv2]
    both_clean = set(c1['LapNum']) & set(c2['LapNum'])

    sector_rows = []
    for sec_name, sec_col in SECTOR_COLS:
        merged = pd.merge(
            d1[['LapNum', sec_col]].rename(columns={sec_col: f'{drv1}_{sec_col}'}),
            d2[['LapNum', sec_col]].rename(columns={sec_col: f'{drv2}_{sec_col}'}),
            on='LapNum', how='inner')
        merged['IsCleanBoth'] = merged['LapNum'].isin(both_clean)
        merged[f'Delta_{drv1}_{drv2}'] = merged[f'{drv1}_{sec_col}'] - merged[f'{drv2}_{sec_col}']
        for _, row in merged.iterrows():
            sector_rows.append({
                'LapNumber': int(row['LapNum']),
                'Sector': sec_name,
                f'{drv1}_sec': round(float(row[f'{drv1}_{sec_col}']), 3) if pd.notna(row[f'{drv1}_{sec_col}']) else None,
                f'{drv2}_sec': round(float(row[f'{drv2}_{sec_col}']), 3) if pd.notna(row[f'{drv2}_{sec_col}']) else None,
                f'Delta_{drv1}_{drv2}_sec': round(float(row[f'Delta_{drv1}_{drv2}']), 3) if pd.notna(row[f'Delta_{drv1}_{drv2}']) else None,
                'IsCleanBoth': bool(row['IsCleanBoth']),
            })

    df_sector = pd.DataFrame(sector_rows)
    fname = f'chart4_{pair_name}_sector_compare.csv'
    df_sector.to_csv(CSV_DIR / fname, index=False, encoding='utf-8-sig')
    print(f'  出力: {fname} ({len(df_sector)}行)')

# ============================================================
# 5. セクター別サマリーテーブル CSV（記事のテーブルと照合）
# ============================================================
print('\n--- [5] セクター別サマリーテーブル ---')

for pair_name, drv1, drv2 in [('rus_vs_lec', 'RUS', 'LEC'),
                                ('ant_vs_lec', 'ANT', 'LEC')]:
    if drv1 not in all_clean_data or drv2 not in all_clean_data:
        continue

    c1 = all_clean_data[drv1]
    c2 = all_clean_data[drv2]
    # L26以降のクリーンラップ（HARDタイヤ区間）
    c1_l26 = c1[c1['LapNum'] >= 26]
    c2_l26 = c2[c2['LapNum'] >= 26]
    both_clean_l26 = set(c1_l26['LapNum']) & set(c2_l26['LapNum'])

    table_rows = []
    for sec_name, sec_col in SECTOR_COLS:
        # 両者クリーンなラップのみ
        d1_vals = c1_l26[c1_l26['LapNum'].isin(both_clean_l26)][sec_col].dropna()
        d2_vals = c2_l26[c2_l26['LapNum'].isin(both_clean_l26)][sec_col].dropna()

        avg1 = d1_vals.mean()
        avg2 = d2_vals.mean()
        diff = avg1 - avg2

        # ラップ勝敗カウント
        merged = pd.merge(
            all_driver_data[drv1][['LapNum', sec_col]].rename(columns={sec_col: 'd1'}),
            all_driver_data[drv2][['LapNum', sec_col]].rename(columns={sec_col: 'd2'}),
            on='LapNum', how='inner')
        merged = merged[merged['LapNum'].isin(both_clean_l26)]
        merged['delta'] = merged['d1'] - merged['d2']
        wins_d1 = int((merged['delta'] < 0).sum())
        wins_d2 = int((merged['delta'] > 0).sum())

        table_rows.append({
            'Sector': sec_name,
            f'{drv1}_avg_sec': round(avg1, 3),
            f'{drv2}_avg_sec': round(avg2, 3),
            f'Diff_sec': round(diff, 3),
            f'Faster': f'{drv1}' if diff < 0 else f'{drv2}',
            f'{drv1}_wins': wins_d1,
            f'{drv2}_wins': wins_d2,
            'CleanLaps': len(both_clean_l26),
        })

    df_table = pd.DataFrame(table_rows)
    fname = f'chart5_{pair_name}_sector_summary_L26.csv'
    df_table.to_csv(CSV_DIR / fname, index=False, encoding='utf-8-sig')
    print(f'  出力: {fname}')
    print(df_table.to_string(index=False))

    # 記事テーブルとの照合（RUS vs LECのみ）
    if pair_name == 'rus_vs_lec':
        # 記事: S1 RUS=29.182, LEC=29.244, 差=-0.061 (RUS), 勝ち23:7
        # 記事: S2 RUS=17.655, LEC=17.710, 差=-0.055 (RUS), 勝ち23:7
        # 記事: S3 RUS=36.264, LEC=36.099, 差=+0.166 (LEC), 勝ち8:22
        article_values = {
            'S1': {'d1_avg': 29.182, 'd2_avg': 29.244, 'diff': -0.061, 'd1_wins': 23, 'd2_wins': 7},
            'S2': {'d1_avg': 17.655, 'd2_avg': 17.710, 'diff': -0.055, 'd1_wins': 23, 'd2_wins': 7},
            'S3': {'d1_avg': 36.264, 'd2_avg': 36.099, 'diff': 0.166, 'd1_wins': 8, 'd2_wins': 22},
        }
        print(f'\n  === 記事テーブルとの照合 (RUS vs LEC) ===')
        for _, trow in df_table.iterrows():
            sec = trow['Sector']
            art = article_values.get(sec, {})
            if not art:
                continue
            actual_d1 = trow[f'{drv1}_avg_sec']
            actual_d2 = trow[f'{drv2}_avg_sec']
            actual_diff = trow['Diff_sec']
            actual_w1 = trow[f'{drv1}_wins']
            actual_w2 = trow[f'{drv2}_wins']

            ok_avg1 = abs(actual_d1 - art['d1_avg']) < 0.002
            ok_avg2 = abs(actual_d2 - art['d2_avg']) < 0.002
            ok_diff = abs(actual_diff - art['diff']) < 0.002
            ok_w1 = actual_w1 == art['d1_wins']
            ok_w2 = actual_w2 == art['d2_wins']

            status = 'OK' if (ok_avg1 and ok_avg2 and ok_diff and ok_w1 and ok_w2) else 'MISMATCH'
            print(f'  {sec}: {status}')
            if not ok_avg1:
                errors_found.append(f'{sec} {drv1}平均: 記事={art["d1_avg"]}, 実={actual_d1}')
                print(f'    {drv1}平均: 記事={art["d1_avg"]}, 実={actual_d1}')
            if not ok_avg2:
                errors_found.append(f'{sec} {drv2}平均: 記事={art["d2_avg"]}, 実={actual_d2}')
                print(f'    {drv2}平均: 記事={art["d2_avg"]}, 実={actual_d2}')
            if not ok_diff:
                errors_found.append(f'{sec} 差: 記事={art["diff"]}, 実={actual_diff}')
                print(f'    差: 記事={art["diff"]}, 実={actual_diff}')
            if not ok_w1:
                errors_found.append(f'{sec} {drv1}勝ち: 記事={art["d1_wins"]}, 実={actual_w1}')
                print(f'    {drv1}勝ち: 記事={art["d1_wins"]}, 実={actual_w1}')
            if not ok_w2:
                errors_found.append(f'{sec} {drv2}勝ち: 記事={art["d2_wins"]}, 実={actual_w2}')
                print(f'    {drv2}勝ち: 記事={art["d2_wins"]}, 実={actual_w2}')

    # ANT vs LEC テーブル照合
    if pair_name == 'ant_vs_lec':
        # 記事: S1 ANT=29.202, LEC=29.244, 差=-0.042 (ANT), 勝ち17:13
        # 記事: S2 ANT=17.747, LEC=17.710, 差=+0.037 (LEC), 勝ち8:22
        # 記事: S3 ANT=35.955, LEC=36.099, 差=-0.144 (ANT), 勝ち24:6
        article_values_ant = {
            'S1': {'d1_avg': 29.202, 'd2_avg': 29.244, 'diff': -0.042, 'd1_wins': 17, 'd2_wins': 13},
            'S2': {'d1_avg': 17.747, 'd2_avg': 17.710, 'diff': 0.037, 'd1_wins': 8, 'd2_wins': 22},
            'S3': {'d1_avg': 35.955, 'd2_avg': 36.099, 'diff': -0.144, 'd1_wins': 24, 'd2_wins': 6},
        }
        print(f'\n  === 記事テーブルとの照合 (ANT vs LEC) ===')
        for _, trow in df_table.iterrows():
            sec = trow['Sector']
            art = article_values_ant.get(sec, {})
            if not art:
                continue
            actual_d1 = trow[f'{drv1}_avg_sec']
            actual_d2 = trow[f'{drv2}_avg_sec']
            actual_diff = trow['Diff_sec']
            actual_w1 = trow[f'{drv1}_wins']
            actual_w2 = trow[f'{drv2}_wins']

            ok_avg1 = abs(actual_d1 - art['d1_avg']) < 0.002
            ok_avg2 = abs(actual_d2 - art['d2_avg']) < 0.002
            ok_diff = abs(actual_diff - art['diff']) < 0.002
            ok_w1 = actual_w1 == art['d1_wins']
            ok_w2 = actual_w2 == art['d2_wins']

            status = 'OK' if (ok_avg1 and ok_avg2 and ok_diff and ok_w1 and ok_w2) else 'MISMATCH'
            print(f'  {sec}: {status}')
            if not ok_avg1:
                errors_found.append(f'ANT-LEC {sec} {drv1}平均: 記事={art["d1_avg"]}, 実={actual_d1}')
                print(f'    {drv1}平均: 記事={art["d1_avg"]}, 実={actual_d1}')
            if not ok_avg2:
                errors_found.append(f'ANT-LEC {sec} {drv2}平均: 記事={art["d2_avg"]}, 実={actual_d2}')
                print(f'    {drv2}平均: 記事={art["d2_avg"]}, 実={actual_d2}')
            if not ok_diff:
                errors_found.append(f'ANT-LEC {sec} 差: 記事={art["diff"]}, 実={actual_diff}')
                print(f'    差: 記事={art["diff"]}, 実={actual_diff}')
            if not ok_w1:
                errors_found.append(f'ANT-LEC {sec} {drv1}勝ち: 記事={art["d1_wins"]}, 実={actual_w1}')
                print(f'    {drv1}勝ち: 記事={art["d1_wins"]}, 実={actual_w1}')
            if not ok_w2:
                errors_found.append(f'ANT-LEC {sec} {drv2}勝ち: 記事={art["d2_wins"]}, 実={actual_w2}')
                print(f'    {drv2}勝ち: 記事={art["d2_wins"]}, 実={actual_w2}')

# ============================================================
# 6. ピットストップ情報 CSV
# ============================================================
print('\n--- [6] ピットストップ情報 ---')
pit_rows = []
for drv in driver_order:
    for pl in all_pit_laps.get(drv, []):
        pit_rows.append({
            'Driver': drv,
            'Team': drv_team.get(drv, ''),
            'PitInLap': pl,
        })
df_pits = pd.DataFrame(pit_rows)
df_pits.to_csv(CSV_DIR / 'pitstops.csv', index=False, encoding='utf-8-sig')
print(f'  出力: pitstops.csv ({len(df_pits)}行)')

# ============================================================
# 7. VSC情報 CSV
# ============================================================
print('\n--- [7] VSC情報 ---')
vsc_rows = [{'VSC_Start': s, 'VSC_End': e} for s, e in vsc_periods]
df_vsc = pd.DataFrame(vsc_rows)
df_vsc.to_csv(CSV_DIR / 'vsc_periods.csv', index=False, encoding='utf-8-sig')
print(f'  出力: vsc_periods.csv ({len(df_vsc)}行)')

# ============================================================
# サマリー
# ============================================================
print('\n' + '=' * 60)
if errors_found:
    print(f'!!! {len(errors_found)}件の不一致を検出 !!!')
    for e in errors_found:
        print(f'  - {e}')
else:
    print('全データ正確性チェック: OK (不一致なし)')
print('=' * 60)

# CSV一覧
print(f'\n出力先: {CSV_DIR}')
for f in sorted(CSV_DIR.glob('*.csv')):
    print(f'  {f.name} ({f.stat().st_size / 1024:.1f} KB)')

print('\n完了!')
