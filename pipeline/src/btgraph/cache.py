"""File-based HTTP response cache.

Stores API responses as JSON files keyed by SHA-256 of the request URL.
Cache directory: <data-dir>/cache/openalex/
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


class FileCache:
    def __init__(self, cache_dir: str | Path):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _key_path(self, url: str) -> Path:
        h = hashlib.sha256(url.encode()).hexdigest()
        return self.cache_dir / f"{h}.json"

    def get(self, url: str) -> dict | None:
        """Return cached response body, or None if not cached."""
        path = self._key_path(url)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            logger.debug("Cache hit: %s", url)
            return data.get("body")
        except (json.JSONDecodeError, KeyError):
            logger.warning("Corrupt cache entry, removing: %s", path)
            path.unlink(missing_ok=True)
            return None

    def put(self, url: str, status_code: int, body: dict) -> None:
        """Write a response to cache."""
        path = self._key_path(url)
        envelope = {
            "url": url,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "status_code": status_code,
            "body": body,
        }
        path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.debug("Cached: %s", url)
