---
name: f1-ui-generate
description: >
  H2Hサブページ（pace/sectors/speed/stints）をHub index.astroの
  デザインパターンに合わせてリファクタリングするGeneratorスキル。
  顔ドット比較、スコアカード、CSS custom propertiesを適用する。
---

# F1 UI Generator

H2Hサブページを、承認済みHub（index.astro）のデザイン言語に合わせてリファクタリングする。

## 使い方

Evaluatorフィードバック付きで呼ばれる場合:
`/f1-ui-generate pace "Visual Consistency: themeBase不一致、Hub-Page Parity: ヒーロー未実装"`

## 入力

1. **ページ名**: pace | sectors | speed | stints
2. **Evaluatorフィードバック**: 前回の評価結果（初回は空）

## 実行手順

### Step 1: 参照ファイル読み込み

必ず以下を Read で読む:
- Hub参照: `site/src/pages/h2h/[...slug]/index.astro`（デザインパターンの源泉）
- 対象ページ: `site/src/pages/h2h/[...slug]/{page}.astro`
- データ型: `site/src/lib/data.ts`（H2HAnalysis型、DRIVER_HEADSHOTS、TEAM_COLORS）
- インサイト: `site/src/lib/insights.ts`（テンプレートベースの関数群）

### Step 2: Hubから再利用するパターン

以下をindex.astroからコピー・適応する:

**A. ScoreRow + makeRow()（index.astro L44-92）**
```typescript
interface ScoreRow {
  label: string; sub: string; subColor: string;
  val1: string; val2: string;
  scale1: number; scale2: number;
  opacity1: number; opacity2: number;
  fontSize1: number; fontSize2: number;
}
function makeRow(label, sub, subColor, val1, val2, v1, v2, maxDelta, lowerIsBetter): ScoreRow
```

**B. DRIVER_HEADSHOTS（index.astro L146-147）**
```typescript
import { DRIVER_HEADSHOTS } from '../../../lib/data';
const face1 = DRIVER_HEADSHOTS[drv1] || '';
const face2 = DRIVER_HEADSHOTS[drv2] || '';
```

**C. ヒーローセクション（index.astro L177-205）**
- 勝敗に応じてポートレートサイズ・透明度が変化
- `.hero-driver.winner` / `.hero-driver.loser` クラス

**D. スコアカードHTML（index.astro L210-233）**
- CSS custom properties: `--s1`, `--s2`, `--o1`, `--o2`, `--fs1`, `--fs2`
- face-dotの大小+透明度で勝敗を視覚化

**E. CSS（index.astro L285-433）**
- `.hero-*`, `.score-row`, `.face-dot-*`, `.score-val-*`, `@media` ブレイクポイント

### Step 3: ページ別変換

#### pace.astro
- **追加**: ペースの勝者を表示するヒーロー（`pace.faster`で判定）
- **追加**: サマリーカード1行（中央値ペース差、clean_laps比率）をmakeRow()で生成
- **保持**: 既存のラップタイム折れ線チャート + デルタバーチャート（script全体）
- **勝者判定**: `pace.faster === drv1 ? 1 : 2`

#### sectors.astro
- **追加**: 累積セクター勝率の勝者をヒーローに表示
- **追加**: S1/S2/S3それぞれのサマリーカード行（勝利数をmakeRowで比較）
- **保持**: 3セクターのデルタバーチャート
- **勝者判定**: 全セクター合計の勝利数で判定

#### speed.astro
- **追加**: スピードトラップの勝者をヒーローに表示
- **追加**: 各計測ポイント（S1末端/S2末端/FL/ST）のサマリーカード行
- **保持**: 箱ひげ図チャート
- **勝者判定**: スピードトラップ（ST）のdelta_kmhで判定

#### stints.astro
- **追加**: Hubと同じストラテジータイムライン（index.astro L236-266のパターン）
- **追加**: 同一コンパウンドのデグ比較サマリーカード行
- **保持**: ドライバー別scatter+trendチャート
- **勝者判定**: スティント数は優劣なし→デグの良い方を勝者に

### Step 4: 共通ルール（厳守）

1. **insights.ts関数のみ使用**: AI生成テキストを絶対に埋め込まない
2. **CSS custom properties**: `var(--bg)`, `var(--bg-card)`, `var(--accent)`, `var(--text)`, `var(--text-dim)`, `var(--border)` を使う
3. **themeBase**: ECharts設定は既存のthemeBaseパターンを維持（tooltip, axis, splitLine）
4. **clamp()**: フォント・パディングにclamp()を使いモバイル対応
5. **resize**: 全チャートに `window.addEventListener('resize', ...)` を維持
6. **DataZoom**: `[{ type: 'inside' }]` を維持
7. **SC/VSC**: markArea表示を維持（該当チャート）

### Step 5: Evaluatorフィードバックへの対応

フィードバックがある場合:
1. 指摘された軸を優先的に修正
2. ソース行番号が引用されていればその箇所を直接修正
3. 他の軸のスコアを下げないよう注意
4. 修正箇所を明示的にコメントで記載（修正後に削除）

### Step 6: ビルド確認

修正後、必ず実行:
```bash
cd /Volumes/intersd2/2026_1_4/Motorsports-Visualised/site && npx astro build
```
エラーがあれば自分で修正してから完了報告。
