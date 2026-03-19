"""resolve-seed: Resolve a DOI / arXiv ID / title to a canonical paper record."""

import argparse
import json
import logging
import os
import re

from btgraph.cache import FileCache
from btgraph.models import Paper
from btgraph.openalex import OpenAlexClient, OpenAlexError
from btgraph.query_detect import QueryType, detect_query_type

logger = logging.getLogger(__name__)


def _normalize_for_match(text: str) -> set[str]:
    """Lowercase, strip punctuation, split into word set."""
    text = re.sub(r"[^\w\s]", "", text.lower())
    return set(text.split())


def pick_best_title_match(query: str, candidates: list[dict]) -> dict | None:
    """Pick the best match from OpenAlex search results.

    Strategy:
    1. Exact match (after normalization) -> return immediately.
    2. First result with >80% word overlap -> return it.
    3. Otherwise -> None.
    """
    if not candidates:
        return None

    query_words = _normalize_for_match(query)
    if not query_words:
        return None

    for work in candidates:
        title = work.get("display_name") or work.get("title") or ""
        title_words = _normalize_for_match(title)
        if not title_words:
            continue

        # Exact match
        if query_words == title_words:
            logger.info("Exact title match: %s", title)
            return work

        # Word overlap
        overlap = len(query_words & title_words) / max(len(query_words), len(title_words))
        if overlap > 0.8:
            logger.info("Title match (%.0f%% overlap): %s", overlap * 100, title)
            return work

    logger.warning("No confident title match found among %d candidates", len(candidates))
    return None


def register(subparsers: argparse._SubParsersAction):
    p = subparsers.add_parser("resolve-seed", help="Resolve seed paper identifier")
    p.add_argument("query", help="DOI, arXiv ID, or paper title")
    p.add_argument("--output", "-o", default=None,
                   help="Output path (default: <data-dir>/seed_resolved.json)")
    p.add_argument("--api-key", default=None,
                   help="OpenAlex API key (from https://openalex.org/settings/api)")
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    """Returns: 0=success, 1=error, 2=partial."""
    output = args.output or f"{args.data_dir}/seed_resolved.json"
    cache_dir = os.path.join(args.data_dir, "cache", "openalex")

    # 1. Detect query type
    query_type, normalized = detect_query_type(args.query)
    logger.info("Query type: %s -> %r", query_type.value, normalized)

    # 2. Build client
    cache = FileCache(cache_dir)
    api_key = getattr(args, "api_key", None)
    client = OpenAlexClient(cache=cache, api_key=api_key)

    # 3. Resolve
    work = None
    try:
        if query_type == QueryType.DOI:
            work = client.get_work_by_doi(normalized)
        elif query_type == QueryType.ARXIV:
            work = client.get_work_by_arxiv(normalized)
        elif query_type == QueryType.OPENALEX:
            work = client.get_work_by_openalex_id(normalized)
        elif query_type == QueryType.TITLE:
            candidates = client.search_works(normalized, per_page=5)
            work = pick_best_title_match(normalized, candidates)
    except OpenAlexError as e:
        logger.error("OpenAlex API error: %s", e)
        return 1

    # 4. Handle failure
    if work is None:
        logger.error("Could not resolve: %s", args.query)
        return 1

    # 5. Convert to Paper
    paper = Paper.from_openalex(work)
    logger.info("Resolved: %s (%s, %d)", paper.title, paper.id, paper.year or 0)

    # 6. Write output
    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(paper.to_dict(), f, indent=2, ensure_ascii=False)
    logger.info("Wrote: %s", output)

    return 0
