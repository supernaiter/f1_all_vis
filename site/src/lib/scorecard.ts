/**
 * スコアカード共通ユーティリティ
 * H2H 5ページ(index/pace/sectors/speed/stints)で使用
 */

export interface ScoreRow {
  label: string;
  sub: string;
  subColor: string;
  val1: string;
  val2: string;
  // 0〜1のスケール値（CSSで実サイズに変換）
  scale1: number;
  scale2: number;
  opacity1: number;
  opacity2: number;
  fontSize1: number;
  fontSize2: number;
}

export function makeRow(
  label: string, sub: string, subColor: string,
  val1: string, val2: string,
  v1: number, v2: number, maxDelta: number, lowerIsBetter: boolean
): ScoreRow {
  const diff = v1 - v2;
  const intensity = Math.min(Math.abs(diff) / maxDelta, 1);
  const winner = lowerIsBetter
    ? (diff < 0 ? 1 : diff > 0 ? 2 : 0)
    : (diff > 0 ? 1 : diff < 0 ? 2 : 0);

  // scale: 0.25(最小)〜1.0(最大)  差が大きいほど勝者が大きく敗者が小さい
  const winScale = 0.6 + intensity * 0.4;   // 0.6〜1.0
  const loseScale = 0.6 - intensity * 0.35; // 0.6〜0.25
  const drawScale = 0.5;

  // 透明度
  const winOpacity = 1;
  const loseOpacity = 0.7 - intensity * 0.35; // 0.7〜0.35

  // フォントサイズ（rem）
  const winFont = 0.85 + intensity * 0.25;  // 0.85〜1.1rem
  const loseFont = 0.85 - intensity * 0.15; // 0.85〜0.7rem

  return {
    label, sub, subColor, val1, val2,
    scale1: winner === 1 ? winScale : winner === 2 ? loseScale : drawScale,
    scale2: winner === 2 ? winScale : winner === 1 ? loseScale : drawScale,
    opacity1: winner === 2 ? loseOpacity : winOpacity,
    opacity2: winner === 1 ? loseOpacity : winOpacity,
    fontSize1: winner === 1 ? winFont : winner === 2 ? loseFont : 0.85,
    fontSize2: winner === 2 ? winFont : winner === 1 ? loseFont : 0.85,
  };
}
