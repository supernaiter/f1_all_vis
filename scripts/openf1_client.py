from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd
import requests
from requests import Response

# Standalone copy: etl.common helpers inlined to avoid external dep
def normalize_session_name(name):
    if not name:
        return name
    s = str(name).strip().lower()
    mapping = {
        "fp1": "FP1", "practice 1": "FP1",
        "fp2": "FP2", "practice 2": "FP2",
        "fp3": "FP3", "practice 3": "FP3",
        "q": "Q", "qualifying": "Q",
        "sprint": "Sprint", "sprint qualifying": "SprintQ",
        "race": "Race", "r": "Race",
    }
    return mapping.get(s, str(name))


def to_utc_iso_millis(dt):
    if dt is None:
        return None
    try:
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    except Exception:
        return None


BASE_URL = "https://api.openf1.org/v1"


@dataclass
class ThrottleConfig:
    qps: float = 1.0
    jitter_seconds: float = 0.25


@dataclass
class RetryConfig:
    max_retries: int = 3
    initial_delay_seconds: float = 1.0
    backoff_factor: float = 2.0
    max_delay_seconds: float = 32.0


class OpenF1Client:
    def __init__(self, throttle: ThrottleConfig | None = None, retry: RetryConfig | None = None):
        self.throttle = throttle or ThrottleConfig()
        self.retry = retry or RetryConfig()
        self._last_call_ts: float = 0.0

    def _sleep_for_throttle(self) -> None:
        interval = 1.0 / max(self.throttle.qps, 1e-6)
        elapsed = time.time() - self._last_call_ts
        need = interval - elapsed
        if need > 0:
            # add small jitter
            time.sleep(need + (self.throttle.jitter_seconds * (0.5 - time.time() % 1)))

    def get(self, path: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        url = f"{BASE_URL}{path}"
        delay = self.retry.initial_delay_seconds
        for attempt in range(self.retry.max_retries + 1):
            self._sleep_for_throttle()
            try:
                resp = requests.get(url, params=params, timeout=30)
                self._last_call_ts = time.time()
            except requests.RequestException:
                if attempt >= self.retry.max_retries:
                    raise
                time.sleep(min(delay, self.retry.max_delay_seconds))
                delay *= self.retry.backoff_factor
                continue

            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (429, 500, 502, 503, 504):
                if attempt >= self.retry.max_retries:
                    # warn and return empty to proceed
                    return []
                time.sleep(min(delay, self.retry.max_delay_seconds))
                delay *= self.retry.backoff_factor
                continue
            # other errors: return empty
            return []
        return []


def find_meeting(client: OpenF1Client, year: int, keyword: str) -> Optional[Dict[str, Any]]:
    meetings = client.get("/meetings", {"year": year})
    if not meetings:
        return None
    keyword_lower = keyword.lower()

    def score(m: Dict[str, Any]) -> tuple[int, datetime]:
        name_fields = [
            str(m.get("meeting_official_name") or ""),
            str(m.get("meeting_name") or ""),
            str(m.get("country_name") or ""),
            str(m.get("round") or ""),
        ]
        # priority: official_name -> name -> country -> round
        priority = 0
        if keyword_lower in name_fields[0].lower():
            priority = 4
        elif keyword_lower in name_fields[1].lower():
            priority = 3
        elif keyword_lower in name_fields[2].lower():
            priority = 2
        elif keyword_lower == name_fields[3].lower():
            priority = 1
        # parse date_start
        ds = m.get("date_start")
        try:
            dt = datetime.fromisoformat(ds.replace("Z", "+00:00")) if isinstance(ds, str) else datetime.min
        except Exception:
            dt = datetime.min
        return (priority, dt)

    # choose the latest by date among highest priority
    meetings_sorted = sorted(meetings, key=score)
    return meetings_sorted[-1] if meetings_sorted else None


def list_sessions_for_meeting(client: OpenF1Client, meeting_key: int) -> List[Dict[str, Any]]:
    sessions = client.get("/sessions", {"meeting_key": meeting_key})
    return sessions or []


def fetch_team_radio(client: OpenF1Client, session_key: int, session_name: Optional[str] = None) -> pd.DataFrame:
    rows = client.get("/team_radio", {"session_key": session_key})
    if not rows:
        return pd.DataFrame(columns=["ts_utc", "session", "driver", "driver_number", "url", "source"])
    df = pd.DataFrame(rows)
    # Normalize columns
    df["ts_utc"] = pd.to_datetime(df["date"], utc=True, format='ISO8601').dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ").str.slice(0, 23) + "Z"
    df.rename(columns={"driver_number": "driver_number", "recording_url": "url"}, inplace=True)
    # driver abbreviation may be in 'driver' or 'driver_tla'
    if "driver" not in df.columns and "driver_tla" in df.columns:
        df["driver"] = df["driver_tla"]
    if session_name:
        df["session"] = normalize_session_name(session_name)
    df["source"] = "openf1"
    cols = ["ts_utc", "session", "driver", "driver_number", "url", "source"]
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    return df[cols]


def fetch_pit_events(client: OpenF1Client, session_key: int, session_name: Optional[str] = None) -> pd.DataFrame:
    rows = client.get("/pit", {"session_key": session_key})
    if not rows:
        return pd.DataFrame(columns=["ts_utc", "session", "driver", "driver_number", "pit_duration_s", "type", "source"])
    df = pd.DataFrame(rows)
    df["ts_utc"] = pd.to_datetime(df["date"], utc=True, format='ISO8601').dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ").str.slice(0, 23) + "Z"
    df.rename(columns={"pit_duration": "pit_duration_s"}, inplace=True)
    df["pit_duration_s"] = pd.to_numeric(df["pit_duration_s"], errors="coerce")
    df["type"] = "PitOpenF1"
    if session_name:
        df["session"] = normalize_session_name(session_name)
    df["source"] = "openf1"
    cols = ["ts_utc", "session", "driver", "driver_number", "pit_duration_s", "type", "source"]
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    return df[cols]


def fetch_position_data(client: OpenF1Client, session_key: int, session_name: Optional[str] = None) -> pd.DataFrame:
    """
    Fetch position data from OpenF1 API for a specific session.

    Args:
        client: OpenF1Client instance
        session_key: Session identifier
        session_name: Optional session name for normalization

    Returns:
        DataFrame with position data
    """
    rows = client.get("/position", {"session_key": session_key})
    if not rows:
        return pd.DataFrame(columns=["ts_utc", "session", "driver_number", "position", "source"])

    df = pd.DataFrame(rows)

    # Normalize timestamp
    if "date" in df.columns:
        df["ts_utc"] = pd.to_datetime(df["date"], utc=True, format='ISO8601').dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ").str.slice(0, 23) + "Z"

    # Add session name if provided
    if session_name:
        df["session"] = normalize_session_name(session_name)

    # Add source identifier
    df["source"] = "openf1"

    # Ensure required columns exist
    cols = ["ts_utc", "session", "driver_number", "position", "source"]
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA

    return df[cols]


def build_openf1_only_timeline(radios: List[pd.DataFrame], pits: List[pd.DataFrame]) -> pd.DataFrame:
    frames = []
    for df in radios:
        if df is None or df.empty:
            continue
        r = df.copy()
        r["type"] = "TeamRadio"
        frames.append(r)
    for df in pits:
        if df is None or df.empty:
            continue
        frames.append(df)
    if not frames:
        return pd.DataFrame(columns=[
            "ts_utc", "session", "type", "driver", "driver_number", "pit_duration_s", "url", "source"
        ])
    all_df = pd.concat(frames, ignore_index=True)
    all_df = all_df.sort_values(by=["ts_utc"]).reset_index(drop=True)
    return all_df


# ----------------------------- New OpenF1 fetchers -----------------------------

def _ensure_iso_ts(df: pd.DataFrame, src_col: str = "date") -> pd.DataFrame:
    if src_col in df.columns:
        df["ts_utc"] = (
            pd.to_datetime(df[src_col], utc=True, errors="coerce", format='ISO8601')
              .dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
              .str.slice(0, 23) + "Z"
        )
    else:
        df["ts_utc"] = pd.NaT
    return df


def _coerce_numeric(series: pd.Series) -> pd.Series:
    try:
        return pd.to_numeric(series, errors="coerce")
    except Exception:
        return pd.Series([pd.NA] * len(series))


def fetch_intervals(client: OpenF1Client, session_key: int, session_name: Optional[str] = None) -> pd.DataFrame:
    """
    Fetch intervals from OpenF1.

    Returns columns: ts_utc, session, driver_number, gap_to_leader_s, interval_s, source
    """
    rows = client.get("/intervals", {"session_key": session_key})
    if not rows:
        return pd.DataFrame(columns=["ts_utc", "session", "driver_number", "gap_to_leader_s", "interval_s", "source"])

    df = pd.DataFrame(rows)
    df = _ensure_iso_ts(df, src_col="date")

    # Column mapping with fallbacks
    driver_col = "driver_number" if "driver_number" in df.columns else None
    gap_col = None
    for c in ["gap_to_leader", "gap_to_leader_s", "gap_leader", "gap"]:
        if c in df.columns:
            gap_col = c
            break
    ivl_col = None
    for c in ["interval", "interval_s", "diff_to_car_ahead", "delta_front"]:
        if c in df.columns:
            ivl_col = c
            break

    if driver_col is None:
        df["driver_number"] = pd.NA
    else:
        df.rename(columns={driver_col: "driver_number"}, inplace=True)

    if gap_col is None:
        df["gap_to_leader_s"] = pd.NA
    else:
        df["gap_to_leader_s"] = _coerce_numeric(df[gap_col])

    if ivl_col is None:
        df["interval_s"] = pd.NA
    else:
        df["interval_s"] = _coerce_numeric(df[ivl_col])

    if session_name:
        df["session"] = normalize_session_name(session_name)
    df["source"] = "openf1"

    cols = ["ts_utc", "session", "driver_number", "gap_to_leader_s", "interval_s", "source"]
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    return df[cols]


def fetch_laps_openf1(client: OpenF1Client, session_key: int, session_name: Optional[str] = None) -> pd.DataFrame:
    """
    Fetch laps from OpenF1.

    Returns columns: ts_utc, session, driver_number, lap_number, lap_time_s, source
    """
    rows = client.get("/laps", {"session_key": session_key})
    if not rows:
        return pd.DataFrame(columns=["ts_utc", "session", "driver_number", "lap_number", "lap_time_s", "source"])

    df = pd.DataFrame(rows)
    df = _ensure_iso_ts(df, src_col="date")

    # driver number
    if "driver_number" not in df.columns:
        df["driver_number"] = pd.NA

    # lap number
    lap_num_col = None
    for c in ["lap_number", "lap", "number"]:
        if c in df.columns:
            lap_num_col = c
            break
    if lap_num_col is None:
        df["lap_number"] = pd.NA
    else:
        df.rename(columns={lap_num_col: "lap_number"}, inplace=True)

    # lap time seconds (robust per-row construction)
    df["lap_time_s"] = pd.NA
    # Prefer a unified 'lap_duration' field if present
    lap_time_col = None
    for c in ["lap_duration", "lap_time", "lap_time_s", "duration", "lap_duration_s", "last_lap_time"]:
        if c in df.columns:
            lap_time_col = c
            break
    if lap_time_col is not None:
        # coerce numeric first
        s_num = pd.to_numeric(df[lap_time_col], errors="coerce")
        # string/ISO durations fallback
        s_td = pd.to_timedelta(df[lap_time_col], errors="coerce")
        s_td_sec = s_td.dt.total_seconds()
        # prefer numeric when available, else timedel
        df["lap_time_s"] = s_num.where(s_num.notna(), s_td_sec)
        # treat very large numeric as milliseconds
        if df["lap_time_s"].notna().any() and df["lap_time_s"].max() > 10000:
            df.loc[df["lap_time_s"].notna(), "lap_time_s"] = df.loc[df["lap_time_s"].notna(), "lap_time_s"] / 1000.0

    # Per-row sector sum fallback
    def _col_to_sec(colnames: list[str]) -> pd.Series:
        for c in colnames:
            if c in df.columns:
                num = pd.to_numeric(df[c], errors="coerce")
                # if numeric empty, try timedelta parse
                td = pd.to_timedelta(df[c], errors="coerce")
                sec = num.where(num.notna(), td.dt.total_seconds())
                # treat very large as milliseconds
                if sec.notna().any() and sec.max() > 10000:
                    sec = sec / 1000.0
                return sec
        return pd.Series([pd.NA] * len(df))

    s1 = _col_to_sec(["duration_sector_1", "sector1", "s1_time", "s1_ms"]) 
    s2 = _col_to_sec(["duration_sector_2", "sector2", "s2_time", "s2_ms"]) 
    s3 = _col_to_sec(["duration_sector_3", "sector3", "s3_time", "s3_ms"]) 
    sector_sum = pd.to_numeric(s1, errors="coerce").fillna(0) + pd.to_numeric(s2, errors="coerce").fillna(0) + pd.to_numeric(s3, errors="coerce").fillna(0)
    # If any sector present for a row and lap_time_s is NaN, fill
    any_sector_present = s1.notna() | s2.notna() | s3.notna()
    df.loc[df["lap_time_s"].isna() & any_sector_present, "lap_time_s"] = sector_sum

    if session_name:
        df["session"] = normalize_session_name(session_name)
    df["source"] = "openf1"

    cols = ["ts_utc", "session", "driver_number", "lap_number", "lap_time_s", "source"]
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    out = df[cols].copy()
    # Ensure ts_utc can hold strings
    try:
        out["ts_utc"] = out["ts_utc"].astype("object")
    except Exception:
        pass

    # Fallback: synthesize ts_utc from session start + cumulative lap_time_s when ts_utc is missing
    try:
        if out["ts_utc"].isna().all() and out["lap_time_s"].notna().any():
            # Find session start from sessions(meeting_key) → our session_key
            t0 = None
            mk = None
            try:
                if "meeting_key" in df.columns:
                    mk = pd.to_numeric(df["meeting_key"], errors="coerce").dropna().astype(int)
                    mk = int(mk.mode().iloc[0]) if not mk.empty else None
            except Exception:
                mk = None
            sess_info = client.get("/sessions", {"meeting_key": mk}) if mk else []
            if sess_info:
                for srow in sess_info:
                    try:
                        if int(srow.get("session_key")) == int(session_key):
                            ds = srow.get("date_start")
                            if isinstance(ds, str) and ds:
                                t0 = pd.to_datetime(ds, utc=True, errors="coerce")
                            break
                    except Exception:
                        continue
            if t0 is not None:
                tmp = out.copy()
                tmp["__row_idx"] = tmp.index
                # order by driver and lap
                tmp["__lap"] = pd.to_numeric(tmp.get("lap_number"), errors="coerce") if "lap_number" in tmp.columns else pd.to_numeric(tmp.get("lap"), errors="coerce")
                tmp = tmp.sort_values(["driver_number", "__lap", "__row_idx"]).reset_index(drop=True)
                # cumulative sum per driver
                csum = tmp.groupby("driver_number")["lap_time_s"].cumsum()
                synth = pd.to_datetime(t0, utc=True) + pd.to_timedelta(csum, unit="s")
                tmp["ts_utc"] = synth.dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ").str.slice(0, 23) + "Z"
                # write back using original row indices
                tmp_map = tmp[["__row_idx", "ts_utc"]]
                out.loc[tmp_map["__row_idx"], "ts_utc"] = tmp_map["ts_utc"].values
                out = out.drop(columns=[c for c in ["__lap"] if c in out.columns])
    except Exception:
        pass

    return out


def fetch_rcm_openf1(client: OpenF1Client, session_key: int, session_name: Optional[str] = None) -> pd.DataFrame:
    """
    Fetch Race Control Messages from OpenF1.

    Returns columns: ts_utc, session, message, flag, type='RaceControl', source
    """
    rows = client.get("/race_control", {"session_key": session_key})
    if not rows:
        return pd.DataFrame(columns=["ts_utc", "session", "message", "flag", "type", "source"])

    df = pd.DataFrame(rows)
    df = _ensure_iso_ts(df, src_col="date")

    # message
    msg_col = None
    for c in ["message", "text", "body", "note"]:
        if c in df.columns:
            msg_col = c
            break
    if msg_col is None:
        df["message"] = pd.NA
    else:
        df.rename(columns={msg_col: "message"}, inplace=True)

    # flag/category
    flag_col = None
    for c in ["flag", "category", "scope", "status"]:
        if c in df.columns:
            flag_col = c
            break
    if flag_col is None:
        df["flag"] = pd.NA
    else:
        df.rename(columns={flag_col: "flag"}, inplace=True)

    if session_name:
        df["session"] = normalize_session_name(session_name)
    df["type"] = "RaceControl"
    df["source"] = "openf1"

    cols = ["ts_utc", "session", "message", "flag", "type", "source"]
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    return df[cols]


def fetch_stints(client: OpenF1Client, session_key: int, session_name: Optional[str] = None) -> pd.DataFrame:
    """
    Fetch tyre stints from OpenF1.

    Returns columns: driver_number, stint_id, compound, from_lap, to_lap, source
    Note: Stints are per session/driver but usually don't have timestamps.
    """
    rows = client.get("/stints", {"session_key": session_key})
    if not rows:
        return pd.DataFrame(columns=["driver_number", "stint_id", "compound", "from_lap", "to_lap", "source"])

    df = pd.DataFrame(rows)

    # driver number
    if "driver_number" not in df.columns:
        df["driver_number"] = pd.NA

    # stint id/number
    stint_col = None
    for c in ["stint_id", "stint", "stint_number"]:
        if c in df.columns:
            stint_col = c
            break
    if stint_col is None:
        df["stint_id"] = pd.NA
    else:
        df.rename(columns={stint_col: "stint_id"}, inplace=True)

    # compound
    comp_col = None
    for c in ["compound", "tyre_compound", "compound_name"]:
        if c in df.columns:
            comp_col = c
            break
    if comp_col is None:
        df["compound"] = pd.NA
    else:
        df.rename(columns={comp_col: "compound"}, inplace=True)

    # from/to lap
    from_col = None
    for c in ["lap_start", "from_lap", "start_lap"]:
        if c in df.columns:
            from_col = c
            break
    to_col = None
    for c in ["lap_end", "to_lap", "end_lap"]:
        if c in df.columns:
            to_col = c
            break
    if from_col is None:
        df["from_lap"] = pd.NA
    else:
        df.rename(columns={from_col: "from_lap"}, inplace=True)
    if to_col is None:
        df["to_lap"] = pd.NA
    else:
        df.rename(columns={to_col: "to_lap"}, inplace=True)

    df["source"] = "openf1"
    cols = ["driver_number", "stint_id", "compound", "from_lap", "to_lap", "source"]
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    return df[cols]


def fetch_weather(client: OpenF1Client, session_key: int, session_name: Optional[str] = None) -> pd.DataFrame:
    """
    Fetch weather timeseries from OpenF1.

    Returns columns: ts_utc, air_temp_c, track_temp_c, humidity_percent, wind, rain, source
    """
    rows = client.get("/weather", {"session_key": session_key})
    if not rows:
        return pd.DataFrame(columns=["ts_utc", "air_temp_c", "track_temp_c", "humidity_percent", "wind", "rain", "source"])

    df = pd.DataFrame(rows)
    df = _ensure_iso_ts(df, src_col="date")

    # Map columns
    def map_col(cands: List[str], target: str):
        for c in cands:
            if c in df.columns:
                df.rename(columns={c: target}, inplace=True)
                return
        df[target] = pd.NA

    map_col(["air_temperature", "air_temp", "temp_air_c"], "air_temp_c")
    map_col(["track_temperature", "track_temp", "temp_track_c"], "track_temp_c")
    map_col(["humidity", "humidity_percent", "rel_humidity"], "humidity_percent")
    # Wind could be speed or a vector; keep as-is string/number
    if "wind" in df.columns:
        pass
    elif "wind_speed" in df.columns:
        df.rename(columns={"wind_speed": "wind"}, inplace=True)
    else:
        df["wind"] = pd.NA

    # Rain could be boolean or rate; keep numeric/boolean as-is
    if "rain" not in df.columns:
        for c in ["rainfall", "rainfall_rate", "is_raining"]:
            if c in df.columns:
                df.rename(columns={c: "rain"}, inplace=True)
                break
        if "rain" not in df.columns:
            df["rain"] = pd.NA

    df["source"] = "openf1"
    cols = ["ts_utc", "air_temp_c", "track_temp_c", "humidity_percent", "wind", "rain", "source"]
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    return df[cols]


def fetch_car_data(client: OpenF1Client, session_key: int, session_name: Optional[str] = None) -> pd.DataFrame:
    """
    Fetch high-frequency car telemetry from OpenF1.

    Returns columns: ts_utc, session, driver_number, speed_kph, rpm, throttle, brake, gear, drs, source
    """
    rows = client.get("/car_data", {"session_key": session_key})
    if not rows:
        return pd.DataFrame(columns=[
            "ts_utc", "session", "driver_number", "speed_kph", "rpm", "throttle", "brake", "gear", "drs", "source"
        ])
    df = pd.DataFrame(rows)
    df = _ensure_iso_ts(df, src_col="date")

    # Normalize columns with fallbacks
    if "driver_number" not in df.columns:
        df["driver_number"] = pd.NA

    col_map = {
        "speed_kph": ["speed", "speed_kph"],
        "rpm": ["engine_rpm", "rpm"],
        "throttle": ["throttle", "throttle_pct"],
        "brake": ["brake", "brake_pressure"],
        "gear": ["n_gear", "gear"],
        "drs": ["drs", "drs_status"],
    }
    for tgt, cands in col_map.items():
        found = None
        for c in cands:
            if c in df.columns:
                found = c
                break
        if found:
            df.rename(columns={found: tgt}, inplace=True)
        else:
            df[tgt] = pd.NA

    for num_col in ["speed_kph", "rpm", "throttle", "brake", "gear", "drs"]:
        if num_col in df.columns:
            try:
                df[num_col] = pd.to_numeric(df[num_col], errors="coerce")
            except Exception:
                pass

    if session_name:
        df["session"] = normalize_session_name(session_name)
    df["source"] = "openf1"
    cols = ["ts_utc", "session", "driver_number", "speed_kph", "rpm", "throttle", "brake", "gear", "drs", "source"]
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    return df[cols]


def fetch_location(client: OpenF1Client, session_key: int, session_name: Optional[str] = None) -> pd.DataFrame:
    """
    Fetch car location stream from OpenF1.

    Returns columns: ts_utc, session, driver_number, x, y, z, lat, lon, source
    """
    rows = client.get("/location", {"session_key": session_key})
    if not rows:
        return pd.DataFrame(columns=[
            "ts_utc", "session", "driver_number", "x", "y", "z", "lat", "lon", "source"
        ])
    df = pd.DataFrame(rows)
    df = _ensure_iso_ts(df, src_col="date")

    if "driver_number" not in df.columns:
        df["driver_number"] = pd.NA

    # Map possible coordinate columns
    for tgt, cands in {
        "x": ["x", "pos_x"],
        "y": ["y", "pos_y"],
        "z": ["z", "pos_z"],
        "lat": ["lat", "latitude"],
        "lon": ["lon", "longitude", "long"]
    }.items():
        found = None
        for c in cands:
            if c in df.columns:
                found = c
                break
        if found:
            df.rename(columns={found: tgt}, inplace=True)
        else:
            df[tgt] = pd.NA

    # Coerce numerics
    for num_col in ["x", "y", "z", "lat", "lon"]:
        try:
            df[num_col] = pd.to_numeric(df[num_col], errors="coerce")
        except Exception:
            pass

    if session_name:
        df["session"] = normalize_session_name(session_name)
    df["source"] = "openf1"
    cols = ["ts_utc", "session", "driver_number", "x", "y", "z", "lat", "lon", "source"]
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    return df[cols]

