"""Input type detection for seed paper queries.

Priority: DOI > arXiv > OpenAlex ID > title.
"""

import re
from enum import Enum


class QueryType(Enum):
    DOI = "doi"
    ARXIV = "arxiv"
    OPENALEX = "openalex"
    TITLE = "title"


# DOI pattern: 10.NNNN/ (with optional https://doi.org/ prefix)
_DOI_PREFIX = re.compile(r"^(?:https?://doi\.org/)?(?:doi:)?(10\.\d{4,}/.+)$", re.IGNORECASE)

# arXiv pattern: YYMM.NNNNN (with optional prefix)
_ARXIV_PREFIX = re.compile(
    r"^(?:https?://arxiv\.org/abs/)?(?:arxiv:)?(\d{4}\.\d{4,}(?:v\d+)?)$", re.IGNORECASE
)

# OpenAlex pattern: W followed by digits (with optional URL prefix)
_OPENALEX_PREFIX = re.compile(
    r"^(?:https?://openalex\.org/)?(W\d+)$", re.IGNORECASE
)


def detect_query_type(query: str) -> tuple[QueryType, str]:
    """Detect the type of a seed paper query and normalize it.

    Returns (QueryType, normalized_value).
    """
    q = query.strip()

    m = _DOI_PREFIX.match(q)
    if m:
        return QueryType.DOI, m.group(1)

    m = _ARXIV_PREFIX.match(q)
    if m:
        return QueryType.ARXIV, m.group(1)

    m = _OPENALEX_PREFIX.match(q)
    if m:
        return QueryType.OPENALEX, m.group(1).upper()

    return QueryType.TITLE, q
