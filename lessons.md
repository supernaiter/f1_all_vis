# Lessons

## Session State
- セッション開始: 本体は `current.txt` だけを読む。必要なら別エージェントが `current.txt` / `decisions.log` / `lessons.md` を20-40行に要約する (理由: 起動時token削減)
- 作業終了: 進捗は `current.txt`、判断は `decisions.log`、再発防止は `lessons.md` へ必ず追記する (理由: 次回作業を止めない)
- 状態整理: 3ファイル単体ではなく、repo全体の指示・skill・script・report・recent commit を見て流れを整理する (理由: 知見は3ファイル外にも溜まる)
- 状態ファイル更新: 短文・高密度・箇条書きで書く。日記・背景説明・重複を書かない (理由: 起動時token削減)
- 自動整理: review reportを通常commit対象にしない。必要時だけ明示してcommitする (理由: report-only commit loop防止)
- 自動整理: 通常runではreportだけを書かない。手動review時は `--no-commit` でreportを書く (理由: worktree汚れ防止)

## Control Tower
- 司令塔workspaceで作業する時: 実装に飛び込まず、repo path / GitHub issue / automation / blocker / next action を先に見る (理由: 全体監視が役割)
- 全workspaceへ変更を配る時: remote先行・履歴分岐・上流なし・権限なし・既存staged・timeoutは止めてreportへ残す (理由: force/rebase/merge事故防止)
- 古い外部タスク管理ツールへ戻りそうな設定を見つけた時: 起動設定・配布テンプレート・通常インストールskillから即削除する (理由: 作業リストをGitHub Issuesに一本化するため)

## GitHub Execution
- GitHub作業: `ready` issue を1件だけ選び、検証後に main へ commit/push し、issue へ commit hash と検証結果を書く (理由: 実行結果を追跡するため)
- scope管理: issue外のcleanupやrefactorを混ぜない。必要なら別issueへ分ける (理由: 自動実行の失敗範囲を狭くする)
- push安全: force push / rebase / merge は自動で行わない。remoteが先なら止める (理由: 履歴破壊防止)

## Human Communication
- 人間と会話する時: genshijin圧縮を使わず、平易な普通文で返す (理由: 説明品質を落とさないため)
- ユーザーが怒っている時: 造語・専門語・英語略語を避け、具体ファイル名・issue番号・変更済み/未変更だけを先に答える (理由: 抽象説明は火に油を注ぐ)
- 状態説明する時: facts / guesses / open questions を分ける (理由: 事実と推測の混同防止)

## Safety
- 安全: unrelated changes / secrets / deploy / publish / delete / billing / production data を勝手に触らない (理由: 破壊事故防止)
- 設定変更: settings.json を直接編集する前に必ず現在内容を読む (理由: 上書き事故防止)
- hook追加: 既存hook配列へ追加し、既存hookを消さない (理由: 既存自動化の破壊防止)

## Skill Design
- ペアskillは同じデータ形式を使う (理由: 保存形式と復元形式が違うと再開が壊れる)
- skillを分岐させる時は別名で分離する (理由: 既存依存先を壊さない)
