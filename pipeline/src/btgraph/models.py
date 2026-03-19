"""Paper data model with OpenAlex mapping.

Provides Paper dataclass conforming to paper.schema.json,
plus extended fields needed by downstream pipeline stages.
"""

from dataclasses import dataclass, field


@dataclass
class Author:
    name: str
    openalex_id: str | None = None

    def to_dict(self) -> dict:
        return {"name": self.name, "openalex_id": self.openalex_id}


def reconstruct_abstract(inverted_index: dict | None) -> str | None:
    """Convert OpenAlex abstract_inverted_index to plain text.

    The inverted index maps word -> list[int] positions.
    Reconstruct by inverting: position -> word, then join.
    """
    if not inverted_index:
        return None
    position_word: dict[int, str] = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            position_word[pos] = word
    if not position_word:
        return None
    max_pos = max(position_word.keys())
    words = [position_word.get(i, "") for i in range(max_pos + 1)]
    return " ".join(words)


def _strip_prefix(value: str | None, prefix: str) -> str | None:
    """Strip a URL prefix from a value, returning None if value is None."""
    if value is None:
        return None
    if value.startswith(prefix):
        return value[len(prefix):]
    return value


def _extract_short_id(openalex_url: str) -> str:
    """Extract short ID (e.g. 'W2741809807') from full OpenAlex URL."""
    if "/" in openalex_url:
        return openalex_url.rsplit("/", 1)[-1]
    return openalex_url


@dataclass
class Paper:
    id: str
    title: str
    doi: str | None = None
    arxiv_id: str | None = None
    authors: list[Author] = field(default_factory=list)
    year: int | None = None
    paper_type: str = "unknown"
    abstract: str | None = None
    source: str = "openalex"
    openalex_id: str | None = None
    venue: str | None = None
    cited_by_count: int | None = None
    open_access_url: str | None = None
    referenced_works: list[str] = field(default_factory=list)
    cited_by_api_url: str | None = None
    topics: list[dict] = field(default_factory=list)
    openalex_type: str | None = None

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict."""
        return {
            "id": self.id,
            "title": self.title,
            "doi": self.doi,
            "arxiv_id": self.arxiv_id,
            "authors": [a.to_dict() for a in self.authors],
            "year": self.year,
            "paper_type": self.paper_type,
            "abstract": self.abstract,
            "source": self.source,
            "openalex_id": self.openalex_id,
            "venue": self.venue,
            "cited_by_count": self.cited_by_count,
            "open_access_url": self.open_access_url,
            "referenced_works": self.referenced_works,
            "cited_by_api_url": self.cited_by_api_url,
            "topics": self.topics,
            "openalex_type": self.openalex_type,
        }

    @classmethod
    def from_openalex(cls, work: dict) -> "Paper":
        """Construct Paper from raw OpenAlex work JSON."""
        oa_id = work.get("id", "")
        ids = work.get("ids", {})

        # Extract arXiv ID from ids dict
        arxiv_raw = ids.get("arxiv")
        arxiv_id = _strip_prefix(arxiv_raw, "https://arxiv.org/abs/")

        # Extract DOI
        doi_raw = work.get("doi") or ids.get("doi")
        doi = _strip_prefix(doi_raw, "https://doi.org/")

        # Authors
        authors = []
        for authorship in work.get("authorships", []):
            author_info = authorship.get("author", {})
            name = author_info.get("display_name", "Unknown")
            author_oa_id = author_info.get("id")
            if author_oa_id:
                author_oa_id = _extract_short_id(author_oa_id)
            authors.append(Author(name=name, openalex_id=author_oa_id))

        # Venue — safe navigation through nested dicts
        venue = None
        primary_loc = work.get("primary_location") or {}
        source_info = primary_loc.get("source") or {}
        venue = source_info.get("display_name")

        # Abstract
        abstract = reconstruct_abstract(work.get("abstract_inverted_index"))

        # Open access
        oa_info = work.get("open_access") or {}
        oa_url = oa_info.get("oa_url")

        # Construct cited_by_api_url (OpenAlex no longer returns this field)
        short_id = _extract_short_id(oa_id)
        cited_by_api_url = (
            work.get("cited_by_api_url")
            or f"https://api.openalex.org/works?filter=cites:{short_id}"
        )

        return cls(
            id=short_id,
            title=work.get("display_name") or work.get("title") or "",
            doi=doi,
            arxiv_id=arxiv_id,
            authors=authors,
            year=work.get("publication_year"),
            paper_type="unknown",
            abstract=abstract,
            source="openalex",
            openalex_id=oa_id,
            venue=venue,
            cited_by_count=work.get("cited_by_count"),
            open_access_url=oa_url,
            referenced_works=work.get("referenced_works", []),
            cited_by_api_url=cited_by_api_url,
            topics=work.get("topics", []),
            openalex_type=work.get("type"),
        )
