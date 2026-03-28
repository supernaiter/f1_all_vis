"""
============================================================
H2H analysis.jsonに予選データを追加するスクリプト
============================================================
FastF1から予選セッションを読み込み、各H2Hペアのanalysis.jsonに
"qualifying"セクションを追加する。

使い方:
  python add_qualifying_to_h2h.py 2026 Australia 1
  python add_qualifying_to_h2h.py 2026 China 2
"""

import sys
import json
import fastf1
import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# キャッシュ有効化
fastf1.Cache.enable_cache('~/f1_cache')


def load_qualifying(year: int, gp_name: str) -> pd.DataFrame:
    """FastF1から予選データを読み込む"""
    session = fastf1.get_session(year, gp_name, 'Q')
    session.load(telemetry=False, laps=True, weather=False)

    laps = session.laps
    if laps.empty:
        print("予選ラップデータが空です")
        sys.exit(1)

    # LapTimeを秒に変換
    df = laps.copy()
    for col in ['LapTime', 'Sector1Time', 'Sector2Time', 'Sector3Time']:
        if col in df.columns:
            df[f'{col}_sec'] = df[col].dt.total_seconds()

    # ドライバー略称とチーム名のマッピング
    drv_team = {}
    for _, row in session.results.iterrows():
        drv_team[row['Abbreviation']] = row['TeamName']

    return df, drv_team, session.results


def get_best_lap_per_driver(laps_df: pd.DataFrame) -> dict:
    """各ドライバーの予選ベストラップ情報を取得"""
    best = {}
    for drv in laps_df['Driver'].unique():
        drv_laps = laps_df[laps_df['Driver'] == drv].copy()
        drv_laps = drv_laps.dropna(subset=['LapTime_sec'])

        if drv_laps.empty:
            continue

        # ベストラップ
        idx = drv_laps['LapTime_sec'].idxmin()
        row = drv_laps.loc[idx]

        best[drv] = {
            'best_time': round(row['LapTime_sec'], 3),
            'sector1': round(row['Sector1Time_sec'], 3) if pd.notna(row.get('Sector1Time_sec')) else None,
            'sector2': round(row['Sector2Time_sec'], 3) if pd.notna(row.get('Sector2Time_sec')) else None,
            'sector3': round(row['Sector3Time_sec'], 3) if pd.notna(row.get('Sector3Time_sec')) else None,
            'compound': row.get('Compound', None),
        }

        # Q1/Q2/Q3別ベスト
        for q_num in [1, 2, 3]:
            q_laps = drv_laps[drv_laps['IsAccurate'] == True] if 'IsAccurate' in drv_laps.columns else drv_laps
            # FastF1ではQ1/Q2/Q3の区別がないため、ラップタイムの分布で推定しない
            # → 代わりにsession.resultsのQ1/Q2/Q3タイムを使用

    return best


def get_q_times_from_results(results) -> dict:
    """session.resultsからQ1/Q2/Q3タイムを取得"""
    q_data = {}
    for _, row in results.iterrows():
        drv = row['Abbreviation']
        entry = {}

        for q in ['Q1', 'Q2', 'Q3']:
            val = row.get(q, pd.NaT)
            if pd.notna(val):
                # Timedeltaの場合
                if hasattr(val, 'total_seconds'):
                    entry[q] = round(val.total_seconds(), 3)
                else:
                    entry[q] = None
            else:
                entry[q] = None

        entry['position'] = int(row['Position']) if pd.notna(row.get('Position')) else None
        q_data[drv] = entry

    return q_data


def build_qualifying_section(drv1: str, drv2: str, best_laps: dict, q_results: dict) -> dict:
    """H2Hペア用の予選比較データを構築"""
    b1 = best_laps.get(drv1)
    b2 = best_laps.get(drv2)
    q1 = q_results.get(drv1, {})
    q2 = q_results.get(drv2, {})

    section = {
        drv1: {},
        drv2: {},
    }

    # ベストラップ
    for drv, b, q in [(drv1, b1, q1), (drv2, b2, q2)]:
        if b is None:
            section[drv] = {
                'best_time': None, 'sector1': None, 'sector2': None, 'sector3': None,
                'compound': None, 'position': q.get('position'),
                'Q1': q.get('Q1'), 'Q2': q.get('Q2'), 'Q3': q.get('Q3'),
            }
        else:
            section[drv] = {
                'best_time': b['best_time'],
                'sector1': b['sector1'],
                'sector2': b['sector2'],
                'sector3': b['sector3'],
                'compound': b['compound'],
                'position': q.get('position'),
                'Q1': q.get('Q1'),
                'Q2': q.get('Q2'),
                'Q3': q.get('Q3'),
            }

    # デルタ計算
    t1 = section[drv1].get('best_time')
    t2 = section[drv2].get('best_time')
    if t1 is not None and t2 is not None:
        delta = round(t1 - t2, 3)
        section['delta_sec'] = delta
        section['faster'] = drv1 if delta < 0 else drv2

        # セクター別デルタ
        for sec in ['sector1', 'sector2', 'sector3']:
            s1 = section[drv1].get(sec)
            s2 = section[drv2].get(sec)
            if s1 is not None and s2 is not None:
                section[f'delta_{sec}'] = round(s1 - s2, 3)
            else:
                section[f'delta_{sec}'] = None
    else:
        section['delta_sec'] = None
        section['faster'] = None
        section['delta_sector1'] = None
        section['delta_sector2'] = None
        section['delta_sector3'] = None

    return section


def main():
    if len(sys.argv) < 4:
        print("使い方: python add_qualifying_to_h2h.py <年> <GP名> <ラウンド番号>")
        print("例: python add_qualifying_to_h2h.py 2026 Australia 1")
        sys.exit(1)

    year = int(sys.argv[1])
    gp_name = sys.argv[2]
    round_number = int(sys.argv[3])

    h2h_dir = Path(f'./data/{year}_R{round_number:02d}_{gp_name}/h2h')
    if not h2h_dir.exists():
        print(f"H2Hディレクトリが見つかりません: {h2h_dir}")
        sys.exit(1)

    print(f"=== {year} R{round_number:02d} {gp_name} GP 予選データ取得 ===")

    # FastF1から予選データ読み込み
    print("FastF1から予選セッションを読み込み中...")
    laps_df, drv_team, results = load_qualifying(year, gp_name)
    print(f"  ドライバー数: {laps_df['Driver'].nunique()}")
    print(f"  総ラップ数: {len(laps_df)}")

    # ベストラップ抽出
    best_laps = get_best_lap_per_driver(laps_df)
    q_results = get_q_times_from_results(results)

    print(f"\n予選結果:")
    for drv in sorted(q_results.keys(), key=lambda d: q_results[d].get('position') or 99):
        q = q_results[drv]
        b = best_laps.get(drv, {})
        t = b.get('best_time', '-')
        print(f"  P{q.get('position', '?'):>2} {drv:>3}  {t}")

    # 各H2Hペアのanalysis.jsonを更新
    updated = 0
    for pair_dir in sorted(h2h_dir.iterdir()):
        if not pair_dir.is_dir():
            continue

        analysis_path = pair_dir / 'analysis.json'
        if not analysis_path.exists():
            continue

        # ペア名からドライバー略称を取得 (例: RUS_vs_ANT)
        parts = pair_dir.name.split('_vs_')
        if len(parts) != 2:
            continue

        drv1, drv2 = parts[0], parts[1]

        # 予選セクション構築
        qual_section = build_qualifying_section(drv1, drv2, best_laps, q_results)

        # analysis.json更新
        with open(analysis_path, 'r', encoding='utf-8') as f:
            analysis = json.load(f)

        analysis['qualifying'] = qual_section

        with open(analysis_path, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2)

        updated += 1

    print(f"\n{updated}ペアのanalysis.jsonに予選データを追加しました")


if __name__ == '__main__':
    main()
