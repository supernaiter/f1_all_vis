#!/usr/bin/env node
// HTML カード → 1080×1080 PNG 変換スクリプト
// 使用法: node scripts/card_to_png.js <input.html> <output.png>

const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

async function main() {
  const [,, inputHtml, outputPng] = process.argv;
  if (!inputHtml || !outputPng) {
    console.error('使用法: node scripts/card_to_png.js <input.html> <output.png>');
    process.exit(1);
  }

  const absInput = path.resolve(inputHtml);
  if (!fs.existsSync(absInput)) {
    console.error(`ファイルが見つかりません: ${absInput}`);
    process.exit(1);
  }

  const absOutput = path.resolve(outputPng);
  const outDir = path.dirname(absOutput);
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });

  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1080, height: 1080 } });

  await page.goto(`file://${absInput}`, { waitUntil: 'networkidle' });
  // フォント読み込み待機
  await page.waitForTimeout(1000);

  const card = await page.$('.card');
  if (card) {
    await card.screenshot({ path: absOutput });
  } else {
    await page.screenshot({ path: absOutput, clip: { x: 0, y: 0, width: 1080, height: 1080 } });
  }

  await browser.close();
  console.log(`✓ ${path.basename(inputHtml)} → ${path.basename(outputPng)}`);
}

main().catch(e => { console.error(e); process.exit(1); });
