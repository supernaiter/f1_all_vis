"""
============================================================
2026 R1 オーストラリアGP — GitHub公開用データセット書き出し
============================================================
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
# 設定
# ============================================================
YEAR = 2026
GP_NAME = 'Australia'
ROUND_NUMBER = 1

EXPORT_DIR = Path(f'./data/{YEAR}_R{ROUND_NUMBER:02d}_{GP_NAME}/export')
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# FastF1からデータ読み込み
# ============================================================
print('FastF1からデータを読み込み中...')
fastf1.Cache.enable_cache('~/f1_cache')

datasets = {}  # {filename: {'df': DataFrame, 'source': str, 'desc': str}}

# --- Race session ---
print('  Race session...')
race = fastf1.get_session(YEAR, GP_NAME, 'R')
race.load(telemetry=False, laps=True, weather=True)

# 1. Race Laps（全ドライバー全ラップ）
race_laps = race.laps.copy()
# Timedelta → 秒に変換（CSVでの可読性のため）
for col in ['LapTime', 'Sector1Time', 'Sector2Time', 'Sector3Time',
            'PitOutTime', 'PitInTime', 'Time', 'LapStartTime',
            'Sector1SessionTime', 'Sector2SessionTime', 'Sector3SessionTime']:
    if col in race_laps.columns:
        race_laps[f'{col}_sec'] = race_laps[col].dt.total_seconds()

# CSV用に整理（使用カラムのみ）
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
    'source': 'FastF1 v3.8.1 (fastf1.get_session → session.laps)',
    'api': 'FastF1 (https://docs.fastf1.dev/) — F1 Live Timing APIのラッパー',
    'desc': '決勝全ドライバー全ラップデータ。ラップタイム、セクタータイム、スピード計測、タイヤ情報、ポジション等。',
    'rows': len(race_laps_export),
}

# Parquet版も出力（型情報保持）
datasets['race_laps.parquet'] = {
    'df': race_laps,  # 元のTimedelta型を含むフルデータ
    'source': 'FastF1 v3.8.1 (session.laps)',
    'api': 'FastF1',
    'desc': 'race_laps.csvの完全版（Timedelta型保持、全31カラム）',
    'rows': len(race_laps),
    'parquet': True,
}

# 2. Race Results
results = race.results.copy()
# Timedelta/datetime列を文字列化
for col in results.columns:
    if hasattr(results[col], 'dt') and results[col].dtype.kind == 'm':
        results[f'{col}_sec'] = results[col].dt.total_seconds()

results_export = results[[
    'DriverNumber', 'Abbreviation', 'FirstName', 'LastName', 'FullName',
    'TeamName', 'TeamColor',
    'Position', 'ClassifiedPosition', 'GridPosition',
    'Status', 'Points', 'Laps',
]].copy()

datasets['race_results.csv'] = {
    'df': results_export,
    'source': 'FastF1 v3.8.1 (session.results)',
    'api': 'FastF1 — F1 Live Timing API',
    'desc': '決勝結果。全22ドライバーの順位、グリッド、ステータス、ポイント。',
    'rows': len(results_export),
}

# 3. Race Control Messages
rcm = race.race_control_messages.copy()
rcm_export = rcm[['Lap', 'Category', 'Message', 'Flag', 'Scope', 'Sector', 'RacingNumber']].copy()
# Lap列のNaNを空文字に
rcm_export['Lap'] = rcm_export['Lap'].fillna('').apply(lambda x: int(x) if x != '' else '')

datasets['race_control_messages.csv'] = {
    'df': rcm_export,
    'source': 'FastF1 v3.8.1 (session.race_control_messages)',
    'api': 'FastF1 — F1 Live Timing API',
    'desc': 'レースコントロールメッセージ（VSC/SC/旗等）。167件。',
    'rows': len(rcm_export),
}

# 4. Race Weather
weather = race.weather_data.copy()
if weather is not None and len(weather) > 0:
    datasets['race_weather.csv'] = {
        'df': weather,
        'source': 'FastF1 v3.8.1 (session.weather_data)',
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

    fp_laps = pd.read_sql('SELECT * FROM laps', conn)
    datasets['fp_laps.csv'] = {
        'df': fp_laps,
        'source': f'gp_weekend.db (lapsテーブル) ← FastF1 v3.8.1',
        'api': 'FastF1 — F1 Live Timing API',
        'desc': 'FP1/FP2/FP3の全ラップデータ。1408行。セッション別にフィルタ可能。',
        'rows': len(fp_laps),
    }

    fp_weather = pd.read_sql('SELECT * FROM weather', conn)
    datasets['fp_weather.csv'] = {
        'df': fp_weather,
        'source': f'gp_weekend.db (weatherテーブル) ← FastF1 v3.8.1',
        'api': 'FastF1 — F1 Live Timing API',
        'desc': 'FP1/FP2/FP3の気象データ。161行。',
        'rows': len(fp_weather),
    }

    fp_summary = pd.read_sql('SELECT * FROM session_summary', conn)
    datasets['fp_session_summary.csv'] = {
        'df': fp_summary,
        'source': f'gp_weekend.db (session_summaryテーブル) ← FastF1 v3.8.1',
        'api': 'FastF1 — F1 Live Timing API',
        'desc': 'FP1/FP2のセッション別ドライバーサマリー（ベストラップ、平均、使用コンパウンド）。',
        'rows': len(fp_summary),
    }

    conn.close()

# ============================================================
# ファイル書き出し
# ============================================================
print('\nデータセット書き出し中...')

manifest = []  # README用

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

readme = f"""# 2026 R1 オーストラリアGP — レースデータセット

## 概要

2026 FIA Formula 1 オーストラリアグランプリ（アルバートパーク、メルボルン）のレース・フリープラクティスデータ。
Head-to-Head レースペース分析レポートの元データとして使用。

- **イベント**: 2026 R1 Australian Grand Prix
- **サーキット**: Albert Park Circuit, Melbourne
- **レース**: {race_laps_export['LapNumber'].max():.0f}周
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
## カラム説明

### race_laps.csv / race_laps.parquet

| カラム | 型 | 説明 | 出所 |
|--------|---|------|------|
| `Driver` | str | ドライバー略称 (例: RUS, LEC) | FastF1 |
| `DriverNumber` | int | カーナンバー | FastF1 |
| `LapNumber` | int | ラップ番号 (1-{race_laps_export['LapNumber'].max():.0f}) | FastF1 |
| `LapTime_sec` | float | ラップタイム (秒) | FastF1 ← F1 Live Timing |
| `Sector1Time_sec` | float | セクター1タイム (秒) | FastF1 ← F1 Live Timing |
| `Sector2Time_sec` | float | セクター2タイム (秒) | FastF1 ← F1 Live Timing |
| `Sector3Time_sec` | float | セクター3タイム (秒) | FastF1 ← F1 Live Timing |
| `SpeedI1` | float | Sector1末端の速度 (km/h) | FastF1 ← F1 Live Timing |
| `SpeedI2` | float | Sector2末端の速度 (km/h) | FastF1 ← F1 Live Timing |
| `SpeedFL` | float | フィニッシュライン通過速度 (km/h) | FastF1 ← F1 Live Timing |
| `SpeedST` | float | スピードトラップ速度 (km/h) — メインストレート上の最高速計測点 | FastF1 ← F1 Live Timing |
| `Stint` | int | スティント番号 (ピットストップで区切り) | FastF1 |
| `Compound` | str | タイヤコンパウンド (SOFT/MEDIUM/HARD/INTERMEDIATE/WET) | FastF1 ← F1 Live Timing |
| `TyreLife` | int | タイヤ使用周回数 | FastF1 ← F1 Live Timing |
| `FreshTyre` | bool | 新品タイヤかどうか | FastF1 |
| `PitOutTime_sec` | float | ピットアウト時刻 (セッション経過秒)。NaN=ピットアウトなし | FastF1 |
| `PitInTime_sec` | float | ピットイン時刻 (セッション経過秒)。NaN=ピットインなし | FastF1 |
| `Position` | int | そのラップ終了時のレースポジション | FastF1 ← F1 Live Timing |
| `TrackStatus` | str | トラック状態コード (1=Green, 4=SC, 6=VSC, etc.) | FastF1 ← F1 Live Timing |
| `IsPersonalBest` | bool | 自己ベスト更新ラップか | FastF1 |
| `IsAccurate` | bool | FastF1によるラップ精度判定 | FastF1 |
| `Team` | str | チーム名 | FastF1 |

### race_results.csv

| カラム | 説明 | 出所 |
|--------|------|------|
| `Abbreviation` | ドライバー略称 | FastF1 ← F1 Live Timing |
| `FullName` | フルネーム | FastF1 |
| `TeamName` | チーム名 | FastF1 |
| `Position` | 最終順位 | FastF1 ← F1 Live Timing |
| `GridPosition` | グリッド位置 | FastF1 ← F1 Live Timing |
| `Status` | 完走/リタイア状態 | FastF1 ← F1 Live Timing |
| `Points` | 獲得ポイント | FastF1 ← F1 Live Timing |

### race_control_messages.csv

| カラム | 説明 | 出所 |
|--------|------|------|
| `Lap` | ラップ番号 | FastF1 ← F1 Live Timing |
| `Category` | カテゴリ (Flag, SafetyCar, etc.) | FastF1 ← F1 Live Timing |
| `Message` | メッセージ本文 | FastF1 ← F1 Live Timing |
| `Flag` | フラグ種別 | FastF1 ← F1 Live Timing |

### race_weather.csv

| カラム | 説明 | 出所 |
|--------|------|------|
| `AirTemp` | 気温 (°C) | FastF1 ← F1 Live Timing |
| `TrackTemp` | 路面温度 (°C) | FastF1 ← F1 Live Timing |
| `Humidity` | 湿度 (%) | FastF1 ← F1 Live Timing |
| `Rainfall` | 降雨フラグ | FastF1 ← F1 Live Timing |
| `WindSpeed` | 風速 (m/s) | FastF1 ← F1 Live Timing |
| `WindDirection` | 風向 (°) | FastF1 ← F1 Live Timing |

### fp_laps.csv

FP1/FP2/FP3のラップデータ。`Session`カラムでセッション別にフィルタ可能。
カラム構成はrace_laps.csvと同等（Session列が追加）。

## 分析レポート

このデータセットを元に以下のH2Hレポートが生成されています:

| レポート | 比較 | ファイル |
|---------|------|---------|
| Mercedes vs Ferrari | RUS vs LEC | `race_h2h_rus_vs_lec_2026_r01.html` |
| Mercedes チームメイト | RUS vs ANT | `race_h2h_rus_vs_ant_2026_r01.html` |
| Ferrari チームメイト | LEC vs HAM | `race_h2h_lec_vs_ham_2026_r01.html` |
| クロス比較 | ANT vs HAM | `race_h2h_ant_vs_ham_2026_r01.html` |

## 再現方法

```python
import fastf1
fastf1.Cache.enable_cache('~/f1_cache')
session = fastf1.get_session(2026, 'Australia', 'R')
session.load(telemetry=False, laps=True, weather=True)

laps = session.laps          # → race_laps に対応
results = session.results     # → race_results に対応
rcm = session.race_control_messages  # → race_control_messages に対応
weather = session.weather_data       # → race_weather に対応
```

## 注意事項

- 全タイムデータは**燃料補正なし**の生データです
- スピードトラップ (SpeedST) の値はVSC/SC中は通常値より大幅に低下します
- FastF1 v3.8.1以上が必要です（2026シーズン対応パッチ）
- データの原著作権はFormula 1に帰属します
"""

readme_path = EXPORT_DIR / 'README.md'
with open(readme_path, 'w', encoding='utf-8') as f:
    f.write(readme)
print(f'  README.md: {readme_path.stat().st_size / 1024:.1f} KB')

# ============================================================
# manifest.json（プログラム的な参照用）
# ============================================================
manifest_json = {
    'event': f'{YEAR} R{ROUND_NUMBER} {GP_NAME} Grand Prix',
    'circuit': 'Albert Park Circuit, Melbourne',
    'race_laps': int(race_laps_export['LapNumber'].max()),
    'exported': datetime.now().isoformat(),
    'tool': 'FastF1 v3.8.1',
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
