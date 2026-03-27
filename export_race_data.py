"""
============================================================
汎用レースデータエクスポートスクリプト
============================================================
使い方: /usr/bin/python3 export_race_data.py <YEAR> <GP_NAME> <ROUND>
例:     /usr/bin/python3 export_race_data.py 2026 Japan 3

H2Hレポートの元データをCSV/Parquetで書き出し、
各データの出所APIを明記したREADMEを生成する。
"""

import fastf1
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import json
import sys

# ============================================================
# CLI引数パース
# ============================================================
if len(sys.argv) < 4:
    print('使い方: python export_race_data.py <YEAR> <GP_NAME> <ROUND>')
    print('例:     python export_race_data.py 2026 Japan 3')
    sys.exit(1)

YEAR = int(sys.argv[1])
GP_NAME = sys.argv[2]
ROUND_NUMBER = int(sys.argv[3])

EXPORT_DIR = Path(f'./data/{YEAR}_R{ROUND_NUMBER:02d}_{GP_NAME}/export')
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# FastF1からデータ読み込み
# ============================================================
print(f'FastF1からデータを読み込み中... ({YEAR} R{ROUND_NUMBER} {GP_NAME})')
fastf1.Cache.enable_cache('~/f1_cache')

datasets = {}  # {filename: {'df': DataFrame, 'source': str, 'desc': str}}

# --- Race session ---
print('  Race session...')
race = fastf1.get_session(YEAR, GP_NAME, 'R')
race.load(telemetry=False, laps=True, weather=True)

# セッション情報取得
circuit_name = race.event.get('CircuitShortName', GP_NAME)
event_name = race.event.get('EventName', f'{GP_NAME} Grand Prix')

# 1. Race Laps（全ドライバー全ラップ）
race_laps = race.laps.copy()
# Timedelta → 秒に変換（CSVでの可読性のため）
for col in ['LapTime', 'Sector1Time', 'Sector2Time', 'Sector3Time',
            'PitOutTime', 'PitInTime', 'Time', 'LapStartTime',
            'Sector1SessionTime', 'Sector2SessionTime', 'Sector3SessionTime']:
    if col in race_laps.columns:
        race_laps[f'{col}_sec'] = race_laps[col].dt.total_seconds()

# CSV用に整理（使用カラムのみ）
export_cols = [
    'Driver', 'DriverNumber', 'LapNumber', 'LapTime_sec',
    'Sector1Time_sec', 'Sector2Time_sec', 'Sector3Time_sec',
    'SpeedI1', 'SpeedI2', 'SpeedFL', 'SpeedST',
    'Stint', 'Compound', 'TyreLife', 'FreshTyre',
    'PitOutTime_sec', 'PitInTime_sec',
    'Position', 'TrackStatus', 'IsPersonalBest', 'IsAccurate',
    'Team',
]
# 存在するカラムのみ選択
export_cols = [c for c in export_cols if c in race_laps.columns]
race_laps_export = race_laps[export_cols].copy()

datasets['race_laps.csv'] = {
    'df': race_laps_export,
    'source': 'FastF1 (fastf1.get_session → session.laps)',
    'api': 'FastF1 (https://docs.fastf1.dev/) — F1 Live Timing APIのラッパー',
    'desc': '決勝全ドライバー全ラップデータ。ラップタイム、セクタータイム、スピード計測、タイヤ情報、ポジション等。',
    'rows': len(race_laps_export),
}

# Parquet版も出力（型情報保持）
datasets['race_laps.parquet'] = {
    'df': race_laps,  # 元のTimedelta型を含むフルデータ
    'source': 'FastF1 (session.laps)',
    'api': 'FastF1',
    'desc': 'race_laps.csvの完全版（Timedelta型保持、全カラム）',
    'rows': len(race_laps),
    'parquet': True,
}

# 2. Race Results
results = race.results.copy()
for col in results.columns:
    if hasattr(results[col], 'dt') and results[col].dtype.kind == 'm':
        results[f'{col}_sec'] = results[col].dt.total_seconds()

results_cols = [
    'DriverNumber', 'Abbreviation', 'FirstName', 'LastName', 'FullName',
    'TeamName', 'TeamColor',
    'Position', 'ClassifiedPosition', 'GridPosition',
    'Status', 'Points', 'Laps',
]
results_cols = [c for c in results_cols if c in results.columns]
results_export = results[results_cols].copy()

datasets['race_results.csv'] = {
    'df': results_export,
    'source': 'FastF1 (session.results)',
    'api': 'FastF1 — F1 Live Timing API',
    'desc': f'決勝結果。全{len(results_export)}ドライバーの順位、グリッド、ステータス、ポイント。',
    'rows': len(results_export),
}

# 3. Race Control Messages
rcm = race.race_control_messages.copy()
rcm_cols = ['Lap', 'Category', 'Message', 'Flag', 'Scope', 'Sector', 'RacingNumber']
rcm_cols = [c for c in rcm_cols if c in rcm.columns]
rcm_export = rcm[rcm_cols].copy()
if 'Lap' in rcm_export.columns:
    rcm_export['Lap'] = rcm_export['Lap'].fillna('').apply(lambda x: int(x) if x != '' else '')

datasets['race_control_messages.csv'] = {
    'df': rcm_export,
    'source': 'FastF1 (session.race_control_messages)',
    'api': 'FastF1 — F1 Live Timing API',
    'desc': f'レースコントロールメッセージ（VSC/SC/旗等）。{len(rcm_export)}件。',
    'rows': len(rcm_export),
}

# 4. Race Weather
weather = race.weather_data.copy()
if weather is not None and len(weather) > 0:
    datasets['race_weather.csv'] = {
        'df': weather,
        'source': 'FastF1 (session.weather_data)',
        'api': 'FastF1 — F1 Live Timing API',
        'desc': '決勝中の気象データ。気温、路面温度、湿度、風向風速、降雨。',
        'rows': len(weather),
    }

# --- FP sessions (既存DBから) ---
print('  FP sessions (既存DB)...')
import sqlite3
db_path = Path(f'./data/{YEAR}_R{ROUND_NUMBER:02d}_{GP_NAME}/gp_weekend.db')
if db_path.exists():
    conn = sqlite3.connect(str(db_path))
    try:
        fp_laps = pd.read_sql('SELECT * FROM laps', conn)
        datasets['fp_laps.csv'] = {
            'df': fp_laps,
            'source': f'gp_weekend.db (lapsテーブル) ← FastF1',
            'api': 'FastF1 — F1 Live Timing API',
            'desc': f'FPセッションの全ラップデータ。{len(fp_laps)}行。',
            'rows': len(fp_laps),
        }
    except Exception as e:
        print(f'    FPラップ読み込みスキップ: {e}')

    try:
        fp_weather = pd.read_sql('SELECT * FROM weather', conn)
        datasets['fp_weather.csv'] = {
            'df': fp_weather,
            'source': f'gp_weekend.db (weatherテーブル) ← FastF1',
            'api': 'FastF1 — F1 Live Timing API',
            'desc': f'FPセッションの気象データ。{len(fp_weather)}行。',
            'rows': len(fp_weather),
        }
    except Exception as e:
        print(f'    FP天候読み込みスキップ: {e}')

    try:
        fp_summary = pd.read_sql('SELECT * FROM session_summary', conn)
        datasets['fp_session_summary.csv'] = {
            'df': fp_summary,
            'source': f'gp_weekend.db (session_summaryテーブル) ← FastF1',
            'api': 'FastF1 — F1 Live Timing API',
            'desc': 'FPセッション別ドライバーサマリー（ベストラップ、平均、使用コンパウンド）。',
            'rows': len(fp_summary),
        }
    except Exception as e:
        print(f'    FPサマリー読み込みスキップ: {e}')

    conn.close()
else:
    print(f'    DB未検出: {db_path}（FPデータはスキップ）')

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

total_laps = int(race_laps_export['LapNumber'].max())

readme = f"""# {YEAR} R{ROUND_NUMBER} {GP_NAME} GP — レースデータセット

## 概要

{YEAR} FIA Formula 1 {event_name}のレース・フリープラクティスデータ。
Head-to-Head レースペース分析レポートの元データとして使用。

- **イベント**: {YEAR} R{ROUND_NUMBER} {event_name}
- **サーキット**: {circuit_name}
- **レース**: {total_laps}周
- **データ取得日**: {datetime.now().strftime('%Y-%m-%d')}
- **ツール**: FastF1 (Python)

## データソースAPI

| API | URL | 提供データ | ライセンス |
|-----|-----|-----------|-----------|
| **FastF1** | https://docs.fastf1.dev/ | ラップタイム、セクター、スピード、タイヤ、結果、気象、レースコントロール | MIT (FastF1自体) |
| **F1 Live Timing** | (FastF1経由で取得) | 上記の原データソース。F1公式ライブタイミングAPI | Formula 1 |

> **注意**: データの原著作権はFormula 1に帰属します。個人的な分析・学習目的で使用しています。

## ファイル一覧

| ファイル | 行数 | カラム数 | サイズ | データソース | 説明 |
|---------|------|---------|--------|-------------|------|
"""

for m in manifest:
    readme += f"| `{m['file']}` | {m['rows']} | {m['columns']} | {m['size_kb']} KB | {m['api']} | {m['description']} |\n"

readme += f"""
## 再現方法

```python
import fastf1
fastf1.Cache.enable_cache('~/f1_cache')
session = fastf1.get_session({YEAR}, '{GP_NAME}', 'R')
session.load(telemetry=False, laps=True, weather=True)

laps = session.laps
results = session.results
rcm = session.race_control_messages
weather = session.weather_data
```

## 注意事項

- 全タイムデータは**燃料補正なし**の生データです
- スピードトラップ (SpeedST) の値はVSC/SC中は通常値より大幅に低下します
- データの原著作権はFormula 1に帰属します
"""

readme_path = EXPORT_DIR / 'README.md'
with open(readme_path, 'w', encoding='utf-8') as f:
    f.write(readme)
print(f'  README.md: {readme_path.stat().st_size / 1024:.1f} KB')

# ============================================================
# manifest.json
# ============================================================
manifest_json = {
    'event': f'{YEAR} R{ROUND_NUMBER} {event_name}',
    'circuit': circuit_name,
    'race_laps': total_laps,
    'exported': datetime.now().isoformat(),
    'tool': 'FastF1',
    'primary_api': 'F1 Live Timing API (via FastF1)',
    'datasets': manifest,
}

manifest_path = EXPORT_DIR / 'manifest.json'
with open(manifest_path, 'w', encoding='utf-8') as f:
    json.dump(manifest_json, f, indent=2, ensure_ascii=False)
print(f'  manifest.json: {manifest_path.stat().st_size / 1024:.1f} KB')

print(f'\n=== 書き出し完了: {EXPORT_DIR} ===')
print(f'ファイル数: {len(list(EXPORT_DIR.iterdir()))}')
total_size = sum(f.stat().st_size for f in EXPORT_DIR.iterdir()) / 1024
print(f'合計サイズ: {total_size:.1f} KB')
