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
    5. 各ドライバーのブレーキ開始点 / コーナー最低速度を集計（GPS最近傍マッチング）
    6. /position からポジション入れ替わりを検出し、ピットラップを除外した上位3オーバーテイクのGPS軌跡を抽出
    7. data/{gp}/cards/ 配下の3種JSONを更新

注意:
    - QPS制限: openf1_client.OpenF1Client (throttle 1.0qps default) を経由
    - 2026セッション未配信時は data/{gp} をスキップ
    - brakeは0/100の離散値（連続値ではない）
"""

import argparse
import json
import math
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# local client (wraps throttle/retry)
sys.path.insert(0, str(Path(__file__).parent))
from openf1_client import OpenF1Client, ThrottleConfig  # noqa: E402

# 公式チームカラー（OpenF1 team_colour のフォールバック）
TEAM_COLORS = {
    "McLaren": "#F47600", "Ferrari": "#DC0000",
    "Red Bull Racing": "#2B5DAB", "Mercedes": "#00B89F",
    "Aston Martin": "#1B7A5A", "Williams": "#3BA3E0",
    "RB": "#4A72CC", "Racing Bulls": "#4A72CC",
    "Alpine": "#0078AA", "Haas F1 Team": "#7A7A7A",
    "Kick Sauber": "#52E252", "Audi": "#3AAA3A", "Cadillac": "#888888",
}

# data/ ディレクトリのパターン: 2026_R{NN}_{Name}
_GP_DIR_PATTERN = re.compile(r"^(\d{4})_R(\d+)_(.+)$")


def find_gp_dir(data_root: Path, year: int, round_no: int):
    """
    data/ ディレクトリをスキャンして {year}_R{round_no:02d}_{name} に一致するものを返す。
    一致しない場合は None。
    戻り値: (dir_path, location_name) or (None, None)
    """
    if not data_root.is_dir():
        return None, None
    for entry in data_root.iterdir():
        if not entry.is_dir():
            continue
        m = _GP_DIR_PATTERN.match(entry.name)
        if not m:
            continue
        dir_year = int(m.group(1))
        dir_round = int(m.group(2))
        dir_name = m.group(3)
        if dir_year == year and dir_round == round_no:
            return entry, dir_name
    return None, None


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


def gps_distance(x1, y1, x2, y2):
    """2点間のユークリッド距離"""
    if x1 is None or y1 is None or x2 is None or y2 is None:
        return float("inf")
    return math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)


def match_corners_by_gps(own_corners, ref_corners):
    """
    own_cornersの各コーナーをref_cornersのGPS最近傍にマッチングする。
    ref_corner 1つに複数のown_cornerが対応する場合、最もspeed_at_apexが低いもの（apex）を採用。
    戻り値: {ref_corner_id: own_corner_dict or None}
    """
    if not ref_corners:
        return {}

    # ref_corner_id → 候補リスト
    candidates = {c["id"]: [] for c in ref_corners}

    for oc in own_corners:
        ox, oy = oc.get("x"), oc.get("y")
        if ox is None or oy is None:
            continue
        # 最近傍 ref corner を見つける
        best_ref = min(
            ref_corners,
            key=lambda rc: gps_distance(ox, oy, rc.get("x"), rc.get("y"))
        )
        candidates[best_ref["id"]].append(oc)

    result = {}
    for c in ref_corners:
        cands = candidates[c["id"]]
        if not cands:
            result[c["id"]] = None
        else:
            # 複数候補があればspeed_at_apexが最も低いものをapexとして採用
            result[c["id"]] = min(cands, key=lambda oc: oc.get("speed_at_apex") or 9999)
    return result


def find_braking_points(car_rows, corner_match, brake_threshold=50):
    """
    各コーナー（GPS最近傍マッチング済み）手前でのbrake立ち上がり地点を検出。
    corner_match: {ref_corner_id: own_corner_dict or None}
    """
    if not car_rows or not corner_match:
        return []
    car_sorted = sorted(car_rows, key=lambda r: r["date"])

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

    points = []
    for ref_id, oc in corner_match.items():
        if oc is None:
            continue
        ct = iso_parse(oc["t"])
        candidates = [e for e in brake_events
                      if 0 < (ct - e["t"]).total_seconds() < 4.0]
        if candidates:
            # 最も遠い（早いブレーキ点）= ブレーキング始点
            best = max(candidates, key=lambda e: (ct - e["t"]).total_seconds())
            points.append({
                "corner_id": ref_id,
                "time_to_apex_s": round((ct - best["t"]).total_seconds(), 2),
                "speed_at_brake": best["speed"],
            })
    return points


def fetch_pit_events(client: OpenF1Client, session_key: int):
    """ピットストップイベントを取得"""
    return client.get("/pit", {"session_key": session_key}) or []


def build_pit_intervals(pit_events, buffer_sec=10.0):
    """
    ピットイベントから (driver_number, start_t, end_t) の除外インターバルを構築。
    pit_dateを基準に ±buffer_sec の窓を作る。
    """
    intervals = []
    for p in pit_events:
        drv = p.get("driver_number")
        pit_date = p.get("date") or p.get("pit_duration") and None
        # date フィールドがない場合は lap_number 基準で後でフィルタ不可 → スキップ
        if drv is None or not pit_date:
            continue
        try:
            t = iso_parse(pit_date)
        except (ValueError, TypeError):
            continue
        intervals.append((drv, t - timedelta(seconds=buffer_sec), t + timedelta(seconds=buffer_sec)))
    return intervals


def is_pit_related(t_str: str, attacker: int, defender: int, pit_intervals):
    """オーバーテイク時刻がピット除外インターバル内かどうか判定"""
    try:
        t = iso_parse(t_str)
    except (ValueError, TypeError):
        return False
    for drv, start, end in pit_intervals:
        if drv in (attacker, defender) and start <= t <= end:
            return True
    return False


def find_overtakes(positions, pit_intervals=None, max_count=5):
    """
    position データから順位入れ替わりペアを検出する。
    各ドライバーの最新position を時系列で追い、2台の順位が swap した瞬間を記録。
    ピット由来のswapはpit_intervalsで除外。ピットデータが取れない場合は3ポジション以上の急変を除外。
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
            pos_change = prev_pos - pos
            # ピットデータなし時のフォールバック: 3ポジション以上の急変はピットの可能性高いので除外
            if pit_intervals is None and pos_change >= 3:
                continue

            # 同じ pos にいた人 = 被抜き車
            for other_drv, other_pos in current.items():
                if other_drv == drv:
                    continue
                if other_pos == prev_pos:
                    # ピット除外チェック
                    if pit_intervals and is_pit_related(r["date"], drv, other_drv, pit_intervals):
                        break
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
    data_root = project_root / "data"
    gp_dir, location = find_gp_dir(data_root, year, round_no)
    if gp_dir is None:
        print(f"[ERR] no directory found for {year} R{round_no:02d} in {data_root}")
        return False
    gp_dir_name = gp_dir.name
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

        # GPS最近傍マッチングで各ドライバーのコーナーをreferenceに対応付け
        own_corners = detect_corners(car, loc)
        corner_match = match_corners_by_gps(own_corners, corners)

        # min_speeds: reference corners順に速度を並べる
        min_speeds = []
        for c in corners:
            matched = corner_match.get(c["id"])
            min_speeds.append(matched["speed_at_apex"] if matched else None)

        # ブレーキングポイント: GPS最近傍マッチング済みのcorner_matchを使用
        braking_remap = find_braking_points(car, corner_match)

        drivers_data.append({
            "code": info.get("name_acronym", f"#{num}"),
            "number": num,
            "team": info.get("team_name", "?"),
            "color": team_color(info.get("team_name"), info.get("team_colour")),
            "min_speeds": min_speeds,
            "braking_points": braking_remap,
        })

    # ピットイベント取得（オーバーテイク除外用）
    print("  fetching pit events...")
    pit_events = fetch_pit_events(client, session_key)
    print(f"    pit events: {len(pit_events)}")
    if pit_events:
        pit_intervals = build_pit_intervals(pit_events)
        print(f"    pit intervals built: {len(pit_intervals)}")
    else:
        print("    no pit data — using fallback (±3 position change filter)")
        pit_intervals = None

    # オーバーテイク検出
    print("  finding overtakes...")
    overtakes_raw = find_overtakes(positions, pit_intervals=pit_intervals, max_count=3)
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
