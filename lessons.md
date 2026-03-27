# Lessons

## General
- /usr/bin/python3を使うこと（/opt/homebrew/python3にはpandas/matplotlibなし）
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

## Astro
- チャート画像のbase64埋め込みは1ページ1MB超になる→外部ファイル参照に切替推奨
- getStaticPaths()でJSONを読み込み、ビルド時に全ページ生成
- site/dist/にビルド出力。npx astro previewでローカル確認
