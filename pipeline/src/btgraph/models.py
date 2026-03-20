"""Paper data model with Semantic Scholar mapping.

Provides Paper dataclass conforming to paper.schema.json,
plus extended fields needed by downstream pipeline stages.
"""

from dataclasses import dataclass, field


@dataclass
class Author:
    name: str
    s2_id: str | None = None

    def to_dict(self) -> dict:
        return {"name": self.name, "s2_id": self.s2_id}


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
    source: str = "s2"
    s2_id: str | None = None
    venue: str | None = None
    cited_by_count: int | None = None
    open_access_url: str | None = None
    referenced_works: list[str] = field(default_factory=list)
    topics: list[dict] = field(default_factory=list)
    publication_types: list[str] = field(default_factory=list)

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
            "s2_id": self.s2_id,
            "venue": self.venue,
            "cited_by_count": self.cited_by_count,
            "open_access_url": self.open_access_url,
            "referenced_works": self.referenced_works,
            "topics": self.topics,
            "publication_types": self.publication_types,
        }

    @classmethod
    def from_s2(cls, work: dict) -> "Paper":
        """Construct Paper from raw Semantic Scholar paper JSON."""
        paper_id = work.get("paperId", "")
        ext_ids = work.get("externalIds") or {}

        # Extract IDs
        doi = ext_ids.get("DOI")
        arxiv_id = ext_ids.get("ArXiv")

        # Authors
        authors = []
        for a in work.get("authors") or []:
            name = a.get("name", "Unknown")
            s2_id = a.get("authorId")
            authors.append(Author(name=name, s2_id=s2_id))

        # Open access URL
        oa_pdf = work.get("openAccessPdf") or {}
        oa_url = oa_pdf.get("url")

        # References → list of S2 paper IDs
        referenced_works = []
        for ref in work.get("references") or []:
            ref_id = ref.get("paperId")
            if ref_id:
                referenced_works.append(ref_id)

        # Topics from s2FieldsOfStudy
        topics = work.get("s2FieldsOfStudy") or []

        # Publication types
        pub_types = work.get("publicationTypes") or []

        return cls(
            id=paper_id,
            title=work.get("title") or "",
            doi=doi,
            arxiv_id=arxiv_id,
            authors=authors,
            year=work.get("year"),
            paper_type="unknown",
            abstract=work.get("abstract"),
            source="s2",
            s2_id=paper_id,
            venue=work.get("venue") or None,
            cited_by_count=work.get("citationCount"),
            open_access_url=oa_url,
            referenced_works=referenced_works,
            topics=topics,
            publication_types=pub_types,
        )
