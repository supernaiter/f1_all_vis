---
name: f1-ui-harness
description: >
  Generator+EvaluatorのGAN風ループでH2Hサブページを反復改善する
  オーケストレーター。/f1-ui-harness pace で起動。
  最大3イテレーションで品質基準を満たすまで改善する。
user-invocable: true
---

# F1 UI Design Harness

GAN風Generator+Evaluatorループでサブページを反復改善するオーケストレーター。

## 使い方

```
/f1-ui-harness pace          # 1ページを改善
/f1-ui-harness all           # pace→sectors→speed→stints を順次
```

## オーケストレーションフロー

各ページについて以下を実行:

### Round 0: 準備

1. 以下を読み込む:
   - Hub参照: `site/src/pages/h2h/[...slug]/index.astro`
   - 対象ページ: `site/src/pages/h2h/[...slug]/{page}.astro`
   - `site/src/lib/data.ts`
   - `site/src/lib/insights.ts`
2. 対象ページの現状を把握

### Round 1-3: Generate → Build → Evaluate ループ

```
┌─────────────────────────────────────────┐
│ Generator Agent                          │
│ - 対象ページを書き換え                      │
│ - Hub のパターンを適用                      │
│ - 前回のEvaluatorフィードバックを反映        │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ Build Check                              │
│ cd site && npx astro build               │
│ - 成功 → Evaluatorへ                      │
│ - 失敗 → エラーをGeneratorに戻す（再試行）   │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ Evaluator Agent                          │
│ - 5軸で採点（0-3）                        │
│ - 加重スコア >= 2.5 → PASS               │
│ - FAIL → 改善点をGeneratorに戻す          │
└──────────────┬──────────────────────────┘
               │
          PASS? ──→ 次のページへ / 完了
               │
          FAIL（< 3回） → Round N+1 へ
               │
          FAIL（3回目） → ベスト版を保持、ユーザーに報告
```

### Agent起動方法

**Generator**: Agent tool で起動。プロンプトに以下を含める:
- f1-ui-generate SKILL.md の内容
- 対象ページ名
- Hub index.astro のコード（参照用）
- Evaluatorフィードバック（2回目以降）

**Evaluator**: Agent tool で起動。プロンプトに以下を含める:
- f1-ui-evaluate SKILL.md の内容
- 対象ページ名

### 判定基準

- **PASS**: 加重スコア >= 2.5、全軸 >= 1
- **FAIL**: 加重スコア < 2.5 または いずれかの軸 = 0
- **最大3ラウンド**: 3回FAILしたら最後の版を保持

### ページ実行順序

`all` の場合: pace → sectors → speed → stints
（paceが最もHubに構造が近いため最初。学んだパターンを後続に活用）

## 完了報告

各ページの結果を以下の形式で報告:

```
=== HARNESS RESULTS ===

pace:     PASS (Round 2, Score: 2.7/3.0)
sectors:  PASS (Round 1, Score: 2.8/3.0)
speed:    PASS (Round 3, Score: 2.5/3.0)
stints:   FAIL (Round 3, Score: 2.2/3.0) — ユーザー確認要
```

## 注意

- GeneratorとEvaluatorは必ず別のAgent subprocessで実行する（自己評価バイアス排除）
- Evaluatorのフィードバックはそのまま次のGeneratorに渡す（要約しない）
- ビルドエラーはGenerator内で解決させる（Evaluatorには渡さない）
- 各ラウンドでgit commitは不要（最終PASSのみユーザーに確認後commit）
