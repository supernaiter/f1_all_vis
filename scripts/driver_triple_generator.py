#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
driver_triple_generator.py

2026シーズン現役22名から C(22,3)=1,540 トリプルを生成し、
各トリプルに career_arc.json / lifetime.json の2種を出力する。

出力先: data/drivers/triples/{slug}/
スラッグ: 3コードを小文字・辞書順で連結（例: alb-ant-bea）

キュレーションなし。全展開。
"""

import json
import os
from itertools import combinations
from pathlib import Path

# 2026現役ドライバー22名
DRIVERS_2026 = [
    'NOR','PIA','RUS','ANT','VER','HAD','LEC','HAM','ALO','STR','GAS',
    'COL','OCO','BEA','LAW','LIN','HUL','BOR','SAI','ALB','PER','BOT',
]

ROOT = Path(__file__).resolve().parent.parent
MASTER_PATH = ROOT / 'data' / 'drivers' / 'master.json'
OUT_ROOT = ROOT / 'data' / 'drivers' / 'triples'


def load_master():
    with open(MASTER_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return {d['code']: d for d in data}


def slug_for(triple):
    # 辞書順の小文字コード
    return '-'.join(sorted([c.lower() for c in triple]))


def career_arc_obj(d):
    """2者版 career_arc.json と同じ driver フィールド形式"""
    return {
        'code': d['code'],
        'name': d['name'],
        'color': d['color'],
        'cumWins': list(d.get('cumulative_wins', []) or [0]),
        'cumPts': list(d.get('cumulative_points', []) or [0]),
        'debut': d['debut_year'],
    }


def lifetime_obj(d):
    """2者版 lifetime.json と同じ driver フィールド形式"""
    return {
        'code': d['code'],
        'name': d['name'],
        'color': d['color'],
        'birth_year': d['birth_year'],
        'debut_year': d['debut_year'],
        'last_year': d.get('last_year', 'active'),
        'career_events': list(d.get('career_events', []) or []),
    }


def main():
    master = load_master()

    missing = [c for c in DRIVERS_2026 if c not in master]
    if missing:
        raise SystemExit(f'master.json に未登録: {missing}')

    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    triples = list(combinations(DRIVERS_2026, 3))
    print(f'[info] generating {len(triples)} triples x 2 = {len(triples)*2} JSON files')

    for idx, triple in enumerate(triples, 1):
        # 辞書順でソートしてから取り出す
        sorted_codes = sorted(triple)
        d1, d2, d3 = (master[c] for c in sorted_codes)
        slug = '-'.join(c.lower() for c in sorted_codes)
        out_dir = OUT_ROOT / slug
        out_dir.mkdir(parents=True, exist_ok=True)

        # career_arc.json
        ca = {
            'driver1': career_arc_obj(d1),
            'driver2': career_arc_obj(d2),
            'driver3': career_arc_obj(d3),
        }
        with open(out_dir / 'career_arc.json', 'w', encoding='utf-8') as f:
            json.dump(ca, f, ensure_ascii=False, separators=(',', ':'))

        # lifetime.json
        lt = {
            'driver1': lifetime_obj(d1),
            'driver2': lifetime_obj(d2),
            'driver3': lifetime_obj(d3),
        }
        with open(out_dir / 'lifetime.json', 'w', encoding='utf-8') as f:
            json.dump(lt, f, ensure_ascii=False, separators=(',', ':'))

        if idx % 200 == 0:
            print(f'  [{idx}/{len(triples)}] {slug}')

    print(f'[done] wrote {len(triples)} triples to {OUT_ROOT}')


if __name__ == '__main__':
    main()
