#!/bin/bash
# 全HTMLカード → PNG一括書き出し
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CARDS_DIR="$SCRIPT_DIR/../site/public/cards"
PNG_DIR="$CARDS_DIR/png"

mkdir -p "$PNG_DIR"

count=0
errors=0
for html in "$CARDS_DIR"/*.html; do
  base=$(basename "$html" .html)
  png="$PNG_DIR/${base}.png"
  if node "$SCRIPT_DIR/card_to_png.js" "$html" "$png" 2>/dev/null; then
    count=$((count + 1))
  else
    echo "✗ FAILED: $base"
    errors=$((errors + 1))
  fi
done

echo ""
echo "=== 書き出し完了: ${count} 成功 / ${errors} 失敗 ==="
echo "HTML: $(ls "$CARDS_DIR"/*.html | wc -l | tr -d ' ') 枚"
echo "PNG:  $(ls "$PNG_DIR"/*.png 2>/dev/null | wc -l | tr -d ' ') 枚"
