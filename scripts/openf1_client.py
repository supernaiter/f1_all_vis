from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Any, Dict, List

import json

import requests

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
            # add small non-negative jitter
            time.sleep(need + random.uniform(0, self.throttle.jitter_seconds))

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
                try:
                    return resp.json()
                except (json.JSONDecodeError, ValueError):
                    return []
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
