"""
============================================================
2026 R2 中国GP — 統合データベース＋エクスポート作成
============================================================
スプリントウィーク全5セッション（FP1/SQ/Sprint/Q/Race）を
SQLiteデータベースに統合し、CSV/Parquetでもエクスポートする。

使い方:
  source /home/redpark92/f1env/bin/activate
  PYTHONIOENCODING=utf-8 python3 build_gp_db_2026_r02.py
"""

import fastf1
import pandas as pd
import numpy as np
import sqlite3
import json
import sys
from pathlib import Path
from datetime import datetime

# ============================================================
# 設定
# ============================================================
YEAR = 2026
GP_NAME = 'China'
ROUND_NUMBER = 2

DATA_DIR = Path(f'./data/{YEAR}_R{ROUND_NUMBER:02d}_{GP_NAME}')
EXPORT_DIR = DATA_DIR / 'export'
DB_PATH = DATA_DIR / 'gp_weekend.db'

DATA_DIR.mkdir(parents=True, exist_ok=True)
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

fastf1.Cache.enable_cache('~/f1_cache')

# セッション定義（スプリントウィーク: FP1のみ + SQ/Sprint/Q/Race）
SESSIONS = {
    'FP1': 'FP1',
    'SQ':  'SQ',
    'Sprint': 'S',
    'Qualifying': 'Q',
    'Race': 'R',
}

# Timedelta→秒変換するカラム
TIMEDELTA_COLS = [
    'LapTime', 'Sector1Time', 'Sector2Time', 'Sector3Time',
    'PitOutTime', 'PitInTime', 'Time', 'LapStartTime',
    'Sector1SessionTime', 'Sector2SessionTime', 'Sector3SessionTime',
]

# lapsテーブル用カラム（R01互換）
LAPS_COLUMNS = [
    'Session', 'Driver', 'DriverNumber', 'Team',
    'LapNumber', 'Stint', 'Compound', 'TyreLife', 'FreshTyre',
    'LapTime_sec', 'Sector1Time_sec', 'Sector2Time_sec', 'Sector3Time_sec',
    'PitOutTime_sec', 'PitInTime_sec',
    'SpeedI1', 'SpeedI2', 'SpeedFL', 'SpeedST',
    'IsPersonalBest', 'Position', 'TrackStatus', 'IsAccurate',
]


# ============================================================
# Step 1: FastF1から全セッションデータ読み込み
# ============================================================
print('=' * 60)
print(f'{YEAR} R{ROUND_NUMBER:02d} {GP_NAME} GP - データベース作成')
print('=' * 60)

session_data = {}  # {session_label: session_object}
all_laps = []      # 統合ラップデータ
all_weather = []   # 統合気象データ
all_results = []   # Sprint + Race結果
all_rcm = []       # Sprint + Raceレースコントロールメッセージ

for label, ff1_id in SESSIONS.items():
    print(f'\n--- {label} ({ff1_id}) 読み込み中... ---')
    try:
        session = fastf1.get_session(YEAR, GP_NAME, ff1_id)
        # テレメトリは不要（DB容量削減）
        session.load(telemetry=False, laps=True, weather=True)
        session_data[label] = session
        print(f'  ラップ数: {len(session.laps)}')

        # --- ラップデータ処理 ---
        laps = session.laps.copy()
        if len(laps) == 0:
            print(f'  警告: {label} のラップデータが空です')
            continue

        # Timedelta → 秒変換
        for col in TIMEDELTA_COLS:
            if col in laps.columns:
                laps[f'{col}_sec'] = laps[col].dt.total_seconds()

        # セッションラベル追加
        laps['Session'] = label

        # 必要カラムのみ抽出（存在しないカラムはNaN）
        for col in LAPS_COLUMNS:
            if col not in laps.columns:
                laps[col] = np.nan
        all_laps.append(laps[LAPS_COLUMNS].copy())

        # --- 気象データ処理 ---
        weather = session.weather_data
        if weather is not None and len(weather) > 0:
            weather = weather.copy()
            # Time列を秒に変換（Timedeltaの場合）
            if 'Time' in weather.columns and hasattr(weather['Time'], 'dt'):
                weather['Time'] = weather['Time'].dt.total_seconds()
            weather['Session'] = label
            all_weather.append(weather)
            print(f'  気象データ: {len(weather)} 件')

        # --- Sprint/Race固有: 結果＋レースコントロール ---
        if ff1_id in ('S', 'R'):
            # 結果
            results = session.results.copy()
            if len(results) > 0:
                # Timedelta列を変換
                for col in results.columns:
                    if hasattr(results[col], 'dt') and results[col].dtype.kind == 'm':
                        results[f'{col}_sec'] = results[col].dt.total_seconds()
                results['Session'] = label
                all_results.append(results)
                print(f'  結果: {len(results)} 件')

            # レースコントロールメッセージ
            try:
                rcm = session.race_control_messages.copy()
                if len(rcm) > 0:
                    rcm['Session'] = label
                    all_rcm.append(rcm)
                    print(f'  レースコントロール: {len(rcm)} 件')
            except Exception as e:
                print(f'  警告: レースコントロールメッセージ取得失敗: {e}')

    except Exception as e:
        print(f'  エラー: {label} の読み込みに失敗しました: {e}')
        print(f'  他のセッションの処理を続行します')

# ============================================================
# データ統合
# ============================================================
print('\n--- データ統合中... ---')

if len(all_laps) == 0:
    print('エラー: ラップデータが1セッションも取得できませんでした')
    sys.exit(1)

df_laps = pd.concat(all_laps, ignore_index=True)
print(f'統合ラップ数: {len(df_laps)}')

df_weather = pd.concat(all_weather, ignore_index=True) if all_weather else pd.DataFrame()
print(f'統合気象データ: {len(df_weather)}')

df_results = pd.concat(all_results, ignore_index=True) if all_results else pd.DataFrame()
print(f'統合結果データ: {len(df_results)}')

df_rcm = pd.concat(all_rcm, ignore_index=True) if all_rcm else pd.DataFrame()
print(f'統合レースコントロール: {len(df_rcm)}')

# セッション別ラップ数確認
print('\nセッション別ラップ数:')
for session, count in df_laps.groupby('Session').size().items():
    print(f'  {session}: {count}')


# ============================================================
# Step 2: SQLiteデータベース作成
# ============================================================
print(f'\n--- SQLiteデータベース作成: {DB_PATH} ---')

# 既存DBがあれば削除して再作成
if DB_PATH.exists():
    DB_PATH.unlink()
    print('  既存DBを削除しました')

conn = sqlite3.connect(str(DB_PATH))

# --- lapsテーブル ---
df_laps.to_sql('laps', conn, index=False, if_exists='replace')
print(f'  laps: {len(df_laps)} rows')

# --- weatherテーブル ---
if len(df_weather) > 0:
    df_weather.to_sql('weather', conn, index=False, if_exists='replace')
    print(f'  weather: {len(df_weather)} rows')

# --- resultsテーブル ---
if len(df_results) > 0:
    # エクスポート用カラムを選択
    results_cols = [
        'Session', 'DriverNumber', 'Abbreviation', 'FirstName', 'LastName',
        'FullName', 'TeamName', 'TeamColor',
        'Position', 'ClassifiedPosition', 'GridPosition',
        'Status', 'Points',
    ]
    # Laps列がある場合は追加
    if 'Laps' in df_results.columns:
        results_cols.append('Laps')
    # 存在するカラムのみ
    results_cols = [c for c in results_cols if c in df_results.columns]
    df_results_db = df_results[results_cols].copy()
    df_results_db.to_sql('results', conn, index=False, if_exists='replace')
    print(f'  results: {len(df_results_db)} rows')

# --- race_control_messagesテーブル ---
if len(df_rcm) > 0:
    rcm_cols = ['Session', 'Lap', 'Category', 'Message', 'Flag', 'Scope', 'Sector', 'RacingNumber']
    rcm_cols = [c for c in rcm_cols if c in df_rcm.columns]
    df_rcm_db = df_rcm[rcm_cols].copy()
    # Lap列のNaN処理
    if 'Lap' in df_rcm_db.columns:
        df_rcm_db['Lap'] = df_rcm_db['Lap'].apply(
            lambda x: int(x) if pd.notna(x) and x != '' else None
        )
    df_rcm_db.to_sql('race_control_messages', conn, index=False, if_exists='replace')
    print(f'  race_control_messages: {len(df_rcm_db)} rows')

# --- ビュー作成 ---
print('\n  ビュー作成中...')

# session_summary: セッション別ドライバー統計
conn.execute("""
CREATE VIEW IF NOT EXISTS session_summary AS
SELECT
    Session,
    Driver,
    Team,
    COUNT(*) AS TotalLaps,
    MIN(LapTime_sec) AS BestLap,
    AVG(LapTime_sec) AS MeanLap,
    GROUP_CONCAT(DISTINCT Compound) AS Compounds
FROM laps
WHERE LapTime_sec IS NOT NULL
GROUP BY Session, Driver, Team
ORDER BY Session, BestLap
""")
print('  session_summary ビュー作成完了')

# driver_best_laps: セッション×ドライバー別ベストラップ
conn.execute("""
CREATE VIEW IF NOT EXISTS driver_best_laps AS
SELECT
    Session,
    Driver,
    DriverNumber,
    Team,
    MIN(LapTime_sec) AS BestLapTime,
    MIN(Sector1Time_sec) AS BestS1,
    MIN(Sector2Time_sec) AS BestS2,
    MIN(Sector3Time_sec) AS BestS3
FROM laps
WHERE LapTime_sec IS NOT NULL
  AND IsAccurate = 1
GROUP BY Session, Driver, DriverNumber, Team
ORDER BY Session, BestLapTime
""")
print('  driver_best_laps ビュー作成完了')

# long_runs: 同一コンパウンド・同一スティント5周以上
conn.execute("""
CREATE VIEW IF NOT EXISTS long_runs AS
SELECT
    Session,
    Driver,
    Team,
    Stint,
    Compound,
    COUNT(*) AS StintLaps,
    MIN(LapTime_sec) AS FastestLap,
    AVG(LapTime_sec) AS AvgLap,
    MIN(TyreLife) AS TyreLifeStart,
    MAX(TyreLife) AS TyreLifeEnd
FROM laps
WHERE LapTime_sec IS NOT NULL
  AND PitOutTime_sec IS NULL
  AND PitInTime_sec IS NULL
GROUP BY Session, Driver, Team, Stint, Compound
HAVING COUNT(*) >= 5
ORDER BY Session, Driver, Stint
""")
print('  long_runs ビュー作成完了')

conn.commit()

# DB検証
print('\n  --- DB検証 ---')
cursor = conn.execute("SELECT Session, COUNT(*) FROM laps GROUP BY Session")
for row in cursor:
    print(f'    laps [{row[0]}]: {row[1]} rows')

cursor = conn.execute("SELECT COUNT(*) FROM session_summary")
print(f'    session_summary: {cursor.fetchone()[0]} rows')

cursor = conn.execute("SELECT COUNT(*) FROM driver_best_laps")
print(f'    driver_best_laps: {cursor.fetchone()[0]} rows')

cursor = conn.execute("SELECT COUNT(*) FROM long_runs")
print(f'    long_runs: {cursor.fetchone()[0]} rows')

conn.close()
print(f'  DB保存完了: {DB_PATH} ({DB_PATH.stat().st_size / 1024:.1f} KB)')


# ============================================================
# Step 3: CSV/Parquetエクスポート
# ============================================================
print(f'\n--- CSV/Parquetエクスポート: {EXPORT_DIR} ---')

datasets = {}  # {filename: {'df': DataFrame, 'source': str, ...}}

# --- Race Laps ---
race_laps = df_laps[df_laps['Session'] == 'Race'].copy()
if len(race_laps) > 0:
    race_laps_export = race_laps[[
        'Driver', 'DriverNumber', 'LapNumber', 'LapTime_sec',
        'Sector1Time_sec', 'Sector2Time_sec', 'Sector3Time_sec',
        'SpeedI1', 'SpeedI2', 'SpeedFL', 'SpeedST',
        'Stint', 'Compound', 'TyreLife', 'FreshTyre',
        'PitOutTime_sec', 'PitInTime_sec',
        'Position', 'TrackStatus', 'IsPersonalBest', 'IsAccurate',
        'Team',
    ]].copy()
    datasets['race_laps.csv'] = {
        'df': race_laps_export,
        'source': 'FastF1 v3.8.1 (fastf1.get_session -> session.laps)',
        'api': 'FastF1 (https://docs.fastf1.dev/)',
        'desc': '決勝全ドライバー全ラップデータ。ラップタイム、セクタータイム、スピード計測、タイヤ情報、ポジション等。',
        'rows': len(race_laps_export),
    }

    # Parquet版（フルデータ、元session.lapsから取得し直し）
    if 'Race' in session_data:
        race_laps_full = session_data['Race'].laps.copy()
        datasets['race_laps.parquet'] = {
            'df': race_laps_full,
            'source': 'FastF1 v3.8.1 (session.laps)',
            'api': 'FastF1',
            'desc': 'race_laps.csvの完全版（Timedelta型保持、全カラム）',
            'rows': len(race_laps_full),
            'parquet': True,
        }

# --- Race Results ---
race_results = df_results[df_results['Session'] == 'Race'].copy() if len(df_results) > 0 else pd.DataFrame()
if len(race_results) > 0:
    results_export_cols = [
        'DriverNumber', 'Abbreviation', 'FirstName', 'LastName', 'FullName',
        'TeamName', 'TeamColor',
        'Position', 'ClassifiedPosition', 'GridPosition',
        'Status', 'Points',
    ]
    if 'Laps' in race_results.columns:
        results_export_cols.append('Laps')
    results_export_cols = [c for c in results_export_cols if c in race_results.columns]
    race_results_export = race_results[results_export_cols].copy()
    datasets['race_results.csv'] = {
        'df': race_results_export,
        'source': 'FastF1 v3.8.1 (session.results)',
        'api': 'FastF1',
        'desc': '決勝結果。全ドライバーの順位、グリッド、ステータス、ポイント。',
        'rows': len(race_results_export),
    }

# --- Race Control Messages ---
race_rcm = df_rcm[df_rcm['Session'] == 'Race'].copy() if len(df_rcm) > 0 else pd.DataFrame()
if len(race_rcm) > 0:
    rcm_export_cols = ['Lap', 'Category', 'Message', 'Flag', 'Scope', 'Sector', 'RacingNumber']
    rcm_export_cols = [c for c in rcm_export_cols if c in race_rcm.columns]
    rcm_export = race_rcm[rcm_export_cols].copy()
    if 'Lap' in rcm_export.columns:
        rcm_export['Lap'] = rcm_export['Lap'].apply(
            lambda x: int(x) if pd.notna(x) and x != '' else ''
        )
    datasets['race_control_messages.csv'] = {
        'df': rcm_export,
        'source': 'FastF1 v3.8.1 (session.race_control_messages)',
        'api': 'FastF1',
        'desc': 'レースコントロールメッセージ（VSC/SC/旗等）。',
        'rows': len(rcm_export),
    }

# --- Race Weather ---
race_weather = df_weather[df_weather['Session'] == 'Race'].copy() if len(df_weather) > 0 else pd.DataFrame()
if len(race_weather) > 0:
    datasets['race_weather.csv'] = {
        'df': race_weather.drop(columns=['Session'], errors='ignore'),
        'source': 'FastF1 v3.8.1 (session.weather_data)',
        'api': 'FastF1',
        'desc': '決勝中の気象データ。気温、路面温度、湿度、風向風速、降雨。',
        'rows': len(race_weather),
    }

# --- FP Laps (FP1のみ、スプリントウィーク) ---
fp_laps = df_laps[df_laps['Session'] == 'FP1'].copy()
if len(fp_laps) > 0:
    fp_export_cols = [
        'Session', 'Driver', 'Team', 'LapNumber', 'Stint', 'Compound', 'TyreLife',
        'LapTime_sec', 'Sector1Time_sec', 'Sector2Time_sec', 'Sector3Time_sec',
        'PitOutTime_sec', 'PitInTime_sec',
        'SpeedI1', 'SpeedI2', 'SpeedFL', 'SpeedST',
        'IsPersonalBest', 'Position', 'IsAccurate',
    ]
    fp_export_cols = [c for c in fp_export_cols if c in fp_laps.columns]
    datasets['fp_laps.csv'] = {
        'df': fp_laps[fp_export_cols].copy(),
        'source': 'FastF1 v3.8.1 (session.laps)',
        'api': 'FastF1',
        'desc': 'FP1の全ラップデータ（スプリントウィークのためFP1のみ）。',
        'rows': len(fp_laps),
    }

# --- FP Weather ---
fp_weather = df_weather[df_weather['Session'] == 'FP1'].copy() if len(df_weather) > 0 else pd.DataFrame()
if len(fp_weather) > 0:
    datasets['fp_weather.csv'] = {
        'df': fp_weather,
        'source': 'FastF1 v3.8.1 (session.weather_data)',
        'api': 'FastF1',
        'desc': 'FP1の気象データ。',
        'rows': len(fp_weather),
    }

# --- FP Session Summary ---
conn = sqlite3.connect(str(DB_PATH))
fp_summary = pd.read_sql(
    "SELECT * FROM session_summary WHERE Session = 'FP1'", conn
)
conn.close()
if len(fp_summary) > 0:
    datasets['fp_session_summary.csv'] = {
        'df': fp_summary,
        'source': f'gp_weekend.db (session_summaryビュー)',
        'api': 'FastF1',
        'desc': 'FP1のセッション別ドライバーサマリー（ベストラップ、平均、使用コンパウンド）。',
        'rows': len(fp_summary),
    }

# --- Sprint Laps ---
sprint_laps = df_laps[df_laps['Session'] == 'Sprint'].copy()
if len(sprint_laps) > 0:
    sprint_laps_export = sprint_laps[[
        'Driver', 'DriverNumber', 'LapNumber', 'LapTime_sec',
        'Sector1Time_sec', 'Sector2Time_sec', 'Sector3Time_sec',
        'SpeedI1', 'SpeedI2', 'SpeedFL', 'SpeedST',
        'Stint', 'Compound', 'TyreLife', 'FreshTyre',
        'PitOutTime_sec', 'PitInTime_sec',
        'Position', 'TrackStatus', 'IsPersonalBest', 'IsAccurate',
        'Team',
    ]].copy()
    datasets['sprint_laps.csv'] = {
        'df': sprint_laps_export,
        'source': 'FastF1 v3.8.1 (session.laps)',
        'api': 'FastF1',
        'desc': 'スプリント全ドライバー全ラップデータ。',
        'rows': len(sprint_laps_export),
    }

# --- Sprint Results ---
sprint_results = df_results[df_results['Session'] == 'Sprint'].copy() if len(df_results) > 0 else pd.DataFrame()
if len(sprint_results) > 0:
    sr_export_cols = [
        'DriverNumber', 'Abbreviation', 'FirstName', 'LastName', 'FullName',
        'TeamName', 'TeamColor',
        'Position', 'ClassifiedPosition', 'GridPosition',
        'Status', 'Points',
    ]
    if 'Laps' in sprint_results.columns:
        sr_export_cols.append('Laps')
    sr_export_cols = [c for c in sr_export_cols if c in sprint_results.columns]
    datasets['sprint_results.csv'] = {
        'df': sprint_results[sr_export_cols].copy(),
        'source': 'FastF1 v3.8.1 (session.results)',
        'api': 'FastF1',
        'desc': 'スプリント結果。全ドライバーの順位、グリッド、ステータス、ポイント。',
        'rows': len(sprint_results),
    }

# --- SQ Laps ---
sq_laps = df_laps[df_laps['Session'] == 'SQ'].copy()
if len(sq_laps) > 0:
    sq_laps_export = sq_laps[[
        'Driver', 'DriverNumber', 'LapNumber', 'LapTime_sec',
        'Sector1Time_sec', 'Sector2Time_sec', 'Sector3Time_sec',
        'SpeedI1', 'SpeedI2', 'SpeedFL', 'SpeedST',
        'Stint', 'Compound', 'TyreLife', 'FreshTyre',
        'PitOutTime_sec', 'PitInTime_sec',
        'Position', 'IsPersonalBest', 'IsAccurate',
        'Team',
    ]].copy()
    datasets['sq_laps.csv'] = {
        'df': sq_laps_export,
        'source': 'FastF1 v3.8.1 (session.laps)',
        'api': 'FastF1',
        'desc': 'スプリント予選（SQ）全ドライバー全ラップデータ。',
        'rows': len(sq_laps_export),
    }

# --- Qualifying Laps ---
quali_laps = df_laps[df_laps['Session'] == 'Qualifying'].copy()
if len(quali_laps) > 0:
    quali_laps_export = quali_laps[[
        'Driver', 'DriverNumber', 'LapNumber', 'LapTime_sec',
        'Sector1Time_sec', 'Sector2Time_sec', 'Sector3Time_sec',
        'SpeedI1', 'SpeedI2', 'SpeedFL', 'SpeedST',
        'Stint', 'Compound', 'TyreLife', 'FreshTyre',
        'PitOutTime_sec', 'PitInTime_sec',
        'Position', 'IsPersonalBest', 'IsAccurate',
        'Team',
    ]].copy()
    datasets['quali_laps.csv'] = {
        'df': quali_laps_export,
        'source': 'FastF1 v3.8.1 (session.laps)',
        'api': 'FastF1',
        'desc': '予選（Q）全ドライバー全ラップデータ。',
        'rows': len(quali_laps_export),
    }


# ============================================================
# ファイル書き出し
# ============================================================
print('\nデータセット書き出し中...')

manifest = []

for filename, info in datasets.items():
    filepath = EXPORT_DIR / filename
    df = info['df']

    if info.get('parquet'):
        df.to_parquet(filepath, index=False)
    else:
        df.to_csv(filepath, index=False, encoding='utf-8')

    size_kb = filepath.stat().st_size / 1024
    print(f'  {filename}: {info["rows"]} rows, {size_kb:.1f} KB')

    manifest.append({
        'file': filename,
        'rows': info['rows'],
        'columns': len(df.columns),
        'size_kb': round(size_kb, 1),
        'source': info['source'],
        'api': info['api'],
        'description': info['desc'],
    })


# ============================================================
# README.md 生成
# ============================================================
print('\nREADME.md生成中...')

# Race周回数を取得
race_total_laps = ''
if len(race_laps) > 0:
    race_total_laps = f"{race_laps['LapNumber'].max():.0f}"

# Sprint周回数を取得
sprint_total_laps = ''
if len(sprint_laps) > 0:
    sprint_total_laps = f"{sprint_laps['LapNumber'].max():.0f}"

readme = f"""# 2026 R2 中国GP - データセット

## 概要

2026 FIA Formula 1 中国グランプリ（上海国際サーキット）のスプリントウィーク全セッションデータ。

- **イベント**: 2026 R2 Chinese Grand Prix (Sprint Weekend)
- **サーキット**: Shanghai International Circuit
- **セッション**: FP1 / Sprint Qualifying / Sprint / Qualifying / Race
- **レース**: {race_total_laps}周 / スプリント: {sprint_total_laps}周
- **データ取得日**: {datetime.now().strftime('%Y-%m-%d')}
- **ツール**: FastF1 v3.8.1 (Python)

## データソースAPI

| API | URL | 提供データ | ライセンス |
|-----|-----|-----------|-----------|
| **FastF1** | https://docs.fastf1.dev/ | ラップタイム、セクター、スピード、タイヤ、結果、気象、レースコントロール | MIT (FastF1自体) |
| **F1 Live Timing** | (FastF1経由で取得) | 上記の原データソース。F1公式ライブタイミングAPI | Formula 1 |

> **注意**: FastF1はF1 Live Timing APIのPythonラッパーです。データの原著作権はFormula 1に帰属します。
> 本データセットは個人的な分析・学習目的で使用しています。

## ファイル一覧

| ファイル | 行数 | カラム数 | サイズ | データソース | 説明 |
|---------|------|---------|--------|-------------|------|
"""

for m in manifest:
    readme += f"| `{m['file']}` | {m['rows']} | {m['columns']} | {m['size_kb']} KB | {m['api']} | {m['description']} |\n"

readme += f"""
## SQLiteデータベース (`gp_weekend.db`)

統合データベースには以下のテーブルとビューが含まれます:

### テーブル
| テーブル | 説明 |
|---------|------|
| `laps` | 全5セッションの全ラップデータ（Session列で区別） |
| `weather` | 全5セッションの気象データ |
| `results` | Sprint + Race の結果 |
| `race_control_messages` | Sprint + Race のレースコントロールメッセージ |

### ビュー
| ビュー | 説明 |
|--------|------|
| `session_summary` | セッション別ドライバー統計（ベストラップ、平均、ラップ数、使用コンパウンド） |
| `driver_best_laps` | セッション x ドライバー別ベストラップ（正確なラップのみ） |
| `long_runs` | 同一コンパウンド・同一スティントで5周以上（アウト/インラップ除外） |

## 再現方法

```python
import fastf1
fastf1.Cache.enable_cache('~/f1_cache')

# 全セッション読み込み例
for sid in ['FP1', 'SQ', 'S', 'Q', 'R']:
    session = fastf1.get_session(2026, 'China', sid)
    session.load(telemetry=False, laps=True, weather=True)
```

## 注意事項

- 全タイムデータは**燃料補正なし**の生データです
- スピードトラップ (SpeedST) の値はVSC/SC中は通常値より大幅に低下します
- FastF1 v3.8.1以上が必要です（2026シーズン対応パッチ）
- データの原著作権はFormula 1に帰属します
- スプリントウィーク: FP2/FP3はありません（FP1のみ）
"""

readme_path = EXPORT_DIR / 'README.md'
with open(readme_path, 'w', encoding='utf-8') as f:
    f.write(readme)
print(f'  README.md: {readme_path.stat().st_size / 1024:.1f} KB')


# ============================================================
# manifest.json
# ============================================================
manifest_json = {
    'event': f'{YEAR} R{ROUND_NUMBER} {GP_NAME} Grand Prix',
    'circuit': 'Shanghai International Circuit',
    'format': 'Sprint Weekend',
    'sessions': list(SESSIONS.keys()),
    'race_laps': int(race_laps['LapNumber'].max()) if len(race_laps) > 0 else None,
    'sprint_laps': int(sprint_laps['LapNumber'].max()) if len(sprint_laps) > 0 else None,
    'exported': datetime.now().isoformat(),
    'tool': 'FastF1 v3.8.1',
    'primary_api': 'F1 Live Timing API (via FastF1)',
    'datasets': manifest,
}

manifest_path = EXPORT_DIR / 'manifest.json'
with open(manifest_path, 'w', encoding='utf-8') as f:
    json.dump(manifest_json, f, indent=2, ensure_ascii=False)
print(f'  manifest.json: {manifest_path.stat().st_size / 1024:.1f} KB')


# ============================================================
# 完了サマリー
# ============================================================
print('\n' + '=' * 60)
print(f'完了: {YEAR} R{ROUND_NUMBER:02d} {GP_NAME} GP データベース作成')
print('=' * 60)
print(f'  DB: {DB_PATH} ({DB_PATH.stat().st_size / 1024:.1f} KB)')
print(f'  エクスポート: {EXPORT_DIR}')
print(f'  ファイル数: {len(list(EXPORT_DIR.iterdir()))}')
total_size = sum(f.stat().st_size for f in EXPORT_DIR.iterdir()) / 1024
print(f'  合計サイズ: {total_size:.1f} KB')
print('\n検証コマンド:')
print(f'  sqlite3 {DB_PATH} "SELECT Session, COUNT(*) FROM laps GROUP BY Session;"')
print(f'  sqlite3 {DB_PATH} "SELECT * FROM session_summary LIMIT 5;"')
print(f'  sqlite3 {DB_PATH} "SELECT * FROM long_runs LIMIT 5;"')
