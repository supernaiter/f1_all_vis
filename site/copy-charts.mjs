/**
 * ビルド前にデータディレクトリからチャートPNGをpublic/charts/にコピー
 * 構造: public/charts/{gpDir}/{pairSlug}/{chartFile}
 */
import fs from 'node:fs';
import path from 'node:path';

const DATA_ROOT = path.resolve('/Volumes/lyssr_workspace/2026_1_4/Motorsports-Visualised/data');
const OUT_DIR = path.resolve('public/charts');

// 出力先をクリーン
if (fs.existsSync(OUT_DIR)) {
  fs.rmSync(OUT_DIR, { recursive: true });
}
fs.mkdirSync(OUT_DIR, { recursive: true });

let copied = 0;

// GPディレクトリを走査
const gpDirs = fs.readdirSync(DATA_ROOT).filter(d => /^\d{4}_R\d{2}_/.test(d));

for (const gpDir of gpDirs) {
  const h2hDir = path.join(DATA_ROOT, gpDir, 'h2h');
  if (!fs.existsSync(h2hDir)) continue;

  const pairDirs = fs.readdirSync(h2hDir).filter(d => {
    return fs.statSync(path.join(h2hDir, d)).isDirectory();
  });

  for (const pairSlug of pairDirs) {
    const srcDir = path.join(h2hDir, pairSlug);
    const pngs = fs.readdirSync(srcDir).filter(f => f.endsWith('.png'));

    if (pngs.length === 0) continue;

    const destDir = path.join(OUT_DIR, gpDir, pairSlug);
    fs.mkdirSync(destDir, { recursive: true });

    for (const png of pngs) {
      fs.copyFileSync(path.join(srcDir, png), path.join(destDir, png));
      copied++;
    }
  }
}

console.log(`コピー完了: ${copied}枚のチャートPNG → public/charts/`);
