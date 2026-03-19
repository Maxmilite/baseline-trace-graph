"""OpenAlex API client with file-based caching and retry logic.

Sole data source for the baseline-trace-graph pipeline.
All requests go through the polite pool (mailto parameter).
"""

import logging
import time
from urllib.parse import urlencode

import httpx

from btgraph.cache import FileCache

logger = logging.getLogger(__name__)

OPENALEX_BASE = "https://api.openalex.org"
DEFAULT_MAILTO = "btgraph-user@example.com"


class OpenAlexError(Exception):
    """Unrecoverable OpenAlex API error."""

    def __init__(self, message: str, url: str, status_code: int | None = None):
        self.url = url
        self.status_code = status_code
        super().__init__(message)


class OpenAlexClient:
    def __init__(
        self,
        cache: FileCache,
        mailto: str = DEFAULT_MAILTO,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.cache = cache
        self.mailto = mailto
        self.timeout = timeout
        self.max_retries = max_retries

    def _build_url(self, path: str, params: dict | None = None) -> str:
        """Build full URL with mailto parameter."""
        url = f"{OPENALEX_BASE}{path}"
        all_params = {"mailto": self.mailto}
        if params:
            all_params.update(params)
        return f"{url}?{urlencode(all_params)}"

    def _get(self, url: str) -> dict | None:
        """GET with cache-first, retry, timeout.

        Returns parsed JSON body, or None for 404.
        Raises OpenAlexError on unrecoverable failure.
        """
        # Cache check
        cached = self.cache.get(url)
        if cached is not None:
            return cached

        # Retry loop
        last_error = None
        for attempt in range(self.max_retries):
            try:
                logger.debug("GET %s (attempt %d)", url, attempt + 1)
                resp = httpx.get(url, timeout=self.timeout, follow_redirects=True)

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
                    logger.warning("Server error %d, retrying in %ds", resp.status_code, wait)
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

        raise OpenAlexError(
            f"Failed after {self.max_retries} retries: {last_error}",
            url=url,
        )

    def get_work_by_doi(self, doi: str) -> dict | None:
        """Fetch a single work by DOI."""
        url = self._build_url(f"/works/https://doi.org/{doi}")
        return self._get(url)

    def get_work_by_openalex_id(self, openalex_id: str) -> dict | None:
        """Fetch a single work by OpenAlex ID (W-prefixed)."""
        url = self._build_url(f"/works/{openalex_id}")
        return self._get(url)

    def get_work_by_arxiv(self, arxiv_id: str) -> dict | None:
        """Fetch a work by arXiv ID.

        Strategy: arXiv papers have DOIs in the form 10.48550/arXiv.{id},
        so we resolve via DOI lookup first, then fall back to title search
        using the OpenAlex search endpoint.
        """
        # arXiv DOI format: 10.48550/arXiv.YYMM.NNNNN
        doi = f"10.48550/arXiv.{arxiv_id}"
        work = self.get_work_by_doi(doi)
        if work is not None:
            return work
        logger.info("arXiv DOI lookup failed, falling back to DOI without 'arXiv.' prefix")
        # Some older arXiv papers may not have the standard DOI
        doi_alt = f"10.48550/{arxiv_id}"
        return self.get_work_by_doi(doi_alt)

    def search_works(self, title: str, per_page: int = 5) -> list[dict]:
        """Search works by title. Returns list of work dicts."""
        url = self._build_url("/works", params={
            "filter": f"title.search:{title}",
            "per_page": str(per_page),
        })
        data = self._get(url)
        if data is None:
            return []
        return data.get("results", [])

    def get_citing_works(
        self,
        openalex_id: str,
        max_pages: int = 5,
        per_page: int = 200,
    ) -> tuple[list[dict], int]:
        """Fetch works that cite the given paper, with cursor pagination.

        Returns (list_of_work_dicts, total_count).
        """
        # Normalize to short ID
        short_id = openalex_id
        if "/" in short_id:
            short_id = short_id.rsplit("/", 1)[-1]

        all_results: list[dict] = []
        total_count = 0
        cursor = "*"

        for page in range(max_pages):
            params = {
                "filter": f"cites:{short_id}",
                "per_page": str(per_page),
                "cursor": cursor,
                "mailto": self.mailto,
            }
            url = f"{OPENALEX_BASE}/works?{urlencode(params)}"
            data = self._get(url)
            if data is None:
                break

            meta = data.get("meta", {})
            if page == 0:
                total_count = meta.get("count", 0)
                logger.info("Citing works for %s: %d total", short_id, total_count)

            results = data.get("results", [])
            if not results:
                break
            all_results.extend(results)

            next_cursor = meta.get("next_cursor")
            if not next_cursor:
                break
            cursor = next_cursor

            logger.debug("Page %d: got %d results, cursor=%s", page + 1, len(results), cursor)

        return all_results, total_count
