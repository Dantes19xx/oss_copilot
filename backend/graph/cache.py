"""Exact-match, on-disk cache for the two genuinely repeated calls in this project's
workload: reviewing a file whose patch hasn't changed since the last run, and
embedding the RAG style-context query (the same fixed string, re-embedded on every
single review run for a given repo — see backend/rag/embeddings.py).

Deliberately NOT a semantic/similarity cache. A code diff's review is exact-content-
sensitive: two patches that are 95% similar can still differ in the one line that
actually matters, so serving a cached review for a diff that merely *looks like* one
already reviewed would risk giving a confidently wrong answer. Exact-match on a hash of
the real inputs (including a prompt-version hash where relevant, so changing the prompt
invalidates old entries automatically) avoids that risk while still catching the real
repeated-request case: the same PR reviewed twice without changing.

Not used by backend/evals/*.py — eval and A/B runs intentionally always call the model
fresh (see PROGRESS.md stages 9 and 11: run-to-run variance is itself a documented
finding, which a cache would silently mask).
"""

import hashlib
import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / ".cache"


class FileCache:
    def __init__(self, name: str) -> None:
        CACHE_DIR.mkdir(exist_ok=True)
        self._path = CACHE_DIR / f"{name}.json"
        self._data: dict[str, Any] = json.loads(self._path.read_text()) if self._path.exists() else {}
        self.hits = 0
        self.misses = 0

    @staticmethod
    def _key(parts: tuple) -> str:
        canonical = json.dumps(parts, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()

    def get(self, parts: tuple) -> Any | None:
        """Manual lookup for batch call sites (e.g. embedding a list of texts where
        each item needs its own hit/miss, not one compute for the whole batch)."""
        key = self._key(parts)
        if key in self._data:
            self.hits += 1
            return self._data[key]
        self.misses += 1
        return None

    def set(self, parts: tuple, value: Any) -> None:
        self._data[self._key(parts)] = value
        self._path.write_text(json.dumps(self._data))

    async def get_or_compute(self, parts: tuple, compute: Callable[[], Awaitable[Any]]) -> Any:
        cached = self.get(parts)
        if cached is not None:
            return cached
        value = await compute()
        self.set(parts, value)
        return value

    @property
    def stats(self) -> dict:
        total = self.hits + self.misses
        return {"hits": self.hits, "misses": self.misses, "hit_rate": self.hits / total if total else 0.0}
