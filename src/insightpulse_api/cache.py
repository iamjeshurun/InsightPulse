"""Small thread-safe TTL cache for inexpensive local deployments."""

from __future__ import annotations

import threading
from time import monotonic
from typing import Any


class TTLCache:
    def __init__(self, ttl_seconds: float = 10.0) -> None:
        self.ttl = ttl_seconds
        self._value: Any = None
        self._expires = 0.0
        self._lock = threading.Lock()

    def get(self) -> Any | None:
        with self._lock:
            return self._value if monotonic() < self._expires else None

    def set(self, value: Any) -> None:
        with self._lock:
            self._value, self._expires = value, monotonic() + self.ttl

    def clear(self) -> None:
        with self._lock:
            self._expires = 0.0
