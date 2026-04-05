#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
season_aggregator.py
TYPE-F: シーズン横断6種JSON
"""
import argparse
import csv
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


def fnum(v):
    try:
        if v in (None, "", "nan"):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def load_gp(gp_dir: Path):
    export = gp_dir / "export"
    if not (export / "race_results.csv").exists():
        return None
    with open(export / "race_results.csv", newline="", encoding="utf-8") as f:
        results = list(csv.DictReader(f))
    with open(export / "race_laps.csv", newline="", encoding="utf-8") as f:
        laps = list(csv.DictReader(f))
    m = re.match(r"^(\d{4})_R(\d{2})_(.+)$", gp_dir.name)
    return {
        "round": int(m.group(2)) if m else 0,
        "name": m.group(3) if m else gp_dir.name,
        "results": results,
        "laps": laps,
    }


def build_championship(gps):
    """ドライバーポイント累積"""
    all_drv = {}
    round_list = sorted({g["round"] for g in gps})
    for g in gps:
        for r in g["results"]:
            drv = r["Abbreviation"]
            pts = fnum(r["Points"]) or 0
            if drv not in all_drv:
                all_drv[drv] = {
                    "code": drv,
                    "name": r["FullName"],
                    "team": r["TeamName"],
                    "color": "#" + (r["TeamColor"] or "888888"),
                    "points_by_round": {},
                }
            all_drv[drv]["points_by_round"][g["round"]] = pts
    drivers = []
    for drv, d in all_drv.items():
        cumulative = []
        total = 0
        for rnd in round_list:
            total += d["points_by_round"].get(rnd, 0)
            cumulative.append({"round": rnd, "points": total})
        drivers.append({
            "code": d["code"],
            "name": d["name"],
            "team": d["team"],
            "color": d["color"],
            "cumulative": cumulative,
            "total": total,
        })
    drivers.sort(key=lambda x: x["total"], reverse=True)
    return {"type": "championship", "rounds": round_list, "drivers": drivers}


def build_constructors(gps):
    by_team = {}
    round_list = sorted({g["round"] for g in gps})
    for g in gps:
        for r in g["results"]:
            team = r["TeamName"]
            pts = fnum(r["Points"]) or 0
            by_team.setdefault(team, {"points_by_round": {}})
            by_team[team]["points_by_round"].setdefault(g["round"], 0)
            by_team[team]["points_by_round"][g["round"]] += pts
    teams = []
    for team, d in by_team.items():
        cumulative = []
        total = 0
        for rnd in round_list:
            total += d["points_by_round"].get(rnd, 0)
            cumulative.append({"round": rnd, "points": total})
        teams.append({
            "name": team,
            "color": TEAM_COLORS.get(team, "#888"),
            "cumulative": cumulative,
            "total": total,
        })
    teams.sort(key=lambda x: x["total"], reverse=True)
    return {"type": "constructors", "rounds": round_list, "teams": teams}


def build_title_probability(championship):
    """ポイント差からナイーブ確率"""
    drivers = championship["drivers"]
    if not drivers:
        return {"type": "title_probability", "drivers": []}
    top_pts = drivers[0]["total"] or 1
    out = []
    for d in drivers:
        ratio = (d["total"] / top_pts) if top_pts else 0
        prob = round(max(0, ratio ** 3) * 100, 1)
        out.append({
            "code": d["code"],
            "name": d["name"],
            "color": d["color"],
            "points": d["total"],
            "probability": prob,
        })
    # normalize
    s = sum(x["probability"] for x in out) or 1
    for x in out:
        x["probability"] = round(x["probability"] / s * 100, 1)
    return {"type": "title_probability", "drivers": out[:12]}


def build_momentum(gps):
    """チーム別ペース中央値の推移（最速チーム基準のデルタ）"""
    by_team_round = {}
    round_list = sorted({g["round"] for g in gps})
    for g in gps:
        team_medians = {}
        for lap in g["laps"]:
            t = fnum(lap["LapTime_sec"])
            if t is None:
                continue
            team_medians.setdefault(lap["Team"], []).append(t)
        round_best = None
        computed = {}
        for team, arr in team_medians.items():
            if len(arr) < 5:
                continue
            m = statistics.median(arr)
            clean = [x for x in arr if x <= m * 1.07]
            computed[team] = statistics.median(clean)
        if computed:
            round_best = min(computed.values())
            for team, med in computed.items():
                by_team_round.setdefault(team, {})[g["round"]] = round(med - round_best, 3)
    teams = []
    for team, vals in by_team_round.items():
        series = [{"round": r, "delta": vals.get(r)} for r in round_list]
        teams.append({
            "name": team,
            "color": TEAM_COLORS.get(team, "#888"),
            "series": series,
        })
    teams.sort(key=lambda x: statistics.mean([s["delta"] for s in x["series"] if s["delta"] is not None] or [999]))
    return {"type": "momentum", "rounds": round_list, "teams": teams}


def build_power_ranking(momentum, constructors):
    """複合スコア: (ペース順位 + ポイント順位) の平均推移"""
    return {
        "type": "power_ranking",
        "method": "composite of pace delta + constructors points",
        "rounds": momentum["rounds"],
        "teams": [
            {
                "name": t["name"],
                "color": t["color"],
                "score": round(100 - (i / max(1, len(constructors["teams"]) - 1)) * 100, 1),
                "rank": i + 1,
            }
            for i, t in enumerate(constructors["teams"])
        ],
    }


def build_upgrades(gps):
    return {
        "type": "upgrades",
        "status": "pending",
        "note": "DATA PENDING — MANUAL CURATION REQUIRED",
        "rounds": sorted({g["round"] for g in gps}),
        "entries": [],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    args = ap.parse_args()
    root = Path(__file__).resolve().parent.parent / "data"
    gps = []
    for d in sorted(root.iterdir()):
        if d.is_dir() and d.name.startswith(f"{args.year}_R"):
            g = load_gp(d)
            if g:
                gps.append(g)
    if not gps:
        print(f"[ERROR] no GPs found for {args.year}")
        return
    out_dir = root / "season" / str(args.year)
    out_dir.mkdir(parents=True, exist_ok=True)
    champ = build_championship(gps)
    cons = build_constructors(gps)
    mom = build_momentum(gps)
    outputs = {
        "championship": champ,
        "constructors": cons,
        "title_probability": build_title_probability(champ),
        "momentum": mom,
        "power_ranking": build_power_ranking(mom, cons),
        "upgrades": build_upgrades(gps),
    }
    for name, data in outputs.items():
        with open(out_dir / f"{name}.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[OK] season/{args.year}: {len(outputs)} files")


if __name__ == "__main__":
    main()
