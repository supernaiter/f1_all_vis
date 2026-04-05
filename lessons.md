# Lessons

## General
- /usr/bin/python3を使うこと（pandas/matplotlibあり、fastf1なし）
- fastf1はどのPythonにもグローバルインストールされていない
- fastf1が必要なスクリプトは `uv run --with fastf1 --with pyarrow python script.py` で実行
- pip installはdeny-check.shフックで禁止されている

## フォント
- Hiragino Sansが/usr/bin/python3のmatplotlibで使える日本語フォント
- Noto Sans JP/Yu Gothic/Meiryoは未インストール
- フォント検出は`matplotlib.font_manager.fontManager.ttflist`の`.name`で確認

## H2Hエンジン
- export済みCSVが前提。新GPはまずexport_race_dataを実行すること
- SC検出: "SAFETY CAR DEPLOYED"+"SAFETY CAR IN THIS LAP"のペアで期間特定
- VSC検出: "VSC DEPLOYED"+"VSC ENDING"のペアで期間特定
- TrackStatusの'1'はstr比較が必要（数値と文字列が混在する場合あり）
- GapToLeader_pctはdf_team（concat後）に追加されるため、元のall_team_pace辞書には存在しない
- --pngフラグでPNG生成はオプション。デフォルトはJSON only

## Astro
- EChartsに移行済み。PNGは不要（copy-charts.mjsも不要化予定）
- getStaticPaths()はgetH2HStaticPaths()ヘルパーで5ページ共通化
- define:varsはモジュールscriptで使えない→script type="application/json"でデータ受け渡し
- site/dist/にビルド出力。npx astro previewでローカル確認
- AstroテンプレートでSVGに動的width/height属性を渡すと壊れる場合がある→CSS custom propertiesかdivのinline styleで制御する方が安全
- IIFE `{(() => { ... })()}` パターンはAstroで問題が起きやすい→frontmatterで事前計算してmapで回す

## デザイン
- F1公式カラー: bg=#15151e, card=#1c1c25, accent=#e10600, text=#ffffff, dim=#aaaaaa, border=#303037
- チームメイト比較ではチームカラーのドットだと区別不可→顔アイコン必須
- 比較の直感表現: アイコンの大小+透明度で勝敗、数字は補助（2層構造）
- ドライバー画像: CDNのc_thumb,g_face で顔クロップ。c_lfillだと全身になる
- サイズの動的変化はCSS custom properties (--s1, --s2等) + calc() + clamp()で実装。viewport連動でモバイル自動対応
- accent色の半透明: `rgba(225,6,0,0.1)` ではなく `color-mix(in srgb, var(--accent) 10%, transparent)` を使う
- face-dot background: Hubでは `var(--bg-card-hover)` を使用。サブページも揃えること

## ハーネス設計
- Generator+Evaluatorは別Agent subprocessで実行（自己評価バイアス排除）
- Evaluator基準は具体的・検証可能にする（「良いデザインか」ではなく「CSS variablesを使っているか」）
- R1でFAILする主な原因: DataZoom欠落、themeBase未抽出、json-ld欠落
- Evaluatorのフィードバックはそのまま次のGeneratorに渡す（要約しない）
- F1固有スキルはプロジェクトローカル(.claude/skills/)に配置。グローバルに置くと他プロジェクトに漏れる
- pace→sectors→speed→stintsの順が効率的（paceがHubに最も構造が近い）

## pSEO generator
- listGPs()はexport/未生成のGPも返す → getStaticPathsでdata nullフィルタ必須
- race_laps.csv Position列は 1,6,671,71 等のトラック状態値を混在 → LapNumber==1 フィルタで Lap1 position取得時に int変換前の数値バリデーション必須
- csv module は pandas なしで十分。Python 3.14 標準ライブラリのみで TYPE-A/E/F 全生成可
- TYPE-C トリプル生成時は scripts/driver_triple_generator.py を master.json 更新後に再実行すること。DRIVERS_2026 配列は2026シーズン限定で年次入れ替え前提
- Astro build メモリ: 3,000ページ超を足すときは NODE_OPTIONS="--max-old-space-size=8192" を付けるのが安全（6,470ページで約270秒）
- cd した Bash コマンドの working directory は以降のコマンドに引き継がれる → プロジェクトルート戻し忘れに注意、絶対パス推奨
- Cloudflare Pages デプロイの新規ファイル数で TYPE-C 拡張成否を検証可能（3,080新規 = 全トリプルが既存ハッシュに無いことの確認）
