#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
team_compare_generator.py
TYPE-E: チーム2者比較 (GP単位)
入力: data/{gp}/export/race_laps.csv
出力: data/teams/{gp_slug}/{team1}-vs-{team2}/{dna|variance}.json
"""
import argparse
import csv
import itertools
import json
import re
import statistics
from pathlib import Path

TEAM_COLORS = {
    "McLaren": "#E07800", "Ferrari": "#DC0000", "Red Bull Racing": "#2B5DAB",
    "Mercedes": "#00B89F", "Aston Martin": "#1B7A5A", "Williams": "#3BA3E0",
    "Racing Bulls": "#4A72CC", "Alpine": "#0078AA", "Haas F1 Team": "#7A7A7A",
    "Audi": "#3AAA3A", "Cadillac": "#888888",
}

TEAM_SLUG = {
    "McLaren": "mcl", "Ferrari": "fer", "Red Bull Racing": "rbr",
    "Mercedes": "mer", "Aston Martin": "amr", "Williams": "wil",
    "Racing Bulls": "rbu", "Alpine": "alp", "Haas F1 Team": "has",
    "Audi": "aud", "Cadillac": "cad",
}


def fnum(v):
    try:
        if v in (None, "", "nan"):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def compute_team_stats(laps):
    """チームごとの素の統計値を出す"""
    by_team = {}
    for lap in laps:
        t = fnum(lap["LapTime_sec"])
        if t is None:
            continue
        team = lap["Team"]
        spd = fnum(lap["SpeedST"])
        by_team.setdefault(team, {"times": [], "speeds": []})
        by_team[team]["times"].append(t)
        if spd is not None:
            by_team[team]["speeds"].append(spd)
    stats = {}
    for team, data in by_team.items():
        times = data["times"]
        if len(times) < 5:
            continue
        m = statistics.median(times)
        clean = [x for x in times if x <= m * 1.07]
        if len(clean) < 3:
            continue
        stats[team] = {
            "median": statistics.median(clean),
            "stdev": statistics.pstdev(clean),
            "top_speed": max(data["speeds"]) if data["speeds"] else 0,
            "pace_min": min(clean),
            "tyre_mgmt": statistics.mean(sorted(clean)[-5:]) - statistics.mean(sorted(clean)[:5]),
            "laps": len(clean),
        }
    return stats


def normalize(value, lo, hi, invert=False):
    if hi - lo < 1e-9:
        return 50.0
    v = (value - lo) / (hi - lo) * 100
    return round(100 - v if invert else v, 1)


def build_dna(stats, team1, team2):
    """5軸スコア: PACE/SPEED/CONSISTENCY/TYRE/ENDURANCE"""
    s1 = stats[team1]
    s2 = stats[team2]
    # 全チーム内のminmaxで正規化
    all_median = [v["median"] for v in stats.values()]
    all_speed = [v["top_speed"] for v in stats.values()]
    all_std = [v["stdev"] for v in stats.values()]
    all_tyre = [v["tyre_mgmt"] for v in stats.values()]
    all_min = [v["pace_min"] for v in stats.values()]
    all_laps = [v["laps"] for v in stats.values()]

    def score(s):
        return [
            normalize(s["median"], min(all_median), max(all_median), invert=True),  # PACE
            normalize(s["top_speed"], min(all_speed), max(all_speed)),  # TOP SPEED
            normalize(s["stdev"], min(all_std), max(all_std), invert=True),  # CONSISTENCY
            normalize(s["tyre_mgmt"], min(all_tyre), max(all_tyre), invert=True),  # TYRE MGMT
            normalize(s["laps"], min(all_laps), max(all_laps)),  # ENDURANCE
        ]

    return {
        "type": "dna",
        "axes": ["PACE", "TOP SPEED", "CONSISTENCY", "TYRE MGMT", "ENDURANCE"],
        "team1": {
            "name": team1,
            "color": TEAM_COLORS.get(team1, "#888"),
            "values": score(s1),
        },
        "team2": {
            "name": team2,
            "color": TEAM_COLORS.get(team2, "#888"),
            "values": score(s2),
        },
    }


def build_variance(laps, team1, team2):
    """box plot用統計（q1, median, q3, whiskers）"""
    def stats_for(team):
        arr = [fnum(l["LapTime_sec"]) for l in laps if l["Team"] == team]
        arr = [x for x in arr if x is not None]
        if len(arr) < 5:
            return None
        m = statistics.median(arr)
        clean = sorted(x for x in arr if x <= m * 1.07)
        n = len(clean)
        if n < 5:
            return None
        q1 = clean[n // 4]
        q2 = clean[n // 2]
        q3 = clean[(3 * n) // 4]
        return {
            "min": round(clean[0], 3),
            "q1": round(q1, 3),
            "median": round(q2, 3),
            "q3": round(q3, 3),
            "max": round(clean[-1], 3),
            "count": n,
        }

    return {
        "type": "variance",
        "team1": {"name": team1, "color": TEAM_COLORS.get(team1, "#888"), **(stats_for(team1) or {})},
        "team2": {"name": team2, "color": TEAM_COLORS.get(team2, "#888"), **(stats_for(team2) or {})},
    }


def process_gp(gp_dir: Path, out_root: Path):
    laps_path = gp_dir / "export" / "race_laps.csv"
    if not laps_path.exists():
        print(f"[SKIP] {gp_dir.name}")
        return 0
    with open(laps_path, newline="", encoding="utf-8") as f:
        laps = list(csv.DictReader(f))
    stats = compute_team_stats(laps)
    teams = sorted(stats.keys())
    if len(teams) < 2:
        return 0

    # gp_slug: 2026_R01_Australia → 2026-r01-australia
    m = re.match(r"^(\d{4})_R(\d{2})_(.+)$", gp_dir.name)
    gp_slug = f"{m.group(1)}-r{m.group(2)}-{m.group(3).lower()}" if m else gp_dir.name.lower()

    pair_count = 0
    for t1, t2 in itertools.combinations(teams, 2):
        slug = f"{TEAM_SLUG.get(t1, t1[:3].lower())}-vs-{TEAM_SLUG.get(t2, t2[:3].lower())}"
        pair_dir = out_root / gp_slug / slug
        pair_dir.mkdir(parents=True, exist_ok=True)
        with open(pair_dir / "dna.json", "w", encoding="utf-8") as f:
            json.dump(build_dna(stats, t1, t2), f, ensure_ascii=False, indent=2)
        with open(pair_dir / "variance.json", "w", encoding="utf-8") as f:
            json.dump(build_variance(laps, t1, t2), f, ensure_ascii=False, indent=2)
        pair_count += 1
    print(f"[OK] {gp_dir.name}: {pair_count} pairs ({pair_count*2} files) → {gp_slug}")
    return pair_count


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    args = ap.parse_args()
    gp_dir = Path(args.dir).resolve()
    out_root = gp_dir.parent / "teams"
    out_root.mkdir(exist_ok=True)
    process_gp(gp_dir, out_root)


if __name__ == "__main__":
    main()
