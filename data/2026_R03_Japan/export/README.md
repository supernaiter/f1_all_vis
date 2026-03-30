# 2026 R3 Japan GP — レースデータセット

## 概要

2026 FIA Formula 1 Japanese Grand Prixのレース・フリープラクティスデータ。
Head-to-Head レースペース分析レポートの元データとして使用。

- **イベント**: 2026 R3 Japanese Grand Prix
- **サーキット**: Japan
- **レース**: 53周
- **データ取得日**: 2026-03-31
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
| `race_laps.csv` | 1107 | 22 | 121.7 KB | FastF1 (https://docs.fastf1.dev/) — F1 Live Timing APIのラッパー | 決勝全ドライバー全ラップデータ。ラップタイム、セクタータイム、スピード計測、タイヤ情報、ポジション等。 |
| `race_laps.parquet` | 1107 | 42 | 172.7 KB | FastF1 | race_laps.csvの完全版（Timedelta型保持、全カラム） |
| `race_results.csv` | 22 | 13 | 1.9 KB | FastF1 — F1 Live Timing API | 決勝結果。全22ドライバーの順位、グリッド、ステータス、ポイント。 |
| `race_control_messages.csv` | 47 | 7 | 3.0 KB | FastF1 — F1 Live Timing API | レースコントロールメッセージ（VSC/SC/旗等）。47件。 |
| `race_weather.csv` | 156 | 8 | 9.0 KB | FastF1 — F1 Live Timing API | 決勝中の気象データ。気温、路面温度、湿度、風向風速、降雨。 |

## 再現方法

```python
import fastf1
fastf1.Cache.enable_cache('~/f1_cache')
session = fastf1.get_session(2026, 'Japan', 'R')
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
