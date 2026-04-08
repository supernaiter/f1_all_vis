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

## OpenF1 API
- `/car_data` は driver_number + date範囲フィルタ必須（指定なしで422 Unprocessable Entity）
- `brake` は 0 または 100 の離散値（FastF1の0-100連続値と異なる）→ 閾値50での立ち上がり検出で代替
- `/location` は x,y,z の三次元。outlineは reference driver を間引きで取得可能
- session_key は /sessions?year=YYYY&session_name=Race で取得（location文字列マッチ）
- QPS=2.0 程度までは許容、上位10ドライバー × 2エンドポイント × 3分窓 = 約40リクエスト/GP で5分以内完了

## 品質改善パターン
- makeRow等の共通関数は lib/ に共有モジュールとして抽出→importで使用。5ファイル150行削減実績
- Canvas系カードページの is:inline スクリプトは ES module import 不可→コンポーネント include か define:vars で対応
- 空データハンドリングは frontmatter で判定フラグを作り、HTML テンプレート側で分岐表示
- OGメタタグは全カードページに必須（ソーシャル共有目的のページなのに未設定だった）
- color-mix(in srgb, var(--accent) N%, transparent) がデザイントークン対応の rgba() 代替。ブラウザ対応は Safari 16.4+

## パス移行
- ディスク移行時はdata.ts/astro.config.mjs/copy-charts.mjsの3箇所にハードコードパスがある
- `grep -r 'intersd2\|lyssr_workspace' --include='*.{ts,js,mjs,astro}' site/` で検出可能
- 根本対策: 相対パス or 環境変数化を検討

## openf1_client.py
- 未使用コードは放置しない。706行→72行に削減した実績
- jitter計算に `time.time() % 1` を使うと負の値になりうる → `random.uniform` が正解

## 燃料補正レースペース（T4結果 2026-04-08）
- 補正モデル: FuelCorrectedTime = LapTime_sec + (LapNumber * 0.06)。0.06 = 1.75kg/lap × 0.035秒/kg
- 補正前後のチームランキング変動は±1-2位程度 → 均一補正では大きな順位逆転は起きない
- レース結果との相関（Spearmanρ）: R01=0.26, R02=0.32, R03=0.28。低い理由: ペースだけでなく戦略・SC・ポジション争いが結果に影響
- R01補正後トップ3: RUS/HAM/ANT（Mercedesが2名、Ferrariが1名）
- ペース≠結果: 速いドライバーが必ずしも上位フィニッシュしない（戦略・SC・インシデント）
- 均一燃料補正は精度限界がある。チーム別の燃費差は不明のため、これ以上の精密化は困難

## ロングラン抽出（T2結果 2026-04-08）
- 6条件フィルタ（グリーンフラグ/アウトイン除外/同一Stint-Compound/5周以上/107%以内）で2415クリーンラップ抽出
- VER R01戦略: HARD→MEDIUM→HARD（一般的なMED→HARDの逆戦略）
- LEC R02 Stint2 HARD = 39周（超ロングスティント）
- 107%フィルタで除外されるラップは想定より少ない → SC/VSCはTrackStatus='1'フィルタで先に除外されるため
- テストケース設計時はcross_gp_deg_rates.csvでスティント構成を事前確認すること

## タイヤデグラデーション分析（T3結果 2026-04-08）
- 2026 R01-R03の124ロングランで線形回帰実施。平均R²=0.309
- 91/124件が負のデグレート → 燃料効果（0.05-0.08秒/ラップ改善）がタイヤ劣化を上回るケースが多い
- R²<0.3の場合は信頼性が低い。燃料効果・路面変化・ドライバーリズムが混在
- Hard平均デグレートのチームランキング（負=タイヤ管理良好）: Aston Martin < Alpine < Red Bull < McLaren < Williams（唯一正の値）
- 107%フィルタ前後の差は小さい（最大0.03秒程度）。SCフィルタが効いているため
- TwoSlopeNorm(vcenter=0)でゼロ中心のヒートマップを描画するのが正負データに有効

## データ品質（T1監査結果 2026-04-08）
- 全25 CSVファイル存在確認済、LapTime異常0件、負セクター0件
- R01のみ1ドライバーでラップ数不整合（±2許容で21/22一致）。R02/R03は全一致
- FP laps.csvのLapTime NaN率: R01=19.4%、R02=20.0%、R03=20.4%（アウト/インラップで正常）
- R01/R03にquali_laps.csvが存在しない → FP→予選検証はR02のみ可能
- R02が最もデータ豊富（quali/sprint/SQ含む7セッションCSV）
- 欠損セル率は全GP 11-13%（大半はPitOutTime/PitInTime/SpeedカラムのNaN）
