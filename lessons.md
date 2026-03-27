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
