#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tier_data_generator.py

12カテゴリのティア表JSONを data/tiers/ に出力する。
単一Astroテンプレート（tiers/[slug].astro）で共通レンダリングされる前提。

スキーマ:
{
  "title": "...",
  "subtitle": "...",
  "tiers": [
    {"label":"S","color":"#FFD700","drivers":[{"code":"SEN","name":"Senna","note":"..."}]},
    ...
  ]
}
"""

import json
from pathlib import Path

TIER_COLORS = {
    "S": "#FFD700",
    "A": "#E0E0E0",
    "B": "#B88A3E",
    "C": "#6E6E6E",
    "D": "#3E3E3E",
    "F": "#7A1F1F",
}


def T(label, drivers):
    return {"label": label, "color": TIER_COLORS.get(label, "#6E6E6E"), "drivers": drivers}


def D(code, name, note=""):
    return {"code": code, "name": name, "note": note}


# ============================================================
# 12カテゴリ
# ============================================================

TIERS = {}

# 1. All-time Greatest
TIERS["all_time"] = {
    "title": "ALL-TIME GREATEST",
    "subtitle": "THE DEFINITIVE F1 GOAT TIER LIST",
    "tiers": [
        T("S", [
            D("SCH", "Schumacher", "7 titles, era-defining"),
            D("HAM", "Hamilton", "7 titles, 105 wins"),
            D("SEN", "Senna", "3 titles, mythical wet pace"),
            D("PRO", "Prost", "4 titles, The Professor"),
            D("VER", "Verstappen", "4 titles, dominance"),
        ]),
        T("A", [
            D("FAN", "Fangio", "5 titles in 8 seasons"),
            D("CLA", "Clark", "2 titles, untouchable in era"),
            D("STE", "Stewart", "3 titles, safety advocate"),
            D("LAU", "Lauda", "3 titles, comeback legend"),
            D("PIQ", "Piquet", "3 titles"),
        ]),
        T("B", [
            D("ALO", "Alonso", "2 titles, longevity"),
            D("VET", "Vettel", "4 titles"),
            D("MAN", "Mansell", "1 title, fighter"),
            D("HAK", "Häkkinen", "2 titles"),
            D("EMS", "Fittipaldi", "2 titles"),
        ]),
        T("C", [
            D("ROS", "N. Rosberg", "1 title"),
            D("BUT", "Button", "1 title, rain master"),
            D("HIL", "D. Hill", "1 title"),
            D("VIL", "Villeneuve", "1 title"),
        ]),
    ],
}

# 2. Clutch Performance
TIERS["clutch"] = {
    "title": "CLUTCH PERFORMANCE",
    "subtitle": "WHO DELIVERS WHEN IT MATTERS MOST",
    "tiers": [
        T("S", [
            D("SEN", "Senna", "Wet-weather god, final-lap overtakes"),
            D("SCH", "Schumacher", "Title deciders"),
            D("VER", "Verstappen", "Final 5 races of 2021"),
        ]),
        T("A", [
            D("HAM", "Hamilton", "2008 Brazil final corner"),
            D("ALO", "Alonso", "2006 Japan"),
            D("LAU", "Lauda", "1984 final race"),
        ]),
        T("B", [
            D("VET", "Vettel", "2012 Brazil"),
            D("RAI", "Räikkönen", "2007 finale"),
            D("BUT", "Button", "2011 Canada"),
        ]),
        T("C", [
            D("ROS", "N. Rosberg", "2016 run-in"),
            D("LEC", "Leclerc", "Mixed showings"),
        ]),
    ],
}

# 3. Wet Weather Kings
TIERS["wet"] = {
    "title": "WET WEATHER KINGS",
    "subtitle": "RAIN MASTERS RANKED",
    "tiers": [
        T("S", [
            D("SEN", "Senna", "Monaco '84, Donington '93"),
            D("SCH", "Schumacher", "Spain '96, USA '03"),
            D("VER", "Verstappen", "Brazil '16 debut"),
        ]),
        T("A", [
            D("HAM", "Hamilton", "Silverstone '08, Turkey '20"),
            D("BUT", "Button", "Canada '11"),
            D("ALO", "Alonso", "Singapore rain stages"),
        ]),
        T("B", [
            D("WEB", "Webber", "Monaco '10"),
            D("VET", "Vettel", "Italy '08"),
            D("VIL", "Villeneuve", "Europe '96"),
        ]),
        T("C", [
            D("RIC", "Ricciardo", "Hungary '14"),
            D("OCO", "Ocon", "Spa '21"),
        ]),
    ],
}

# 4. One-Lap Pace
TIERS["one_lap"] = {
    "title": "ONE-LAP KING",
    "subtitle": "PURE QUALIFYING PACE RANKED",
    "tiers": [
        T("S", [
            D("SEN", "Senna", "65 poles in 161 starts"),
            D("HAM", "Hamilton", "104 poles"),
            D("VER", "Verstappen", "Ruthless single-lap"),
        ]),
        T("A", [
            D("SCH", "Schumacher", "68 poles"),
            D("CLA", "Clark", "33 poles in short career"),
            D("LEC", "Leclerc", "Monaco specialist"),
        ]),
        T("B", [
            D("PRO", "Prost", "33 poles"),
            D("MAN", "Mansell", "32 poles"),
            D("VET", "Vettel", "57 poles"),
        ]),
        T("C", [
            D("ALO", "Alonso", "22 poles"),
            D("BUT", "Button", "8 poles"),
            D("RAI", "Räikkönen", "18 poles"),
        ]),
    ],
}

# 5. Overachiever
TIERS["overachiever"] = {
    "title": "OVERACHIEVER",
    "subtitle": "PUNCHING ABOVE THE MACHINE",
    "tiers": [
        T("S", [
            D("ALO", "Alonso", "Extracted miracles from mid-pack cars"),
            D("VER", "Verstappen", "2016 breakthrough in STR"),
            D("PER", "Pérez", "Sauber/Force India podiums"),
        ]),
        T("A", [
            D("HUL", "Hülkenberg", "Regular Q3 in midfield"),
            D("OCO", "Ocon", "Hungary 2021 win"),
            D("GAS", "Gasly", "Monza 2020 win"),
        ]),
        T("B", [
            D("SAI", "Sainz", "McLaren era consistency"),
            D("ALB", "Albon", "Williams salvage jobs"),
            D("MAG", "Magnussen", "Haas peaks"),
        ]),
        T("C", [
            D("STR", "Stroll", "Baku pole '17"),
            D("BOT", "Bottas", "Mercedes support role"),
        ]),
    ],
}

# 6. 2024 Season
TIERS["season_2024"] = {
    "title": "2024 SEASON",
    "subtitle": "DRIVER RANKINGS FROM THE 2024 CAMPAIGN",
    "tiers": [
        T("S", [
            D("VER", "Verstappen", "4th title despite RB decline"),
            D("NOR", "Norris", "MCL leader, 4 wins"),
        ]),
        T("A", [
            D("LEC", "Leclerc", "3 wins incl. Monaco"),
            D("PIA", "Piastri", "2 wins, step up"),
            D("SAI", "Sainz", "Consistent podium-getter"),
            D("HAM", "Hamilton", "2 wins in swan song"),
        ]),
        T("B", [
            D("RUS", "Russell", "Qualifying edge in MER"),
            D("ALO", "Alonso", "Points-gathering"),
            D("PER", "Pérez", "Collapse from Q2"),
        ]),
        T("C", [
            D("HUL", "Hülkenberg", "Solid Haas"),
            D("TSU", "Tsunoda", "RB improvements"),
            D("ALB", "Albon", "Williams 1A"),
        ]),
        T("D", [
            D("GAS", "Gasly", "Alpine rebuild"),
            D("OCO", "Ocon", "Exit season"),
            D("STR", "Stroll", "Off the pace"),
            D("BOT", "Bottas", "Last Sauber year"),
        ]),
    ],
}

# 7. Pay Driver Hall of Shame
TIERS["pay_drivers"] = {
    "title": "PAY DRIVER HALL OF SHAME",
    "subtitle": "SEATS BOUGHT, NOT EARNED (OPINION)",
    "tiers": [
        T("F", [
            D("CHA", "Chanoch", "Placeholder — edit list"),
            D("YOO", "Yoong", "Minardi struggles"),
            D("IDE", "Ide", "Super Aguri exit"),
        ]),
        T("D", [
            D("MAL", "Maldonado", "Spain '12 win aside, mostly chaos"),
            D("MAZ", "Mazepin", "Haas 2021"),
            D("LAT", "Latifi", "Williams underwhelm"),
        ]),
        T("C", [
            D("PER", "Pérez", "Partial — career turned"),
            D("STR", "Stroll", "Family team controversy"),
        ]),
    ],
}

# 8. Championship Choke Artists
TIERS["choke"] = {
    "title": "CHAMPIONSHIP CHOKE ARTISTS",
    "subtitle": "TITLES LOST FROM WINNING POSITIONS",
    "tiers": [
        T("S", [
            D("HAM", "Hamilton", "2007 China pit entry"),
            D("COU", "Coulthard", "1997-2000 implosions"),
            D("MAS", "Massa", "2008 Brazil last-corner loss"),
        ]),
        T("A", [
            D("VET", "Vettel", "2018 self-destructs"),
            D("RAI", "Räikkönen", "2003 reliability chain"),
            D("ALO", "Alonso", "2010 Abu Dhabi strategy"),
        ]),
        T("B", [
            D("PRO", "Prost", "1984 by half-point"),
            D("HIL", "D. Hill", "1994 Adelaide"),
            D("ARN", "Arnoux", "1983 title fight"),
        ]),
    ],
}

# 9. Wasted Talent
TIERS["wasted"] = {
    "title": "WASTED TALENT",
    "subtitle": "TITLES THEY SHOULD HAVE WON",
    "tiers": [
        T("S", [
            D("MON", "Montoya", "Raw speed without title"),
            D("KUB", "Kubica", "Rally injury cut career"),
            D("HEI", "Heidfeld", "Never won a race"),
        ]),
        T("A", [
            D("WEB", "Webber", "Always #2 at RBR"),
            D("BAR", "Barrichello", "Schumacher's shadow"),
            D("RIC", "Ricciardo", "Post-RBR decline"),
        ]),
        T("B", [
            D("DIR", "di Resta", "Promising Force India"),
            D("FRE", "Frentzen", "'99 title shot"),
            D("TRU", "Trulli", "Qualifying demon"),
        ]),
    ],
}

# 10. Villain Era
TIERS["villain"] = {
    "title": "VILLAIN ERA",
    "subtitle": "MOST-BOOED DRIVERS IN F1 HISTORY",
    "tiers": [
        T("S", [
            D("SCH", "Schumacher", "Adelaide '94, Jerez '97"),
            D("VER", "Verstappen", "2021 title controversy"),
            D("SEN", "Senna", "Prost collisions"),
        ]),
        T("A", [
            D("PRO", "Prost", "'The Professor' calculation"),
            D("ALO", "Alonso", "Crashgate implication"),
            D("HAM", "Hamilton", "2008 Spa penalty saga"),
        ]),
        T("B", [
            D("MAL", "Maldonado", "Crash reputation"),
            D("MAZ", "Mazepin", "Pre-F1 controversy"),
        ]),
    ],
}

# 11. Team Atmosphere Destroyer
TIERS["destroyer"] = {
    "title": "TEAM ATMOSPHERE DESTROYER",
    "subtitle": "GARAGE VIBES NUKED FROM ORBIT",
    "tiers": [
        T("S", [
            D("ALO", "Alonso", "McLaren '07, Ferrari '14"),
            D("SEN", "Senna", "McLaren vs Prost"),
            D("VET", "Vettel", "Ferrari exit"),
        ]),
        T("A", [
            D("ROS", "N. Rosberg", "Hamilton rivalry '14-'16"),
            D("HAM", "Hamilton", "McLaren exit '12"),
            D("PIQ", "Piquet", "Williams lockerroom"),
        ]),
        T("B", [
            D("MAN", "Mansell", "Williams demands"),
            D("RAI", "Räikkönen", "Lotus silences"),
        ]),
    ],
}

# 12. Most Underrated
TIERS["underrated"] = {
    "title": "MOST UNDERRATED",
    "subtitle": "NEVER GOT THE CREDIT THEY DESERVED",
    "tiers": [
        T("S", [
            D("REG", "Regazzoni", "Overshadowed by Lauda"),
            D("PAT", "Patrese", "256 GPs of consistency"),
            D("HEI", "Heidfeld", "13 podiums, 0 wins"),
        ]),
        T("A", [
            D("HUL", "Hülkenberg", "Most-starts without podium then points"),
            D("PER", "Pérez", "Sauber-era miracles"),
            D("ALO", "Alonso", "Post-Ferrari years"),
        ]),
        T("B", [
            D("BUT", "Button", "Title often dismissed"),
            D("BAR", "Barrichello", "Longevity"),
            D("WEB", "Webber", "RBR consistency"),
        ]),
    ],
}


def main():
    root = Path(__file__).resolve().parent.parent
    out_dir = root / "data" / "tiers"
    out_dir.mkdir(parents=True, exist_ok=True)
    for slug, payload in TIERS.items():
        (out_dir / f"{slug}.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    print(f"[OK] tiers: {len(TIERS)} files")


if __name__ == "__main__":
    main()
