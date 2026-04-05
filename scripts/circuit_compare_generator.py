#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
circuit_compare_generator.py

24サーキットのマスターデータから、
276ペア × 2種（radar, era_adjusted）のJSONを一括生成する。

出力:
  data/circuits/master.json                       — 24コースマスター
  data/circuits/pairs/{c1}-vs-{c2}/radar.json     — 6軸レーダー用
  data/circuits/pairs/{c1}-vs-{c2}/era_adjusted.json — Era比較用（Phase 2でFastF1実データ差し替え）

注意:
  - 各軸の 0-100 スコアは公開情報・定性観察・平均速度等から手動スケーリング
  - era_adjusted は source: "pending" で Phase 2 再生成を示唆
  - ペアキーは辞書順（driver_compare_generator.py と同じ規約）
"""

import json
from itertools import combinations
from pathlib import Path

# ============================================================
# 24サーキットマスター（2026カレンダー順）
# ============================================================
# 6軸: straight_speed / low_speed / high_speed / braking / tyre_deg / overtaking
# すべて 0-100。直感的スケーリング。
CIRCUITS = [
    # slug, display_name, country, length_km, corners, drs_zones,
    # avg_speed_kmh, downforce(1-5), color, axes(6)
    ("albert_park", "Albert Park", "AUS", 5.278, 14, 4, 237, 3, "#00843D",
     [70, 55, 75, 60, 55, 65]),
    ("shanghai", "Shanghai", "CHN", 5.451, 16, 2, 206, 3, "#EE1C25",
     [78, 70, 68, 75, 60, 78]),
    ("suzuka", "Suzuka", "JPN", 5.807, 18, 1, 227, 4, "#BC002D",
     [65, 55, 92, 75, 70, 55]),
    ("bahrain", "Bahrain", "BHR", 5.412, 15, 3, 208, 3, "#E80020",
     [85, 60, 68, 88, 78, 80]),
    ("jeddah", "Jeddah", "SAU", 6.174, 27, 3, 252, 2, "#006C35",
     [90, 30, 90, 70, 60, 55]),
    ("miami", "Miami", "USA", 5.412, 19, 3, 221, 3, "#FF6600",
     [80, 60, 75, 82, 65, 78]),
    ("montreal", "Montreal", "CAN", 4.361, 14, 3, 207, 2, "#FF0000",
     [82, 70, 60, 90, 60, 85]),
    ("monaco", "Monaco", "MON", 3.337, 19, 1, 166, 5, "#FFD700",
     [30, 95, 45, 70, 40, 8]),
    ("barcelona", "Barcelona", "ESP", 4.657, 14, 2, 209, 4, "#AA151B",
     [65, 60, 85, 70, 75, 50]),
    ("spielberg", "Spielberg", "AUT", 4.318, 10, 3, 225, 2, "#ED2939",
     [80, 55, 70, 80, 60, 82]),
    ("silverstone", "Silverstone", "GBR", 5.891, 18, 2, 237, 3, "#012169",
     [72, 55, 95, 70, 72, 75]),
    ("spa", "Spa", "BEL", 7.004, 20, 2, 234, 2, "#FAE042",
     [92, 55, 92, 72, 65, 85]),
    ("hungaroring", "Hungaroring", "HUN", 4.381, 14, 2, 189, 4, "#477050",
     [50, 85, 70, 75, 70, 40]),
    ("zandvoort", "Zandvoort", "NED", 4.259, 14, 2, 200, 4, "#FF4F00",
     [55, 70, 88, 65, 75, 35]),
    ("monza", "Monza", "ITA", 5.793, 11, 3, 264, 1, "#008C45",
     [98, 45, 60, 92, 55, 85]),
    ("madrid", "Madrid", "ESP", 5.474, 22, 3, 215, 3, "#C60B1E",
     [78, 70, 72, 75, 65, 70]),
    ("baku", "Baku", "AZE", 6.003, 20, 2, 215, 2, "#00B9E4",
     [92, 78, 55, 85, 55, 80]),
    ("singapore", "Singapore", "SGP", 4.940, 19, 3, 172, 4, "#EF3340",
     [55, 88, 60, 80, 78, 55]),
    ("austin", "Austin", "USA", 5.513, 20, 2, 205, 3, "#3C3B6E",
     [72, 65, 88, 78, 65, 75]),
    ("mexico", "Mexico City", "MEX", 4.304, 17, 3, 223, 3, "#006847",
     [85, 68, 65, 82, 55, 78]),
    ("interlagos", "Interlagos", "BRA", 4.309, 15, 2, 215, 3, "#FEDD00",
     [78, 62, 80, 75, 72, 88]),
    ("las_vegas", "Las Vegas", "USA", 6.201, 17, 2, 240, 2, "#C8102E",
     [92, 55, 65, 82, 55, 82]),
    ("lusail", "Lusail", "QAT", 5.419, 16, 2, 213, 3, "#8B1538",
     [68, 55, 90, 70, 88, 50]),
    ("yas_marina", "Yas Marina", "UAE", 5.281, 16, 2, 198, 3, "#00732F",
     [75, 70, 72, 78, 60, 65]),
]

AXIS_LABELS = [
    "STRAIGHT SPEED",
    "LOW-SPEED",
    "HIGH-SPEED",
    "BRAKING",
    "TYRE DEG",
    "OVERTAKING",
]


def build_master():
    """24コースマスター辞書を返す"""
    master = {}
    for (slug, name, country, length, corners, drs, avg_speed, df, color, axes) in CIRCUITS:
        master[slug] = {
            "slug": slug,
            "name": name,
            "country": country,
            "length_km": length,
            "corners": corners,
            "drs_zones": drs,
            "avg_speed_kmh": avg_speed,
            "downforce": df,
            "color": color,
            "axes": dict(zip(AXIS_LABELS, axes)),
        }
    return master


def pair_slug(a, b):
    """辞書順で {a}-vs-{b} を返す"""
    a, b = sorted([a, b])
    return f"{a}-vs-{b}"


def build_radar(c1, c2):
    """TYPE-D1: 6軸レーダー用JSON"""
    return {
        "type": "radar",
        "axes": AXIS_LABELS,
        "circuit1": {
            "slug": c1["slug"],
            "name": c1["name"].upper(),
            "country": c1["country"],
            "color": c1["color"],
            "values": [c1["axes"][k] for k in AXIS_LABELS],
        },
        "circuit2": {
            "slug": c2["slug"],
            "name": c2["name"].upper(),
            "country": c2["country"],
            "color": c2["color"],
            "values": [c2["axes"][k] for k in AXIS_LABELS],
        },
        "meta": {
            "subtitle": f"{c1['name'].upper()} vs {c2['name'].upper()} · 6-AXIS CIRCUIT CHARACTER",
            "source": "manual-curated",
        },
    }


def build_era_adjusted(c1, c2):
    """
    TYPE-D2: Era-Adjusted Qualifying
    FastF1実データが取得されるまで source: "pending" のプレースホルダ。
    Phase 2 で2018-2025の予選ベストラップから year×circuit の正規化ペースを埋める。
    """
    return {
        "type": "era_adjusted_qualifying",
        "circuit1": {
            "slug": c1["slug"],
            "name": c1["name"].upper(),
            "color": c1["color"],
            # 各要素: {year, pole_time_sec, pole_driver, delta_vs_baseline_sec}
            "era_points": [],
        },
        "circuit2": {
            "slug": c2["slug"],
            "name": c2["name"].upper(),
            "color": c2["color"],
            "era_points": [],
        },
        "meta": {
            "subtitle": f"{c1['name'].upper()} vs {c2['name'].upper()} · ERA-ADJUSTED POLE TIMES",
            "source": "pending",  # Phase 2で FastF1 2018-2025 から実データ化
            "note": "This card is a Phase-2 placeholder. Real data requires FastF1 quali export.",
        },
    }


def main():
    root = Path(__file__).resolve().parent.parent
    out_dir = root / "data" / "circuits"
    pairs_dir = out_dir / "pairs"
    pairs_dir.mkdir(parents=True, exist_ok=True)

    # マスター
    master = build_master()
    (out_dir / "master.json").write_text(
        json.dumps(master, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"[OK] master.json: {len(master)} circuits")

    # 276ペア × 2種
    slugs = [row[0] for row in CIRCUITS]
    pair_count = 0
    for a, b in combinations(slugs, 2):
        pair = pair_slug(a, b)
        c1, c2 = master[sorted([a, b])[0]], master[sorted([a, b])[1]]
        pdir = pairs_dir / pair
        pdir.mkdir(exist_ok=True)
        (pdir / "radar.json").write_text(
            json.dumps(build_radar(c1, c2), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (pdir / "era_adjusted.json").write_text(
            json.dumps(build_era_adjusted(c1, c2), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        pair_count += 1

    print(f"[OK] pairs: {pair_count} × 2 files = {pair_count * 2}")


if __name__ == "__main__":
    main()
