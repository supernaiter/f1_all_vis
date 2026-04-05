#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
driver_compare_generator.py

歴代トップ30ドライバーのマスターデータから、
435ペア × 4種（career_arc, h2h_sim, lifetime, milestone）の
JSONを一括生成するスクリプト。

出力:
  data/drivers/master.json       - 30名マスター
  data/drivers/pairs/{d1}-vs-{d2}/career_arc.json
  data/drivers/pairs/{d1}-vs-{d2}/h2h_sim.json
  data/drivers/pairs/{d1}-vs-{d2}/lifetime.json
  data/drivers/pairs/{d1}-vs-{d2}/milestone.json

注意:
  - 数値は公開統計・常識的近似に基づく（厳密な史実再現ではない）
  - cumulative_wins は年ごとの累積（index=デビューからの年数）
  - milestone_wins は参戦レース数ごとの累積勝利数（index=レース番号）
"""

import json
import os
from itertools import combinations
from pathlib import Path

# ============================================================
# マスターデータ（30名）
# ============================================================
# 各ドライバー:
#   code, name, color, debut_year, last_year (int or "active")
#   total_wins, total_poles, total_races, championships
#   elo              : Teammate Chain Elo 推定値
#   strengths        : {wet, quali, racecraft, consistency, tyre}  0-100
#   wins_by_year     : デビュー年から最終年までの各年の勝利数
#   points_by_year   : デビュー年から最終年までの各年の獲得ポイント
#   birth_year       : 誕生年
#   career_events    : [{age, label, type}]  type ∈ {debut, win, title, career, life}
# ------------------------------------------------------------

DRIVERS_RAW = [
    # --- 現役トップ ---
    dict(code='VER', name='Verstappen', color='#0600ef',
         debut_year=2015, last_year='active', birth_year=1997,
         total_races=220, total_poles=44, championships=4, elo=2180,
         wins_by_year=[0,0,1,2,3,2,10,15,19,4,2],
         points_by_year=[49,204,168,249,278,214,395,454,575,437,210],
         strengths=dict(wet=95, quali=92, racecraft=94, consistency=90, tyre=88),
         career_events=[
             (17,'F1 DEBUT (TORO ROSSO)','debut'),
             (18,'YOUNGEST F1 WINNER (SPAIN 2016)','win'),
             (23,'FIRST TITLE (ABU DHABI FINALE)','title'),
             (24,'BACK-TO-BACK TITLES','title'),
             (25,'TRIPLE CHAMPION','title'),
             (26,'FOUR-TIME CHAMPION','title'),
         ]),
    dict(code='HAM', name='Hamilton', color='#27f4d2',
         debut_year=2007, last_year='active', birth_year=1985,
         total_races=360, total_poles=104, championships=7, elo=2200,
         wins_by_year=[4,5,2,3,3,4,1,11,10,10,9,11,11,2,8,0,0,2,0],
         points_by_year=[109,98,49,240,227,190,189,384,381,380,363,408,413,347,387,240,234,223,50],
         strengths=dict(wet=97, quali=96, racecraft=93, consistency=91, tyre=90),
         career_events=[
             (22,'F1 DEBUT (MCLAREN)','debut'),
             (23,'FIRST TITLE (BRAZIL 2008)','title'),
             (29,'MERCEDES TITLE #2','title'),
             (30,'BACK-TO-BACK WITH MERC','title'),
             (32,'FOUR-TIME CHAMPION','title'),
             (33,'FIVE-TIME','title'),
             (34,'SIX-TIME','title'),
             (35,'EQUALS SCHUMI AT 7','title'),
             (40,'FERRARI MOVE','career'),
         ]),
    dict(code='LEC', name='Leclerc', color='#e8002d',
         debut_year=2018, last_year='active', birth_year=1997,
         total_races=160, total_poles=26, championships=0, elo=2050,
         wins_by_year=[0,2,0,0,3,0,3,0],
         points_by_year=[39,264,98,159,308,206,356,210],
         strengths=dict(wet=85, quali=94, racecraft=85, consistency=82, tyre=80),
         career_events=[
             (20,'F1 DEBUT (SAUBER)','debut'),
             (21,'FIRST WIN (BELGIUM 2019)','win'),
             (26,'MONACO HOME WIN','win'),
         ]),
    dict(code='NOR', name='Norris', color='#ff8000',
         debut_year=2019, last_year='active', birth_year=1999,
         total_races=140, total_poles=12, championships=0, elo=2070,
         wins_by_year=[0,0,0,0,0,4,6,2],
         points_by_year=[49,97,160,122,205,374,298,180],
         strengths=dict(wet=86, quali=90, racecraft=87, consistency=88, tyre=85),
         career_events=[
             (19,'F1 DEBUT (MCLAREN)','debut'),
             (24,'FIRST WIN (MIAMI 2024)','win'),
             (25,'MCLAREN COMEBACK LEADER','career'),
         ]),
    dict(code='SAI', name='Sainz', color='#005bbb',
         debut_year=2015, last_year='active', birth_year=1994,
         total_races=220, total_poles=6, championships=0, elo=2000,
         wins_by_year=[0,0,0,0,0,0,0,1,1,2,0,0],
         points_by_year=[18,46,54,53,96,105,164,246,200,290,40,30],
         strengths=dict(wet=80, quali=85, racecraft=86, consistency=88, tyre=84),
         career_events=[
             (20,'F1 DEBUT (TORO ROSSO)','debut'),
             (28,'FIRST WIN (BRITAIN 2022)','win'),
             (29,'SINGAPORE BEATS RED BULL','win'),
             (30,'WILLIAMS MOVE','career'),
         ]),
    dict(code='PIA', name='Piastri', color='#ff8000',
         debut_year=2023, last_year='active', birth_year=2001,
         total_races=70, total_poles=4, championships=0, elo=2030,
         wins_by_year=[0,2,4,1],
         points_by_year=[97,292,280,90],
         strengths=dict(wet=82, quali=89, racecraft=88, consistency=89, tyre=86),
         career_events=[
             (21,'F1 DEBUT (MCLAREN)','debut'),
             (23,'FIRST WIN (HUNGARY 2024)','win'),
         ]),
    dict(code='RUS', name='Russell', color='#27f4d2',
         debut_year=2019, last_year='active', birth_year=1998,
         total_races=140, total_poles=6, championships=0, elo=2020,
         wins_by_year=[0,0,0,1,0,2,1,0],
         points_by_year=[0,3,16,275,175,245,130,50],
         strengths=dict(wet=84, quali=89, racecraft=84, consistency=87, tyre=83),
         career_events=[
             (21,'F1 DEBUT (WILLIAMS)','debut'),
             (24,'FIRST WIN (BRAZIL 2022)','win'),
             (26,'MERCEDES LEADER','career'),
         ]),
    dict(code='ALO', name='Alonso', color='#00665f',
         debut_year=2001, last_year='active', birth_year=1981,
         total_races=420, total_poles=22, championships=2, elo=2160,
         # 2001 debut (Minardi), gap 2002, 2003-2006 Renault, ... 2019-2020 gap, 2021-
         wins_by_year=[0, 1,1,7,7, 4,2,2,0, 1,3,3,2,0, 0,0,0,0, 0,0,0,0,0,0],
         points_by_year=[0, 55,59,133,252, 109,61,75,86, 257,278,207,242,97, 11,0,17, 0,0, 81,206,62,70,20],
         strengths=dict(wet=96, quali=90, racecraft=96, consistency=93, tyre=94),
         career_events=[
             (19,'F1 DEBUT (MINARDI)','debut'),
             (22,'FIRST WIN (HUNGARY 2003)','win'),
             (24,'WORLD CHAMPION (RENAULT)','title'),
             (25,'BACK-TO-BACK TITLES','title'),
             (26,'MCLAREN — TIED WITH ROOKIE HAM','career'),
             (37,'LEAVES F1','career'),
             (40,'F1 RETURN (ALPINE)','career'),
             (43,'STILL RACING AGE 43','career'),
         ]),
    dict(code='VET', name='Vettel', color='#1e41ff',
         debut_year=2007, last_year=2022, birth_year=1987,
         total_races=299, total_poles=57, championships=4, elo=2150,
         wins_by_year=[0,1,4,5,11,5,13,0,3,0,4,5,1,0,0,0],
         points_by_year=[6,35,84,256,392,281,397,167,278,212,317,320,240,33,43,37],
         strengths=dict(wet=88, quali=94, racecraft=89, consistency=90, tyre=87),
         career_events=[
             (19,'F1 DEBUT (BMW SUBSTITUTE)','debut'),
             (21,'FIRST WIN (MONZA 2008)','win'),
             (23,'YOUNGEST CHAMPION','title'),
             (24,'BACK-TO-BACK','title'),
             (25,'THREE IN A ROW','title'),
             (26,'FOUR STRAIGHT','title'),
             (27,'FERRARI MOVE','career'),
             (35,'RETIRES','career'),
         ]),
    dict(code='PRO', name='Prost', color='#ffbf00',
         debut_year=1980, last_year=1993, birth_year=1955,
         total_races=199, total_poles=33, championships=4, elo=2170,
         wins_by_year=[0,2,2,4,7,5,4,3,7,4,5,0,0,7],
         points_by_year=[5,43,34,57,71.5,73,72,46,105,81,71.5,34,0,99],
         strengths=dict(wet=88, quali=92, racecraft=94, consistency=96, tyre=95),
         career_events=[
             (25,'F1 DEBUT (MCLAREN)','debut'),
             (26,'FIRST WIN (FRANCE 1981)','win'),
             (30,'FIRST TITLE (MCLAREN)','title'),
             (31,'BACK-TO-BACK','title'),
             (34,'THIRD TITLE','title'),
             (38,'FOURTH TITLE (WILLIAMS)','title'),
             (38,'RETIRES','career'),
         ]),
    dict(code='SEN', name='Senna', color='#ffd700',
         debut_year=1984, last_year=1994, birth_year=1960,
         total_races=161, total_poles=65, championships=3, elo=2175,
         wins_by_year=[0,1,2,2,8,6,6,7,3,5,0],
         points_by_year=[13,38,55,57,94,60,78,96,50,73,0],
         strengths=dict(wet=99, quali=98, racecraft=94, consistency=85, tyre=88),
         career_events=[
             (24,'F1 DEBUT (TOLEMAN)','debut'),
             (25,'FIRST WIN (PORTUGAL 1985)','win'),
             (28,'FIRST TITLE (MCLAREN)','title'),
             (30,'SECOND TITLE','title'),
             (31,'THIRD TITLE','title'),
             (34,'DEATH AT IMOLA','life'),
         ]),
    dict(code='MSC', name='Schumacher', color='#e80020',
         debut_year=1991, last_year=2012, birth_year=1969,
         total_races=306, total_poles=68, championships=7, elo=2190,
         wins_by_year=[0,1,1,8,9,3,5,6,2,9,9,11,6,13,1,7,0, 0,0,0,0],
         points_by_year=[4,53,52,92,102,59,78,86,44,108,123,144,93,148,62,121,0, 0,0,0,49],
         strengths=dict(wet=98, quali=95, racecraft=95, consistency=96, tyre=94),
         career_events=[
             (22,'F1 DEBUT (JORDAN)','debut'),
             (23,'FIRST WIN (BELGIUM 1992)','win'),
             (25,'FIRST TITLE (BENETTON)','title'),
             (26,'BACK-TO-BACK','title'),
             (31,'FERRARI TITLE','title'),
             (32,'BACK-TO-BACK','title'),
             (33,'THREE STRAIGHT','title'),
             (34,'FOUR STRAIGHT','title'),
             (35,'FIVE STRAIGHT','title'),
             (37,'FIRST RETIREMENT','career'),
             (41,'F1 COMEBACK (MERCEDES)','career'),
             (44,'SKIING ACCIDENT','life'),
         ]),
    dict(code='RAI', name='Raikkonen', color='#c8102e',
         debut_year=2001, last_year=2021, birth_year=1979,
         total_races=349, total_poles=18, championships=1, elo=2100,
         wins_by_year=[0,0,1,1,7,0,6,2,1, 0,0, 0,1,0,0,0,0,1,0,0,0],
         points_by_year=[9,24,91,45,112,65,110,75,48, 0,0, 0,207,183,55,150,186,205,251,43,18,10],
         strengths=dict(wet=90, quali=88, racecraft=88, consistency=85, tyre=86),
         career_events=[
             (21,'F1 DEBUT (SAUBER)','debut'),
             (23,'FIRST WIN (MALAYSIA 2003)','win'),
             (28,'WORLD CHAMPION (FERRARI)','title'),
             (30,'RALLY SABBATICAL','career'),
             (32,'F1 RETURN (LOTUS)','career'),
             (42,'RETIRES','career'),
         ]),
    dict(code='ROS', name='Rosberg', color='#27f4d2',
         debut_year=2006, last_year=2016, birth_year=1985,
         total_races=206, total_poles=30, championships=1, elo=2030,
         wins_by_year=[0,0,0,0,0,0,1,2,5,6,9],
         points_by_year=[4,20,17,34.5,142,89,93,171,317,322,385],
         strengths=dict(wet=83, quali=91, racecraft=85, consistency=88, tyre=85),
         career_events=[
             (20,'F1 DEBUT (WILLIAMS)','debut'),
             (26,'FIRST WIN (CHINA 2012)','win'),
             (31,'WORLD CHAMPION','title'),
             (31,'INSTANT RETIREMENT','career'),
         ]),
    dict(code='BUT', name='Button', color='#ffffff',
         debut_year=2000, last_year=2017, birth_year=1980,
         total_races=306, total_poles=8, championships=1, elo=2040,
         wins_by_year=[0,0,0,0,0,0,1,0,0,6,2,3,3,0,0,0,0,0],
         points_by_year=[12,14,14,17,85,37,56,6,3,95,214,270,188,73,126,16,21,0],
         strengths=dict(wet=96, quali=82, racecraft=88, consistency=89, tyre=92),
         career_events=[
             (20,'F1 DEBUT (WILLIAMS)','debut'),
             (26,'FIRST WIN (HUNGARY 2006)','win'),
             (29,'WORLD CHAMPION (BRAWN GP)','title'),
             (37,'RETIRES','career'),
         ]),
    dict(code='RIC', name='Ricciardo', color='#fcd700',
         debut_year=2011, last_year=2024, birth_year=1989,
         total_races=257, total_poles=3, championships=0, elo=2020,
         wins_by_year=[0,0,0,3,0,1,3,2,0,0,1,0,0,0],
         points_by_year=[0,10,20,214,92,256,200,170,54,119,115,37,6,12],
         strengths=dict(wet=83, quali=86, racecraft=92, consistency=83, tyre=85),
         career_events=[
             (21,'F1 DEBUT (HRT)','debut'),
             (25,'FIRST WIN (CANADA 2014)','win'),
             (28,'RED BULL PEAK','career'),
             (35,'RETIRES','career'),
         ]),
    dict(code='PER', name='Perez', color='#1e41ff',
         debut_year=2011, last_year=2024, birth_year=1990,
         total_races=281, total_poles=3, championships=0, elo=1990,
         wins_by_year=[0,0,0,0,0,0,0,0,0,1,1,2,2,0],
         points_by_year=[2,66,49,59,78,101,100,62,69,125,190,305,285,152],
         strengths=dict(wet=84, quali=82, racecraft=86, consistency=81, tyre=90),
         career_events=[
             (21,'F1 DEBUT (SAUBER)','debut'),
             (30,'FIRST WIN (SAKHIR 2020)','win'),
             (33,'VICE CHAMPION','career'),
         ]),
    dict(code='ANT', name='Antonelli', color='#27f4d2',
         debut_year=2025, last_year='active', birth_year=2006,
         total_races=30, total_poles=1, championships=0, elo=1950,
         wins_by_year=[0,0],
         points_by_year=[55,20],
         strengths=dict(wet=80, quali=84, racecraft=82, consistency=80, tyre=80),
         career_events=[
             (18,'F1 DEBUT (MERCEDES)','debut'),
             (19,'FIRST PODIUM','career'),
         ]),
    dict(code='SAT', name='Sato', color='#e80020',
         debut_year=2002, last_year=2008, birth_year=1977,
         total_races=90, total_poles=0, championships=0, elo=1830,
         wins_by_year=[0,0,0,0,0,0,0],
         points_by_year=[2,3,34,1,4,4,0],
         strengths=dict(wet=78, quali=78, racecraft=82, consistency=72, tyre=75),
         career_events=[
             (25,'F1 DEBUT (JORDAN)','debut'),
             (27,'FIRST PODIUM (USA 2004)','career'),
             (31,'LEAVES F1','career'),
         ]),
    dict(code='GAS', name='Gasly', color='#0090ff',
         debut_year=2017, last_year='active', birth_year=1996,
         total_races=170, total_poles=0, championships=0, elo=1960,
         wins_by_year=[0,0,0,1,0,0,0,0,0],
         points_by_year=[0,29,95,75,110,23,62,42,30],
         strengths=dict(wet=84, quali=83, racecraft=85, consistency=82, tyre=82),
         career_events=[
             (21,'F1 DEBUT (TORO ROSSO)','debut'),
             (24,'SHOCK WIN AT MONZA','win'),
             (27,'ALPINE MOVE','career'),
         ]),
    dict(code='OCO', name='Ocon', color='#ff87bc',
         debut_year=2016, last_year='active', birth_year=1996,
         total_races=170, total_poles=0, championships=0, elo=1960,
         wins_by_year=[0,0,0,0,0,1,0,0,0,0],
         points_by_year=[0,87,49,0,62,74,92,58,23,20],
         strengths=dict(wet=82, quali=82, racecraft=84, consistency=84, tyre=83),
         career_events=[
             (20,'F1 DEBUT (MANOR)','debut'),
             (25,'SHOCK WIN (HUNGARY 2021)','win'),
             (28,'HAAS MOVE','career'),
         ]),
    dict(code='BOT', name='Bottas', color='#005050',
         debut_year=2013, last_year='active', birth_year=1989,
         total_races=240, total_poles=20, championships=0, elo=2010,
         wins_by_year=[0,186//6,0,0,3,2,2,2,1,0,0,0,0],
         points_by_year=[4,186,136,289,305,326,223,49,10,0,0,0,0],
         strengths=dict(wet=82, quali=88, racecraft=82, consistency=87, tyre=85),
         career_events=[
             (23,'F1 DEBUT (WILLIAMS)','debut'),
             (27,'MERCEDES PROMOTION','career'),
             (27,'FIRST WIN (RUSSIA 2017)','win'),
             (32,'LEAVES MERCEDES','career'),
         ]),
    dict(code='HUL', name='Hulkenberg', color='#52e252',
         debut_year=2010, last_year='active', birth_year=1987,
         total_races=240, total_poles=1, championships=0, elo=1970,
         wins_by_year=[0]*16,
         points_by_year=[22,0,63,51,96,58,72,43,69,37,10,0,22,9,41,15],
         strengths=dict(wet=85, quali=87, racecraft=82, consistency=83, tyre=80),
         career_events=[
             (23,'F1 DEBUT (WILLIAMS)','debut'),
             (23,'SHOCK POLE (BRAZIL 2010)','career'),
             (38,'STILL WINLESS RECORD','career'),
         ]),
    dict(code='MAG', name='Magnussen', color='#b6babd',
         debut_year=2014, last_year=2024, birth_year=1992,
         total_races=185, total_poles=0, championships=0, elo=1920,
         wins_by_year=[0]*10,
         points_by_year=[55,0,7,19,56,20,1,0,25,3],
         strengths=dict(wet=80, quali=82, racecraft=85, consistency=78, tyre=78),
         career_events=[
             (21,'F1 DEBUT PODIUM (AUS)','debut'),
             (29,'HAAS RETURN','career'),
             (31,'RETIRES','career'),
         ]),
    dict(code='ALB', name='Albon', color='#005bbb',
         debut_year=2019, last_year='active', birth_year=1996,
         total_races=130, total_poles=0, championships=0, elo=1970,
         wins_by_year=[0]*7,
         points_by_year=[92,105,0,4,27,12,20],
         strengths=dict(wet=83, quali=84, racecraft=84, consistency=84, tyre=84),
         career_events=[
             (23,'F1 DEBUT (TORO ROSSO)','debut'),
             (23,'RED BULL PROMOTION','career'),
             (26,'WILLIAMS REVIVAL','career'),
         ]),
    dict(code='GRO', name='Grosjean', color='#ffbf00',
         debut_year=2009, last_year=2020, birth_year=1986,
         total_races=180, total_poles=0, championships=0, elo=1920,
         wins_by_year=[0]*10,
         points_by_year=[0,96,132,126,8,51,29,13,37,8],
         strengths=dict(wet=80, quali=84, racecraft=80, consistency=76, tyre=78),
         career_events=[
             (23,'F1 DEBUT (RENAULT)','debut'),
             (26,'LOTUS PODIUM STREAK','career'),
             (34,'BAHRAIN FIREBALL','life'),
         ]),
    dict(code='BAR', name='Barrichello', color='#e80020',
         debut_year=1993, last_year=2011, birth_year=1972,
         total_races=322, total_poles=14, championships=0, elo=2020,
         wins_by_year=[0,0,0,0,0,0,0,2,4,4,2,2,0,0,1,0,0,0,0],
         points_by_year=[2,19,11,14,6,4,21,62,56,77,65,114,38,30,0,11,77,47,4],
         strengths=dict(wet=87, quali=85, racecraft=86, consistency=88, tyre=86),
         career_events=[
             (20,'F1 DEBUT (JORDAN)','debut'),
             (27,'JOINS FERRARI','career'),
             (28,'FIRST WIN (GERMANY 2000)','win'),
             (37,'BRAWN GP CHALLENGE','career'),
             (39,'RETIRES','career'),
         ]),
    dict(code='MAS', name='Massa', color='#e80020',
         debut_year=2002, last_year=2017, birth_year=1981,
         total_races=269, total_poles=16, championships=0, elo=2030,
         wins_by_year=[0,0,0,0,2,3,6,0,0,0,0,0,0,0,0,0],
         points_by_year=[4,12,11,0,80,94,97,22,144,118,122,112,134,121,53,43],
         strengths=dict(wet=85, quali=88, racecraft=85, consistency=85, tyre=84),
         career_events=[
             (21,'F1 DEBUT (SAUBER)','debut'),
             (25,'FERRARI PROMOTION','career'),
             (25,'FIRST WIN (TURKEY 2006)','win'),
             (27,'LOST TITLE BY 1 POINT','life'),
             (28,'HUNGARY ACCIDENT','life'),
             (36,'RETIRES','career'),
         ]),
    dict(code='CLA', name='Clark', color='#006341',
         debut_year=1960, last_year=1968, birth_year=1936,
         total_races=72, total_poles=33, championships=2, elo=2180,
         wins_by_year=[0,0,3,7,3,6,1,4,1],
         points_by_year=[8,11,30,54,32,54,16,41,9],
         strengths=dict(wet=95, quali=97, racecraft=93, consistency=94, tyre=92),
         career_events=[
             (24,'F1 DEBUT (LOTUS)','debut'),
             (26,'FIRST WIN (BELGIUM 1962)','win'),
             (27,'FIRST TITLE','title'),
             (29,'SECOND TITLE','title'),
             (32,'DEATH AT HOCKENHEIM','life'),
         ]),
    dict(code='PIQ', name='Piquet', color='#1e41ff',
         debut_year=1978, last_year=1991, birth_year=1952,
         total_races=204, total_poles=24, championships=3, elo=2140,
         wins_by_year=[0,0,3,3,1,3,4,4,3,3,0,0,2,0],
         points_by_year=[0,3,54,50,20,59,73,74,69,76,22,12,43,26.5],
         strengths=dict(wet=88, quali=93, racecraft=90, consistency=88, tyre=89),
         career_events=[
             (25,'F1 DEBUT','debut'),
             (28,'FIRST TITLE (BRABHAM)','title'),
             (31,'SECOND TITLE','title'),
             (35,'THIRD TITLE (WILLIAMS)','title'),
             (39,'RETIRES','career'),
         ]),
]


# ============================================================
# ヘルパー関数
# ============================================================

def build_cumulative(by_year):
    """年ごとの配列から累積配列を生成"""
    cum = []
    s = 0
    for v in by_year:
        s += v
        cum.append(s)
    return cum


def build_milestone_wins(wins_by_year, races_per_year=None):
    """
    参戦レース数ごとの累積勝利数配列を生成。
    各年の勝利は均等にレースに分配する近似。
    races_per_year が無ければ年20戦で近似。
    """
    if races_per_year is None:
        races_per_year = [20] * len(wins_by_year)
    milestone = [0]  # index 0 = 0 races, 0 wins
    cum_wins = 0
    for year_idx, wins in enumerate(wins_by_year):
        n_races = races_per_year[year_idx] if year_idx < len(races_per_year) else 20
        if n_races <= 0:
            continue
        # 年内の勝利を均等分配
        for r in range(1, n_races + 1):
            added = (wins * r // n_races) - (wins * (r - 1) // n_races)
            cum_wins += added
            milestone.append(cum_wins)
    return milestone


def enrich_driver(raw):
    """生マスターから派生フィールドを計算"""
    wins_by_year = raw['wins_by_year']
    points_by_year = raw['points_by_year']
    # 配列長を揃える
    n = max(len(wins_by_year), len(points_by_year))
    while len(wins_by_year) < n:
        wins_by_year.append(0)
    while len(points_by_year) < n:
        points_by_year.append(0)

    cum_wins = build_cumulative(wins_by_year)
    cum_pts = build_cumulative(points_by_year)
    total_wins = cum_wins[-1] if cum_wins else 0
    milestone = build_milestone_wins(wins_by_year)

    career_events = [
        {'age': age, 'label': label, 'type': etype}
        for (age, label, etype) in raw['career_events']
    ]

    return {
        'code': raw['code'],
        'name': raw['name'],
        'color': raw['color'],
        'debut_year': raw['debut_year'],
        'last_year': raw['last_year'],
        'birth_year': raw['birth_year'],
        'total_wins': total_wins,
        'total_poles': raw['total_poles'],
        'total_races': raw['total_races'],
        'championships': raw['championships'],
        'elo': raw['elo'],
        'strengths': raw['strengths'],
        'cumulative_wins': cum_wins,
        'cumulative_points': cum_pts,
        'milestone_wins': milestone,
        'career_events': career_events,
    }


# ============================================================
# ペアJSON生成
# ============================================================

def make_career_arc(d1, d2):
    return {
        'driver1': {
            'code': d1['code'], 'name': d1['name'], 'color': d1['color'],
            'cumWins': d1['cumulative_wins'], 'cumPts': d1['cumulative_points'],
            'debut': d1['debut_year'],
        },
        'driver2': {
            'code': d2['code'], 'name': d2['name'], 'color': d2['color'],
            'cumWins': d2['cumulative_wins'], 'cumPts': d2['cumulative_points'],
            'debut': d2['debut_year'],
        },
    }


def elo_expected(r1, r2):
    """Elo期待勝率"""
    return 1.0 / (1.0 + 10 ** ((r2 - r1) / 400))


def make_h2h_sim(d1, d2):
    s1, s2 = d1['strengths'], d2['strengths']
    # 予選 = quali重み大、レース = racecraft+consistency、勝利確率 = 全要素
    quali1 = s1['quali'] * 0.8 + s1['consistency'] * 0.2
    quali2 = s2['quali'] * 0.8 + s2['consistency'] * 0.2
    race1 = s1['racecraft'] * 0.4 + s1['consistency'] * 0.3 + s1['tyre'] * 0.3
    race2 = s2['racecraft'] * 0.4 + s2['consistency'] * 0.3 + s2['tyre'] * 0.3
    # Elo期待値を win_probabilityに使用
    win_prob1 = elo_expected(d1['elo'], d2['elo'])

    # 予選・レースH2Hは強さ差から
    def pct(a, b):
        t = a + b
        if t == 0:
            return (50, 50)
        p1 = round(a / t * 100)
        return (p1, 100 - p1)

    q1, q2 = pct(quali1, quali2)
    r1, r2 = pct(race1, race2)
    w1 = round(win_prob1 * 100)
    w2 = 100 - w1

    return {
        'driver1': {
            'code': d1['code'], 'name': d1['name'], 'color': d1['color'],
            'elo': d1['elo'], 'strengths': d1['strengths'],
        },
        'driver2': {
            'code': d2['code'], 'name': d2['name'], 'color': d2['color'],
            'elo': d2['elo'], 'strengths': d2['strengths'],
        },
        'predictions': {
            'qualifying':   {'left': q1, 'right': q2},
            'race':         {'left': r1, 'right': r2},
            'win_prob_20r': {'left': w1, 'right': w2},
        },
    }


def make_lifetime(d1, d2):
    return {
        'driver1': {
            'code': d1['code'], 'name': d1['name'], 'color': d1['color'],
            'birth_year': d1['birth_year'], 'debut_year': d1['debut_year'],
            'last_year': d1['last_year'],
            'career_events': d1['career_events'],
        },
        'driver2': {
            'code': d2['code'], 'name': d2['name'], 'color': d2['color'],
            'birth_year': d2['birth_year'], 'debut_year': d2['debut_year'],
            'last_year': d2['last_year'],
            'career_events': d2['career_events'],
        },
    }


def make_milestone(d1, d2):
    return {
        'driver1': {
            'code': d1['code'], 'name': d1['name'], 'color': d1['color'],
            'milestone_wins': d1['milestone_wins'],
            'total_races': d1['total_races'],
            'total_wins': d1['total_wins'],
        },
        'driver2': {
            'code': d2['code'], 'name': d2['name'], 'color': d2['color'],
            'milestone_wins': d2['milestone_wins'],
            'total_races': d2['total_races'],
            'total_wins': d2['total_wins'],
        },
    }


# ============================================================
# メイン
# ============================================================

def main():
    repo_root = Path(__file__).resolve().parent.parent
    out_root = repo_root / 'data' / 'drivers'
    pairs_root = out_root / 'pairs'
    pairs_root.mkdir(parents=True, exist_ok=True)

    # マスター生成
    drivers = [enrich_driver(r) for r in DRIVERS_RAW]
    master_path = out_root / 'master.json'
    with open(master_path, 'w', encoding='utf-8') as f:
        json.dump(drivers, f, ensure_ascii=False, indent=2)
    print(f'[OK] master.json: {len(drivers)} drivers -> {master_path}')

    # 435ペア × 4 JSON
    n_pairs = 0
    n_files = 0
    for d1, d2 in combinations(drivers, 2):
        slug = f"{d1['code'].lower()}-vs-{d2['code'].lower()}"
        pair_dir = pairs_root / slug
        pair_dir.mkdir(parents=True, exist_ok=True)

        payloads = {
            'career_arc': make_career_arc(d1, d2),
            'h2h_sim':    make_h2h_sim(d1, d2),
            'lifetime':   make_lifetime(d1, d2),
            'milestone':  make_milestone(d1, d2),
        }
        for kind, payload in payloads.items():
            p = pair_dir / f'{kind}.json'
            with open(p, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            n_files += 1
        n_pairs += 1

    print(f'[OK] pairs: {n_pairs} pairs, {n_files} files under {pairs_root}')
    expected_pairs = len(drivers) * (len(drivers) - 1) // 2
    assert n_pairs == expected_pairs, f'expected {expected_pairs} pairs, got {n_pairs}'
    assert n_files == expected_pairs * 4, f'expected {expected_pairs*4} files, got {n_files}'
    print(f'[OK] verified: {expected_pairs} pairs × 4 = {expected_pairs*4} files')


if __name__ == '__main__':
    main()
