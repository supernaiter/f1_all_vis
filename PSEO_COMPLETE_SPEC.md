# pSEO 2.0 完全統合仕様 — Motorsports-Visualised
## 39カード種 × 組み合わせ爆発 = 10,000+ページ

---

## 思想
- JSON dataset + specialized renderer = データとプレゼンテーション完全分離
- 1テンプレート × N組み合わせ = Nページ自動生成
- 3種Renderer: 詳細（1対1）/ 比較（N横並び）/ ランキング（Top/Bottom N）
- pipeline.sh一発で全ページ再生成

---

## 全39カード種 × 爆発軸マッピング

### TYPE-A: GPごと生成（24GP × カード種）
毎GPでデータが変わる。pipeline.shでGPごとに自動生成。

| # | カード名 | テンプレート | データソース | 爆発数/GP |
|---|---------|-------------|-------------|----------|
| A1 | Lap 1 Position Delta Swarm | [gp]/lap1-delta.astro | race_results.csv (FastF1) | 1 |
| A2 | Tyre Cliff Detector | [gp]/tyre-cliff.astro | race_laps.csv + FPプロファイル (f1_analysis) | 1 |
| A3 | Braking Point Overlay | [gp]/braking-point.astro | OpenF1 GPS (f1_analysis/etl/openf1.py) | 1 |
| A4 | Corner Speed Fingerprint | [gp]/corner-speed.astro | OpenF1テレメトリ + コーナー定義 | 1 |
| A5 | Overtake Replay Minimap | [gp]/overtake-replay.astro | ポジション変化検出 (f1_analysis/etl/overtake.py) | 1 |
| A6 | Constructor Pace Variance | [gp]/pace-variance.astro | race_laps.csv (FastF1) | 1 |
| A7 | What If Strategy Simulator | [gp]/what-if.astro | race_laps + pit_stops + レースペース予測 (f1_analysis) | 1 |

**URL: /cards/{gp}/lap1-delta/ 等**
**24GP × 7種 = 168ページ**

---

### TYPE-B: ドライバー2者比較（nC2ペア × カード種）
同一テンプレートに2名のドライバーIDを差し替えるだけ。

| # | カード名 | テンプレート | データソース | 爆発基数 |
|---|---------|-------------|-------------|---------|
| B1 | Career Arc Overlay | [pair]/career-arc.astro | 歴代統計（静的） + f1db | 435ペア |
| B2 | H2H Simulator | [pair]/h2h-sim.astro | Teammate Chain Elo (ベイズスキャン活用) | 435ペア |
| B3 | Lifetime Timeline | [pair]/lifetime.astro | キャリアイベントDB（手動キュレーション） | 435ペア |
| B4 | Milestone Race | [pair]/milestone.astro | 歴代統計（静的） | 435ペア |

**URL: /compare/drivers/ver-vs-ham/career-arc/ 等**

ドライバープール:
- 現役20名: 20C2 = 190ペア
- 歴代トップ30（SEN,PRO,MSC,HAM,VER,ALO,VET,RAI,ROS,BUT,RIC,LEC,NOR,SAI,PIA,RUS,PER,ANT,SAT,GAS,OCO,BOT,HUL,MAG,ALB,GRO,BAR,MAS,CLA,PIQ）: 30C2 = 435ペア
- **435ペア × 4種 = 1,740ページ**

---

### TYPE-C: ドライバー3者比較（キュレーション × カード種）
全展開は20C3=1,140で多すぎるため、主要トリプルをキュレーション。

| # | カード名 | テンプレート | 爆発基数 |
|---|---------|-------------|---------|
| C1 | Career Arc (3者) | [triple]/career-arc.astro | 100トリプル |
| C2 | Lifetime Timeline (3者) | [triple]/lifetime.astro | 100トリプル |

キュレーション例: VER-HAM-MSC, VER-HAM-SEN, VER-LEC-NOR, HAM-ALO-VET, SEN-PRO-MSC...
**100 × 2種 = 200ページ**

---

### TYPE-D: コース2者比較（24C2ペア × カード種）

| # | カード名 | テンプレート | データソース | 爆発基数 |
|---|---------|-------------|-------------|---------|
| D1 | Circuit Comparison Radar | [pair]/radar.astro | コース特性DB（静的） | 276ペア |
| D2 | Era-Adjusted Qualifying | [pair]/era-adjusted.astro | FastF1予選データ (2018-) | 276ペア |

**URL: /compare/circuits/monza-vs-spa/radar/ 等**
**276 × 2種 = 552ページ**

---

### TYPE-E: チーム2者比較（10C2ペア × GP × カード種）

| # | カード名 | テンプレート | データソース | 爆発基数 |
|---|---------|-------------|-------------|---------|
| E1 | Team DNA Radar | [pair]/dna.astro | FastF1テレメトリ + OpenF1 | 45ペア × 24GP |
| E2 | Pace Variance Compare | [pair]/variance.astro | race_laps.csv | 45ペア × 24GP |

**URL: /compare/teams/2026-r01/mercedes-vs-ferrari/dna/ 等**
**45 × 24 × 2種 = 2,160ページ**

---

### TYPE-F: シーズン横断（GPごと累積更新）

| # | カード名 | テンプレート | データソース |
|---|---------|-------------|-------------|
| F1 | Title Probability | season/title-prob.astro | チャンピオンシップ予測 (f1_analysis: 76シーズン×8軸ベイズ) |
| F2 | Season Momentum | season/momentum.astro | 全GPペースデータ集計 |
| F3 | Power Ranking Shift | season/power-ranking.astro | 全GP結果集計 |
| F4 | Championship Swing | season/championship.astro | ポイント推移 |
| F5 | Upgrade Impact | season/upgrades.astro | 手動 + ペースデルタ |
| F6 | Constructor Standings Evolution | season/constructors.astro | ポイント推移 |

**URL: /season/2026/title-probability/ 等**
**6ページ（毎GP後に再生成）**

---

### TYPE-G: 歴代ランキング / 単体分析（静的ピラー）

| # | カード名 | テンプレート | データソース |
|---|---------|-------------|-------------|
| G1 | GOAT Index | insights/goat-index.astro | 歴代統計 + チャンピオンシップ予測データ |
| G2 | Teammate Eliminator | insights/teammate-eliminator.astro | h2h_engine.py + 歴代H2Hデータ |
| G3 | Clutch Rating | insights/clutch.astro | 歴代統計（最終5戦 vs シーズン平均） |
| G4 | Win Style DNA | insights/win-style.astro | 歴代勝利分類データ |
| G5 | Points If... | insights/points-if.astro | 歴代レース結果再計算 |
| G6 | One-Lap King | insights/one-lap.astro | 歴代予選統計 |
| G7 | Teammate Chain Elo | insights/elo.astro | ベイズシグナルスキャン (f1_analysis: 3506ペア) |
| G8 | Dominance Percentile | insights/dominance.astro | 歴代フィールド内順位統計 |
| G9 | Wet Weather Index | insights/wet.astro | 雨天ドライバー分析 (f1_analysis) |

**URL: /insights/goat-index/ 等**
**9ページ**

---

### TYPE-H: ティア表（静的、議論喚起コンテンツ）

| # | カテゴリ | テンプレート |
|---|---------|-------------|
| H1 | All-time Greatest | tiers/all-time.astro |
| H2 | Clutch Performance | tiers/clutch.astro |
| H3 | Wet Weather Kings | tiers/wet.astro |
| H4 | One-Lap Pace | tiers/one-lap.astro |
| H5 | Overachiever | tiers/overachiever.astro |
| H6 | 2024 Season | tiers/season-2024.astro |
| H7 | Pay Driver Hall of Shame | tiers/pay-drivers.astro |
| H8 | Championship Choke Artists | tiers/choke.astro |
| H9 | Wasted Talent | tiers/wasted.astro |
| H10 | Villain Era | tiers/villain.astro |
| H11 | Team Atmosphere Destroyer | tiers/destroyer.astro |
| H12 | Most Underrated | tiers/underrated.astro |

ティア表は全カテゴリ共通テンプレート1つ + JSONデータで切替も可能。
**URL: /tiers/choke-artists/ 等**
**12ページ（または共通テンプレート1つ × 12 JSON）**

---

### TYPE-I: 既存H2H（稼働中）

| # | カード名 | テンプレート |
|---|---------|-------------|
| I1-5 | Hub / Pace / Sectors / Speed / Stints | h2h/[...slug]/*.astro |

**24GP × 45ペア × 5ページ = 5,400ページ**

---

## 合計ページ数

| TYPE | 計算 | ページ数 |
|------|------|---------|
| A. GPカード | 24 × 7 | 168 |
| B. ドライバー2者 | 435 × 4 | 1,740 |
| C. ドライバー3者 | 100 × 2 | 200 |
| D. コース2者 | 276 × 2 | 552 |
| E. チーム2者×GP | 45 × 24 × 2 | 2,160 |
| F. シーズン横断 | 6 | 6 |
| G. ピラー | 9 | 9 |
| H. ティア表 | 12 | 12 |
| I. H2H（既存） | 24 × 45 × 5 | 5,400 |
| **合計** | | **10,247** |

---

## データパイプライン統合

### リポジトリ間のデータフロー

```
f1_analysis (既存)                    f1_all_vis (本番)
┌─────────────────────┐              ┌──────────────────────┐
│ etl/openf1.py       │──GPS/テレメ──→│ cards/[gp]/ TYPE-A   │
│ etl/overtake.py     │──ポジション──→│ A5 Overtake Replay   │
│ etl/fastf1.py       │──ラップ────→│ export_race_data.py  │
│                     │              │                      │
│ scripts/            │              │ scripts/             │
│  build_features.py  │──特徴量────→│  card_data_gen.py    │
│  race_pace_analyzer │──ペース予測─→│  A7 What If          │
│                     │              │                      │
│ out/                │              │ data/                │
│  championship_*     │──76S×8軸───→│  F1 Title Prob       │
│  bayes_signal_scan/ │──3506ペア──→│  G7 Elo, B2 H2H Sim │
│  grid_finish_*      │──60レース──→│  G1 GOAT, D2 Era-Adj │
│                     │              │                      │
│ asr/transcribe.py   │──無線テキスト→│  (将来: Radio Sent.) │
│ openF1_analyzer/    │──リアルタイム→│  (将来: Live cards)  │
└─────────────────────┘              └──────────────────────┘
```

### 統合pipeline.sh

```bash
#!/bin/bash
# 使い方: ./pipeline.sh 2026 Bahrain 4 --build
YEAR=$1; GP=$2; ROUND=$3; PADDED=$(printf '%02d' $ROUND)
DIR="data/${YEAR}_R${PADDED}_${GP}"

echo "=== Stage 1: FastF1 Export ==="
uv run export_race_data.py --year $YEAR --gp $GP --round $ROUND

echo "=== Stage 2: H2H Engine (既存, 45ペア) ==="
uv run h2h_engine.py --dir $DIR --top10

echo "=== Stage 3: GP Card Data (TYPE-A: 7種JSON) ==="
uv run card_data_generator.py --dir $DIR

echo "=== Stage 4: Team Compare (TYPE-E: 45ペアJSON) ==="
uv run team_compare_generator.py --dir $DIR

echo "=== Stage 5: Season Aggregate (TYPE-F: 6種JSON) ==="
uv run season_aggregator.py --year $YEAR

if [[ "$4" == "--build" ]]; then
  echo "=== Stage 6: Astro Build ==="
  cd site && npx astro build
fi

# 初回のみ（静的データ、GP非依存）:
# uv run driver_compare_generator.py --all    # TYPE-B: 435ペア×4種JSON
# uv run circuit_compare_generator.py --all   # TYPE-D: 276ペア×2種JSON
# uv run pillar_data_generator.py             # TYPE-G: 9種JSON
# uv run tier_data_generator.py               # TYPE-H: 12種JSON
```

### f1_analysisからの取り込みスクリプト

```bash
#!/bin/bash
# f1_analysisの成果物をf1_all_visのdata/に取り込む
F1A="/Volumes/intersd2/2026_1_4/f1_analysis"
DEST="data/f1_analysis_imports"

mkdir -p $DEST

# チャンピオンシップ予測データ（76シーズン）
cp -r $F1A/out/championship_* $DEST/

# ベイズシグナルスキャン（3506ペア）
cp -r $F1A/out/bayes_signal_scan/ $DEST/

# グリッド-最終順位分析（60レース）
cp -r $F1A/out/grid_finish_dry_analysis/ $DEST/

# 雨天分析
cp $F1A/out/*wet* $DEST/ 2>/dev/null || true
cp $F1A/out/*rain* $DEST/ 2>/dev/null || true

echo "Import complete: $(ls $DEST | wc -l) items"
```

---

## Astroページ構造

```
site/src/pages/
├── index.astro                                    ← ホーム
│
├── h2h/[...slug]/                                 ← TYPE-I（既存、5,400p）
│   ├── index.astro
│   ├── pace.astro
│   ├── sectors.astro
│   ├── speed.astro
│   └── stints.astro
│
├── cards/[gp]/[card].astro                        ← TYPE-A（168p）
│   getStaticPaths: listGPs() × 7カード種
│
├── compare/
│   ├── drivers/[pair]/[type].astro                ← TYPE-B（1,740p）
│   │   getStaticPaths: listDriverPairs() × 4カード種
│   ├── drivers/[triple]/[type].astro              ← TYPE-C（200p）
│   │   getStaticPaths: listDriverTriples() × 2カード種
│   ├── circuits/[pair]/[type].astro               ← TYPE-D（552p）
│   │   getStaticPaths: listCircuitPairs() × 2カード種
│   └── teams/[gp]/[pair]/[type].astro             ← TYPE-E（2,160p）
│       getStaticPaths: listGPs() × listTeamPairs() × 2カード種
│
├── season/[type].astro                            ← TYPE-F（6p）
│   getStaticPaths: ['title-prob','momentum','power-ranking','championship','upgrades','constructors']
│
├── insights/[slug].astro                          ← TYPE-G（9p）
│   getStaticPaths: listPillarPages()
│
└── tiers/[slug].astro                             ← TYPE-H（12p）
    getStaticPaths: listTierPages()
```

---

## data.ts 拡張

```typescript
// ===== 既存 =====
export function listGPs(): GPInfo[] { ... }
export function loadH2HIndex(dir: string): H2HIndex { ... }
export function loadH2HAnalysis(dir: string, pair: string): Analysis { ... }

// ===== TYPE-A: GPカード =====
export function loadCardData(gp: string, cardType: string): CardData { ... }
// data/{gp}/cards/{cardType}.json を読む

// ===== TYPE-B: ドライバー2者比較 =====
export function listDriverPairs(): string[] { ... }
// data/drivers/pairs/ 配下のディレクトリ名一覧
export function loadDriverCompare(pair: string, type: string): DriverCompareData { ... }
// data/drivers/pairs/{pair}/{type}.json を読む

// ===== TYPE-C: ドライバー3者比較 =====
export function listDriverTriples(): string[] { ... }
// data/drivers/triples/ 配下

// ===== TYPE-D: コース2者比較 =====
export function listCircuitPairs(): string[] { ... }
export function loadCircuitCompare(pair: string, type: string): CircuitCompareData { ... }

// ===== TYPE-E: チーム2者比較 =====
export function listTeamPairs(): string[] { ... }
export function loadTeamCompare(gp: string, pair: string, type: string): TeamCompareData { ... }

// ===== TYPE-F: シーズン横断 =====
export function loadSeasonData(type: string): SeasonData { ... }

// ===== TYPE-G: ピラー =====
export function listPillarPages(): string[] { ... }
export function loadPillarData(slug: string): PillarData { ... }

// ===== TYPE-H: ティア =====
export function listTierPages(): string[] { ... }
export function loadTierData(slug: string): TierData { ... }
```

---

## データ出力ディレクトリ構造

```
data/
├── 2026_R01_Australia/              ← GPごと（既存 + 拡張）
│   ├── export/                      ← FastF1 CSV（既存）
│   ├── h2h/                         ← H2Hペア分析（既存）
│   └── cards/                       ← NEW: TYPE-A用JSON
│       ├── lap1_delta.json
│       ├── tyre_cliff.json
│       ├── braking_point.json
│       ├── corner_speed.json
│       ├── overtake_replay.json
│       ├── pace_variance.json
│       └── what_if.json
│
├── drivers/                         ← NEW: TYPE-B,C用
│   ├── master.json                  ← 30名の歴代統計
│   ├── pairs/                       ← 435ペア
│   │   ├── ver-vs-ham/
│   │   │   ├── career_arc.json
│   │   │   ├── h2h_sim.json
│   │   │   ├── lifetime.json
│   │   │   └── milestone.json
│   │   ├── ver-vs-msc/
│   │   └── ... (433 more)
│   └── triples/                     ← 100トリプル
│       ├── ver-ham-msc/
│       │   ├── career_arc.json
│       │   └── lifetime.json
│       └── ...
│
├── circuits/                        ← NEW: TYPE-D用
│   ├── master.json                  ← 24コース特性
│   └── pairs/                       ← 276ペア
│       ├── monza-vs-spa/
│       │   ├── radar.json
│       │   └── era_adjusted.json
│       └── ...
│
├── teams/                           ← NEW: TYPE-E用
│   └── 2026_R01/
│       ├── mercedes-vs-ferrari/
│       │   ├── dna.json
│       │   └── variance.json
│       └── ...
│
├── season/                          ← NEW: TYPE-F用
│   └── 2026/
│       ├── title_probability.json
│       ├── momentum.json
│       ├── power_ranking.json
│       ├── championship.json
│       ├── upgrades.json
│       └── constructors.json
│
├── insights/                        ← NEW: TYPE-G用
│   ├── goat_index.json
│   ├── teammate_eliminator.json
│   ├── clutch.json
│   ├── win_style.json
│   ├── points_if.json
│   ├── one_lap.json
│   ├── elo.json
│   ├── dominance.json
│   └── wet_weather.json
│
├── tiers/                           ← NEW: TYPE-H用
│   ├── all_time.json
│   ├── clutch.json
│   ├── wet.json
│   ├── one_lap.json
│   ├── overachiever.json
│   ├── season_2024.json
│   ├── pay_drivers.json
│   ├── choke.json
│   ├── wasted.json
│   ├── villain.json
│   ├── destroyer.json
│   └── underrated.json
│
└── f1_analysis_imports/             ← f1_analysisからの取り込み
    ├── championship_*/
    ├── bayes_signal_scan/
    └── grid_finish_dry_analysis/
```

---

## 実装順序

### Phase 0（今すぐ）: 1ペア1種で貫通テスト
1. `data/drivers/pairs/ver-vs-ham/career_arc.json` を手動作成
2. `data.ts` に `listDriverPairs()` + `loadDriverCompare()` 追加
3. `compare/drivers/[pair]/career-arc.astro` 作成
4. ビルドして `/compare/drivers/ver-vs-ham/career-arc/` が生成されることを確認
5. 同テンプレートで3ペア分（ver-vs-ham, ver-vs-msc, ham-vs-alo）が自動生成されることを確認

### Phase 1（今週）: データジェネレーター
1. `driver_compare_generator.py` — 30名マスターデータから435ペア×4種JSONを一括生成
2. `circuit_compare_generator.py` — 24コースから276ペア×2種JSON
3. `tier_data_generator.py` — 12カテゴリJSON
4. `pillar_data_generator.py` — 9種JSON

### Phase 2（来週）: GPカードパイプライン
1. `card_data_generator.py` — R01-R03の既存CSVから7種JSON生成
2. `team_compare_generator.py` — 45チームペア×GP
3. `season_aggregator.py` — シーズン横断6種

### Phase 3（R04 4/10まで）: 全統合
1. pipeline.sh でStage 1-6を一括実行
2. f1_analysisインポートスクリプト実行
3. フルビルド → 10,000+ページ確認
4. Cloudflare Pagesデプロイ

---

## 最初のClaude Codeへの指示

```
Phase 0を実行せよ。

1. data/drivers/pairs/ver-vs-ham/career_arc.json を作成:
{
  "driver1": {
    "code": "VER", "name": "Verstappen", "color": "#0600ef",
    "cumWins": [0,0,1,2,5,7,17,32,51,55],
    "cumPts": [49,204,371,580,791,873,1268,1843,2418,2600],
    "debut": 2015
  },
  "driver2": {
    "code": "HAM", "name": "Hamilton", "color": "#27f4d2",
    "cumWins": [4,9,11,14,17,21,32,42,52,61,72,83,85,93,93],
    "cumPts": [109,207,256,396,523,630,939,1223,1506,1765,2068,2396,2459,2670,2710],
    "debut": 2007
  }
}

2. data/drivers/pairs/ver-vs-msc/ と data/drivers/pairs/ham-vs-alo/ にも同様のJSONを作成

3. site/src/lib/data.ts に以下を追加:
   - listDriverPairs(): data/drivers/pairs/ 配下のディレクトリ名一覧を返す
   - loadDriverCompare(pair, type): data/drivers/pairs/{pair}/{type}.json を読む

4. site/src/pages/compare/drivers/[pair]/career-arc.astro を作成:
   - getStaticPaths で listDriverPairs() から全ペアのパスを生成
   - loadDriverCompare(pair, 'career_arc') でデータ読み込み
   - 既存のcard_career_arc.htmlのCSS/レイアウトを移植（#060606, Bebas Neue, IBM Plex Mono）
   - Canvas APIで折れ線グラフを描画
   - 1080x1080px

5. npx astro build でビルド

6. 以下のページが生成されていることを確認して報告:
   - /compare/drivers/ver-vs-ham/career-arc/
   - /compare/drivers/ver-vs-msc/career-arc/
   - /compare/drivers/ham-vs-alo/career-arc/

追加の質問はするな。実行して結果を報告。
```
