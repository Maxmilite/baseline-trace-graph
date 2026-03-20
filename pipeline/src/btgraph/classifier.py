"""Rule-based paper type classifier and visibility policy.

Classifies papers into types (technical, survey, dataset, benchmark, etc.)
using metadata signals from Semantic Scholar. Determines visibility in the graph.
"""

import re
from dataclasses import dataclass


@dataclass
class ClassificationResult:
    paper_type: str
    confidence: float
    reason: str
    show_in_main_graph: bool
    show_in_side_table: bool
    side_table_kind: str | None

    def to_dict(self) -> dict:
        return {
            "paper_type": self.paper_type,
            "confidence": self.confidence,
            "reason": self.reason,
            "show_in_main_graph": self.show_in_main_graph,
            "show_in_side_table": self.show_in_side_table,
            "side_table_kind": self.side_table_kind,
        }


VISIBILITY_POLICY: dict[str, dict] = {
    "technical":   {"main": True,  "side": False, "side_kind": None},
    "survey":      {"main": False, "side": True,  "side_kind": "survey"},
    "dataset":     {"main": False, "side": True,  "side_kind": "dataset"},
    "benchmark":   {"main": False, "side": True,  "side_kind": "benchmark"},
    "application": {"main": False, "side": False, "side_kind": None},
    "theory":      {"main": False, "side": False, "side_kind": None},
    "system":      {"main": False, "side": False, "side_kind": None},
    "unknown":     {"main": True,  "side": False, "side_kind": None},
}

# Word-boundary patterns for title matching
_SURVEY_TITLE = re.compile(
    r"\b(survey|surveys|review|overview|systematic review|meta-analysis|"
    r"literature review|state of the art|state-of-the-art review)\b", re.IGNORECASE
)
_BENCHMARK_TITLE = re.compile(
    r"\b(benchmark|benchmarking|leaderboard|evaluation suite|shared task)\b", re.IGNORECASE
)
_DATASET_TITLE = re.compile(
    r"\b(dataset|datasets|corpus|corpora|data collection|annotation|annotated)\b", re.IGNORECASE
)

# Abstract patterns (more specific to reduce false positives)
_SURVEY_ABSTRACT = re.compile(
    r"\b(we survey|this survey|we review|this review|comprehensive review|"
    r"comprehensive survey|systematic review|we provide a survey|"
    r"we present a survey|literature review)\b", re.IGNORECASE
)
_DATASET_ABSTRACT = re.compile(
    r"\b(we introduce a dataset|we release a dataset|we present a dataset|"
    r"we construct a dataset|new dataset|novel dataset|"
    r"we introduce a corpus|we release a corpus)\b", re.IGNORECASE
)
_BENCHMARK_ABSTRACT = re.compile(
    r"\b(we introduce a benchmark|we propose a benchmark|we present a benchmark|"
    r"new benchmark|novel benchmark|benchmark suite)\b", re.IGNORECASE
)

# S2 publicationTypes that map directly
_S2_TYPE_MAP: dict[str, str] = {
    "Review": "survey",
    "Dataset": "dataset",
}

# S2 publicationTypes considered technical
_TECHNICAL_S2_TYPES = {"JournalArticle", "Conference", "Book", "BookSection"}


def _apply_visibility(paper_type: str, confidence: float, reason: str) -> ClassificationResult:
    """Apply visibility policy to a classification."""
    policy = VISIBILITY_POLICY.get(paper_type, VISIBILITY_POLICY["unknown"])
    return ClassificationResult(
        paper_type=paper_type,
        confidence=confidence,
        reason=reason,
        show_in_main_graph=policy["main"],
        show_in_side_table=policy["side"],
        side_table_kind=policy["side_kind"],
    )


def classify_paper(paper: dict) -> ClassificationResult:
    """Classify a paper using rule-based heuristics on metadata.

    Rules are applied in priority order; first match wins.
    """
    title = (paper.get("title") or "").strip()
    abstract = (paper.get("abstract") or "").strip()
    venue = (paper.get("venue") or "").strip()
    pub_types = paper.get("publication_types") or []
    topics = paper.get("topics") or []

    # --- Rule 1: Title keywords (highest precision) ---
    if _SURVEY_TITLE.search(title):
        return _apply_visibility("survey", 0.9, f"Title keyword match: survey/review in '{title[:80]}'")
    if _BENCHMARK_TITLE.search(title):
        return _apply_visibility("benchmark", 0.9, f"Title keyword match: benchmark in '{title[:80]}'")
    if _DATASET_TITLE.search(title):
        return _apply_visibility("dataset", 0.9, f"Title keyword match: dataset/corpus in '{title[:80]}'")

    # --- Rule 2: S2 publicationTypes ---
    for pt in pub_types:
        if pt in _S2_TYPE_MAP:
            mapped = _S2_TYPE_MAP[pt]
            return _apply_visibility(mapped, 0.85, f"S2 publicationType: {pt}")

    # --- Rule 3: Venue keywords ---
    if venue:
        venue_lower = venue.lower()
        if "dataset" in venue_lower or "shared task" in venue_lower:
            return _apply_visibility("dataset", 0.7, f"Venue keyword: '{venue[:60]}'")
        if "benchmark" in venue_lower:
            return _apply_visibility("benchmark", 0.7, f"Venue keyword: '{venue[:60]}'")

    # --- Rule 4: Abstract keywords ---
    if abstract:
        abstract_start = abstract[:500]
        if _SURVEY_ABSTRACT.search(abstract_start):
            return _apply_visibility("survey", 0.7, "Abstract keyword: survey/review phrase")
        if _DATASET_ABSTRACT.search(abstract_start):
            return _apply_visibility("dataset", 0.6, "Abstract keyword: dataset introduction phrase")
        if _BENCHMARK_ABSTRACT.search(abstract_start):
            return _apply_visibility("benchmark", 0.6, "Abstract keyword: benchmark introduction phrase")

    # --- Rule 5: S2 field of study signals ---
    for topic in topics:
        category = (topic.get("category") or "").lower()
        source = topic.get("source", "")
        if source != "s2-fos-model":
            continue
        if "survey" in category or "review" in category:
            return _apply_visibility("survey", 0.5, f"S2 field signal: '{topic.get('category')}'")
        if "benchmark" in category:
            return _apply_visibility("benchmark", 0.5, f"S2 field signal: '{topic.get('category')}'")
        if "dataset" in category:
            return _apply_visibility("dataset", 0.5, f"S2 field signal: '{topic.get('category')}'")

    # --- Rule 6: Default ---
    if any(pt in _TECHNICAL_S2_TYPES for pt in pub_types):
        return _apply_visibility("technical", 0.4,
                                 f"Default: S2 types={pub_types}, no survey/dataset/benchmark signals")

    # If no publication types but has a title, likely technical
    if title:
        return _apply_visibility("technical", 0.3,
                                 "Default: has title but no S2 type info")

    return _apply_visibility("unknown", 0.0,
                             f"No classification signals (pub_types={pub_types or 'none'})")


def classify_paper_with_model(paper: dict, model_fn=None) -> ClassificationResult:
    """Classify using an LLM model function (placeholder for future use).

    Falls back to rule-based classification if model_fn is None.
    """
    if model_fn is None:
        return classify_paper(paper)
    raise NotImplementedError("Model-based classification not yet implemented")
