"""
t6_run.py — R02中国GP FP予選シミュレーションラップ特定 & 実際の予選結果比較
CLAUDE.md準拠の個別ラップベース識別ロジック使用
"""

import matplotlib
matplotlib.use('Agg')  # GUIなし環境対応

import csv
import os
import math
import statistics
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from scipy import stats

# ===== パス設定 =====
BASE_DIR = '/Volumes/lyssr_workspace/2026_1_4/Motorsports-Visualised'
FP_CSV = os.path.join(BASE_DIR, 'data/2026_R02_China/export/fp_laps.csv')
QUALI_CSV = os.path.join(BASE_DIR, 'data/2026_R02_China/export/quali_laps.csv')
OUTPUT_DIR = os.path.join(BASE_DIR, 'notebooks/output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ===== グラフスタイル =====
STYLE = {
    'bg_color': '#1a1a2e',
    'text_color': '#ffffff',
    'grid_color': '#333355',
    'figsize': (12, 6.75),
    'title_size': 18,
    'label_size': 12,
}

# ===== CSV読み込みヘルパー =====
def load_csv(path):
    """CSVをdict listとして読み込む"""
    with open(path, encoding='utf-8') as f:
        return list(csv.DictReader(f))

def to_float(val, default=None):
    """文字列→float変換（空文字・NaN対応）"""
    try:
        v = float(val)
        return v if not math.isnan(v) else default
    except (TypeError, ValueError):
        return default

# ===== FPデータ読み込み =====
print("=== FPデータ読み込み ===")
fp_rows = load_csv(FP_CSV)
print(f"総FPラップ数: {len(fp_rows)}")

# セッション種別を動的に確認
sessions_found = sorted(set(r['Session'] for r in fp_rows))
print(f"検出されたセッション: {sessions_found}")

# ===== 予選シミュレーションラップ識別（CLAUDE.md準拠）=====
# 1. Softタイヤで記録されたラップ
# 2. アウトラップ（PitOutTime_sec が存在する）を除外
# 3. TyreLife <= 8
# 4. セッション最速の103%以内

def identify_qualisim_laps(rows, session_name=None):
    """
    予選シミュレーションラップを特定する
    session_name: Noneの場合は全セッション対象
    """
    # セッションフィルタ
    if session_name:
        target = [r for r in rows if r['Session'] == session_name]
    else:
        target = rows

    # ステップ1: Softタイヤのみ
    soft_laps = [
        r for r in target
        if r['Compound'] == 'SOFT' and to_float(r['LapTime_sec']) is not None
    ]

    # ステップ2: アウトラップ除外（PitOutTime_secが存在 → アウトラップ）
    no_outlap = [
        r for r in soft_laps
        if not r.get('PitOutTime_sec', '').strip()
    ]

    # ステップ3: TyreLife <= 8
    fresh_laps = [
        r for r in no_outlap
        if to_float(r['TyreLife'], 999) <= 8
    ]

    # ステップ4: セッション最速の103%以内
    valid_times = [to_float(r['LapTime_sec']) for r in fresh_laps]
    valid_times = [t for t in valid_times if t is not None]
    if not valid_times:
        return []
    session_best = min(valid_times)
    threshold = session_best * 1.03

    qualisim = [
        r for r in fresh_laps
        if to_float(r['LapTime_sec'], 9999) <= threshold
    ]

    return qualisim

# セッション別に予選シミュラップを特定
print("\n=== 予選シミュレーションラップ特定 ===")
qualisim_by_session = {}
for sess in sessions_found:
    laps = identify_qualisim_laps(fp_rows, sess)
    qualisim_by_session[sess] = laps
    print(f"  {sess}: {len(laps)}ラップ特定")

# 全セッション統合
all_qualisim = []
for laps in qualisim_by_session.values():
    all_qualisim.extend(laps)
print(f"  全セッション合計: {len(all_qualisim)}ラップ")

# ===== ドライバー別FPベストラップ取得 =====
def get_driver_best_by_session(qualisim_laps):
    """
    セッション×ドライバーのベストラップタイム辞書を返す
    戻り値: {driver: {session: best_time}}
    """
    best = {}
    for r in qualisim_laps:
        driver = r['Driver']
        sess = r['Session']
        t = to_float(r['LapTime_sec'])
        if t is None:
            continue
        if driver not in best:
            best[driver] = {}
        if sess not in best[driver] or t < best[driver][sess]:
            best[driver][sess] = t
    return best

driver_session_best = get_driver_best_by_session(all_qualisim)

# FP予測ベスト（FP3優先 → FP2 → FP1）
# ただしR02はFP1のみのためFP1ベストを使用
SESSION_PRIORITY = ['FP3', 'FP2', 'FP1']

def get_fp_prediction(driver_session_best, sessions_available):
    """
    ドライバーごとのFP予測ラップタイムを算出
    利用可能セッションを優先順に使用
    FP2/FP3が存在する場合はトラックエボリューション補正を行う
    """
    priority = [s for s in SESSION_PRIORITY if s in sessions_available]

    # トラックエボリューション補正係数（FP間の中央値差分）
    # 同一セッションのみ利用可能な場合は補正不要
    corrections = {}
    if len(priority) >= 2:
        # 複数セッションが存在する場合: 前後セッション間の改善量を推定
        for i in range(len(priority) - 1):
            sess_a = priority[i]   # より予選に近いセッション
            sess_b = priority[i+1]  # 古いセッション
            diffs = []
            for driver, sbest in driver_session_best.items():
                if sess_a in sbest and sess_b in sbest:
                    diffs.append(sbest[sess_b] - sbest[sess_a])  # 古い - 新しい = 改善量
            if diffs:
                corrections[(sess_b, sess_a)] = statistics.median(diffs)
            else:
                corrections[(sess_b, sess_a)] = 0.0

    predictions = {}
    for driver, sbest in driver_session_best.items():
        # 優先順に最良セッションを選択
        best_time = None
        best_sess = None
        for sess in priority:
            if sess in sbest:
                best_time = sbest[sess]
                best_sess = sess
                break

        if best_time is None:
            continue

        # 最優先セッションより古いセッションを使用している場合、補正
        corrected = best_time
        if best_sess != priority[0]:
            # FP3から何段階離れているか
            idx = priority.index(best_sess)
            for k in range(idx):
                older = priority[k + 1]
                newer = priority[k]
                key = (older, newer)
                corrected -= corrections.get(key, 0.0)  # 補正量を引く（速い方向に補正）

        predictions[driver] = {
            'fp_time': corrected,
            'fp_raw_time': best_time,
            'fp_session': best_sess,
            'corrected': best_sess != priority[0]
        }

    return predictions

fp_predictions = get_fp_prediction(driver_session_best, sessions_found)

print("\n=== FP予測ラップタイム（ドライバー別）===")
sorted_fp = sorted(fp_predictions.items(), key=lambda x: x[1]['fp_time'])
for rank, (driver, info) in enumerate(sorted_fp, 1):
    mark = "*補正" if info['corrected'] else ""
    print(f"  P{rank:2d}. {driver}: {info['fp_time']:.3f}秒 ({info['fp_session']}{mark})")

# ===== 予選実績の読み込み =====
print("\n=== 予選実績読み込み ===")
quali_rows = load_csv(QUALI_CSV)
print(f"予選総ラップ数: {len(quali_rows)}")

# 予選ドライバー一覧（FP1リザーブ除外の基準として使用）
quali_drivers = set(r['Driver'] for r in quali_rows)
print(f"予選出走ドライバー: {sorted(quali_drivers)}")

# ドライバー別予選ベストラップ（Softタイヤ）
def get_quali_best(quali_rows):
    """予選ドライバー別ベストラップ（アウトラップ除外、SoftのみOK）"""
    best = {}
    for r in quali_rows:
        driver = r['Driver']
        t = to_float(r['LapTime_sec'])
        if t is None:
            continue
        # アウトラップ除外
        if r.get('PitOutTime_sec', '').strip():
            continue
        if driver not in best or t < best[driver]:
            best[driver] = t
    return best

quali_best = get_quali_best(quali_rows)
print(f"予選ベスト取得: {len(quali_best)}ドライバー")

# 予選順位リスト
quali_ranked = sorted(quali_best.items(), key=lambda x: x[1])
print("\n=== 実際の予選結果 ===")
for rank, (driver, t) in enumerate(quali_ranked, 1):
    print(f"  P{rank:2d}. {driver}: {t:.3f}秒")

# ===== FP1リザーブドライバー除外 =====
# 予選に出走しているドライバーのみを分析対象とする
fp_pred_filtered = {
    d: info for d, info in fp_predictions.items()
    if d in quali_drivers
}
quali_best_filtered = {
    d: t for d, t in quali_best.items()
    if d in fp_pred_filtered
}

# 共通ドライバー（FPと予選の両方でデータあり）
common_drivers = sorted(set(fp_pred_filtered.keys()) & set(quali_best_filtered.keys()))
print(f"\n=== 分析対象共通ドライバー: {len(common_drivers)}名 ===")
print(f"  {common_drivers}")

# FPにデータがなかった予選ドライバー
missing_fp = [d for d in quali_drivers if d not in fp_pred_filtered]
if missing_fp:
    print(f"\n⚠ FPデータなし（予選出走済み）: {missing_fp}")

# ===== 比較メトリクス計算 =====
print("\n=== 比較メトリクス計算 ===")

# FP順位と予選順位
fp_times_sorted = sorted([(d, fp_pred_filtered[d]['fp_time']) for d in common_drivers], key=lambda x: x[1])
fp_ranks = {d: rank for rank, (d, _) in enumerate(fp_times_sorted, 1)}

quali_times_sorted = sorted([(d, quali_best_filtered[d]) for d in common_drivers], key=lambda x: x[1])
quali_ranks = {d: rank for rank, (d, _) in enumerate(quali_times_sorted, 1)}

fp_rank_list = [fp_ranks[d] for d in common_drivers]
quali_rank_list = [quali_ranks[d] for d in common_drivers]
fp_time_list = [fp_pred_filtered[d]['fp_time'] for d in common_drivers]
quali_time_list = [quali_best_filtered[d] for d in common_drivers]

# Spearman順位相関
spearman_rho, spearman_p = stats.spearmanr(fp_rank_list, quali_rank_list)

# Pearsonタイム相関
pearson_r, pearson_p = stats.pearsonr(fp_time_list, quali_time_list)

# 順位MAE
rank_errors = [abs(fp_ranks[d] - quali_ranks[d]) for d in common_drivers]
rank_mae = statistics.mean(rank_errors)

# 系統バイアス（FP - Quali の中央値）
time_diffs = [fp_pred_filtered[d]['fp_time'] - quali_best_filtered[d] for d in common_drivers]
systematic_bias = statistics.median(time_diffs)

print(f"  Spearman順位相関 (ρ): {spearman_rho:.3f} (p={spearman_p:.3f})")
print(f"  Pearsonタイム相関 (r): {pearson_r:.3f} (p={pearson_p:.3f})")
print(f"  順位MAE: {rank_mae:.2f}ポジション")
print(f"  系統バイアス（中央値）: {systematic_bias:+.3f}秒 (FP {'遅い' if systematic_bias > 0 else '速い'}方向)")

# ===== ドライバーごとの予測精度テーブル =====
print("\n=== ドライバーごとの予測精度テーブル ===")
print(f"{'Driver':<6} {'FP順位':>6} {'予選順位':>8} {'順位誤差':>8} {'FP時間':>10} {'予選時間':>10} {'差分':>8} {'使用セッション':<12}")
print("-" * 80)

table_rows = []
for d in sorted(common_drivers):
    fp_rank = fp_ranks[d]
    q_rank = quali_ranks[d]
    rank_err = fp_rank - q_rank
    fp_t = fp_pred_filtered[d]['fp_time']
    q_t = quali_best_filtered[d]
    diff = fp_t - q_t
    sess = fp_pred_filtered[d]['fp_session']
    corr = "*" if fp_pred_filtered[d]['corrected'] else ""
    print(f"{d:<6} {fp_rank:>6} {q_rank:>8} {rank_err:>+8} {fp_t:>10.3f} {q_t:>10.3f} {diff:>+8.3f} {sess+corr:<12}")
    table_rows.append({
        'Driver': d,
        'FP_Rank': fp_rank,
        'Quali_Rank': q_rank,
        'Rank_Error': rank_err,
        'FP_Time': round(fp_t, 3),
        'Quali_Time': round(q_t, 3),
        'Time_Diff': round(diff, 3),
        'FP_Session': sess + corr
    })

# ===== CSV出力 =====
csv_out = os.path.join(OUTPUT_DIR, 'fp_quali_comparison.csv')
fieldnames = ['Driver', 'FP_Rank', 'Quali_Rank', 'Rank_Error', 'FP_Time', 'Quali_Time', 'Time_Diff', 'FP_Session']
with open(csv_out, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(table_rows)
print(f"\nCSV保存: {csv_out}")

# ===== グラフ描画 =====
print("\n=== グラフ描画 ===")

fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.patch.set_facecolor(STYLE['bg_color'])
fig.suptitle(
    '2026 R02 中国GP — FP予選シミュレーション vs 実際の予選結果',
    color=STYLE['text_color'],
    fontsize=STYLE['title_size'],
    fontweight='bold',
    y=0.98
)

text_c = STYLE['text_color']
grid_c = STYLE['grid_color']
bg_c = STYLE['bg_color']
card_bg = '#1a1a2e'

# --- パネル1: FP順位 vs 予選順位 散布図 ---
ax1 = axes[0, 0]
ax1.set_facecolor(card_bg)
ax1.tick_params(colors=text_c)
for spine in ax1.spines.values():
    spine.set_color(grid_c)

n = len(common_drivers)
fp_r = [fp_ranks[d] for d in common_drivers]
q_r = [quali_ranks[d] for d in common_drivers]

scatter = ax1.scatter(fp_r, q_r, c='#e10600', s=80, zorder=5, alpha=0.9)
# ドライバー名ラベル
for d in common_drivers:
    ax1.annotate(d, (fp_ranks[d], quali_ranks[d]),
                 textcoords='offset points', xytext=(4, 4),
                 color=text_c, fontsize=7)

# 対角線（完全一致）
diag = list(range(1, n + 1))
ax1.plot(diag, diag, '--', color=grid_c, linewidth=1, alpha=0.7, label='完全一致')

# 回帰直線
slope, intercept, _, _, _ = stats.linregress(fp_r, q_r)
x_line = np.linspace(1, n, 100)
ax1.plot(x_line, slope * x_line + intercept, '-', color='#FFD700', linewidth=1.5,
         alpha=0.7, label=f'回帰直線')

ax1.set_xlabel('FPシミュラップ順位', color=text_c, fontsize=STYLE['label_size'])
ax1.set_ylabel('実際の予選順位', color=text_c, fontsize=STYLE['label_size'])
ax1.set_title(f'順位相関 (Spearman ρ={spearman_rho:.2f})', color=text_c, fontsize=13)
ax1.grid(True, color=grid_c, alpha=0.4, linestyle='--')
ax1.legend(framealpha=0.3, labelcolor=text_c, facecolor=bg_c, fontsize=8)
ax1.invert_xaxis()
ax1.invert_yaxis()
ax1.set_xlim(n + 0.5, 0.5)
ax1.set_ylim(n + 0.5, 0.5)

# --- パネル2: FPタイム vs 予選タイム 散布図 ---
ax2 = axes[0, 1]
ax2.set_facecolor(card_bg)
ax2.tick_params(colors=text_c)
for spine in ax2.spines.values():
    spine.set_color(grid_c)

fp_t_arr = [fp_pred_filtered[d]['fp_time'] for d in common_drivers]
q_t_arr = [quali_best_filtered[d] for d in common_drivers]

ax2.scatter(fp_t_arr, q_t_arr, c='#39B54A', s=80, zorder=5, alpha=0.9)
for d in common_drivers:
    ax2.annotate(d, (fp_pred_filtered[d]['fp_time'], quali_best_filtered[d]),
                 textcoords='offset points', xytext=(4, 4),
                 color=text_c, fontsize=7)

# 対角線
min_t = min(min(fp_t_arr), min(q_t_arr)) - 0.5
max_t = max(max(fp_t_arr), max(q_t_arr)) + 0.5
ax2.plot([min_t, max_t], [min_t, max_t], '--', color=grid_c, linewidth=1, alpha=0.7)

# バイアス線（中央値シフト）
ax2.plot([min_t, max_t], [min_t - systematic_bias, max_t - systematic_bias],
         '-', color='#FF9900', linewidth=1.5, alpha=0.7,
         label=f'系統バイアス {systematic_bias:+.3f}秒')

ax2.set_xlabel('FPシミュラップタイム (秒)', color=text_c, fontsize=STYLE['label_size'])
ax2.set_ylabel('実際の予選タイム (秒)', color=text_c, fontsize=STYLE['label_size'])
ax2.set_title(f'タイム相関 (Pearson r={pearson_r:.2f})', color=text_c, fontsize=13)
ax2.grid(True, color=grid_c, alpha=0.4, linestyle='--')
ax2.legend(framealpha=0.3, labelcolor=text_c, facecolor=bg_c, fontsize=8)

# --- パネル3: 順位誤差の棒グラフ（ドライバー別）---
ax3 = axes[1, 0]
ax3.set_facecolor(card_bg)
ax3.tick_params(colors=text_c)
for spine in ax3.spines.values():
    spine.set_color(grid_c)

# 予選順位でソート
sorted_by_q = sorted(common_drivers, key=lambda d: quali_ranks[d])
rank_errs = [fp_ranks[d] - quali_ranks[d] for d in sorted_by_q]
bar_colors = ['#e10600' if e < 0 else '#39B54A' for e in rank_errs]
bars = ax3.bar(range(len(sorted_by_q)), rank_errs, color=bar_colors, alpha=0.85, zorder=5)
ax3.set_xticks(range(len(sorted_by_q)))
ax3.set_xticklabels(sorted_by_q, rotation=45, ha='right', color=text_c, fontsize=8)
ax3.axhline(0, color=text_c, linewidth=0.8, alpha=0.5)
ax3.set_xlabel('ドライバー（予選順位順）', color=text_c, fontsize=STYLE['label_size'])
ax3.set_ylabel('順位誤差 (FP順位 - 予選順位)', color=text_c, fontsize=STYLE['label_size'])
ax3.set_title(f'ドライバー別順位誤差 (MAE={rank_mae:.2f}pos)', color=text_c, fontsize=13)
ax3.grid(True, color=grid_c, alpha=0.4, linestyle='--', axis='y')
red_patch = mpatches.Patch(color='#e10600', alpha=0.85, label='FP過大評価（予選より低順位）')
green_patch = mpatches.Patch(color='#39B54A', alpha=0.85, label='FP過小評価（予選より高順位）')
ax3.legend(handles=[red_patch, green_patch], framealpha=0.3, labelcolor=text_c, facecolor=bg_c, fontsize=7)

# --- パネル4: タイム差のヒストグラム & メトリクスサマリー ---
ax4 = axes[1, 1]
ax4.set_facecolor(card_bg)
ax4.tick_params(colors=text_c)
for spine in ax4.spines.values():
    spine.set_color(grid_c)

ax4.hist(time_diffs, bins=8, color='#0072CE', alpha=0.8, edgecolor=grid_c, zorder=5)
ax4.axvline(0, color=text_c, linewidth=1, alpha=0.6, linestyle='--', label='差分ゼロ')
ax4.axvline(systematic_bias, color='#FF9900', linewidth=1.5, alpha=0.8,
            label=f'中央値 {systematic_bias:+.3f}秒')
ax4.set_xlabel('FP時間 - 予選時間 (秒)', color=text_c, fontsize=STYLE['label_size'])
ax4.set_ylabel('ドライバー数', color=text_c, fontsize=STYLE['label_size'])
ax4.set_title('タイム差分分布', color=text_c, fontsize=13)
ax4.grid(True, color=grid_c, alpha=0.4, linestyle='--', axis='y')
ax4.legend(framealpha=0.3, labelcolor=text_c, facecolor=bg_c, fontsize=8)

# メトリクスサマリーテキスト
metrics_text = (
    f"Spearman ρ: {spearman_rho:.3f}\n"
    f"Pearson r:  {pearson_r:.3f}\n"
    f"順位MAE:    {rank_mae:.2f} pos\n"
    f"系統バイアス: {systematic_bias:+.3f}秒\n"
    f"対象ドライバー: {len(common_drivers)}名\n"
    f"使用FPセッション: {', '.join(sessions_found)}"
)
ax4.text(0.97, 0.97, metrics_text,
         transform=ax4.transAxes,
         verticalalignment='top', horizontalalignment='right',
         color=text_c, fontsize=9,
         bbox=dict(boxstyle='round', facecolor='#1c1c25', alpha=0.8, edgecolor=grid_c))

plt.tight_layout(rect=[0, 0, 1, 0.96])

png_out = os.path.join(OUTPUT_DIR, 'fp_quali_scatter.png')
plt.savefig(png_out, dpi=150, bbox_inches='tight', facecolor=STYLE['bg_color'])
plt.close()
print(f"PNG保存: {png_out}")

# ===== 最終サマリー =====
print("\n" + "=" * 60)
print("=== 2026 R02 中国GP FP→予選予測 分析サマリー ===")
print("=" * 60)
print(f"使用FPセッション: {sessions_found} (スプリントWEのためFP1のみ)")
print(f"予選シミュラップ特定数: {len(all_qualisim)}ラップ")
print(f"分析対象ドライバー: {len(common_drivers)}名")
print()
print(f"  Spearman順位相関 (ρ): {spearman_rho:.3f}")
print(f"  Pearsonタイム相関 (r): {pearson_r:.3f}")
print(f"  順位MAE: {rank_mae:.2f}ポジション")
print(f"  系統バイアス: {systematic_bias:+.3f}秒")
print()
print("【解釈】")
if spearman_rho > 0.7:
    print("  ✓ 順位相関が高い → FPシミュラップは予選順位の良い指標")
elif spearman_rho > 0.5:
    print("  △ 順位相関が中程度 → FPシミュラップはある程度有用だが精度に限界")
else:
    print("  ✗ 順位相関が低い → FPシミュラップからの予選予測は困難")

if abs(systematic_bias) > 0.5:
    direct = "遅い" if systematic_bias > 0 else "速い"
    print(f"  ! 系統バイアスが大きい ({systematic_bias:+.3f}秒) → FPは予選より{direct}傾向")
else:
    print(f"  ✓ 系統バイアスは小さい ({systematic_bias:+.3f}秒) → FPタイムは予選と近い")

print(f"\n出力ファイル:")
print(f"  {csv_out}")
print(f"  {png_out}")
