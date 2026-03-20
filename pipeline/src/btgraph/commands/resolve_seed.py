"""resolve-seed: Resolve a DOI / arXiv ID / title to a canonical paper record."""

import argparse
import json
import logging
import os
import re

from btgraph.cache import FileCache
from btgraph.models import Paper
from btgraph.s2 import S2Client, S2Error
from btgraph.query_detect import QueryType, detect_query_type

logger = logging.getLogger(__name__)


def _normalize_for_match(text: str) -> set[str]:
    """Lowercase, strip punctuation, split into word set."""
    text = re.sub(r"[^\w\s]", "", text.lower())
    return set(text.split())


def pick_best_title_match(query: str, candidates: list[dict]) -> dict | None:
    """Pick the best match from search results.

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
        title = work.get("title") or ""
        title_words = _normalize_for_match(title)
        if not title_words:
            continue

        if query_words == title_words:
            logger.info("Exact title match: %s", title)
            return work

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
    p.add_argument("--s2-api-key", default=None,
                   help="Semantic Scholar API key (optional, for higher rate limits)")
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    """Returns: 0=success, 1=error, 2=partial."""
    output = args.output or f"{args.data_dir}/seed_resolved.json"
    cache_dir = os.path.join(args.data_dir, "cache", "s2")

    # 1. Detect query type
    query_type, normalized = detect_query_type(args.query)
    logger.info("Query type: %s -> %r", query_type.value, normalized)

    # 2. Build client
    cache = FileCache(cache_dir)
    api_key = getattr(args, "s2_api_key", None)
    client = S2Client(cache=cache, api_key=api_key)

    # 3. Resolve
    work = None
    try:
        if query_type == QueryType.DOI:
            work = client.get_paper_with_references(f"DOI:{normalized}")
        elif query_type == QueryType.ARXIV:
            work = client.get_paper_with_references(f"ArXiv:{normalized}")
        elif query_type == QueryType.TITLE:
            candidates = client.search(normalized, limit=5)
            best = pick_best_title_match(normalized, candidates)
            if best:
                # Re-fetch with full fields + references
                work = client.get_paper_with_references(best["paperId"])
    except S2Error as e:
        logger.error("Semantic Scholar API error: %s", e)
        return 1

    # 4. Handle failure
    if work is None:
        logger.error("Could not resolve: %s", args.query)
        return 1

    # 5. Convert to Paper
    paper = Paper.from_s2(work)
    logger.info("Resolved: %s (%s, %d)", paper.title, paper.id, paper.year or 0)

    # 6. Write output
    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(paper.to_dict(), f, indent=2, ensure_ascii=False)
    logger.info("Wrote: %s", output)

    return 0
