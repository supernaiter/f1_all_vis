---
name: f1-ui-evaluate
description: >
  H2Hサブページ（pace/sectors/speed/stints）のUI品質を5軸で評価し、
  PASS/FAILとスコア、具体的改善点を返すEvaluatorスキル。
  Generator+Evaluatorハーネスの評価側。単体でも使用可能。
---

# F1 UI Evaluator

H2Hサブページを5軸の具体的基準で評価する。主観を排除し、検証可能な基準のみを使う。

## 使い方

`/f1-ui-evaluate pace` のようにページ名を渡す。
ページ名: `pace | sectors | speed | stints`

## 評価手順

### Step 1: ビルド検証
```bash
cd /Volumes/intersd2/2026_1_4/Motorsports-Visualised/site && npx astro build
```
ビルドエラーがあればスコア0で即FAIL。エラーメッセージを返す。

### Step 2: ソースコード読み込み
以下を Read で読む:
- 対象ページ: `site/src/pages/h2h/[...slug]/{page}.astro`
- 参照Hub: `site/src/pages/h2h/[...slug]/index.astro`
- テーマ: `site/src/lib/echarts-theme.ts`（存在すれば）
- 型定義: `site/src/lib/data.ts`

### Step 3: 5軸採点

各軸 0-3 で採点（0=未実装/壊れ, 1=部分的, 2=良好, 3=優秀）

---

### 軸1: Visual Consistency（重み25%）

**3点の条件:**
- 色は全て CSS custom properties (`var(--bg)`, `var(--bg-card)`, `var(--accent)`, `var(--text)`, `var(--text-dim)`, `var(--border)`) を使用
- 例外: `COMPOUND_COLORS`, `TEAM_COLORS`, `color1`/`color2`（ドライバー色）のみハードコード許可
- ECharts themeBase が以下と一致:
  ```
  textStyle.color: '#aaaaaa'
  fontFamily: 'Hiragino Sans, system-ui, sans-serif'
  tooltip.backgroundColor: '#1c1c25'
  tooltip.borderColor: '#303037'
  axisLine.lineStyle.color: '#303037'
  splitLine.lineStyle.color: '#303037', type: 'dashed'
  ```
- `<style>` ブロック内で `var(--*)` を使用

**検証方法:** ソースをgrepし、`#` で始まる色リテラルを列挙。許可リスト外があれば減点。

---

### 軸2: Hub-Page Parity（重み25%）

**3点の条件:**
- ページ上部にドライバー比較ヒーロー（顔アイコン、勝敗でサイズ/透明度が変化）
- `ScoreRow` パターンまたは同等の勝敗可視化（face-dot + CSS `--s1`/`--s2`/`--o1`/`--o2`）
- `DRIVER_HEADSHOTS` をインポートして使用
- サマリーセクションがチャートの上にある（チャートだけのページではない）

**検証方法:** HTMLの構造を確認。`.hero-*` または同等クラス、`.face-dot` または同等要素、CSS custom properties の存在。

---

### 軸3: Chart Quality（重み25%）

**3点の条件:**
- SC/VSC markArea が表示される（該当ページの場合）
- tooltip にコンパウンド名+タイヤライフを含む
- `DataZoom: [{ type: 'inside' }]` が有効
- `window.addEventListener('resize', ...)` で全チャートがresizeされる
- チャートコンテナが `width: 100%` で固定幅ではない

**検証方法:** scriptタグ内のECharts設定オブジェクトを読み、各項目の有無を確認。

---

### 軸4: Data Integrity（重み15%）

**3点の条件:**
- insights.ts の対応関数を呼び出している（paceInsight, sectorInsight, speedInsight, stintInsight）
- AI生成テキストが直接埋め込まれていない（日本語の長文リテラルがテンプレート内にない）
- `analysis.per_lap` からデータを取得し、undefined チェックまたは optional chaining を使用
- `InsightBox` コンポーネントを使用

**検証方法:** import文とfrontmatterのコードパスを確認。

---

### 軸5: Mobile（重み10%）

**3点の条件:**
- `clamp()` を使用している箇所がある（フォントサイズ、パディング等）
- `@media (max-width: 640px)` ブレイクポイントがある
- チャートの resize イベントリスナーがある
- 横スクロールを発生させる固定幅要素がない

**検証方法:** CSSブロックを読み確認。

---

## Step 4: 判定

```
加重スコア = (軸1×0.25 + 軸2×0.25 + 軸3×0.25 + 軸4×0.15 + 軸5×0.10)
PASS: 加重スコア >= 2.5 かつ 全軸 >= 1
FAIL: 加重スコア < 2.5 または いずれかの軸が 0
```

## Step 5: 出力フォーマット

```
=== UI EVALUATION: {page} ===

Visual Consistency:  {score}/3  {PASS|FAIL}
  {具体的な根拠。問題があればソース行番号を引用}

Hub-Page Parity:     {score}/3  {PASS|FAIL}
  {具体的な根拠}

Chart Quality:       {score}/3  {PASS|FAIL}
  {具体的な根拠}

Data Integrity:      {score}/3  {PASS|FAIL}
  {具体的な根拠}

Mobile:              {score}/3  {PASS|FAIL}
  {具体的な根拠}

Weighted Score: {score}/3.0
RESULT: {PASS|FAIL}

Improvements needed:
1. {最も重要な改善点 — ソース行を引用}
2. {2番目の改善点}
3. {3番目の改善点}
```

## 注意

- 厳しく採点する。3点は本当に優秀な場合のみ
- 改善点は必ずソースファイルの具体的な行や要素を引用する
- Hub index.astro と同等の品質が目標。「チャートが動く」だけでは2点止まり
- AI生成テキスト（insights.ts経由でない日本語文）を発見したら即Data Integrity=0
