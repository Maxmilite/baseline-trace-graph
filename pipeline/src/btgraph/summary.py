"""Edge summary generation: short, delta-focused summaries.

For each edge A→B, produces a 1–2 sentence summary explaining
what B changed relative to A and why it's worth comparing.

Rule-based template approach. No LLM calls.
"""

import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class EdgeSummary:
    source: str
    target: str
    relation_type: str       # direct_comparison / method_extension / weak_reference / unknown
    short_summary: str       # ≤2 sentences
    confidence: float        # 0.0–1.0
    evidence_pointers: list[str] = field(default_factory=list)  # e.g. ["table:experiments", "result_comparison:results"]

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "relation_type": self.relation_type,
            "short_summary": self.short_summary,
            "confidence": round(self.confidence, 2),
            "evidence_pointers": self.evidence_pointers,
        }


# ---------------------------------------------------------------------------
# Relation type inference
# ---------------------------------------------------------------------------

def _infer_relation_type(edge_level: str, evidence: list[dict]) -> str:
    """Map edge_level + evidence kinds to a relation_type."""
    kinds = {e.get("kind", "") for e in evidence}

    if edge_level == "strong":
        if kinds & {"table_mention", "result_comparison", "figure_caption"}:
            return "direct_comparison"
        return "direct_comparison"

    if edge_level == "medium":
        if "improvement_claim" in kinds:
            return "method_extension"
        if "method_discussion" in kinds:
            return "method_extension"
        return "method_extension"

    if edge_level == "weak":
        return "weak_reference"

    return "unknown"


# ---------------------------------------------------------------------------
# Template-based summary generation
# ---------------------------------------------------------------------------

# Patterns to extract delta clues from snippets
_OUTPERFORM_RE = re.compile(
    r"(outperform|surpass|exceed|improve[sd]?\s+(over|upon|on)|better\s+than|"
    r"achieve[sd]?\s+higher|gain\s+of\s+[\d.]+)", re.I
)
_EXTEND_RE = re.compile(
    r"(extend|build[sd]?\s+(on|upon)|modif(y|ies|ied)|adapt|"
    r"we\s+(extend|modify|adapt|build\s+on))", re.I
)
_REPLACE_RE = re.compile(
    r"(replac|substitut|instead\s+of|rather\s+than|eliminat)", re.I
)
_ADD_RE = re.compile(
    r"(add|introduc|incorporat|augment|equip|integrat)", re.I
)
_ADDRESS_RE = re.compile(
    r"(address|overcome|solve|mitigat|alleviat|limitation|drawback|shortcoming)", re.I
)


def _pick_best_snippet(evidence: list[dict]) -> dict | None:
    """Pick the most informative evidence snippet for summary generation.

    Priority: table_mention > result_comparison > improvement_claim > method_discussion > rest.
    """
    priority = {
        "table_mention": 0,
        "result_comparison": 1,
        "figure_caption": 2,
        "improvement_claim": 3,
        "method_discussion": 4,
        "related_work_only": 5,
        "generic_citation": 6,
    }
    if not evidence:
        return None
    ranked = sorted(evidence, key=lambda e: priority.get(e.get("kind", ""), 99))
    return ranked[0]


def _extract_delta_clue(snippet_text: str) -> str | None:
    """Try to extract a short delta phrase from a snippet."""
    # Look for "outperforms X by ..." or "improves over X ..."
    m = _OUTPERFORM_RE.search(snippet_text)
    if m:
        # Grab surrounding context (up to 80 chars after match)
        start = m.start()
        end = min(len(snippet_text), m.end() + 80)
        fragment = snippet_text[start:end].strip()
        # Trim to sentence boundary
        dot = fragment.find(".")
        if dot > 0:
            fragment = fragment[:dot + 1]
        return fragment

    return None


def _short_title(title: str, max_len: int = 50) -> str:
    """Shorten a paper title for use in summaries."""
    if len(title) <= max_len:
        return title
    # Cut at colon or dash
    for sep in [":", " - ", " — "]:
        if sep in title:
            short = title[:title.index(sep)].strip()
            if len(short) >= 15:
                return short
    return title[:max_len].rsplit(" ", 1)[0] + "..."


def _first_author(paper: dict) -> str:
    """Extract first author surname."""
    authors = paper.get("authors") or []
    if not authors:
        return "Unknown"
    name = authors[0].get("name", "Unknown")
    if "," in name:
        return name.split(",")[0].strip()
    parts = name.strip().split()
    return parts[-1] if parts else "Unknown"


def _author_year(paper: dict) -> str:
    """Format as 'Surname et al. (YYYY)' or 'Surname (YYYY)'."""
    surname = _first_author(paper)
    year = paper.get("year", "?")
    authors = paper.get("authors") or []
    if len(authors) > 1:
        return f"{surname} et al. ({year})"
    return f"{surname} ({year})"


# ---------------------------------------------------------------------------
# Core summary generation
# ---------------------------------------------------------------------------

def generate_summary(
    source_paper: dict,
    target_paper: dict,
    edge_evidence: dict,
) -> EdgeSummary:
    """Generate a short summary for edge source→target.

    Args:
        source_paper: dict with id, title, authors, year
        target_paper: dict with id, title, authors, year
        edge_evidence: dict from edge_evidence.json (edge_level, why, evidence[])
    """
    source_id = source_paper.get("id", "")
    target_id = target_paper.get("id", "")
    edge_level = edge_evidence.get("edge_level", "unknown")
    evidence = edge_evidence.get("evidence", [])
    why = edge_evidence.get("why", "")

    relation_type = _infer_relation_type(edge_level, evidence)

    # Build evidence pointers
    pointers = []
    for e in evidence:
        kind = e.get("kind", "")
        section = e.get("section", "")
        pointers.append(f"{kind}:{section}")

    target_ref = _author_year(target_paper)
    target_title_short = _short_title(target_paper.get("title", ""))

    # --- Generate summary based on relation type ---

    if relation_type == "direct_comparison":
        summary = _summary_direct_comparison(
            source_paper, target_paper, evidence, target_ref, target_title_short
        )
    elif relation_type == "method_extension":
        summary = _summary_method_extension(
            source_paper, target_paper, evidence, target_ref, target_title_short
        )
    elif relation_type == "weak_reference":
        summary = _summary_weak(source_paper, target_paper, target_ref)
    else:
        summary = _summary_unknown(source_paper, target_paper, target_ref)

    confidence = edge_evidence.get("confidence", 0.0)

    return EdgeSummary(
        source=source_id,
        target=target_id,
        relation_type=relation_type,
        short_summary=summary,
        confidence=confidence,
        evidence_pointers=pointers,
    )


def _summary_direct_comparison(
    source: dict, target: dict, evidence: list[dict],
    target_ref: str, target_title: str,
) -> str:
    """Summary for strong/direct_comparison edges."""
    best = _pick_best_snippet(evidence)
    snippet_text = best.get("snippet", "") if best else ""

    # Try to extract a concrete delta
    delta = _extract_delta_clue(snippet_text)

    # Detect what kind of change was made
    kinds = {e.get("kind", "") for e in evidence}
    sections = {e.get("section", "") for e in evidence}

    if delta:
        return f"{target_ref} directly compares against this work in experiments. {delta}"

    if "table_mention" in kinds:
        if _EXTEND_RE.search(snippet_text):
            return (f"{target_ref} extends this approach and includes it as a baseline "
                    f"in experimental tables.")
        return (f"{target_ref} uses this work as a baseline in experimental comparison tables.")

    if "result_comparison" in kinds:
        if _ADDRESS_RE.search(snippet_text):
            return (f"{target_ref} addresses limitations of this work and reports "
                    f"comparative results.")
        return f"{target_ref} reports direct performance comparison against this work."

    if "figure_caption" in kinds:
        return f"{target_ref} includes this work in result figures for visual comparison."

    return f"{target_ref} directly compares against this work in experiments."


def _summary_method_extension(
    source: dict, target: dict, evidence: list[dict],
    target_ref: str, target_title: str,
) -> str:
    """Summary for medium/method_extension edges."""
    best = _pick_best_snippet(evidence)
    snippet_text = best.get("snippet", "") if best else ""

    if _REPLACE_RE.search(snippet_text):
        return (f"{target_ref} replaces or modifies a component from this work. "
                f"No strong quantitative comparison found.")

    if _ADD_RE.search(snippet_text):
        return (f"{target_ref} builds on this work by adding new components. "
                f"No direct experimental comparison found.")

    if _ADDRESS_RE.search(snippet_text):
        return (f"{target_ref} claims to address limitations of this work. "
                f"No strong quantitative evidence found.")

    if _EXTEND_RE.search(snippet_text):
        return (f"{target_ref} explicitly extends this approach in its method. "
                f"Quantitative comparison not confirmed.")

    return (f"{target_ref} discusses this work as a methodological predecessor. "
            f"No direct experimental comparison found.")


def _summary_weak(source: dict, target: dict, target_ref: str) -> str:
    """Summary for weak edges."""
    return (f"{target_ref} cites this work but only in related work or passing reference. "
            f"Not a direct baseline comparison.")


def _summary_unknown(source: dict, target: dict, target_ref: str) -> str:
    """Summary for unknown edges."""
    return (f"Insufficient evidence to determine how {target_ref} uses this work. "
            f"Full text may be unavailable.")
