# Plan: SNS共有対応 — OGPメタタグ実装

Date: 2026-03-31
Prompt: "SNS共有を実現する — H2Hページにog:image/og:title/og:descriptionを実装し、Twitter/LINE共有時にドライバー比較カードが正しくプレビュー表示される状態にする"

## Goal

H2Hドライバー比較ページをTwitter・LINE等でURLを共有した際に、リッチなプレビューカード（タイトル・説明文・画像）が表示される状態にする。現在は全ページでOGPメタタグが完全に不在であり、SNS共有時にはURLのみが表示される。done_definitionの「OGP付きでSNS共有可能な状態」を満たすための核心実装。

## Acceptance Criteria

- [ ] すべてのH2Hページ（hub, pace, sectors, speed, stints）でog:title, og:description, og:imageメタタグが出力される
- [ ] Twitter Cards用のmeta tags（twitter:card, twitter:title, twitter:description, twitter:image）が出力される
- [ ] og:imageには各ペアのラップタイムデルタチャート画像（chart_laptime_delta.png）が使用される
- [ ] og:titleはドライバー名とGP名を含む（例: "VER vs NOR — 2026 R01 Australia GP"）
- [ ] og:descriptionはレース結果の要約を含む
- [ ] トップページ（/）にもサイト全体のOGPが設定される
- [ ] Astroビルドが成功し、HTMLソースにOGPタグが正しく出力されていることを確認
- [ ] og:urlが各ページの正規URLを指す
- [ ] og:typeが適切に設定される（article for h2h pages, website for top）

## Out of Scope

- OGP専用画像の動的生成（Satori/Puppeteer等によるOG Image API）
- Twitter/LINE等での実際の共有テスト（ビルド出力のHTML検証のみ）
- サブページ（pace/sectors/speed/stints）ごとの個別OG画像（全サブページでhubと同じチャート画像を使用）
- サイトURLの実ドメイン設定（現在のexampleドメインのまま）

## Notes

- Base.astroにimage, url, typeのpropsを追加する方針が自然
- 既存のseoオブジェクト（title, title_ja, description, keywords）がanalysis.jsonに含まれている
- チャート画像は `/charts/{gp_dir}/{pair_dir}/chart_laptime_delta.png` にある
- astro.configのsite設定は `https://f1-data.example.com`
- サブページ（pace.astro等）にも同じOGP propsをBase経由で渡す必要がある
