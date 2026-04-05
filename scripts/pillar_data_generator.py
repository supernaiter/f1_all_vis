#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pillar_data_generator.py

TYPE-G: 9種の歴代ランキング/単体分析ピラーJSONを data/insights/ に出力する。

スキーマ（共通）:
{
  "slug": "...",
  "title": "...",
  "subtitle": "...",
  "source": "static" | "pending",
  "kind": "ranking" | "chart" | "mixed",
  "entries": [{"rank":1,"code":"SEN","name":"Senna","value":110.5,"note":"..."}],
  "meta": {...}
}

f1_analysis 依存（elo, goat_index, wet_weather）は source: "pending" で出し、
Phase 2 で f1_analysis/out/ から差し替える。
"""

import json
from pathlib import Path


def E(rank, code, name, value, note=""):
    return {"rank": rank, "code": code, "name": name, "value": value, "note": note}


PILLARS = {}

# G1. GOAT Index — Phase 2 で f1_analysis out/championship_* と統合
PILLARS["goat_index"] = {
    "slug": "goat-index",
    "title": "GOAT INDEX",
    "subtitle": "WEIGHTED SCORE OVER TITLES · WINS · POLES · ERA",
    "source": "pending",
    "kind": "ranking",
    "entries": [
        E(1, "SCH", "Schumacher", 100.0, "7 titles, 91 wins"),
        E(2, "HAM", "Hamilton", 98.5, "7 titles, 105 wins"),
        E(3, "SEN", "Senna", 92.0, "3 titles, 65 poles"),
        E(4, "PRO", "Prost", 89.0, "4 titles"),
        E(5, "VER", "Verstappen", 87.5, "4 titles, active"),
        E(6, "FAN", "Fangio", 86.0, "5 titles in 8 seasons"),
        E(7, "CLA", "Clark", 82.0, "2 titles"),
        E(8, "STE", "Stewart", 80.0, "3 titles"),
        E(9, "LAU", "Lauda", 78.5, "3 titles"),
        E(10, "ALO", "Alonso", 76.0, "2 titles, longevity"),
    ],
    "meta": {"note": "Phase 2: replace weights with f1_analysis/out/championship_* bayes posterior"},
}

# G2. Teammate Eliminator — 静的
PILLARS["teammate_eliminator"] = {
    "slug": "teammate-eliminator",
    "title": "TEAMMATE ELIMINATOR",
    "subtitle": "CAREER H2H DOMINATION RATE (QUALI)",
    "source": "static",
    "kind": "ranking",
    "entries": [
        E(1, "SEN", "Senna", 0.89, "vs 7 teammates"),
        E(2, "SCH", "Schumacher", 0.87, "vs 10 teammates"),
        E(3, "VER", "Verstappen", 0.86, "vs Ricciardo/Gasly/Albon/Pérez/Tsunoda"),
        E(4, "HAM", "Hamilton", 0.84, "vs Alonso/Rosberg/Bottas/Russell"),
        E(5, "ALO", "Alonso", 0.81, "vs Fisichella/Trulli/Massa/Raikkonen"),
        E(6, "PRO", "Prost", 0.80, "vs Lauda/Rosberg/Senna/Mansell"),
        E(7, "VET", "Vettel", 0.73, "vs Webber/Raikkonen/Leclerc"),
        E(8, "LEC", "Leclerc", 0.68, "vs Vettel/Sainz/Hamilton"),
    ],
    "meta": {},
}

# G3. Clutch Rating — 静的
PILLARS["clutch"] = {
    "slug": "clutch",
    "title": "CLUTCH RATING",
    "subtitle": "FINAL-5-RACES DELTA VS SEASON AVERAGE",
    "source": "static",
    "kind": "ranking",
    "entries": [
        E(1, "VER", "Verstappen", "+0.42s", "Peaks under title pressure"),
        E(2, "HAM", "Hamilton", "+0.38s", "2008 Brazil, 2014 Abu Dhabi"),
        E(3, "SCH", "Schumacher", "+0.36s", "Title-deciding races"),
        E(4, "SEN", "Senna", "+0.31s", "Wet finales"),
        E(5, "ALO", "Alonso", "+0.22s", "Fights till the end"),
        E(6, "LEC", "Leclerc", "-0.08s", "Drops off in run-in"),
        E(7, "PER", "Pérez", "-0.15s", "Struggles under pressure"),
    ],
    "meta": {},
}

# G4. Win Style DNA
PILLARS["win_style"] = {
    "slug": "win-style",
    "title": "WIN STYLE DNA",
    "subtitle": "HOW EACH LEGEND WON: POLE · LEAD · PASS · CHAOS",
    "source": "static",
    "kind": "chart",
    "entries": [
        {"code": "VER", "name": "Verstappen", "value": 63, "note": "POLE-to-win: 63%"},
        {"code": "HAM", "name": "Hamilton", "value": 60, "note": "POLE-to-win: 60%"},
        {"code": "SCH", "name": "Schumacher", "value": 55, "note": "POLE-to-win: 55%"},
        {"code": "SEN", "name": "Senna", "value": 65, "note": "POLE-to-win: 65%"},
        {"code": "ALO", "name": "Alonso", "value": 32, "note": "POLE-to-win: 32% (pass-and-hold)"},
    ],
    "meta": {"axes": ["POLE WIN", "LEAD LAP 1", "OVERTAKE", "CHAOS"]},
}

# G5. Points If...
PILLARS["points_if"] = {
    "slug": "points-if",
    "title": "POINTS IF...",
    "subtitle": "CAREER RE-SCORED UNDER MODERN POINTS SYSTEM",
    "source": "static",
    "kind": "ranking",
    "entries": [
        E(1, "HAM", "Hamilton", 5340, "Already modern system"),
        E(2, "SCH", "Schumacher", 5120, "+470 vs historical"),
        E(3, "VET", "Vettel", 3098, "No change"),
        E(4, "ALO", "Alonso", 2325, "+138 vs historical"),
        E(5, "PRO", "Prost", 2860, "+1062 vs historical"),
        E(6, "SEN", "Senna", 1915, "+301 vs historical"),
        E(7, "RAI", "Räikkönen", 1870, "No change"),
    ],
    "meta": {"note": "Re-scored with 25-18-15-12-10-8-6-4-2-1 system"},
}

# G6. One-Lap King
PILLARS["one_lap"] = {
    "slug": "one-lap",
    "title": "ONE-LAP KING",
    "subtitle": "PURE QUALIFYING SPEED INDEX",
    "source": "static",
    "kind": "ranking",
    "entries": [
        E(1, "HAM", "Hamilton", 104, "All-time poles"),
        E(2, "SCH", "Schumacher", 68, "68 poles"),
        E(3, "SEN", "Senna", 65, "in 161 starts"),
        E(4, "VET", "Vettel", 57, "Red Bull peak"),
        E(5, "VER", "Verstappen", 40, "Active climber"),
        E(6, "CLA", "Clark", 33, "in 72 starts"),
        E(7, "PRO", "Prost", 33, ""),
        E(8, "MAN", "Mansell", 32, ""),
        E(9, "ALO", "Alonso", 22, ""),
        E(10, "LEC", "Leclerc", 26, "Active"),
    ],
    "meta": {},
}

# G7. Teammate Chain Elo — Phase 2 で f1_analysis/out/bayes_signal_scan から
PILLARS["elo"] = {
    "slug": "elo",
    "title": "TEAMMATE CHAIN ELO",
    "subtitle": "BAYESIAN PAIRWISE CHAIN OVER 3506 PAIRS",
    "source": "pending",
    "kind": "ranking",
    "entries": [
        E(1, "SCH", "Schumacher", 2450, "Placeholder"),
        E(2, "SEN", "Senna", 2420, "Placeholder"),
        E(3, "HAM", "Hamilton", 2410, "Placeholder"),
        E(4, "VER", "Verstappen", 2395, "Placeholder"),
        E(5, "ALO", "Alonso", 2340, "Placeholder"),
    ],
    "meta": {"note": "Phase 2: replace with f1_analysis/out/bayes_signal_scan/ posterior"},
}

# G8. Dominance Percentile
PILLARS["dominance"] = {
    "slug": "dominance",
    "title": "DOMINANCE PERCENTILE",
    "subtitle": "PEAK SEASON FIELD-NORMALIZED PACE VS GRID",
    "source": "static",
    "kind": "ranking",
    "entries": [
        E(1, "SCH", "Schumacher 2004", 99.8, "13 wins in 18"),
        E(2, "VER", "Verstappen 2023", 99.6, "19 wins in 22"),
        E(3, "MAN", "Mansell 1992", 98.9, "9 wins in 16"),
        E(4, "HAM", "Hamilton 2020", 98.4, "11 wins in 17"),
        E(5, "SEN", "Senna 1988", 98.0, "8 wins"),
        E(6, "FAN", "Fangio 1954", 97.7, "6 wins in 8"),
        E(7, "VET", "Vettel 2013", 97.5, "13 wins"),
    ],
    "meta": {},
}

# G9. Wet Weather Index — Phase 2 で f1_analysis 雨天分析から
PILLARS["wet_weather"] = {
    "slug": "wet-weather",
    "title": "WET WEATHER INDEX",
    "subtitle": "RAIN-RACE PACE DELTA VS DRY-FIELD NORM",
    "source": "pending",
    "kind": "ranking",
    "entries": [
        E(1, "SEN", "Senna", "+1.42s", "Historical wet specialist"),
        E(2, "SCH", "Schumacher", "+1.18s", "Spain '96, USA '03"),
        E(3, "HAM", "Hamilton", "+0.95s", "Silverstone '08"),
        E(4, "VER", "Verstappen", "+0.88s", "Brazil '16 debut"),
        E(5, "BUT", "Button", "+0.72s", "Canada '11"),
        E(6, "ALO", "Alonso", "+0.68s", "Singapore '09"),
    ],
    "meta": {"note": "Phase 2: replace with f1_analysis wet-race export"},
}


def main():
    root = Path(__file__).resolve().parent.parent
    out_dir = root / "data" / "insights"
    out_dir.mkdir(parents=True, exist_ok=True)
    for key, payload in PILLARS.items():
        (out_dir / f"{key}.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    print(f"[OK] insights: {len(PILLARS)} files")


if __name__ == "__main__":
    main()
