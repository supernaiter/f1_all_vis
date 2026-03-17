"""
現役F1ドライバー22名 — デビューからX年目に初優勝？
水平バーチャート（X投稿用・チームカラー版）
"""

import matplotlib.pyplot as plt
from matplotlib.transforms import blended_transform_factory
import numpy as np

# ============================================================
# フォント設定
# ============================================================
plt.rcParams['font.family'] = ['Yu Gothic', 'Meiryo', 'Noto Sans JP', 'Arial']
plt.rcParams['axes.unicode_minus'] = False

# ============================================================
# プロジェクト標準スタイル
# ============================================================
BG_COLOR   = '#1a1a2e'
TEXT_COLOR  = '#ffffff'
GRID_COLOR = '#333355'
GREY_TEXT  = '#aaaaaa'

# ============================================================
# 2026チームカラー
# ============================================================
TEAM_COLORS = {
    'McLaren':      '#FF8000',
    'Ferrari':      '#E8002D',
    'Red Bull':     '#3671C6',
    'Mercedes':     '#27F4D2',
    'Aston Martin': '#229971',
    'Williams':     '#64C4FF',
    'Racing Bulls': '#6692FF',
    'Alpine':       '#ff87bc',
    'Haas':         '#B6BABD',
    'Audi':         '#ff2d00',
    'Cadillac':     '#888888',
}

# ============================================================
# 世界チャンピオン（☆マーク対象）
# ============================================================
WDC_DRIVERS = {'Hamilton', 'Verstappen', 'Alonso', 'Norris'}

# デビュー年の定義: その年のレースの半数以上に出走した最初の年
# *マーク = 初年度が半数未満のため翌年以降をデビュー年とした
ASTERISK_DRIVERS = {'Gasly', 'Ocon', 'Lawson', 'Bearman', 'Colapinto'}

# ============================================================
# データ（current_team = 2026年所属チーム）
# ============================================================
winners = [
    {"driver": "Hamilton",   "debut": 2007, "first_win": 2007, "win_race": "Canadian GP",   "year_n": 1,  "win_gp": 6,   "current_team": "Ferrari"},
    {"driver": "Verstappen", "debut": 2015, "first_win": 2016, "win_race": "Spanish GP",    "year_n": 2,  "win_gp": 24,  "current_team": "Red Bull"},
    {"driver": "Leclerc",    "debut": 2018, "first_win": 2019, "win_race": "Belgian GP",    "year_n": 2,  "win_gp": 34,  "current_team": "Ferrari"},
    {"driver": "Antonelli",  "debut": 2025, "first_win": 2026, "win_race": "Chinese GP",    "year_n": 2,  "win_gp": 26,  "current_team": "Mercedes"},
    {"driver": "Piastri",    "debut": 2023, "first_win": 2024, "win_race": "Hungarian GP",  "year_n": 2,  "win_gp": 35,  "current_team": "McLaren"},
    {"driver": "Alonso",     "debut": 2001, "first_win": 2003, "win_race": "Hungarian GP",  "year_n": 3,  "win_gp": 30,  "current_team": "Aston Martin"},  # 2019-2020休止(WEC/Indy) ※初優勝後
    {"driver": "Gasly",      "debut": 2018, "first_win": 2020, "win_race": "Italian GP",    "year_n": 3,  "win_gp": 55,  "current_team": "Alpine"},  # 2017年5戦(半数未満)→2018デビュー
    {"driver": "Russell",    "debut": 2019, "first_win": 2022, "win_race": "Brazilian GP",  "year_n": 4,  "win_gp": 81,  "current_team": "Mercedes"},
    {"driver": "Bottas",     "debut": 2013, "first_win": 2017, "win_race": "Russian GP",    "year_n": 5,  "win_gp": 81,  "current_team": "Cadillac"},  # 2025休止(Sauber離脱) ※初優勝後
    {"driver": "Ocon",       "debut": 2017, "first_win": 2021, "win_race": "Hungarian GP",  "year_n": 4,  "win_gp": 78,  "current_team": "Haas"},  # 2016年9戦(半数未満)→2017デビュー, 2019休止
    {"driver": "Norris",     "debut": 2019, "first_win": 2024, "win_race": "Miami GP",      "year_n": 6,  "win_gp": 110, "current_team": "McLaren"},
    {"driver": "Sainz",      "debut": 2015, "first_win": 2022, "win_race": "British GP",    "year_n": 8,  "win_gp": 150, "current_team": "Williams"},
    {"driver": "Perez",      "debut": 2011, "first_win": 2020, "win_race": "Sakhir GP",     "year_n": 10, "win_gp": 190, "current_team": "Cadillac"},
]

no_wins = [
    {"driver": "Hülkenberg", "debut": 2010, "year_n": 14, "current_team": "Audi"},  # 2020-2022休止(代走のみ)
    {"driver": "Stroll",     "debut": 2017, "year_n": 10, "current_team": "Aston Martin"},
    {"driver": "Albon",      "debut": 2019, "year_n": 7,  "current_team": "Williams"},  # 2021休止(Red Bull reserve)
    {"driver": "Lawson",     "debut": 2025, "year_n": 2,  "current_team": "Racing Bulls"},  # 2023年5戦+2024年6戦(共に半数未満)→2025デビュー
    {"driver": "Colapinto",  "debut": 2025, "year_n": 2,  "current_team": "Alpine"},  # 2024年9戦(半数未満)→2025デビュー
    {"driver": "Bearman",    "debut": 2025, "year_n": 2,  "current_team": "Haas"},  # 2024年3戦(半数未満)→2025デビュー
    {"driver": "Hadjar",     "debut": 2025, "year_n": 2,  "current_team": "Red Bull"},
    {"driver": "Bortoleto",  "debut": 2025, "year_n": 2,  "current_team": "Audi"},
    {"driver": "Lindblad",   "debut": 2026, "year_n": 1,  "current_team": "Racing Bulls"},
]

# ============================================================
# ソート: 優勝者（年数昇順）→ 未勝利（年数昇順）
# ============================================================
# 同じ年数の場合、GP出走数が少ない（＝より早く勝った）方を上に
winners_sorted = sorted(winners, key=lambda x: (x['year_n'], x['win_gp']))
no_wins_sorted = sorted(no_wins, key=lambda x: x['year_n'])


def create_chart(lang='jp'):
    """
    チャート生成（X投稿用・チームカラー版）
    lang: 'jp' = 日本語版, 'en' = 英語版
    """
    # 全ドライバーリスト（反転: matplotlibのbarhは下から描画）
    all_drivers = winners_sorted + no_wins_sorted
    all_drivers = all_drivers[::-1]

    n = len(all_drivers)
    y_pos = np.arange(n)

    values = [d['year_n'] for d in all_drivers]
    is_winner = ['first_win' in d for d in all_drivers]
    team_colors = [TEAM_COLORS[d['current_team']] for d in all_drivers]

    # ドライバー名ラベル（WDC星は別列で表示するためプレフィックス不要）
    labels = [d['driver'] for d in all_drivers]

    # --- 図の作成（モバイル最適化: 縦長3:4） ---
    fig, ax = plt.subplots(figsize=(10, 13))
    fig.set_facecolor(BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    bar_height = 0.70

    # --- Antonelliハイライト（背景コントラスト強 + 太い実線枠） ---
    trans_highlight = blended_transform_factory(ax.transAxes, ax.transData)
    for i, d in enumerate(all_drivers):
        if d['driver'] == 'Antonelli':
            import matplotlib.patches as mpatches
            # 濃い背景帯
            ax.axhspan(i - 0.48, i + 0.48, color='#27F4D2', alpha=0.25, zorder=0)
            # 太い実線枠
            highlight_rect = mpatches.FancyBboxPatch(
                (-0.18, i - 0.46), 1.27, 0.92,
                boxstyle='round,pad=0.02',
                facecolor='none',
                edgecolor='#27F4D2', linewidth=3.0,
                zorder=4, clip_on=False,
                transform=trans_highlight)
            ax.add_patch(highlight_rect)
            break

    # バーを描画
    for i, (val, col, winner) in enumerate(zip(values, team_colors, is_winner)):
        if not winner:
            # 未勝利: ハッチング + 低alpha
            ax.barh(i, val, color=col, alpha=0.40, edgecolor=col,
                    linewidth=1.0, height=bar_height, hatch='///', zorder=2)
        else:
            # 優勝者: ソリッド + エッジ強調
            ax.barh(i, val, color=col, alpha=0.90, edgecolor='#ffffff',
                    linewidth=0.6, height=bar_height, zorder=2)

    # --- アノテーション（長いバーはバー内、短いバーは右側） ---
    INSIDE_THRESHOLD = 6  # year_n >= 6 のバーはテキストを内側に

    for i, d in enumerate(all_drivers):
        asterisk = '*' if d['driver'] in ASTERISK_DRIVERS else ''
        val = d['year_n']

        if 'first_win' in d:
            race_short = d['win_race'].replace(' Grand Prix', '').replace(' GP', '')

            if val >= INSIDE_THRESHOLD:
                # --- バー内配置（右寄せ） ---
                num_text = f"{val}{asterisk}"
                detail = f"({d['first_win']} {race_short})"
                ax.text(val - 0.3, i, num_text,
                        color='#ffffff', fontsize=22, fontweight='bold',
                        ha='right', va='center', zorder=3)
                ax.text(val - 0.3 - (1.2 if val < 10 else 1.7), i, detail,
                        color='#ffffffbb', fontsize=11,
                        ha='right', va='center', zorder=3)
            else:
                # --- バー右側配置 ---
                x_offset = val + 0.3
                if d['driver'] == 'Hamilton':
                    if lang == 'jp':
                        num_text = f"{val}年目"
                        gap = 2.5
                    else:
                        num_text = f"Year {val}"
                        gap = 3.5
                else:
                    num_text = f"{val}{asterisk}"
                    gap = 1.2 if val < 10 else 1.7

                ax.text(x_offset, i, num_text,
                        color=TEXT_COLOR, fontsize=22, fontweight='bold',
                        va='center', zorder=3)
                detail = f"({d['first_win']} {race_short})"
                ax.text(x_offset + gap, i, detail,
                        color=GREY_TEXT, fontsize=11,
                        va='center', zorder=3)
        else:
            if lang == 'jp':
                label = f"未勝利{asterisk}（{d['debut']}〜）"
            else:
                label = f"No wins{asterisk} (since {d['debut']})"

            if val >= INSIDE_THRESHOLD:
                # --- バー内配置（右寄せ） ---
                ax.text(val - 0.3, i, label,
                        color='#ffffff', fontsize=13, fontweight='bold',
                        ha='right', va='center', zorder=3)
            else:
                # --- バー右側配置 ---
                ax.text(val + 0.3, i, label,
                        color=GREY_TEXT, fontsize=13,
                        va='center', zorder=3)

    # --- Y軸ラベル（ドライバー名、チームカラーで着色） ---
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=16, fontweight='bold')
    # チームカラーでY軸ラベルを着色
    for tick_label, d in zip(ax.get_yticklabels(), all_drivers):
        tick_label.set_color(TEAM_COLORS[d['current_team']])

    # --- 優勝者と未勝利者の境界線 ---
    boundary_idx = len(no_wins_sorted) - 0.5
    ax.axhline(y=boundary_idx, color='#666688', linewidth=1.2,
               linestyle='--', zorder=1)

    # 境界ラベル
    if lang == 'jp':
        sep_up = '▼ 優勝経験あり'
        sep_down = '▲ 未勝利'
    else:
        sep_up = '▼ Race winners'
        sep_down = '▲ No wins yet'

    # 境界ラベル（バー内テキスト化により右端を節約）
    label_x = max(values) - 0.3
    ax.text(label_x, boundary_idx + 0.35, sep_up,
            color='#888899', fontsize=11, va='center', ha='right', zorder=3)
    ax.text(label_x, boundary_idx - 0.35, sep_down,
            color='#888899', fontsize=11, va='center', ha='right', zorder=3)

    # --- X軸（バー内テキスト化で右余白を削減） ---
    x_max = max(values) + 2
    ax.set_xlim(0, x_max)
    ax.set_xticks(range(0, int(x_max), 2))
    if lang == 'jp':
        ax.set_xticklabels([f'{x}年目' if x > 0 else '0' for x in range(0, int(x_max), 2)],
                           fontsize=12, color=TEXT_COLOR)
        ax.set_xlabel('フル参戦からの年数（休止年除外）', fontsize=14, color=TEXT_COLOR, labelpad=8)
    else:
        ax.set_xticklabels([f'Year {x}' if x > 0 else '0' for x in range(0, int(x_max), 2)],
                           fontsize=12, color=TEXT_COLOR)
        ax.set_xlabel('Full-time Seasons from Debut (sabbaticals excluded)', fontsize=14, color=TEXT_COLOR, labelpad=8)

    # --- グリッド ---
    ax.xaxis.grid(True, color=GRID_COLOR, linewidth=0.5, alpha=0.85, zorder=0)
    ax.yaxis.grid(False)
    ax.set_axisbelow(True)

    # --- タイトル ---
    if lang == 'jp':
        title = '2026 F1ドライバー — デビューからX年目に初優勝？'
    else:
        title = '2026 F1 Drivers: Years from Debut to First Win'

    fig.text(0.06, 0.975, title,
             fontsize=22, color=TEXT_COLOR, fontweight='bold',
             ha='left', va='top')

    # --- フッター ---
    if lang == 'jp':
        footer = 'Data: Wikipedia, F1.com, StatsF1 | 休止年は年数から除外 | * = 初年度半数未満のためフル参戦初年をデビュー年とした'
    else:
        footer = 'Data: Wikipedia, F1.com, StatsF1 | Sabbaticals excluded | * = Debut year set to first season with 50%+ race starts'
    copyright_text = '\u00a9 Motorsports Visualised'

    fig.text(0.02, 0.008, footer, fontsize=7, color='#777777',
             ha='left', va='bottom')
    fig.text(0.98, 0.008, copyright_text, fontsize=7, color='#777777',
             ha='right', va='bottom')

    # --- 枠線を整える ---
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(axis='y', length=0)
    ax.tick_params(axis='x', colors=TEXT_COLOR, length=3)

    # --- GP出走数列（右端に縦列として表示） ---
    plt.tight_layout(rect=[0, 0.02, 0.92, 0.96])  # サブタイトル削除で上部余白を縮小
    fig.canvas.draw()
    trans_right = blended_transform_factory(ax.transAxes, ax.transData)

    # ヘッダー
    if lang == 'jp':
        gp_header = 'GP数'
    else:
        gp_header = 'GPs'
    # ヘッダーは優勝者エリアの上部に配置
    winner_top_idx = n - 1 + 0.7  # 最上行の少し上
    ax.text(1.06, winner_top_idx, gp_header, transform=trans_right,
            color=GREY_TEXT, fontsize=12, fontweight='bold',
            ha='center', va='center', clip_on=False)

    # 各優勝者のGP出走数
    for i, d in enumerate(all_drivers):
        if 'win_gp' in d:
            is_antonelli = d['driver'] == 'Antonelli'
            ax.text(1.06, i, str(d['win_gp']), transform=trans_right,
                    color='#27F4D2' if is_antonelli else TEXT_COLOR,
                    fontsize=15 if is_antonelli else 13,
                    fontweight='bold' if is_antonelli else 'normal',
                    ha='center', va='center', clip_on=False)

    # --- WDC星マーク（ドライバー名の左側に黄色い大きな★を配置） ---
    trans = blended_transform_factory(ax.transAxes, ax.transData)
    for i, d in enumerate(all_drivers):
        if d['driver'] in WDC_DRIVERS:
            ax.text(-0.22, i, '★', transform=trans,
                    color='#FFD700', fontsize=22, fontweight='bold',
                    ha='center', va='center', clip_on=False, zorder=5)

    # --- 保存 ---
    suffix = 'jp' if lang == 'jp' else 'en'
    out_path = f'years_to_first_win_current_grid_{suffix}.png'
    plt.savefig(out_path, dpi=200, bbox_inches='tight',
                facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()
    print(f"保存完了: {out_path}")
    return out_path


# ============================================================
# 実行
# ============================================================
if __name__ == '__main__':
    create_chart('jp')
    create_chart('en')
