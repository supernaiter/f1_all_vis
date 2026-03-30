# Plan: R03 H2Hデータ生成 + R04-R06パイプライン自動化
Date: 2026-03-31
Prompt: "2026 R03 日本GPのH2Hデータ生成を完了し、R04-R06のデータ投入パイプラインをワンコマンドで実行できるスクリプトにまとめる"

## Goal

R03 日本GP（鈴鹿）のレースデータエクスポートとH2H分析JSONの生成を完了させ、Astroサイトに組み込める状態にする。R01/R02で手動実行していた2段階プロセス（export_race_data.py → h2h_engine.py）を、R04バーレーン以降は単一コマンドで実行できるパイプラインスクリプトに統合する。これにより、レース週末の翌日にデータ更新からサイトビルドまでを迅速かつ確実に回せるようにする。

## Acceptance Criteria

### R03 日本GP データ生成
- [ ] R03日本GPの決勝レースデータ（race_laps.csv, race_results.csv, race_control_messages.csv等）がdata/2026_R03_Japan/export/に存在する
- [ ] R03日本GPのH2HデータがTop10モード（--top10）でdata/2026_R03_Japan/h2h/に生成されている
- [ ] data/2026_R03_Japan/h2h/index.jsonが存在し、Astroサイトの`listGPs()`で自動検出される
- [ ] `cd site && npm run build` が成功し、R03のH2Hページがビルド出力に含まれる

### ワンコマンドパイプラインスクリプト
- [ ] 単一のスクリプトにGP名/年/ラウンド番号を渡すだけで、export→H2H生成→（オプションで）サイトビルドまでが順次実行される
- [ ] export_race_data.pyはfastf1が必要なため`uv run`経由で実行し、h2h_engine.pyは`/usr/bin/python3`で実行する、という環境差を内部で正しく処理する
- [ ] 各ステップの成功/失敗をターミナルに明示し、途中で失敗した場合はその時点で停止する（部分的に壊れたデータを残さない）
- [ ] exportデータが既に存在する場合はスキップする`--force`オプション（or デフォルトスキップ＋上書きオプション）がある
- [ ] R04バーレーン、R05サウジアラビア、R06マイアミに対して、レース終了後に即座に使える（GP名やラウンド番号の手入力のみで動く）
- [ ] スクリプトのヘルプ（`--help`）を見れば、必要な引数と使い方がわかる

### クロスGP分析の対応
- [ ] R03追加後のクロスGP比較データ（R01-R02-R03）も生成できる、もしくは次フェーズとして明示的にスキップしている

### 品質
- [ ] 生成されたR03のanalysis.jsonが、R01/R02と同じスキーマ構造を持つ（Astroページが型エラーなくレンダリングできる）
- [ ] パイプラインを2回連続実行しても冪等（同じ結果になる）

## Out of Scope
- Cloudflare Pagesへの自動デプロイ（手動確認後にデプロイするフロー）
- 予選データ(quali_laps.csv)やスプリントデータのH2H分析への統合
- クロスGP比較スクリプトの汎用化（現状R01-R02固定のスクリプトが存在）
- FPデータのH2H分析
- サイトのUI変更やデザイン修正
- PNG画像の生成（EChartsで描画するためPNGは不要）

## Notes
- R03のexportディレクトリにはFPデータ（fp_laps.csv, fp1_summary.csv, fp2_summary.csv）のみ存在。決勝データのexportがまだ未実行
- export_race_data.pyはfastf1を使うため `uv run --with fastf1 --with pyarrow python export_race_data.py 2026 Japan 3` で実行する必要がある
- h2h_engine.pyはpandas/numpy/matplotlibのみ使用し、/usr/bin/python3で動作する
- R01/R02ではH2Hを`--top10`モードで生成している（全ペアではなく上位10台の組み合わせ）
- Astroサイトの`getH2HStaticPaths()`はdata/ディレクトリを自動スキャンしてGPを検出するため、正しいディレクトリ構造とindex.jsonがあれば追加設定は不要
- pip installはdeny-check.shフックで禁止されている。uv runのみが外部パッケージの実行手段
- 2026カレンダー: R04=バーレーン(4/10-12), R05=サウジアラビア(4/17-19), R06=マイアミ(5/1-3, Sprint)
- R06マイアミはスプリントウィークエンドのため、sprint_laps.csv等の追加exportが発生する可能性がある（export_race_data.pyが既に対応済みかはR02中国で確認可能→R02にsprint_laps.csv, sq_laps.csvが存在するため対応済み）
