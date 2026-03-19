"""Open-access content fetcher with caching, retry, and daily limits.

Downloads full-text content (PDF, XML, HTML) for papers that have
open_access_url. Stores files in data/content/ keyed by paper ID.
"""

import logging
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# Content-Type to extension mapping
_CT_MAP = {
    "application/pdf": "pdf",
    "text/xml": "xml",
    "application/xml": "xml",
    "text/html": "html",
    "application/xhtml+xml": "html",
    "text/plain": "txt",
}

# Status codes that should not be retried
_NO_RETRY_CODES = {401, 403, 404, 451}


@dataclass
class FetchResult:
    paper_id: str
    status: str  # success / failed / skipped / skipped_no_url / skipped_limit
    content_type: str | None  # pdf / xml / html / text / unknown
    content_path: str | None  # relative path from data dir
    content_size: int  # bytes
    url: str | None
    fetched_at: str | None  # ISO 8601
    error: str | None

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "content_type": self.content_type,
            "content_path": self.content_path,
            "content_size": self.content_size,
            "url": self.url,
            "fetched_at": self.fetched_at,
            "error": self.error,
        }


def _ext_from_content_type(ct: str | None) -> str:
    """Map Content-Type header value to file extension."""
    if not ct:
        return "bin"
    # Strip parameters (e.g. "text/html; charset=utf-8")
    base = ct.split(";")[0].strip().lower()
    return _CT_MAP.get(base, "bin")


def _friendly_type(ext: str) -> str:
    """Map extension to content_type field value."""
    return {"pdf": "pdf", "xml": "xml", "html": "html", "txt": "text"}.get(ext, "unknown")


def _find_cached(content_dir: Path, paper_id: str) -> Path | None:
    """Check if any file for this paper_id already exists in content_dir."""
    for p in content_dir.iterdir():
        if p.stem == paper_id:
            return p
    return None


class ContentFetcher:
    """Downloads open-access content with caching and daily limits."""

    def __init__(
        self,
        content_dir: str | Path,
        timeout: float = 60.0,
        max_retries: int = 2,
        daily_limit: int = 200,
    ):
        self.content_dir = Path(content_dir)
        self.content_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.max_retries = max_retries
        self.daily_limit = daily_limit
        self._today_count = self._load_daily_count()

    # -- daily limit tracking --

    def _count_file(self) -> Path:
        return self.content_dir / f".fetch_count_{date.today().isoformat()}.txt"

    def _load_daily_count(self) -> int:
        cf = self._count_file()
        if cf.exists():
            try:
                return int(cf.read_text().strip())
            except ValueError:
                return 0
        return 0

    def _bump_daily_count(self) -> None:
        self._today_count += 1
        self._count_file().write_text(str(self._today_count))

    def at_daily_limit(self) -> bool:
        return self._today_count >= self.daily_limit

    # -- main fetch --

    def fetch(self, paper_id: str, url: str) -> FetchResult:
        """Download content for a single paper. Returns FetchResult."""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()

        # Check daily limit
        if self.at_daily_limit():
            return FetchResult(
                paper_id=paper_id, status="skipped_limit",
                content_type=None, content_path=None, content_size=0,
                url=url, fetched_at=now, error=None,
            )

        # Check cache
        cached = _find_cached(self.content_dir, paper_id)
        if cached is not None:
            ext = cached.suffix.lstrip(".")
            return FetchResult(
                paper_id=paper_id, status="success",
                content_type=_friendly_type(ext),
                content_path=f"content/{cached.name}",
                content_size=cached.stat().st_size,
                url=url, fetched_at=now, error=None,
            )

        # Download with retry
        last_error: str | None = None
        for attempt in range(self.max_retries + 1):
            try:
                ext, data = self._download(url, attempt)
                # Save
                out_path = self.content_dir / f"{paper_id}.{ext}"
                out_path.write_bytes(data)
                self._bump_daily_count()
                logger.info("Saved %s (%d bytes)", out_path.name, len(data))
                return FetchResult(
                    paper_id=paper_id, status="success",
                    content_type=_friendly_type(ext),
                    content_path=f"content/{out_path.name}",
                    content_size=len(data),
                    url=url, fetched_at=now, error=None,
                )
            except _NoRetry as e:
                return FetchResult(
                    paper_id=paper_id, status="failed",
                    content_type=None, content_path=None, content_size=0,
                    url=url, fetched_at=now, error=str(e),
                )
            except _Retryable as e:
                last_error = str(e)
                if attempt < self.max_retries:
                    wait = e.wait or (2 ** attempt)
                    logger.warning("Retry %d/%d for %s: %s (wait %ds)",
                                   attempt + 1, self.max_retries, paper_id, e, wait)
                    time.sleep(wait)

        return FetchResult(
            paper_id=paper_id, status="failed",
            content_type=None, content_path=None, content_size=0,
            url=url, fetched_at=now, error=f"Failed after {self.max_retries + 1} attempts: {last_error}",
        )

    def _download(self, url: str, attempt: int) -> tuple[str, bytes]:
        """Single download attempt. Returns (extension, bytes).

        Raises _NoRetry or _Retryable on failure.
        """
        try:
            # Try HEAD first to detect content type
            ext = self._probe_content_type(url)

            resp = httpx.get(url, timeout=self.timeout, follow_redirects=True,
                             headers={"User-Agent": "btgraph/0.1 (research tool)"})

            if resp.status_code in _NO_RETRY_CODES:
                raise _NoRetry(f"HTTP {resp.status_code}")

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", "10"))
                raise _Retryable(f"HTTP 429", wait=retry_after)

            if resp.status_code >= 500:
                raise _Retryable(f"HTTP {resp.status_code}", wait=2 ** attempt)

            resp.raise_for_status()

            # If HEAD didn't give us a type, infer from GET response
            if ext == "bin":
                ext = _ext_from_content_type(resp.headers.get("content-type"))

            return ext, resp.content

        except httpx.TimeoutException as e:
            raise _Retryable(f"Timeout: {e}", wait=2 ** attempt)
        except httpx.TransportError as e:
            raise _Retryable(f"Network error: {e}", wait=2 ** attempt)

    def _probe_content_type(self, url: str) -> str:
        """HEAD request to detect content type. Returns extension or 'bin'."""
        try:
            resp = httpx.head(url, timeout=15.0, follow_redirects=True,
                              headers={"User-Agent": "btgraph/0.1 (research tool)"})
            if resp.status_code < 400:
                return _ext_from_content_type(resp.headers.get("content-type"))
        except httpx.HTTPError:
            pass
        return "bin"


# -- internal exception types for retry control --

class _NoRetry(Exception):
    """Error that should not be retried (403, 404, etc.)."""


class _Retryable(Exception):
    """Error that can be retried."""
    def __init__(self, message: str, wait: int | None = None):
        self.wait = wait
        super().__init__(message)


# -- utility stubs for future steps --

def detect_content_format(path: str) -> str:
    """Detect actual content format from file (pdf/xml/html/text)."""
    p = Path(path)
    ext = p.suffix.lstrip(".")
    return _friendly_type(ext)


def extract_text_from_content(path: str, content_type: str) -> str | None:
    """Placeholder: extract plain text from content file.

    Future: PDF parser, XML parser, HTML parser.
    """
    raise NotImplementedError("Text extraction not yet implemented")
