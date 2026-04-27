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

## クロスGPトレンド（T8結果 2026-04-08）
- Mercedes 123pt（R01-R03首位）、Ferrari 77pt、McLaren 38pt
- 最も安定したチーム（ConsistencyScore低い順）: Racing Bulls(0.12) > Mercedes(0.16) > Ferrari(0.20)
- 正規化ペース = (ドライバーペース - GPリーダーペース) / GPリーダーペース * 100 (%)
- サーキット差を除去するにはリーダー比正規化が有効。絶対値では比較不可（R01=82秒台 vs R02=96秒台）
- 3GPだけでトレンドを語るのは統計的に弱い。シーズン前半（6-8GP）まで待つべき

## セーフティカー影響（T7結果 2026-04-08 R03日本GP）
- SC期間: Lap22-27（race_control_messages.csvから自動特定成功）
- SC中ピット: 11名/22名（約半数がSCを利用してピット）
- 最大勝者: PIA +3位, OCO +3位（SCピットで有利なポジションに）
- 最大敗者: ALB -4位, GAS -3位（SCでアンダーカットされた）
- SC前後のポジション変動は13/22名で発生（59%）→ SCは戦略を大きく左右する
- race_control_messages.csvのMessageカラムでSC検出: "SAFETY CAR DEPLOYED"で開始、"SAFETY CAR IN THIS LAP"で終了

## チームメイト比較（T5結果 2026-04-08）
- 30ペア（10チーム×3GP）全生成。PaceDelta範囲: -1.13〜+0.46秒
- Ferrari R01 LEC-HAM差=0.12秒（接戦）。Mercedes R01 RUS-ANT差=-0.05秒（さらに接戦）
- 最大差: Cadillac(PER-BOT)で-1.13秒 → バックマーカーほどチームメイト差が大きい傾向
- Team列は race_results.csvの TeamName をそのまま使用（"Red Bull Racing"等フルネーム）
- GP列はGP名のみ（"Australia"等）で R01_ prefix なし → クエリ時に注意

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

## FP→予選予測（T6結果 2026-04-08 R02中国GP）
- スプリントWE（FP1のみ）の系統バイアスは+1.25秒（通常WEの+0.34秒の約3.7倍）
- 順位相関はスプリントWEでも高い: Spearman ρ=0.868（通常WE: 0.82）
- FP1でシミュラップなしドライバーが22名中6名（STR/SAI/BOT/ALO/LIN/PER）→ スプリントWEではチームがFP1でシミュラップ優先度を下げる可能性
- fp_laps.csvのSession列は動的に確認すること: スプリントWEはFP1のみ、通常WEはFP1-3
- quali_laps.csvにはSession列がない（fp_laps.csvとは異なる）→ ドライバー別ベスト集計は全ラップ対象でOK

## Git Pilot
- 作業開始: GitHub issue契約確認→ready 1件だけ実装 (理由: scope拡散防止)
- 完了時: commit hash + verificationをissue commentへ書く (理由: 再開可能)

## Session Brief
- 人間へ説明する時: 直接答え、短文、平易語、事実/推測/未解決を分ける (理由: 非専門家も追える説明にするため)
- 人間と会話する時: genshijin圧縮を使わず、平易な普通文で返す。圧縮は状態ファイル・作業ログだけに使う (理由: 読みやすさを壊さないため)




## Current Model

- GitHub Issues: active work list.
- `ready`: automation executable.
- `current.txt`: short startup cache only.
- `kizami`: recovery only.

## Watchpoints

- Do not add `ready` without Goal / Scope / Acceptance / Verification / Non-goals.
- Stage only current issue files.
- Commit hash + verification must go back to GitHub issue.
- Old external task trackers: no new progress / blocker / decision.
- Human explanation rule: direct answer, plain words, facts/guesses/questions separated, missing or broken items named.
- Human conversation rule: normal plain sentences. Genshijin compression only for state files and work notes.


updated: 2026-04-27
style: short bullets, plain words, no jargon

[FACTS]
- GitHub Issues = active work list.
- current.txt = local startup cache, max 50 lines.
- decisions.log = decision history.
- lessons.md = reusable behavior rules.

[STARTUP]
- Read current.txt first.
- Use source files directly only when brief lacks needed detail.

[WORK]
- Only ready GitHub issue can be automation work.
- One run = one issue.
- Success: commit hash + verification to issue.
- Blocker: state exact missing piece.
- No deploy/delete/publish unless issue permits.

[LANGUAGE]
- Human conversation: normal plain Japanese sentences.
- Do not use genshijin compression for human explanations unless user asks.
- Genshijin compression: state files, work logs, internal task notes only.
- Avoid jargon, coined words, inner jokes.
- If technical term needed: explain immediately.
- Separate facts, guesses, open questions.
- Say missing/broken items exactly.

## Compacted Rules
- セッション開始: 本体は `current.txt` だけを読む。必要なら別エージェントが `current.txt` / `decisions.log` / `lessons.md` を20-40行に要約する (理由: 起動時token削減)
- 作業終了: 進捗は `current.txt`、判断は `decisions.log`、再発防止は `lessons.md` へ必ず追記する (理由: 次回作業を止めない)
- GitHub作業: `ready` issue を1件だけ選び、検証後に main へ commit/push し、issue へ commit hash と検証結果を書く (理由: 実行結果を追跡するため)
- 安全: unrelated changes / secrets / deploy / publish / delete / billing / production data を勝手に触らない (理由: 破壊事故防止)
- 人間向け会話: 平易な普通文で返す。圧縮文は状態ファイルと作業ログだけに使う (理由: 説明品質を落とさない)
- Use GitHub Issues as the active work list.
- Treat old task trackers as history only.
- Do not create or update task state outside GitHub Issues.
- Use commits on `main` as implementation records.
- Use CI, tests, lint, build, or smoke checks as verification records.
- List open GitHub Issues.
- Select exactly one issue with label `ready`.
- If no `ready` issue exists: stop and report `not ready`.
- If issue has `blocked`, `needs-human`, `needs-contract`, or `no-autopilot`: skip it.
- If issue lacks Goal, Scope, Acceptance, or Verification: remove `ready`, comment the missing fields, and stop.
- If local work already exists, continue only when it maps to the selected ready issue.
- Read the selected GitHub Issue.
- Inspect repo state before editing.
- If unrelated uncommitted changes exist: preserve them and do not stage them.
- If the safe edit path is unclear: stop and comment the blocker.
- Implement the smallest change that satisfies the issue.
- Do not expand scope for cleanup, refactor, or polish unless required by the issue.
- Run the closest deterministic check first: test, lint, build, or smoke.
- If verification fails and the fix is in scope: fix and rerun the check.
- If verification fails and the cause is unclear: stop, mark blocked, and comment the failing command.
- If verification passes: commit only the files changed for this issue.
- Push `main`.
- Comment on the issue with summary, changed files, verification, commit hash, and next action.
- Close the issue when acceptance is met.
- Never overwrite or revert unrelated user changes.
- No deploy, publish, billing, credential, production data, or destructive operation without explicit human approval.
- If CI fails after a pushed local-code change and the responsible commit is clear: revert that commit and write the result to the issue.
- If failure cause is unclear: stop and write a blocker comment.
- If secrets or credentials appear in the diff: stop and remove them before commit.
- Answer the question directly first.
- Use normal plain sentences for human conversation.
- Do not use genshijin compression for human-facing explanations unless the user explicitly asks.
- Use genshijin compression only for state files, work logs, and internal task notes.
- Avoid jargon. If a technical term is necessary, explain it immediately.
- Separate facts, guesses, and open questions.
- State missing or broken items exactly.
- Do not overclaim or hide weak results.
- Find project-specific rules below.
- Convert each value judgment into yes/no checks before acting.
- If a rule says something must be rejected, blocked, or noindexed: treat it as a hard gate.
- If project-specific rules conflict with this common policy: follow the stricter safety rule and write the conflict to the issue.
- If the project-specific rule is too vague to execute: mark `needs-contract`, ask for the missing decision, and stop.
- GitHub Issues are the only active work list for tasks, decisions, blockers, and execution results.
- Repository files hold durable policy, templates, and reusable operating rules.
- `current.txt` is a local startup cache.
- Before running `uv` or other heavy tooling: check free disk (`df -h /`) and stop if near-full.
- When posting shell commands in `gh issue comment`: avoid backticks; prefer a quoted heredoc (`<<'EOF'`) to prevent command substitution.
