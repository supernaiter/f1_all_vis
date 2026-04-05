#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
openf1_card_generator.py
OpenF1 API から braking_point / corner_speed / overtake_replay の 3種JSONを生成する。

使い方:
    python3 scripts/openf1_card_generator.py --year 2026 --round 1

処理フロー:
    1. /sessions から該当GPのRace session_keyを取得
    2. /drivers からドライバー一覧取得
    3. /car_data + /location で代表ラップ窓を取得（上位ドライバー限定）
    4. reference driver のspeed極小値からコーナー自動検出
    5. 各ドライバーのブレーキ開始点 / コーナー最低速度を集計
    6. /position からポジション入れ替わりを検出し、上位3オーバーテイクのGPS軌跡を抽出
    7. data/{gp}/cards/ 配下の3種JSONを更新

注意:
    - QPS制限: openf1_client.OpenF1Client (throttle 1.0qps default) を経由
    - 2026セッション未配信時は data/{gp} をスキップ
    - brakeは0/100の離散値（連続値ではない）
"""

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# local client (wraps throttle/retry)
sys.path.insert(0, str(Path(__file__).parent))
from openf1_client import OpenF1Client, ThrottleConfig  # noqa: E402

# GP 名マッピング（data/ ディレクトリ ↔ OpenF1 country/location）
GP_DIR_MAP = {
    1: ("2026_R01_Australia", "Australia", "Melbourne"),
    2: ("2026_R02_China", "China", "Shanghai"),
    3: ("2026_R03_Japan", "Japan", "Suzuka"),
}

# 公式チームカラー（OpenF1 team_colour のフォールバック）
TEAM_COLORS = {
    "McLaren": "#F47600", "Ferrari": "#DC0000",
    "Red Bull Racing": "#2B5DAB", "Mercedes": "#00B89F",
    "Aston Martin": "#1B7A5A", "Williams": "#3BA3E0",
    "RB": "#4A72CC", "Racing Bulls": "#4A72CC",
    "Alpine": "#0078AA", "Haas F1 Team": "#7A7A7A",
    "Kick Sauber": "#52E252", "Audi": "#3AAA3A", "Cadillac": "#888888",
}


def iso_parse(s: str) -> datetime:
    """ISO8601 文字列 → aware datetime"""
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def find_race_session(client: OpenF1Client, year: int, location: str):
    """年+ロケーションから Race session dict を取得"""
    rows = client.get("/sessions", {"year": year, "session_name": "Race"})
    for s in rows:
        if location.lower() in (s.get("location") or "").lower():
            return s
    return None


def list_drivers(client: OpenF1Client, session_key: int):
    """ドライバー一覧取得"""
    return client.get("/drivers", {"session_key": session_key}) or []


def fetch_car_data_window(client: OpenF1Client, session_key: int, driver_number: int,
                          start_iso: str, end_iso: str):
    """指定窓の car_data を取得"""
    return client.get("/car_data", {
        "session_key": session_key,
        "driver_number": driver_number,
        "date>": start_iso,
        "date<": end_iso,
    }) or []


def fetch_location_window(client: OpenF1Client, session_key: int, driver_number: int,
                          start_iso: str, end_iso: str):
    """指定窓の location を取得"""
    return client.get("/location", {
        "session_key": session_key,
        "driver_number": driver_number,
        "date>": start_iso,
        "date<": end_iso,
    }) or []


def detect_lap_window(car_rows):
    """1周分の時間窓を検出: speed 最小値間隔 or 単純に中央から前後60秒"""
    if not car_rows:
        return None, None
    times = [iso_parse(r["date"]) for r in car_rows]
    return times[0], times[-1]


def detect_corners(car_rows, location_rows, speed_threshold=180, min_gap_sec=2.0):
    """
    speed 極小値からコーナーを検出する。
    - speed が閾値以下で局所最小になる点を候補とする
    - min_gap_sec 以内の重複候補は除外
    - (x, y) は location_rows からタイムスタンプ最近傍で補完
    """
    if not car_rows:
        return []

    # location をタイムスタンプ→(x, y) の辞書に
    loc_sorted = sorted(location_rows, key=lambda r: r["date"])
    loc_ts = [iso_parse(r["date"]) for r in loc_sorted]

    def nearest_xy(t):
        if not loc_ts:
            return None, None
        # 線形検索: 小さいのでOK
        best = min(range(len(loc_ts)), key=lambda i: abs((loc_ts[i] - t).total_seconds()))
        return loc_sorted[best].get("x"), loc_sorted[best].get("y")

    # speed 極小値検出
    corners = []
    car_sorted = sorted(car_rows, key=lambda r: r["date"])
    n = len(car_sorted)
    last_t = None
    for i in range(3, n - 3):
        s = car_sorted[i].get("speed")
        if s is None or s > speed_threshold:
            continue
        # 前後3サンプルより小さいか
        window = [car_sorted[j].get("speed") or 9999 for j in range(i - 3, i + 4)]
        if s != min(window):
            continue
        t = iso_parse(car_sorted[i]["date"])
        if last_t and (t - last_t).total_seconds() < min_gap_sec:
            continue
        x, y = nearest_xy(t)
        corners.append({
            "id": len(corners) + 1,
            "name_approx": f"T{len(corners) + 1}",
            "x": x, "y": y,
            "speed_at_apex": s,
            "t": t.isoformat(),
        })
        last_t = t
    return corners


def find_braking_points(car_rows, corners, brake_threshold=50):
    """各コーナー手前での brake 立ち上がり地点を検出"""
    if not car_rows or not corners:
        return []
    car_sorted = sorted(car_rows, key=lambda r: r["date"])
    points = []
    corner_times = [iso_parse(c["t"]) for c in corners]
    # ブレーキ立ち上がり点（brake 0→100 の遷移）を全列挙
    brake_events = []
    prev_brake = 0
    for r in car_sorted:
        b = r.get("brake") or 0
        if b >= brake_threshold and prev_brake < brake_threshold:
            brake_events.append({
                "t": iso_parse(r["date"]),
                "speed": r.get("speed"),
            })
        prev_brake = b
    # 各コーナー apex の直前 (0〜3秒前) のブレーキ点を対応付け
    for ci, ct in enumerate(corner_times):
        candidates = [e for e in brake_events
                      if 0 < (ct - e["t"]).total_seconds() < 4.0]
        if candidates:
            # 最も遠い（早いブレーキ点）= ブレーキング始点
            best = max(candidates, key=lambda e: (ct - e["t"]).total_seconds())
            points.append({
                "corner_id": corners[ci]["id"],
                "time_to_apex_s": round((ct - best["t"]).total_seconds(), 2),
                "speed_at_brake": best["speed"],
            })
    return points


def find_overtakes(positions, max_count=5):
    """
    position データから順位入れ替わりペアを検出する。
    各ドライバーの最新position を時系列で追い、2台の順位が swap した瞬間を記録。
    """
    if not positions:
        return []
    sorted_pos = sorted(positions, key=lambda r: r["date"])
    # 各ドライバーの最新位置
    current = {}
    overtakes = []
    seen_pairs = set()
    for r in sorted_pos:
        drv = r.get("driver_number")
        pos = r.get("position")
        if drv is None or pos is None:
            continue
        prev_pos = current.get(drv)
        current[drv] = pos
        if prev_pos is None or prev_pos == pos:
            continue
        # 位置が上がった → 誰を抜いたか: 現在pos以下にいるはずの元pos占有者
        if pos < prev_pos:
            # 同じ pos にいた人 = 被抜き車
            for other_drv, other_pos in current.items():
                if other_drv == drv:
                    continue
                if other_pos == prev_pos:
                    # swap!
                    key = tuple(sorted([drv, other_drv]) + [int(pos)])
                    if key in seen_pairs:
                        continue
                    seen_pairs.add(key)
                    overtakes.append({
                        "t": r["date"],
                        "attacker": drv,
                        "defender": other_drv,
                        "new_pos": pos,
                    })
                    break
        if len(overtakes) >= max_count * 3:
            break
    # 位置の若い順（上位争い優先）
    overtakes.sort(key=lambda o: o["new_pos"])
    return overtakes[:max_count]


def fetch_overtake_traces(client, session_key, overtake, duration_sec=6):
    """オーバーテイクの瞬間前後の両車GPS軌跡"""
    t = iso_parse(overtake["t"])
    start = (t - timedelta(seconds=duration_sec)).isoformat()
    end = (t + timedelta(seconds=duration_sec)).isoformat()
    a_loc = fetch_location_window(client, session_key, overtake["attacker"], start, end)
    d_loc = fetch_location_window(client, session_key, overtake["defender"], start, end)

    def compress(rows):
        rows = sorted(rows, key=lambda r: r["date"])
        # 10サンプル毎に間引き（静的カード用）
        return [{"x": r.get("x"), "y": r.get("y"), "t": r.get("date")}
                for i, r in enumerate(rows) if i % 5 == 0]

    return compress(a_loc), compress(d_loc)


def team_color(team_name, team_colour_hex):
    """TeamColorフォールバック"""
    if team_colour_hex:
        return "#" + team_colour_hex.lstrip("#")
    return TEAM_COLORS.get(team_name, "#888888")


def process_gp(year: int, round_no: int, project_root: Path):
    if round_no not in GP_DIR_MAP:
        print(f"[ERR] unknown round {round_no}")
        return False
    gp_dir_name, country, location = GP_DIR_MAP[round_no]
    gp_dir = project_root / "data" / gp_dir_name
    if not gp_dir.exists():
        print(f"[ERR] gp dir not found: {gp_dir}")
        return False
    out_dir = gp_dir / "cards"
    out_dir.mkdir(exist_ok=True)

    client = OpenF1Client(throttle=ThrottleConfig(qps=2.0))
    print(f"[{gp_dir_name}] Looking up {year} Race at {location}...")
    session = find_race_session(client, year, location)
    if not session:
        print(f"[SKIP] {gp_dir_name}: OpenF1 session not found")
        return False
    session_key = int(session["session_key"])
    date_start = iso_parse(session["date_start"])
    date_end = iso_parse(session["date_end"])
    print(f"  session_key={session_key}, {date_start} → {date_end}")

    drivers = list_drivers(client, session_key)
    if not drivers:
        print(f"[SKIP] {gp_dir_name}: no drivers")
        return False
    print(f"  drivers: {len(drivers)}")

    # 解析対象: 上位10ドライバー（driver_number降順だと意味なし → positionが必要）
    # まずpositionで最終順位を取得
    positions = client.get("/position", {"session_key": session_key}) or []
    if not positions:
        print(f"[SKIP] {gp_dir_name}: no position data")
        return False

    # 最終position
    latest_pos = {}
    for p in sorted(positions, key=lambda r: r["date"]):
        if p.get("position") is not None:
            latest_pos[p["driver_number"]] = p["position"]
    top10 = sorted(latest_pos.items(), key=lambda kv: kv[1])[:10]
    top10_nums = [d for d, _ in top10]
    print(f"  top10 driver_numbers: {top10_nums}")

    drv_by_num = {d["driver_number"]: d for d in drivers}

    # レース10%-20%間の窓を使う（ピットストップやSCを避けたい。完全ではない）
    race_duration = (date_end - date_start).total_seconds()
    window_start = date_start + timedelta(seconds=race_duration * 0.25)
    window_end = window_start + timedelta(seconds=180)  # 3分窓（2-3周分）
    ws_iso = window_start.isoformat()
    we_iso = window_end.isoformat()
    print(f"  analysis window: {ws_iso} → {we_iso}")

    # reference driver（最上位）
    ref_num = top10_nums[0]
    print(f"  fetching reference car_data+location (driver {ref_num})...")
    ref_car = fetch_car_data_window(client, session_key, ref_num, ws_iso, we_iso)
    ref_loc = fetch_location_window(client, session_key, ref_num, ws_iso, we_iso)
    print(f"    car rows={len(ref_car)}, loc rows={len(ref_loc)}")

    corners = detect_corners(ref_car, ref_loc)
    print(f"  corners detected: {len(corners)}")

    # 各ドライバーのデータ取得
    drivers_data = []
    for num in top10_nums:
        info = drv_by_num.get(num, {})
        print(f"  fetching driver {num} ({info.get('name_acronym','?')})...")
        car = fetch_car_data_window(client, session_key, num, ws_iso, we_iso)
        loc = fetch_location_window(client, session_key, num, ws_iso, we_iso)
        # 車の corner speeds: reference corner時刻近傍で各ドライバー位置は違うが、代わりに
        # 各ドライバーのspeed極小値をそのまま使う（コーナー順対応付けはindex整合）
        own_corners = detect_corners(car, loc)
        # top N (reference cornersと同じ数まで切り詰め)
        min_speeds = [c["speed_at_apex"] for c in own_corners[:len(corners)]]
        # 不足分は None
        while len(min_speeds) < len(corners):
            min_speeds.append(None)

        braking = find_braking_points(car, own_corners[:len(corners)])
        # braking は own_corners index なので corners.id に直す（1:1）
        braking_remap = []
        for bp in braking:
            if bp["corner_id"] <= len(corners):
                braking_remap.append({
                    "corner_id": corners[bp["corner_id"] - 1]["id"],
                    "time_to_apex_s": bp["time_to_apex_s"],
                    "speed_at_brake": bp["speed_at_brake"],
                })

        drivers_data.append({
            "code": info.get("name_acronym", f"#{num}"),
            "number": num,
            "team": info.get("team_name", "?"),
            "color": team_color(info.get("team_name"), info.get("team_colour")),
            "min_speeds": min_speeds,
            "braking_points": braking_remap,
        })

    # オーバーテイク検出
    print("  finding overtakes...")
    overtakes_raw = find_overtakes(positions, max_count=3)
    overtakes_out = []
    for ot in overtakes_raw:
        a_info = drv_by_num.get(ot["attacker"], {})
        d_info = drv_by_num.get(ot["defender"], {})
        print(f"    OT: {a_info.get('name_acronym')} vs {d_info.get('name_acronym')} @ P{ot['new_pos']}")
        a_trace, d_trace = fetch_overtake_traces(client, session_key, ot)
        overtakes_out.append({
            "t": ot["t"],
            "new_pos": ot["new_pos"],
            "attacker": {
                "code": a_info.get("name_acronym", f"#{ot['attacker']}"),
                "team": a_info.get("team_name"),
                "color": team_color(a_info.get("team_name"), a_info.get("team_colour")),
                "trace": a_trace,
            },
            "defender": {
                "code": d_info.get("name_acronym", f"#{ot['defender']}"),
                "team": d_info.get("team_name"),
                "color": team_color(d_info.get("team_name"), d_info.get("team_colour")),
                "trace": d_trace,
            },
        })

    # サーキット形状（reference driver の location 間引き）
    circuit_outline = [{"x": r.get("x"), "y": r.get("y")}
                       for i, r in enumerate(sorted(ref_loc, key=lambda r: r["date"]))
                       if i % 3 == 0][:800]

    # 書き出し
    gp_key = gp_dir_name

    braking_json = {
        "type": "braking_point",
        "gp": gp_key,
        "status": "ok",
        "corners": corners,
        "outline": circuit_outline,
        "drivers": [{k: v for k, v in d.items() if k != "min_speeds"} for d in drivers_data],
    }
    corner_speed_json = {
        "type": "corner_speed",
        "gp": gp_key,
        "status": "ok",
        "corners": [c["name_approx"] for c in corners],
        "drivers": [{k: v for k, v in d.items() if k != "braking_points"} for d in drivers_data],
    }
    overtake_json = {
        "type": "overtake_replay",
        "gp": gp_key,
        "status": "ok",
        "outline": circuit_outline,
        "overtakes": overtakes_out,
    }

    for name, payload in [
        ("braking_point", braking_json),
        ("corner_speed", corner_speed_json),
        ("overtake_replay", overtake_json),
    ]:
        path = out_dir / f"{name}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"  [OK] {path}")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--project-root", default=None)
    args = ap.parse_args()

    root = Path(args.project_root) if args.project_root else Path(__file__).resolve().parent.parent
    ok = process_gp(args.year, args.round, root)
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
