"""Edge evidence extraction: find how paper B uses paper A.

Given a candidate edge A→B, reads B's full text (HTML/XML/plain text),
finds mentions of A, classifies the section context, and assigns
edge strength (strong / medium / weak / unknown).

Design: rule-based, explainable, conservative. No LLM calls.
"""

import re
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class EvidenceSnippet:
    section: str          # e.g. "experiments", "related_work", "abstract"
    kind: str             # schema enum: table_mention, result_comparison, etc.
    snippet: str          # raw text excerpt (≤300 chars)
    confidence: float     # 0.0–1.0

    def to_dict(self) -> dict:
        return {
            "section": self.section,
            "kind": self.kind,
            "snippet": self.snippet,
            "confidence": round(self.confidence, 2),
        }


@dataclass
class EdgeEvidence:
    source: str
    target: str
    edge_level: str       # strong / medium / weak / unknown
    confidence: float
    why: str
    evidence: list[EvidenceSnippet] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "edge_level": self.edge_level,
            "confidence": round(self.confidence, 2),
            "why": self.why,
            "evidence": [e.to_dict() for e in self.evidence],
        }


# ---------------------------------------------------------------------------
# Text extraction (HTML / XML / plain text — no PDF yet)
# ---------------------------------------------------------------------------

def extract_text(path: str, content_type: str) -> str | None:
    """Extract plain text from a downloaded content file.

    Supports: html, xml, text. PDF is not supported yet (returns None).
    """
    p = Path(path)
    if not p.exists():
        return None

    if content_type == "pdf":
        # PDF text extraction requires external libs — skip for now
        return None

    try:
        raw = p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        logger.warning("Cannot read %s: %s", path, e)
        return None

    if content_type in ("html", "xml"):
        return _strip_tags(raw)
    return raw


_TAG_RE = re.compile(r"<[^>]+>")
_MULTI_SPACE = re.compile(r"[ \t]+")
_MULTI_NL = re.compile(r"\n{3,}")


def _strip_tags(html: str) -> str:
    """Minimal HTML/XML tag stripping. Good enough for section detection."""
    text = _TAG_RE.sub(" ", html)
    text = _MULTI_SPACE.sub(" ", text)
    text = _MULTI_NL.sub("\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Name variants for matching paper A in text of paper B
# ---------------------------------------------------------------------------

def build_name_variants(paper: dict) -> list[str]:
    """Build a list of string patterns to search for paper A in B's text.

    Includes: title (and short title), first-author-year, DOI fragment.
    Returns patterns sorted longest-first for greedy matching.
    """
    variants: list[str] = []
    title = (paper.get("title") or "").strip()
    if title:
        # Full title (lowered for matching)
        variants.append(title)
        # Title up to first colon/dash if long
        if len(title) > 60:
            for sep in [":", " - ", " — "]:
                if sep in title:
                    short = title[:title.index(sep)].strip()
                    if len(short) >= 15:
                        variants.append(short)
                    break

    # First-author et al. year patterns, e.g. "Vaswani et al., 2017"
    authors = paper.get("authors") or []
    year = paper.get("year")
    if authors and year:
        surname = _extract_surname(authors[0].get("name", ""))
        if surname:
            variants.append(f"{surname} et al., {year}")
            variants.append(f"{surname} et al. ({year})")
            variants.append(f"{surname} et al. {year}")
            variants.append(f"{surname} et al.")
            if len(authors) == 1:
                variants.append(f"{surname} ({year})")
                variants.append(f"{surname}, {year}")
            elif len(authors) == 2:
                s2 = _extract_surname(authors[1].get("name", ""))
                if s2:
                    variants.append(f"{surname} and {s2}, {year}")
                    variants.append(f"{surname} and {s2} ({year})")
                    variants.append(f"{surname} & {s2}")

    # Sort longest first so we match the most specific variant
    variants = [v for v in variants if v and len(v) >= 4]
    variants.sort(key=len, reverse=True)
    return variants


def _extract_surname(full_name: str) -> str:
    """Extract likely surname from 'First Last' or 'Last, First'."""
    if not full_name:
        return ""
    if "," in full_name:
        return full_name.split(",")[0].strip()
    parts = full_name.strip().split()
    return parts[-1] if parts else ""


# ---------------------------------------------------------------------------
# Section classification
# ---------------------------------------------------------------------------

# Section heading patterns → canonical section name
_SECTION_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(abstract)\b", re.I), "abstract"),
    (re.compile(r"\b(introduction|1\s+introduction)\b", re.I), "introduction"),
    (re.compile(r"\b(related\s+work|prior\s+work|background|literature\s+review|2\s+related)\b", re.I), "related_work"),
    (re.compile(r"\b(method|methodology|approach|proposed\s+method|our\s+method|model|framework|architecture)\b", re.I), "method"),
    (re.compile(r"\b(experiment|evaluation|empirical|setup|implementation\s+details)\b", re.I), "experiments"),
    (re.compile(r"\b(result|finding|performance|comparison|ablation|analysis)\b", re.I), "results"),
    (re.compile(r"\b(conclusion|summary|future\s+work|discussion)\b", re.I), "conclusion"),
    (re.compile(r"\b(appendix|supplementary|supplemental)\b", re.I), "appendix"),
    (re.compile(r"\b(table\s+\d|tab\.\s*\d)", re.I), "table"),
    (re.compile(r"\b(figure\s+\d|fig\.\s*\d)", re.I), "figure"),
]


def classify_section(text_window: str) -> str:
    """Guess which section a text window belongs to.

    Looks at the ~500 chars before the mention for section headings.
    Returns canonical section name or 'unknown'.
    """
    # Search backwards through patterns
    best_pos = -1
    best_section = "unknown"
    for pat, section in _SECTION_PATTERNS:
        m = pat.search(text_window)
        if m and m.start() > best_pos:
            best_pos = m.start()
            best_section = section
    return best_section


def _get_section_at_position(full_text: str, pos: int, window: int = 1500) -> str:
    """Determine section for a mention at `pos` by looking at preceding text."""
    start = max(0, pos - window)
    preceding = full_text[start:pos]
    return classify_section(preceding)


# ---------------------------------------------------------------------------
# Evidence kind classification (what type of mention is this?)
# ---------------------------------------------------------------------------

# Patterns that indicate strong evidence (experiments/results context)
_TABLE_MENTION = re.compile(
    r"(table\s+\d|tab\.\s*\d|tabular|baseline.*result|result.*baseline)", re.I
)
_RESULT_COMPARISON = re.compile(
    r"(outperform|surpass|exceed|improve\s+(over|upon|on)|better\s+than|"
    r"worse\s+than|comparable\s+to|competitive\s+with|"
    r"achieve.*higher|achieve.*lower|gain\s+of|"
    r"(\d+\.?\d*)\s*(%|percent|point)|"
    r"state.of.the.art|SOTA|"
    r"our\s+(method|model|approach|system)\s+(achieve|obtain|reach|get))", re.I
)
_FIGURE_CAPTION = re.compile(
    r"(figure\s+\d|fig\.\s*\d)", re.I
)

# Medium evidence patterns
_METHOD_DISCUSSION = re.compile(
    r"(build\s+(on|upon)|extend|modify|adapt|follow|inspired\s+by|"
    r"similar\s+to|based\s+on|borrow|leverage|adopt|"
    r"we\s+(modify|extend|adapt|build|follow)|"
    r"unlike|in\s+contrast\s+to|different\s+from|"
    r"our\s+approach\s+differs)", re.I
)
_IMPROVEMENT_CLAIM = re.compile(
    r"(improve|enhancement|advance|address\s+(the\s+)?limitation|"
    r"overcome|solve|mitigate|alleviate|"
    r"limitation\s+of|drawback\s+of|shortcoming|"
    r"we\s+propose.*to\s+(address|overcome|improve|solve))", re.I
)

# Weak evidence patterns
_RELATED_WORK_ONLY = re.compile(
    r"(has\s+been\s+(studied|explored|investigated|proposed)|"
    r"previous(ly)?\s+(studied|proposed|explored)|"
    r"a\s+line\s+of\s+(work|research)|"
    r"several\s+(works|methods|approaches)\s+have)", re.I
)


def classify_mention_kind(snippet: str, section: str) -> tuple[str, float]:
    """Classify what kind of evidence a mention represents.

    Returns (kind, confidence).
    """
    # Table mentions are strong regardless of section
    if _TABLE_MENTION.search(snippet):
        return "table_mention", 0.9

    # Result comparison language
    if _RESULT_COMPARISON.search(snippet):
        if section in ("experiments", "results", "table"):
            return "result_comparison", 0.9
        if section in ("abstract", "introduction"):
            return "result_comparison", 0.7
        return "result_comparison", 0.6

    # Figure caption
    if _FIGURE_CAPTION.search(snippet) and section in ("experiments", "results", "figure"):
        return "figure_caption", 0.7

    # Method discussion / improvement claim
    if section in ("method", "introduction"):
        if _IMPROVEMENT_CLAIM.search(snippet):
            return "improvement_claim", 0.7
        if _METHOD_DISCUSSION.search(snippet):
            return "method_discussion", 0.6

    # Improvement claim in any section
    if _IMPROVEMENT_CLAIM.search(snippet):
        return "improvement_claim", 0.5

    # Method discussion in any section
    if _METHOD_DISCUSSION.search(snippet):
        return "method_discussion", 0.4

    # Related work only
    if section == "related_work":
        return "related_work_only", 0.5

    # Generic citation
    return "generic_citation", 0.3


# ---------------------------------------------------------------------------
# Core: find all mentions of A in B's text, produce evidence snippets
# ---------------------------------------------------------------------------

def find_mentions(full_text: str, name_variants: list[str],
                  max_snippets: int = 10) -> list[tuple[int, str, str]]:
    """Find positions where any name variant appears in text.

    Returns list of (position, matched_variant, snippet_around_match).
    Deduplicates overlapping matches.
    """
    if not full_text or not name_variants:
        return []

    text_lower = full_text.lower()
    seen_positions: set[int] = set()
    mentions: list[tuple[int, str, str]] = []

    for variant in name_variants:
        vl = variant.lower()
        start = 0
        while True:
            idx = text_lower.find(vl, start)
            if idx == -1:
                break
            start = idx + 1

            # Deduplicate: skip if within 100 chars of an existing match
            if any(abs(idx - sp) < 100 for sp in seen_positions):
                continue
            seen_positions.add(idx)

            # Extract snippet: 150 chars before, the match, 150 chars after
            snip_start = max(0, idx - 150)
            snip_end = min(len(full_text), idx + len(variant) + 150)
            snippet = full_text[snip_start:snip_end].strip()
            # Clean up for readability
            snippet = re.sub(r"\s+", " ", snippet)
            if len(snippet) > 300:
                snippet = snippet[:300] + "..."

            mentions.append((idx, variant, snippet))

            if len(mentions) >= max_snippets:
                return mentions

    return mentions


# ---------------------------------------------------------------------------
# Edge grading: aggregate evidence snippets → edge level
# ---------------------------------------------------------------------------

def grade_edge(snippets: list[EvidenceSnippet]) -> tuple[str, float, str]:
    """Determine edge level from collected evidence snippets.

    Returns (edge_level, confidence, why).

    Rules:
    - strong: at least one table_mention or result_comparison in experiments/results
    - medium: method_discussion or improvement_claim, but no strong quantitative evidence
    - weak: only related_work_only or generic_citation
    - unknown: no evidence found
    """
    if not snippets:
        return "unknown", 0.0, "No evidence found in available text"

    kinds = {s.kind for s in snippets}
    sections = {s.section for s in snippets}
    best_confidence = max(s.confidence for s in snippets)

    # Strong: table mention or result comparison in experiment/result sections
    strong_kinds = {"table_mention", "result_comparison", "figure_caption"}
    strong_sections = {"experiments", "results", "table", "figure"}

    has_strong_kind = bool(kinds & strong_kinds)
    has_strong_section = bool(sections & strong_sections)

    if has_strong_kind and has_strong_section:
        reasons = []
        if "table_mention" in kinds:
            reasons.append("mentioned in experiment table")
        if "result_comparison" in kinds:
            reasons.append("direct result comparison")
        if "figure_caption" in kinds:
            reasons.append("appears in result figure")
        return "strong", min(best_confidence, 0.9), "; ".join(reasons)

    # Also strong if result_comparison appears in abstract/intro (claims comparison)
    if "result_comparison" in kinds:
        return "strong", min(best_confidence, 0.8), "result comparison language found (not in experiments section)"

    # Medium: method discussion or improvement claim
    medium_kinds = {"method_discussion", "improvement_claim"}
    if kinds & medium_kinds:
        reasons = []
        if "improvement_claim" in kinds:
            reasons.append("claims improvement over this work")
        if "method_discussion" in kinds:
            reasons.append("discussed in method/approach context")
        return "medium", min(best_confidence, 0.7), "; ".join(reasons)

    # Weak: only related work or generic citation
    if kinds <= {"related_work_only", "generic_citation"}:
        return "weak", min(best_confidence, 0.5), "only mentioned in related work or generic citation"

    # Fallback
    return "weak", 0.3, "evidence found but insufficient for medium/strong"


# ---------------------------------------------------------------------------
# Main entry point: extract evidence for one edge
# ---------------------------------------------------------------------------

def extract_edge_evidence(
    source_paper: dict,
    target_paper: dict,
    target_text: str | None,
) -> EdgeEvidence:
    """Extract evidence for edge source→target.

    Args:
        source_paper: dict with id, title, authors, year, etc. (paper A)
        target_paper: dict with id, title, etc. (paper B)
        target_text: full text of paper B (or None if unavailable)
    """
    source_id = source_paper.get("id", "")
    target_id = target_paper.get("id", "")

    # If no text available, check abstract as fallback
    if not target_text:
        abstract = target_paper.get("abstract") or ""
        if not abstract:
            return EdgeEvidence(
                source=source_id, target=target_id,
                edge_level="unknown", confidence=0.0,
                why="No full text or abstract available for target paper",
            )
        target_text = abstract

    # Build name variants for source paper
    variants = build_name_variants(source_paper)
    if not variants:
        return EdgeEvidence(
            source=source_id, target=target_id,
            edge_level="unknown", confidence=0.0,
            why="Cannot build name variants for source paper",
        )

    # Find mentions
    mentions = find_mentions(target_text, variants)
    if not mentions:
        # No textual mention found — could still be a real edge,
        # but we can't confirm from text alone
        return EdgeEvidence(
            source=source_id, target=target_id,
            edge_level="unknown", confidence=0.0,
            why=f"No mention of source paper found in target text (searched {len(variants)} variants)",
        )

    # Classify each mention
    snippets: list[EvidenceSnippet] = []
    for pos, variant, snippet_text in mentions:
        section = _get_section_at_position(target_text, pos)
        kind, conf = classify_mention_kind(snippet_text, section)
        snippets.append(EvidenceSnippet(
            section=section,
            kind=kind,
            snippet=snippet_text,
            confidence=conf,
        ))

    # Grade the edge
    edge_level, confidence, why = grade_edge(snippets)

    return EdgeEvidence(
        source=source_id, target=target_id,
        edge_level=edge_level, confidence=confidence,
        why=why, evidence=snippets,
    )
