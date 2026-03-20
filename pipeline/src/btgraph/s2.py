"""Semantic Scholar API client with file-based caching and retry logic.

Sole data source for the baseline-trace-graph pipeline.
API docs: https://api.semanticscholar.org/api-docs/graph
"""

import logging
import time
from urllib.parse import urlencode

import httpx

from btgraph.cache import FileCache

logger = logging.getLogger(__name__)

S2_BASE = "https://api.semanticscholar.org/graph/v1"

# Default fields for paper lookups
PAPER_FIELDS = [
    "paperId", "externalIds", "title", "year", "authors",
    "citationCount", "venue", "publicationTypes", "abstract",
    "openAccessPdf", "fieldsOfStudy", "s2FieldsOfStudy",
    "referenceCount",
]

# Fields for citing papers (lighter — no abstract/references to save quota)
CITATION_FIELDS = [
    "paperId", "externalIds", "title", "year", "authors",
    "citationCount", "venue", "publicationTypes", "abstract",
    "openAccessPdf", "fieldsOfStudy", "s2FieldsOfStudy",
    "referenceCount",
]

# Fields for references (needed for referenced_works)
REFERENCE_FIELDS = ["paperId"]


class S2Error(Exception):
    """Unrecoverable Semantic Scholar API error."""

    def __init__(self, message: str, url: str, status_code: int | None = None):
        self.url = url
        self.status_code = status_code
        super().__init__(message)


class S2Client:
    def __init__(
        self,
        cache: FileCache,
        api_key: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.cache = cache
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries

    def _headers(self) -> dict[str, str]:
        """Build request headers."""
        h: dict[str, str] = {}
        if self.api_key:
            h["x-api-key"] = self.api_key
        return h

    def _get(self, url: str) -> dict | None:
        """GET with cache-first, retry, timeout.

        Returns parsed JSON body, or None for 404.
        Raises S2Error on unrecoverable failure.
        """
        cached = self.cache.get(url)
        if cached is not None:
            return cached

        last_error = None
        headers = self._headers()

        for attempt in range(self.max_retries):
            try:
                logger.debug("GET %s (attempt %d)", url, attempt + 1)
                resp = httpx.get(
                    url, timeout=self.timeout,
                    headers=headers, follow_redirects=True,
                )

                if resp.status_code == 404:
                    logger.info("404 Not Found: %s", url)
                    return None

                if resp.status_code == 400:
                    logger.warning("400 Bad Request: %s", url)
                    return None

                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", "5"))
                    logger.warning("Rate limited, sleeping %ds", retry_after)
                    time.sleep(retry_after)
                    continue

                if resp.status_code >= 500:
                    wait = 2 ** attempt
                    logger.warning(
                        "Server error %d, retrying in %ds",
                        resp.status_code, wait,
                    )
                    time.sleep(wait)
                    continue

                resp.raise_for_status()
                body = resp.json()
                self.cache.put(url, resp.status_code, body)
                return body

            except httpx.TransportError as e:
                wait = 2 ** attempt
                logger.warning("Network error: %s, retrying in %ds", e, wait)
                last_error = e
                time.sleep(wait)

        raise S2Error(
            f"Failed after {self.max_retries} retries: {last_error}",
            url=url,
        )

    def get_paper(
        self,
        paper_id: str,
        fields: list[str] | None = None,
    ) -> dict | None:
        """Fetch a single paper.

        paper_id can be: S2 hash, DOI:xxx, ArXiv:xxx, CorpusId:xxx, etc.
        """
        if fields is None:
            fields = PAPER_FIELDS
        params = {"fields": ",".join(fields)}
        url = f"{S2_BASE}/paper/{paper_id}?{urlencode(params)}"
        return self._get(url)

    def get_paper_with_references(
        self,
        paper_id: str,
    ) -> dict | None:
        """Fetch a paper with its full field set plus reference IDs."""
        fields = PAPER_FIELDS + [f"references.{f}" for f in REFERENCE_FIELDS]
        params = {"fields": ",".join(fields)}
        url = f"{S2_BASE}/paper/{paper_id}?{urlencode(params)}"
        return self._get(url)

    def get_citations(
        self,
        paper_id: str,
        fields: list[str] | None = None,
        max_results: int = 1000,
    ) -> tuple[list[dict], int]:
        """Fetch papers that cite the given paper, with offset pagination.

        Returns (list_of_citing_paper_dicts, total_fetched).
        S2 citations endpoint returns {data: [{citingPaper: {...}}, ...], next}.
        """
        if fields is None:
            fields = CITATION_FIELDS
        field_str = ",".join(fields)

        all_results: list[dict] = []
        offset = 0
        limit = min(max_results, 1000)  # S2 max per request is 1000

        while offset < max_results:
            batch_limit = min(limit, max_results - offset)
            params = {
                "fields": field_str,
                "offset": str(offset),
                "limit": str(batch_limit),
            }
            url = f"{S2_BASE}/paper/{paper_id}/citations?{urlencode(params)}"
            data = self._get(url)
            if data is None:
                break

            items = data.get("data", [])
            if not items:
                break

            for item in items:
                citing = item.get("citingPaper")
                if citing and citing.get("paperId"):
                    all_results.append(citing)

            next_offset = data.get("next")
            if next_offset is None:
                break
            offset = next_offset

            logger.debug(
                "Citations page: offset=%d, got %d, total so far %d",
                offset, len(items), len(all_results),
            )

        logger.info(
            "Citations for %s: fetched %d",
            paper_id, len(all_results),
        )
        return all_results, len(all_results)

    def search(
        self,
        query: str,
        fields: list[str] | None = None,
        limit: int = 5,
    ) -> list[dict]:
        """Search papers by query string."""
        if fields is None:
            fields = PAPER_FIELDS
        params = {
            "query": query,
            "fields": ",".join(fields),
            "limit": str(limit),
        }
        url = f"{S2_BASE}/paper/search?{urlencode(params)}"
        data = self._get(url)
        if data is None:
            return []
        return data.get("data", [])
