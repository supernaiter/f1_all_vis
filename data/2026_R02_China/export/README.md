# 2026 R2 中国GP - データセット

## 概要

2026 FIA Formula 1 中国グランプリ（上海国際サーキット）のスプリントウィーク全セッションデータ。

- **イベント**: 2026 R2 Chinese Grand Prix (Sprint Weekend)
- **サーキット**: Shanghai International Circuit
- **セッション**: FP1 / Sprint Qualifying / Sprint / Qualifying / Race
- **レース**: 56周 / スプリント: 19周
- **データ取得日**: 2026-03-16
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
| `race_laps.csv` | 924 | 22 | 102.3 KB | FastF1 (https://docs.fastf1.dev/) | 決勝全ドライバー全ラップデータ。ラップタイム、セクタータイム、スピード計測、タイヤ情報、ポジション等。 |
| `race_laps.parquet` | 924 | 31 | 88.3 KB | FastF1 | race_laps.csvの完全版（Timedelta型保持、全カラム） |
| `race_results.csv` | 22 | 13 | 1.9 KB | FastF1 | 決勝結果。全ドライバーの順位、グリッド、ステータス、ポイント。 |
| `race_control_messages.csv` | 86 | 7 | 5.9 KB | FastF1 | レースコントロールメッセージ（VSC/SC/旗等）。 |
| `race_weather.csv` | 152 | 8 | 6.8 KB | FastF1 | 決勝中の気象データ。気温、路面温度、湿度、風向風速、降雨。 |
| `fp_laps.csv` | 540 | 20 | 55.0 KB | FastF1 | FP1の全ラップデータ（スプリントウィークのためFP1のみ）。 |
| `fp_weather.csv` | 84 | 9 | 4.1 KB | FastF1 | FP1の気象データ。 |
| `fp_session_summary.csv` | 22 | 7 | 1.3 KB | FastF1 | FP1のセッション別ドライバーサマリー（ベストラップ、平均、使用コンパウンド）。 |
| `sprint_laps.csv` | 397 | 22 | 44.4 KB | FastF1 | スプリント全ドライバー全ラップデータ。 |
| `sprint_results.csv` | 22 | 13 | 1.9 KB | FastF1 | スプリント結果。全ドライバーの順位、グリッド、ステータス、ポイント。 |
| `sq_laps.csv` | 257 | 21 | 27.2 KB | FastF1 | スプリント予選（SQ）全ドライバー全ラップデータ。 |
| `quali_laps.csv` | 325 | 21 | 34.1 KB | FastF1 | 予選（Q）全ドライバー全ラップデータ。 |

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
