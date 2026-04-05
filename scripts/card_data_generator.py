#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
card_data_generator.py
TYPE-A: GPカード7種JSON生成
入力: data/{gp}/export/race_laps.csv, race_results.csv
出力: data/{gp}/cards/ 配下に7種JSON
"""
import argparse
import csv
import json
import statistics
from pathlib import Path

# チームカラー（race_results.TeamColor相当・fallback）
TEAM_COLORS = {
    "McLaren": "#E07800", "Ferrari": "#DC0000", "Red Bull Racing": "#2B5DAB",
    "Mercedes": "#00B89F", "Aston Martin": "#1B7A5A", "Williams": "#3BA3E0",
    "Racing Bulls": "#4A72CC", "Alpine": "#0078AA", "Haas F1 Team": "#7A7A7A",
    "Audi": "#3AAA3A", "Cadillac": "#888888",
}


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fnum(v):
    try:
        if v in (None, "", "nan"):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def generate_lap1_delta(results, laps):
    """grid → lap1 position delta"""
    # Lap1のPositionを取る
    lap1_pos = {}
    for lap in laps:
        if fnum(lap["LapNumber"]) == 1.0:
            p = fnum(lap["Position"])
            if p is not None:
                lap1_pos[lap["Driver"]] = int(p)
    rows = []
    for r in results:
        drv = r["Abbreviation"]
        grid = fnum(r["GridPosition"])
        finish = fnum(r["Position"])
        lap1 = lap1_pos.get(drv, int(finish) if finish else None)
        if grid is None or lap1 is None:
            continue
        rows.append({
            "code": drv,
            "team": r["TeamName"],
            "color": "#" + (r["TeamColor"] or "888888"),
            "grid": int(grid),
            "lap1": int(lap1),
            "delta": int(grid) - int(lap1),
        })
    rows.sort(key=lambda x: x["grid"])
    return {"type": "lap1_delta", "drivers": rows}


def generate_tyre_cliff(laps):
    """ドライバー別ラップタイム配列 + 3lap MA微分でクリフ検出"""
    by_drv = {}
    for lap in laps:
        t = fnum(lap["LapTime_sec"])
        if t is None:
            continue
        by_drv.setdefault(lap["Driver"], []).append({
            "lap": int(fnum(lap["LapNumber"]) or 0),
            "time": t,
            "tyre_life": fnum(lap["TyreLife"]),
            "compound": lap["Compound"],
            "stint": int(fnum(lap["Stint"]) or 0),
        })
    drivers = []
    for drv, arr in by_drv.items():
        arr.sort(key=lambda x: x["lap"])
        # 最速周の107%以内
        valid = [a["time"] for a in arr if a["time"]]
        if not valid:
            continue
        best = min(valid)
        clean = [a for a in arr if a["time"] <= best * 1.10]
        if len(clean) < 5:
            continue
        # 3lap MA
        times = [a["time"] for a in clean]
        ma = []
        for i in range(len(times)):
            window = times[max(0, i - 1):i + 2]
            ma.append(sum(window) / len(window))
        drivers.append({
            "code": drv,
            "laps": [a["lap"] for a in clean],
            "times": times,
            "ma": ma,
            "best": best,
        })
    return {"type": "tyre_cliff", "drivers": drivers}


def generate_pace_variance(laps):
    """チーム別ラップタイム分散"""
    by_team = {}
    for lap in laps:
        t = fnum(lap["LapTime_sec"])
        if t is None:
            continue
        by_team.setdefault(lap["Team"], []).append(t)
    teams = []
    for team, arr in by_team.items():
        if len(arr) < 5:
            continue
        m = statistics.median(arr)
        # クリーンラップのみ（107%）
        clean = [x for x in arr if x <= m * 1.07]
        if len(clean) < 3:
            continue
        teams.append({
            "team": team,
            "color": TEAM_COLORS.get(team, "#888"),
            "median": round(statistics.median(clean), 3),
            "mean": round(statistics.mean(clean), 3),
            "stdev": round(statistics.pstdev(clean), 3),
            "min": round(min(clean), 3),
            "max": round(max(clean), 3),
            "count": len(clean),
        })
    teams.sort(key=lambda x: x["stdev"])
    return {"type": "pace_variance", "teams": teams}


def generate_what_if(laps, results):
    """ピットラップ推定+各ドライバーのロストタイム推定"""
    # PitInTime/PitOutTime があるラップをピットとする
    by_drv = {}
    for lap in laps:
        drv = lap["Driver"]
        entry = {
            "lap": int(fnum(lap["LapNumber"]) or 0),
            "time": fnum(lap["LapTime_sec"]),
            "pit_in": fnum(lap["PitInTime_sec"]) is not None,
            "pit_out": fnum(lap["PitOutTime_sec"]) is not None,
        }
        by_drv.setdefault(drv, []).append(entry)
    drivers = []
    for drv, arr in by_drv.items():
        arr.sort(key=lambda x: x["lap"])
        pit_laps = [a["lap"] for a in arr if a["pit_in"]]
        times = [a["time"] for a in arr if a["time"]]
        if not times:
            continue
        best = min(times)
        # ピット1回の想定ロス: ピットラップのタイム - best
        pit_losses = [
            a["time"] - best for a in arr
            if a["pit_in"] and a["time"] and a["time"] > best
        ]
        drivers.append({
            "code": drv,
            "pit_laps": pit_laps,
            "pit_loss_sum": round(sum(pit_losses), 3),
            "best_lap": round(best, 3),
        })
    drivers.sort(key=lambda x: x["pit_loss_sum"], reverse=True)
    return {"type": "what_if", "drivers": drivers}


def generate_skeleton(card_type, note):
    return {
        "type": card_type,
        "status": "pending",
        "note": note,
        "data": [],
    }


def process_gp(gp_dir: Path):
    export = gp_dir / "export"
    if not (export / "race_laps.csv").exists():
        print(f"[SKIP] {gp_dir.name}: race_laps.csv not found")
        return 0
    results = read_csv(export / "race_results.csv")
    laps = read_csv(export / "race_laps.csv")

    out_dir = gp_dir / "cards"
    out_dir.mkdir(exist_ok=True)

    cards = {
        "lap1_delta": generate_lap1_delta(results, laps),
        "tyre_cliff": generate_tyre_cliff(laps),
        "pace_variance": generate_pace_variance(laps),
        "what_if": generate_what_if(laps, results),
        "braking_point": generate_skeleton("braking_point", "DATA PENDING — OPENF1 INTEGRATION REQUIRED"),
        "corner_speed": generate_skeleton("corner_speed", "DATA PENDING — OPENF1 INTEGRATION REQUIRED"),
        "overtake_replay": generate_skeleton("overtake_replay", "DATA PENDING — OPENF1 INTEGRATION REQUIRED"),
    }
    for name, data in cards.items():
        data["gp"] = gp_dir.name
        with open(out_dir / f"{name}.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[OK] {gp_dir.name}: {len(cards)} cards written")
    return len(cards)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="GP directory (e.g. data/2026_R01_Australia)")
    args = ap.parse_args()
    process_gp(Path(args.dir).resolve())


if __name__ == "__main__":
    main()
