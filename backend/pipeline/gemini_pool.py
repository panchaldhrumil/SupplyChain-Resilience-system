"""
backend/pipeline/gemini_pool.py
================================
Shared round-robin Gemini API key pool.

Reads keys from environment (in priority order):
  GEMINI_API_KEY       — primary key (no suffix)
  GEMINI_API_KEY_2
  GEMINI_API_KEY_3
  GEMINI_API_KEY_4

On 429 / rate-limit errors, call pool.rotate() to immediately advance to the
next key before retrying — this quadruples effective free-tier throughput.

Usage:
    from pipeline.gemini_pool import pool as gemini_pool

    key = gemini_pool.get_next_key()
    # on 429:
    key = gemini_pool.rotate()
"""

import itertools
import os
import threading
import logging

log = logging.getLogger("gemini_pool")


class GeminiKeyPool:
    """
    Thread-safe round-robin key pool that re-reads env vars on each .get_all_keys()
    call so that keys added to the environment after startup are picked up without
    a restart.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._last_keys: list[str] = []
        self._cycle = None
        self._call_count = 0
        self._key_index: dict[str, int] = {}   # key → position in pool for logging

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_keys(self) -> list[str]:
        """Read and deduplicate keys from environment, skipping placeholders."""
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass

        candidates = [
            os.environ.get("GEMINI_API_KEY",   ""),   # primary — no suffix
            os.environ.get("GEMINI_API_KEY_2",  ""),
            os.environ.get("GEMINI_API_KEY_3",  ""),
            os.environ.get("GEMINI_API_KEY_4",  ""),
        ]
        seen = set()
        clean: list[str] = []
        for k in candidates:
            k = (k or "").strip()
            if k and not k.startswith("your_gemini_api_key") and k not in seen:
                clean.append(k)
                seen.add(k)
        return clean

    def _maybe_reinit(self, keys: list[str]):
        """Reinitialise the cycle if the key list has changed."""
        if keys != self._last_keys or self._cycle is None:
            self._last_keys = keys
            self._cycle = itertools.cycle(range(len(keys)))
            self._key_index = {k: i for i, k in enumerate(keys)}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_all_keys(self) -> list[str]:
        """Return all valid keys currently in the pool."""
        return self._read_keys()

    def get_next_key(self) -> str:
        """
        Return the next key in round-robin order.
        Returns "" if no valid keys are configured.
        """
        keys = self._read_keys()
        with self._lock:
            if not keys:
                return ""
            self._maybe_reinit(keys)
            idx = next(self._cycle)
            key = keys[idx]
            self._call_count += 1
            log.debug("[GeminiPool] call #%d → key slot %d/%d", self._call_count, idx + 1, len(keys))
            return key

    def rotate(self) -> str:
        """
        Advance to the *next* key immediately (called on 429).
        Returns the new key, or "" if pool is empty.
        """
        keys = self._read_keys()
        with self._lock:
            if not keys:
                return ""
            self._maybe_reinit(keys)
            idx = next(self._cycle)
            key = keys[idx]
            log.warning("[GeminiPool] Rotated to key slot %d/%d after rate-limit.", idx + 1, len(keys))
            return key

    def __len__(self) -> int:
        return len(self._read_keys())

    def __repr__(self) -> str:
        n = len(self._read_keys())
        return f"GeminiKeyPool(keys={n}, calls_made={self._call_count})"


# Module-level singleton shared across all importers
pool = GeminiKeyPool()
