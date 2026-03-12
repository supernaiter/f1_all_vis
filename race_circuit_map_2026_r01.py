"""
Albert Park Circuit - 速度計測ポイント コースマップ
"""

import fastf1
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

for fn in ['Yu Gothic', 'Meiryo', 'MS Gothic']:
    try:
        matplotlib.font_manager.FontProperties(family=fn)
        plt.rcParams['font.family'] = fn
        break
    except:
        continue

# データ読み込み
print('データ読み込み中...')
fastf1.Cache.enable_cache('~/f1_cache')
s = fastf1.get_session(2026, 'Australia', 'R')
s.load(telemetry=True, laps=True, weather=False)

fastest = s.laps.pick_fastest()
tel = fastest.get_telemetry()
ci = s.get_circuit_info()

# 回転補正
theta = np.radians(ci.rotation)
cos_t, sin_t = np.cos(theta), np.sin(theta)

x_raw, y_raw = tel['X'].values, tel['Y'].values
x_rot = x_raw * cos_t - y_raw * sin_t
y_rot = x_raw * sin_t + y_raw * cos_t
dist = tel['Distance'].values
total_dist = dist.max()

# セクター境界距離（テレメトリの時間→距離補間）
rel_time = (tel['SessionTime'] - tel['SessionTime'].iloc[0]).dt.total_seconds().values
s1t = fastest['Sector1Time'].total_seconds()
s2t = fastest['Sector2Time'].total_seconds()
s1_end_dist = np.interp(s1t, rel_time, dist)
s2_end_dist = np.interp(s1t + s2t, rel_time, dist)

print(f'S1 end: {s1_end_dist:.0f}m, S2 end: {s2_end_dist:.0f}m, Total: {total_dist:.0f}m')

# 距離→回転済み座標
def dist_to_xy(d):
    return np.interp(d, dist, x_rot), np.interp(d, dist, y_rot)

# 速度計測ポイント
points = {
    'SpeedI1\n(S1末端)': s1_end_dist,
    'SpeedI2\n(S2末端)': s2_end_dist,
    'SpeedFL\n(フィニッシュライン)': total_dist - 10,
    'SpeedST\n(スピードトラップ)': total_dist - 200,
}

# プロット
print('コースマップ生成中...')
fig, ax = plt.subplots(figsize=(14, 12), facecolor='white')
ax.set_facecolor('white')

# コース下地（太いグレー）
ax.plot(x_rot, y_rot, color='#DDDDDD', linewidth=12, solid_capstyle='round', zorder=1)

# セクター色分けライン
pts = np.array([x_rot, y_rot]).T.reshape(-1, 1, 2)
segments = np.concatenate([pts[:-1], pts[1:]], axis=1)

sector_colors_map = {'s1': '#4488CC', 's2': '#CC6644', 's3': '#44AA66'}
track_colors = []
for i in range(len(dist) - 1):
    d = dist[i]
    if d <= s1_end_dist:
        track_colors.append(sector_colors_map['s1'])
    elif d <= s2_end_dist:
        track_colors.append(sector_colors_map['s2'])
    else:
        track_colors.append(sector_colors_map['s3'])

lc = LineCollection(segments, colors=track_colors, linewidths=6, zorder=2)
ax.add_collection(lc)

# セクター境界マーカー
for label, d in [('Sector 1 | 2', s1_end_dist), ('Sector 2 | 3', s2_end_dist)]:
    sx, sy = dist_to_xy(d)
    ax.plot(sx, sy, 'o', color='white', markersize=14, zorder=5,
            markeredgecolor='#333', markeredgewidth=2)
    ax.annotate(label, (sx, sy), xytext=(15, -25), textcoords='offset points',
                fontsize=9, color='#444', fontweight='bold', ha='left',
                arrowprops=dict(arrowstyle='->', color='#666', lw=1.2))

# 速度計測ポイント
marker_colors = {
    'SpeedI1\n(S1末端)': '#2255AA',
    'SpeedI2\n(S2末端)': '#BB4422',
    'SpeedFL\n(フィニッシュライン)': '#8B008B',
    'SpeedST\n(スピードトラップ)': '#CC0000',
}
offsets = {
    'SpeedI1\n(S1末端)': (-120, 30),
    'SpeedI2\n(S2末端)': (20, -40),
    'SpeedFL\n(フィニッシュライン)': (-160, -30),
    'SpeedST\n(スピードトラップ)': (20, 30),
}

for label, d in points.items():
    px, py = dist_to_xy(d)
    mc = marker_colors[label]
    ax.plot(px, py, 's', color=mc, markersize=14, zorder=10,
            markeredgecolor='white', markeredgewidth=2)
    ox, oy = offsets[label]
    ax.annotate(label, (px, py), xytext=(ox, oy), textcoords='offset points',
                fontsize=11, color=mc, fontweight='bold', ha='center', va='center',
                bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                          edgecolor=mc, alpha=0.9, linewidth=1.5),
                arrowprops=dict(arrowstyle='->', color=mc, lw=1.5,
                                connectionstyle='arc3,rad=0.2'),
                zorder=11)

# コーナー番号
corners = ci.corners
for _, row in corners.iterrows():
    cx = row['X'] * cos_t - row['Y'] * sin_t
    cy = row['X'] * sin_t + row['Y'] * cos_t
    num = int(row['Number'])
    ax.plot(cx, cy, 'o', color='#999', markersize=5, zorder=3)
    ax.text(cx + 80, cy + 80, f'T{num}', fontsize=7, color='#999',
            ha='center', va='center', fontweight='bold')

# 走行方向矢印
for ad in [500, 1500, 2500, 3500, 4500]:
    a1x, a1y = dist_to_xy(ad)
    a2x, a2y = dist_to_xy(ad + 80)
    ax.annotate('', xy=(a2x, a2y), xytext=(a1x, a1y),
                arrowprops=dict(arrowstyle='->', color='#AAA', lw=1.5), zorder=4)

# セクターラベル
for label, mid_d, color in [('Sector 1', s1_end_dist / 2, sector_colors_map['s1']),
                              ('Sector 2', (s1_end_dist + s2_end_dist) / 2, sector_colors_map['s2']),
                              ('Sector 3', (s2_end_dist + total_dist) / 2, sector_colors_map['s3'])]:
    mx, my = dist_to_xy(mid_d)
    ax.text(mx, my - 400, label, fontsize=13, color=color, fontweight='bold',
            ha='center', va='center', alpha=0.7)

# スタート/フィニッシュ
fx, fy = dist_to_xy(0)
ax.plot(fx, fy, 'D', color='#333', markersize=10, zorder=10,
        markeredgecolor='white', markeredgewidth=2)
ax.annotate('START / FINISH', (fx, fy), xytext=(-30, -40),
            textcoords='offset points', fontsize=9, color='#333', fontweight='bold',
            ha='center',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#FFD700',
                      edgecolor='#333', alpha=0.8))

# 軸設定
ax.set_aspect('equal')
ax.axis('off')
ax.set_title('Albert Park Circuit - 速度計測ポイント\n'
             '2026 Australian Grand Prix',
             fontsize=18, fontweight='bold', color='#1a1a2e', pad=20)

# 凡例
legend_items = [
    plt.Line2D([0], [0], color='#4488CC', linewidth=6, label='Sector 1'),
    plt.Line2D([0], [0], color='#CC6644', linewidth=6, label='Sector 2'),
    plt.Line2D([0], [0], color='#44AA66', linewidth=6, label='Sector 3'),
    plt.Line2D([0], [0], marker='s', color='w', markerfacecolor='#2255AA',
               markersize=10, label='SpeedI1 (S1末端速度)'),
    plt.Line2D([0], [0], marker='s', color='w', markerfacecolor='#BB4422',
               markersize=10, label='SpeedI2 (S2末端速度)'),
    plt.Line2D([0], [0], marker='s', color='w', markerfacecolor='#8B008B',
               markersize=10, label='SpeedFL (フィニッシュライン速度)'),
    plt.Line2D([0], [0], marker='s', color='w', markerfacecolor='#CC0000',
               markersize=10, label='SpeedST (スピードトラップ)'),
]
ax.legend(handles=legend_items, loc='lower right', fontsize=10, framealpha=0.95,
          facecolor='white', edgecolor='#AAA', labelcolor='#333')

out = Path('./data/2026_R01_Australia/article/art_circuit_speed_points.png')
out.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(out, dpi=180, facecolor='white', bbox_inches='tight', pad_inches=0.3)
print(f'保存: {out} ({out.stat().st_size / 1024:.0f} KB)')
plt.close(fig)
print('完了!')
