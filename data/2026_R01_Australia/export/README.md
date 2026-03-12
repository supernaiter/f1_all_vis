# 2026 R1 オーストラリアGP — レースデータセット

## 概要

2026 FIA Formula 1 オーストラリアグランプリ（アルバートパーク、メルボルン）のレース・フリープラクティスデータ。
Head-to-Head レースペース分析レポートの元データとして使用。

- **イベント**: 2026 R1 Australian Grand Prix
- **サーキット**: Albert Park Circuit, Melbourne
- **レース**: 58周
- **データ取得日**: 2026-03-12
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
| `race_laps.csv` | 1007 | 22 | 111.5 KB | FastF1 (https://docs.fastf1.dev/) — F1 Live Timing APIのラッパー | 決勝全ドライバー全ラップデータ。ラップタイム、セクタータイム、スピード計測、タイヤ情報、ポジション等。 |
| `race_laps.parquet` | 1007 | 42 | 162.9 KB | FastF1 | race_laps.csvの完全版（Timedelta型保持、全31カラム） |
| `race_results.csv` | 22 | 13 | 1.9 KB | FastF1 — F1 Live Timing API | 決勝結果。全22ドライバーの順位、グリッド、ステータス、ポイント。 |
| `race_control_messages.csv` | 167 | 7 | 11.6 KB | FastF1 — F1 Live Timing API | レースコントロールメッセージ（VSC/SC/旗等）。167件。 |
| `race_weather.csv` | 148 | 8 | 8.7 KB | FastF1 — F1 Live Timing API | 決勝中の気象データ。気温、路面温度、湿度、風向風速、降雨。 |
| `fp_laps.csv` | 1408 | 20 | 132.2 KB | FastF1 — F1 Live Timing API | FP1/FP2/FP3の全ラップデータ。1408行。セッション別にフィルタ可能。 |
| `fp_weather.csv` | 161 | 9 | 7.2 KB | FastF1 — F1 Live Timing API | FP1/FP2/FP3の気象データ。161行。 |
| `fp_session_summary.csv` | 43 | 7 | 2.4 KB | FastF1 — F1 Live Timing API | FP1/FP2のセッション別ドライバーサマリー（ベストラップ、平均、使用コンパウンド）。 |

## カラム説明

### race_laps.csv / race_laps.parquet

| カラム | 型 | 説明 | 出所 |
|--------|---|------|------|
| `Driver` | str | ドライバー略称 (例: RUS, LEC) | FastF1 |
| `DriverNumber` | int | カーナンバー | FastF1 |
| `LapNumber` | int | ラップ番号 (1-58) | FastF1 |
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
