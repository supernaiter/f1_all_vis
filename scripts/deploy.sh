#!/bin/bash
# Cloudflare Pages デプロイ
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SITE_DIR="$SCRIPT_DIR/../site"

echo "=== Astro ビルド ==="
cd "$SITE_DIR" && npm run build

echo ""
echo "=== Cloudflare Pages デプロイ ==="
npx wrangler pages deploy "$SITE_DIR/dist/" --project-name=motorsports-visualised

echo ""
echo "✓ デプロイ完了"
