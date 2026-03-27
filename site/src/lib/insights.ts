/**
 * analysis.jsonからテンプレートベースで日本語インサイトを自動生成
 * AIテキストではなくデータ駆動
 */
import type { H2HAnalysis } from './data';

// ペースページ用インサイト
export function paceInsight(analysis: H2HAnalysis): string {
  const { pace, meta, per_lap } = analysis;
  const drv1 = meta.driver1, drv2 = meta.driver2;
  const faster = pace.faster;
  const delta = Math.abs(pace.delta_median_sec ?? 0);
  const deltas = per_lap.pace.deltas;
  const total = deltas.length;
  const drv1Faster = deltas.filter(d => d.delta < 0).length;
  const drv2Faster = deltas.filter(d => d.delta > 0).length;

  if (delta === 0) {
    return `${drv1}と${drv2}の中央値ペースは同一。${total}周のクリーンラップで拮抗した展開。`;
  }

  const winnerCount = faster === drv1 ? drv1Faster : drv2Faster;
  const pct = Math.round((winnerCount / total) * 100);

  let lines = `${faster}が中央値で${delta.toFixed(3)}秒/ラップ速いペース。${total}周中${winnerCount}周（${pct}%）で${faster}が上回った。`;

  // 連続優勢区間の検出
  const streak = findLongestStreak(deltas, faster === drv1);
  if (streak.length >= 5) {
    lines += ` Lap ${streak.start}-${streak.end}で${streak.length}周連続${faster}が優勢。`;
  }

  return lines;
}

// セクターページ用インサイト
export function sectorInsight(analysis: H2HAnalysis): string {
  const { sectors, meta } = analysis;
  const drv1 = meta.driver1, drv2 = meta.driver2;
  const parts: string[] = [];

  for (const [name, data] of Object.entries(sectors) as [string, any][]) {
    const d1Wins = data[`${drv1}_wins`];
    const d2Wins = data[`${drv2}_wins`];
    const delta = data.delta_sec;
    const winner = delta < 0 ? drv1 : drv2;
    const loser = delta < 0 ? drv2 : drv1;
    const winnerWins = delta < 0 ? d1Wins : d2Wins;
    const total = d1Wins + d2Wins;

    parts.push(`${name}: ${winner}が${winnerWins}/${total}周で勝利（平均${Math.abs(delta).toFixed(3)}秒差）`);
  }

  // 最も差が大きいセクター
  const maxSec = Object.entries(sectors).reduce((max, [name, data]: [string, any]) =>
    Math.abs(data.delta_sec) > Math.abs(max[1].delta_sec) ? [name, data] : max
  );
  const maxDelta = Math.abs((maxSec[1] as any).delta_sec);
  const maxWinner = (maxSec[1] as any).delta_sec < 0 ? drv1 : drv2;

  return parts.join('。') + `。最大の差は${maxSec[0]}の${maxWinner} +${maxDelta.toFixed(3)}秒。`;
}

// スピードページ用インサイト
export function speedInsight(analysis: H2HAnalysis): string {
  const { speed, meta } = analysis;
  const drv1 = meta.driver1, drv2 = meta.driver2;
  const parts: string[] = [];

  let maxLabel = '', maxDelta = 0, maxWinner = '';

  for (const [label, data] of Object.entries(speed) as [string, any][]) {
    const delta = data.delta_kmh;
    if (delta === 0) continue;
    const winner = delta > 0 ? drv1 : drv2;
    parts.push(`${label}: ${winner} +${Math.abs(delta)}km/h`);

    if (Math.abs(delta) > Math.abs(maxDelta)) {
      maxDelta = delta;
      maxLabel = label;
      maxWinner = delta > 0 ? drv1 : drv2;
    }
  }

  if (parts.length === 0) return 'スピード計測では両者ほぼ同等。';

  let result = parts.join('、') + '。';
  if (maxLabel) {
    result += `最大差は${maxLabel}の${maxWinner} +${Math.abs(maxDelta)}km/h。`;
  }
  return result;
}

// スティントページ用インサイト
export function stintInsight(analysis: H2HAnalysis): string {
  const { degradation, stints, meta } = analysis;
  const drv1 = meta.driver1, drv2 = meta.driver2;
  const parts: string[] = [];

  // 戦略サマリー
  const s1 = stints.drv1.map((s: any) => `${s.compound.charAt(0)}${s.total_laps}周`).join('→');
  const s2 = stints.drv2.map((s: any) => `${s.compound.charAt(0)}${s.total_laps}周`).join('→');
  parts.push(`${drv1}: ${s1}、${drv2}: ${s2}`);

  // デグラデーション比較（同一コンパウンドのスティントがあれば）
  const d1 = degradation.drv1 || [];
  const d2 = degradation.drv2 || [];

  for (const deg1 of d1 as any[]) {
    const match = (d2 as any[]).find((d: any) => d.compound === deg1.compound);
    if (match) {
      const fc1 = Math.abs(deg1.fuel_corrected_deg);
      const fc2 = Math.abs(match.fuel_corrected_deg);
      const diff = Math.abs(fc1 - fc2);
      const better = fc1 < fc2 ? drv1 : drv2;
      if (diff < 0.005) {
        parts.push(`${deg1.compound}のデグ: 両者ほぼ同等（${fc1.toFixed(3)}秒/周 vs ${fc2.toFixed(3)}秒/周）`);
      } else {
        parts.push(`${deg1.compound}のデグ: ${better}が良好（${Math.min(fc1, fc2).toFixed(3)} vs ${Math.max(fc1, fc2).toFixed(3)}秒/周）`);
      }
    }
  }

  return parts.join('。') + '。';
}

// ハブページ用ワンラインインサイト
export function hubPaceOneLiner(analysis: H2HAnalysis): string {
  const { pace } = analysis;
  if (!pace.faster || pace.delta_median_sec === null) return 'データ不足';
  return `${pace.faster}が${Math.abs(pace.delta_median_sec).toFixed(3)}秒速い`;
}

export function hubSectorOneLiner(analysis: H2HAnalysis): string {
  const { sectors, meta } = analysis;
  const entries = Object.entries(sectors) as [string, any][];
  const d1Total = entries.reduce((s, [, d]) => s + d[`${meta.driver1}_wins`], 0);
  const d2Total = entries.reduce((s, [, d]) => s + d[`${meta.driver2}_wins`], 0);
  const winner = d1Total > d2Total ? meta.driver1 : meta.driver2;
  return `${winner}が${Math.max(d1Total, d2Total)}/${d1Total + d2Total}セクターで優勢`;
}

export function hubSpeedOneLiner(analysis: H2HAnalysis): string {
  const { speed, meta } = analysis;
  const st = speed['ST'];
  if (!st || st.delta_kmh === 0) return 'スピード同等';
  const winner = st.delta_kmh > 0 ? meta.driver1 : meta.driver2;
  return `スピードトラップ: ${winner} +${Math.abs(st.delta_kmh)}km/h`;
}

export function hubStintOneLiner(analysis: H2HAnalysis): string {
  const { stints } = analysis;
  const s1 = stints.drv1.length;
  const s2 = stints.drv2.length;
  return `${Math.max(s1, s2)}スティント戦略`;
}

// ユーティリティ: 連続優勢区間の検出
function findLongestStreak(deltas: {lap: number; delta: number}[], drv1Wins: boolean) {
  let best = { start: 0, end: 0, length: 0 };
  let current = { start: 0, end: 0, length: 0 };

  for (const d of deltas) {
    const isWin = drv1Wins ? d.delta < 0 : d.delta > 0;
    if (isWin) {
      if (current.length === 0) current.start = d.lap;
      current.end = d.lap;
      current.length++;
      if (current.length > best.length) best = { ...current };
    } else {
      current = { start: 0, end: 0, length: 0 };
    }
  }
  return best;
}
