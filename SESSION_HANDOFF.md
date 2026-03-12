# SESSION_HANDOFF.md — F1 Fantasy 開発計画

## 最終更新: 2026-03-07

---

## 1. 完了した作業

### Block 0: 環境準備 + 2026価格データ
- 2026年用ディレクトリ構造作成: `data/f1_fantasy/2026/{raw/prices, analysis}`
- 全22ドライバー + 11コンストラクターの価格をJSON + SQLiteに格納
  - Web調査で確認済み（verified=true）: 12ドライバー + 7コンストラクター
  - 推定値（verified=false）: 10ドライバー + 4コンストラクター
- `f1_fantasy_2026_price_scraper.py` 作成（Cookie認証 + 手動JSONフォールバック対応）

### Block 1: 2025シーズン分析基盤
- **Task 1A**: 全21ドライバーの年間サマリー（avg/std/max/min/negative/efficiency）
  - 得点パターン5分類: 安定高得点型(VER), バジェット安定型(TSU,OCO), DNFリスク型(13名), 等
- **Task 1B**: 2025→2026マッピング + 期待値算出
  - confidence_factor: 同チーム0.80, リブランド0.70, 新チーム0.40-0.50
  - 期待コスパTOP3: BEA(1.10 pts/$M), OCO(0.92), NOR(0.88)
- **Task 1C**: ルール変更の戦略的影響メモ（DRS廃止、Sprint DNF半減、最低価格引下げ等）
- **コンストラクター分析**: MCLが圧倒的効率(44.7 pts/$M)、HASがコスパ良好(29.8)
- **スプリント定量化**: VER/NOR +15-17pts bonus、LEC -11pts（2025実績）

### Block 2: チーム最適化エンジン
- **Task 2A**: 913,610通り総当たり探索（0.8秒）
  - #1: NOR | ANT | BEA | OCO | DRU + MCL | HAS (133.7pts, $98.7M)
- **Task 2B**: 2xブースト分析 — NOR推奨
- **Task 2C**: DNFリスク評価 — HIGH: ALO, STR, HUL, BOR
- **Task 2D**: チップ戦略 — R1全チップ温存推奨
- **Task 2E**: 感度分析 6シナリオ — CORE: BEA, OCO, NOR, ALB

### Block 3: トップ得点者分析（スクリプト準備）
- `f1_fantasy_top_scorer_pdf.py` 作成（Phase 2データ取得後に実行可能）

### Block 4: 2025シーズンファクトブック ✅
- `f1_fantasy_2025_factbook_generator.py`（62KB, 標準ライブラリのみ）
- 出力: 452KB HTML、モバイル対応、sticky column

### Block 5: FP分析テンプレート
- `FP_ANALYSIS_TEMPLATE_SPEC.md` 作成（セクションA-E仕様書）

### Block 6: CLAUDE.md改善 ✅
- 予選シミュ識別改訂、分析落とし穴追加、FP→予選予測手法追加

### Block 7: 2026 R1 オーストラリアGP FP分析レポート ✅ NEW
- **`fp_analysis_2026_r01.py`** 作成（2161行, 標準ライブラリのみ）
- **`fetch_f1_article.py`** 作成（F1公式記事テキスト抽出ユーティリティ）
- **`serve_reports.py`** 作成（ライブリロード付きHTTPサーバー）
- **出力**: `data/2026_R01_Australia/fp_analysis_2026_r01.html`（403KB）

#### レポート構成（全セクション実装済み）:
| セクション | 内容 | 状態 |
|-----------|------|------|
| 目次 | 6セクションへのリンク | ✅ |
| 概要 | FP1/FP2ラップ数、リザーブ、トラックエボリューション | ✅ |
| A. スティントマップ & 分類 | タイムライン可視化、LR/QS/OTHER分類、スティント一覧 | ✅ |
| B. 予選ペース予測 | 22ドライバー、FP2ベース＋FP1フォールバック | ✅ |
| C. ロングラン分析 | 12スティント(6チーム)、streak≥3連続クリーンラップ、デグ | ✅ |
| D. レースペース推定 | 11チーム、M/H補正ペース | ✅ |
| E. Fantasy予測 & 戦略 | 22ドライバースコアカード、チーム入替推奨 | ✅ |
| F. Practice Debrief | F1公式記事サマリー（Cookie未設定=3セクションのみ） | ✅ 部分的 |

#### 実装済み分析機能:
- **スティントマップ**: タイムライン可視化（FP1/FP2別、コンパウンド色分け）
- **スティント分類**: LR(ロングラン)、QS(予選シム)、OTHER(その他)の3分類
- **ロングラン識別**: streak≥3連続クリーンラップ方式（旧107%散在ラップ方式から改善）
- **予選シミュレーション識別**: TyreLife≤8 + 103%フィルタ（個別ラップ判定）
- **トラックエボリューション補正**: FP1→FP2中央値差で補正
- **燃料補正**: 0.06s/lap（暫定値）
- **コンパウンド補正**: M-H実測差でHペースを推定
- **フリー走行プログラム解説**: 22ドライバー×4要素（概観/LR評価/QS評価/特記）
- **チーム競争力評価**: 11チーム×セクター特性/LR/レースペース/総合寸評
- **チームメイト比較**: 11チーム×予選差/セクター別/スピードトラップ/LR比較
- **Practice Debrief**: F1.com記事のRSC抽出（Cookie対応）

#### モバイル対応:
- viewport meta、@media 768px、横スクロール
- sticky header + sticky first column
- back-to-topボタン
- `serve_reports.py` でTailscale経由のリモートアクセス対応

---

## 2. 主要な分析結果サマリー

### 推奨チーム（R1 オーストラリアGP）
```
ドライバー: NOR | ANT | BEA | OCO | DRU
コンストラクター: MCL | HAS
期待: 133.7pts | コスト: $98.7M
2xブースト: NOR
チップ: 全温存
```

### コア vs 可変枠
```
CORE（必須）: BEA, OCO, NOR, ALB
FLEX（FPデータ次第）: STR, ANT, DRU, HUL
```

---

## 3. 残タスク

### 優先度1: F1.com Cookie認証セットアップ 🔜
F1公式Practice Debrief全文取得に必要。Fantasy APIにも使用可能。
```
手順:
1. PCでChromeを開き、formula1.comにログイン（F1 Unlocked無料登録）
2. Chrome拡張「Get cookies.txt LOCALLY」をインストール
   https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc
3. formula1.comを開いた状態で拡張アイコン → Export（Netscape形式）
4. cookies.txtをWSL側にコピー:
   cp /mnt/c/Users/<name>/Downloads/cookies.txt ~/cookies_f1.txt
5. fp_analysis_2026_r01.py の COOKIE_FILE を更新:
   COOKIE_FILE = '/home/redpark92/cookies_f1.txt'
6. レポート再生成 → Practice Debriefが全文表示される
```
**影響範囲**: Practice Debrief全文取得、F1 Fantasy APIアクセス

### 優先度2: R1予選・決勝後の精度検証
```
1. 予選後: FP予測 vs 実予選結果を比較
   - Spearman相関、順位MAE、系統バイアスを計測
   - 2025 Italy GP実績(Spearman=0.82)との比較
2. 決勝後: レースペース予測 vs 実レース結果
   - ポジションゲイン予測精度
   - Fantasy実ポイント vs 予測ポイント
3. 結果をCLAUDE.mdの精度指標に反映
```

### 優先度3: R2中国GP対応（テンプレート化）
```
1. fp_analysis_2026_r01.py → fp_analysis_template.py に汎用化
   - 設定セクション(YEAR, GP_NAME, ROUND_NUMBER等)のみ変更で動作
   - PRACTICE_DEBRIEF_URLをGPごとに設定
   - Sprint GPフォーマット対応（FP1のみ＋Sprint予測セクション追加）
2. R2中国GPはSprint週末 → Sprint分析セクションが必要
3. gp_database_builder.py のコンフィグ切替
```

### 優先度4: Phase 2 Fantasy APIデータ
```bash
# Cookie取得後に実行可能:
python f1_fantasy_phase2_leaderboard.py --cookie-file ~/cookies_f1.txt --top 20
python f1_fantasy_2026_price_scraper.py --cookie-file ~/cookies_f1.txt
python f1_fantasy_top_scorer_pdf.py --top 5
```

### 優先度5: コンテンツ制作パイプライン（将来）
- ファクトブックの自動化・定期更新フロー構築
- YouTube/X用グラフ自動生成（CLAUDE.md仕様準拠）
- 英語版ファクトブックの対応
- GPごとのPractice Debriefサマリー蓄積

---

## 4. ファイル構成

```
MSIllustrated/
├── CLAUDE.md                              ← プロジェクト設定
├── SESSION_HANDOFF.md                     ← このファイル
│
├── # 2026 R1 FP分析（Block 7）
├── fp_analysis_2026_r01.py                ← FPレポート生成（2161行, 403KB HTML出力）
├── fetch_f1_article.py                    ← F1公式記事テキスト抽出（RSCパーサー）
├── serve_reports.py                       ← ライブリロード付きHTTPサーバー
│
├── # F1 Fantasy 2025 ファクトブック
├── f1_fantasy_2025_factbook_generator.py  ← ファクトブックHTML生成（62KB）
│
├── # F1 Fantasy 2026
├── f1_fantasy_2026_price_scraper.py       ← 2026価格取得
├── f1_fantasy_optimizer.py                ← チーム最適化エンジン
├── f1_fantasy_top_scorer_pdf.py           ← トップ得点者PDFビジュアル
│
├── # F1 Fantasy 2025（既存）
├── f1_fantasy_phase1_collector.py         ← Phase 1: 公開データ収集
├── f1_fantasy_phase2_leaderboard.py       ← Phase 2: 認証APIデータ
├── f1_fantasy_phase3_analysis.py          ← Phase 3: 分析パイプライン
│
├── # GP分析（既存 — 2025 Italy用、レガシー）
├── gp_database_builder.py                 ← DB構築
├── fp_longrun_analysis_v2.py              ← ロングラン分析（旧）
├── fp_quali_prediction.py                 ← 予選予測（旧）
│
└── data/
    ├── f1_fantasy/
    │   ├── 2025/
    │   │   ├── f1_fantasy_2025.db
    │   │   ├── raw/price_history_2025.json
    │   │   └── analysis/f1_fantasy_2025_factbook.html
    │   └── 2026/
    │       ├── f1_fantasy_2026.db
    │       ├── raw/prices/f1_fantasy_2026_prices.json
    │       ├── analysis/
    │       └── FP_ANALYSIS_TEMPLATE_SPEC.md
    ├── 2026_R01_Australia/
    │   ├── gp_weekend.db                  ← FP1+FP2 SQLite
    │   ├── fastf1/                        ← Parquet生データ
    │   ├── summary/                       ← CSVサマリー
    │   └── fp_analysis_2026_r01.html      ← レポート出力（403KB）
    └── 2025_R15_Italy/                    ← イタリアGP参考データ
```

---

## 5. 技術メモ

### 実行環境
- WSL2 (Linux 6.6.87), Python 3.12.3
- venv: `/home/redpark92/f1env` — FastF1 3.8.1, pandas, numpy, matplotlib, scipy, pyarrow
- 有効化: `source /home/redpark92/f1env/bin/activate`
- FastF1キャッシュ: `/home/redpark92/f1_cache`
- レポート配信: `python3 serve_reports.py`（Tailscale経由ポート8080）

### FP分析の主要データ構造
```python
# fp_analysis_2026_r01.py 内の主要変数
stint_map_data[(sess, drv)]  # → スティント一覧（FP概観に使用）
long_runs                     # → ロングラン（Streak≥3のクリーンラップ連続）
qs_by_stint                   # → 予選シミュレーション（TyreLife≤8, 103%）
quali_prediction              # → 予選ペース推定（22ドライバー）
race_pace                     # → レースペース推定（11チーム）
fantasy_cards                 # → Fantasyスコアカード（22ドライバー）
```

### F1.com記事抽出（fetch_f1_article.py）
- Next.js RSC (React Server Components) データからT-blockを抽出
- Freewall前: 約3セクション（Cookie不要）
- Freewall後: 残り全セクション（Cookie必要）
- Cookie形式: Netscape形式（curl -b 対応）
