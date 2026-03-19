"""Graph pruning and ranking engine.

Filters edges by strength, ranks children per parent using an
explainable weighted formula, and produces the pruned main graph
plus side tables for survey/dataset/benchmark papers.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DEFAULT_WEIGHTS = {
    "strength": 0.40,
    "relevance": 0.25,
    "branch": 0.15,
    "recency": 0.20,
}

# Edge levels that qualify for the pruned graph
_QUALIFYING_LEVELS = {"strong", "medium"}


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class RankFactor:
    name: str
    value: float
    weight: float
    contribution: float
    detail: str

    def to_dict(self) -> dict:
        return {
            "value": round(self.value, 3),
            "weight": round(self.weight, 2),
            "contribution": round(self.contribution, 4),
            "detail": self.detail,
        }


@dataclass
class RankedEdge:
    source: str
    target: str
    strength: str
    rank_score: float
    rank_breakdown: list[RankFactor]
    rank_among_siblings: int
    default_visible: bool
    summary: str | None
    evidence_count: int

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "strength": self.strength,
            "rank_score": round(self.rank_score, 4),
            "rank_breakdown": {f.name: f.to_dict() for f in self.rank_breakdown},
            "rank_among_siblings": self.rank_among_siblings,
            "default_visible": self.default_visible,
            "summary": self.summary,
            "evidence_count": self.evidence_count,
        }


# ---------------------------------------------------------------------------
# Scoring functions — each returns (value, detail_string)
# ---------------------------------------------------------------------------

def compute_strength_factor(edge_level: str, confidence: float) -> tuple[float, str]:
    """Map edge_level + confidence to [0, 1]."""
    if edge_level == "strong":
        if confidence >= 0.8:
            return 1.0, f"strong (confidence={confidence:.2f})"
        return 0.85, f"strong (confidence={confidence:.2f}, <0.8)"
    if edge_level == "medium":
        if confidence >= 0.6:
            return 0.6, f"medium (confidence={confidence:.2f})"
        return 0.45, f"medium (confidence={confidence:.2f}, <0.6)"
    if edge_level == "unknown":
        return 0.2, "unknown edge level"
    return 0.0, f"edge_level={edge_level}"


def compute_topic_relevance(child: dict, seed: dict) -> tuple[float, str]:
    """Topic overlap between child and seed using OpenAlex topic hierarchy."""
    child_topics = child.get("topics") or []
    seed_topics = seed.get("topics") or []

    if not seed_topics:
        return 0.0, "seed has no topics"

    # Extract IDs at each level
    seed_topic_ids = {t.get("id") for t in seed_topics if t.get("id")}
    seed_subfields = set()
    seed_fields = set()
    for t in seed_topics:
        sf = t.get("subfield", {})
        if isinstance(sf, dict) and sf.get("id"):
            seed_subfields.add(sf["id"])
        f = t.get("field", {})
        if isinstance(f, dict) and f.get("id"):
            seed_fields.add(f["id"])

    score = 0.0
    details = []

    topic_matches = 0
    subfield_matches = 0
    field_matches = 0

    for t in child_topics:
        tid = t.get("id")
        if tid and tid in seed_topic_ids:
            topic_matches += 1
            continue
        sf = t.get("subfield", {})
        if isinstance(sf, dict) and sf.get("id") and sf["id"] in seed_subfields:
            subfield_matches += 1
            continue
        f = t.get("field", {})
        if isinstance(f, dict) and f.get("id") and f["id"] in seed_fields:
            field_matches += 1

    score += topic_matches * 0.4
    score += subfield_matches * 0.2
    score += field_matches * 0.05

    if topic_matches:
        details.append(f"{topic_matches} topic match")
    if subfield_matches:
        details.append(f"{subfield_matches} subfield match")
    if field_matches:
        details.append(f"{field_matches} field match")

    # Bibliographic coupling bonus
    child_refs = set(child.get("referenced_works") or [])
    seed_refs = set(seed.get("referenced_works") or [])
    shared_refs = len(child_refs & seed_refs)
    if shared_refs >= 2:
        score += 0.15
        details.append(f"{shared_refs} shared refs")

    score = min(1.0, score)
    detail = "; ".join(details) if details else "no topic overlap"
    return score, detail


def compute_branch_potential(
    node_id: str,
    outgoing_strengths: dict[str, list[str]],
    node_map: dict,
) -> tuple[float, str]:
    """Score based on downstream edges from this node.

    outgoing_strengths: node_id -> list of edge_levels for outgoing edges.
    """
    levels = outgoing_strengths.get(node_id, [])
    n_strong = levels.count("strong")
    n_medium = levels.count("medium")

    if n_strong or n_medium:
        score = min(1.0, n_strong * 0.3 + n_medium * 0.1)
        return score, f"{n_strong} strong + {n_medium} medium downstream"

    # Fallback: cited_by_count proxy
    node = node_map.get(node_id, {})
    cbc = node.get("cited_by_count") or 0
    score = min(1.0, cbc / 1000) * 0.5
    return score, f"cited_by fallback: {cbc}"


def compute_recency(year: int | None, min_year: int, max_year: int) -> tuple[float, str]:
    """Linear normalization of publication year."""
    if year is None:
        return 0.0, "year unknown"
    if max_year <= min_year:
        return 0.5, f"year={year}, single-year range"
    score = (year - min_year) / (max_year - min_year)
    score = max(0.0, min(1.0, score))
    return score, f"year={year}, range={min_year}-{max_year}"


# ---------------------------------------------------------------------------
# Edge ranking
# ---------------------------------------------------------------------------

def rank_edge(
    source_id: str,
    target_id: str,
    edge_level: str,
    edge_confidence: float,
    edge_summary: str | None,
    evidence_count: int,
    seed_node: dict,
    node_map: dict,
    outgoing_strengths: dict[str, list[str]],
    year_range: tuple[int, int],
    weights: dict,
) -> RankedEdge:
    """Compute full ranked edge with breakdown."""
    child = node_map.get(target_id, {})
    min_year, max_year = year_range

    fs_val, fs_detail = compute_strength_factor(edge_level, edge_confidence)
    fr_val, fr_detail = compute_topic_relevance(child, seed_node)
    fb_val, fb_detail = compute_branch_potential(target_id, outgoing_strengths, node_map)
    fy_val, fy_detail = compute_recency(child.get("year"), min_year, max_year)

    w_s = weights.get("strength", 0.40)
    w_r = weights.get("relevance", 0.25)
    w_b = weights.get("branch", 0.15)
    w_y = weights.get("recency", 0.20)

    factors = [
        RankFactor("f_strength", fs_val, w_s, fs_val * w_s, fs_detail),
        RankFactor("f_relevance", fr_val, w_r, fr_val * w_r, fr_detail),
        RankFactor("f_branch", fb_val, w_b, fb_val * w_b, fb_detail),
        RankFactor("f_recency", fy_val, w_y, fy_val * w_y, fy_detail),
    ]
    rank_score = sum(f.contribution for f in factors)

    strength = "strong" if edge_level == "strong" else "medium"

    return RankedEdge(
        source=source_id,
        target=target_id,
        strength=strength,
        rank_score=rank_score,
        rank_breakdown=factors,
        rank_among_siblings=0,  # filled later
        default_visible=False,  # filled later
        summary=edge_summary,
        evidence_count=evidence_count,
    )


# ---------------------------------------------------------------------------
# Main pruning orchestrator
# ---------------------------------------------------------------------------

def prune_graph(
    nodes: list[dict],
    edges: list[dict],
    paper_types: dict,
    edge_evidence: dict,
    edge_summaries: dict,
    seed_id: str,
    top_k: int = 5,
    weights: dict | None = None,
    include_medium: bool = True,
) -> tuple[dict, dict]:
    """Prune and rank the graph.

    Returns (graph_pruned_dict, side_tables_dict).
    """
    weights = weights or dict(DEFAULT_WEIGHTS)
    node_map = {n["id"]: n for n in nodes if "id" in n}
    seed_node = node_map.get(seed_id, {})

    # --- 1. Determine year range ---
    years = [n.get("year") for n in nodes if n.get("year") is not None]
    min_year = min(years) if years else 2017
    max_year = max(years) if years else 2025
    year_range = (min_year, max_year)

    # --- 2. Build outgoing edge strength map (for branch_potential) ---
    outgoing_strengths: dict[str, list[str]] = defaultdict(list)
    for edge_key, ev in edge_evidence.items():
        src = ev.get("source", "")
        level = ev.get("edge_level", "unknown")
        if level in _QUALIFYING_LEVELS:
            outgoing_strengths[src].append(level)

    # --- 3. Filter and rank edges ---
    ranked_edges: list[RankedEdge] = []
    skipped_no_evidence = 0
    skipped_weak = 0
    skipped_type = 0

    for edge in edges:
        source_id = edge["source"]
        target_id = edge["target"]
        edge_key = f"{source_id}->{target_id}"

        # Get evidence
        ev = edge_evidence.get(edge_key)
        if ev is None:
            skipped_no_evidence += 1
            continue

        edge_level = ev.get("edge_level", "unknown")

        # Filter: only strong and medium
        if edge_level not in _QUALIFYING_LEVELS:
            skipped_weak += 1
            continue

        # Filter: medium only if include_medium
        if edge_level == "medium" and not include_medium:
            skipped_weak += 1
            continue

        # Filter: target must be main-graph eligible
        tinfo = paper_types.get(target_id, {})
        in_main = tinfo.get("show_in_main_graph", True)  # default unknown → main
        if not in_main:
            skipped_type += 1
            continue

        # Get summary
        summary_entry = edge_summaries.get(edge_key, {})
        summary_text = summary_entry.get("short_summary")
        evidence_count = len(ev.get("evidence", []))

        re = rank_edge(
            source_id=source_id,
            target_id=target_id,
            edge_level=edge_level,
            edge_confidence=ev.get("confidence", 0.0),
            edge_summary=summary_text,
            evidence_count=evidence_count,
            seed_node=seed_node,
            node_map=node_map,
            outgoing_strengths=outgoing_strengths,
            year_range=year_range,
            weights=weights,
        )
        ranked_edges.append(re)

    logger.info("Edges: %d qualifying, %d no evidence, %d weak/unknown, %d wrong type",
                len(ranked_edges), skipped_no_evidence, skipped_weak, skipped_type)

    # --- 4. Assign rank_among_siblings and default_visible ---
    by_parent: dict[str, list[RankedEdge]] = defaultdict(list)
    for re in ranked_edges:
        by_parent[re.source].append(re)

    for parent_id, children in by_parent.items():
        children.sort(key=lambda e: e.rank_score, reverse=True)
        for i, child_edge in enumerate(children):
            child_edge.rank_among_siblings = i + 1
            if child_edge.strength == "strong" and i < top_k:
                child_edge.default_visible = True
            # medium edges stay default_visible=False

    # --- 5. Collect reachable nodes ---
    reachable_ids = {seed_id}
    for re in ranked_edges:
        reachable_ids.add(re.source)
        reachable_ids.add(re.target)

    pruned_nodes = []
    for nid in reachable_ids:
        node = node_map.get(nid)
        if node is None:
            continue
        pruned_node = _make_pruned_node(node, nid == seed_id)
        pruned_nodes.append(pruned_node)

    # --- 6. Build side tables ---
    side_tables = _build_side_tables(nodes, paper_types, edges, edge_evidence, seed_id)

    # --- 7. Assemble output ---
    strong_count = sum(1 for e in ranked_edges if e.strength == "strong")
    medium_count = sum(1 for e in ranked_edges if e.strength == "medium")

    graph_pruned = {
        "nodes": pruned_nodes,
        "edges": [e.to_dict() for e in ranked_edges],
        "metadata": {
            "seed_id": seed_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "node_count": len(pruned_nodes),
            "edge_count": len(ranked_edges),
            "strong_edge_count": strong_count,
            "medium_edge_count": medium_count,
            "pruning_config": {
                "top_k": top_k,
                "weights": weights,
                "include_medium": include_medium,
            },
        },
    }

    return graph_pruned, side_tables


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pruned_node(node: dict, is_seed: bool) -> dict:
    """Extract minimal node fields for the pruned graph."""
    return {
        "id": node.get("id"),
        "title": node.get("title"),
        "authors": node.get("authors", []),
        "year": node.get("year"),
        "paper_type": node.get("paper_type", "unknown"),
        "venue": node.get("venue"),
        "doi": node.get("doi"),
        "arxiv_id": node.get("arxiv_id"),
        "cited_by_count": node.get("cited_by_count"),
        "is_seed": is_seed,
    }


def _build_side_tables(
    nodes: list[dict],
    paper_types: dict,
    edges: list[dict],
    edge_evidence: dict,
    seed_id: str,
) -> dict:
    """Build side tables for survey/dataset/benchmark papers."""
    # Group side-table papers
    tables: dict[str, list[dict]] = defaultdict(list)

    # Build edge lookup for side-table entries
    edge_lookup: dict[str, list[dict]] = defaultdict(list)
    for edge in edges:
        edge_lookup[edge["target"]].append(edge)

    for node in nodes:
        nid = node.get("id", "")
        tinfo = paper_types.get(nid, {})
        if not tinfo.get("show_in_side_table", False):
            continue

        kind = tinfo.get("side_table_kind", "other")

        # Find edges connecting this paper to main graph
        incoming = edge_lookup.get(nid, [])
        edge_refs = []
        for e in incoming:
            ek = f"{e['source']}->{e['target']}"
            ev = edge_evidence.get(ek, {})
            edge_refs.append({
                "source": e["source"],
                "target": e["target"],
                "strength": ev.get("edge_level", e.get("strength", "candidate")),
            })

        entry = {
            "id": nid,
            "title": node.get("title"),
            "authors": node.get("authors", []),
            "year": node.get("year"),
            "paper_type": tinfo.get("paper_type", "unknown"),
            "venue": node.get("venue"),
            "cited_by_count": node.get("cited_by_count"),
            "edges_to_main_graph": edge_refs,
        }
        tables[kind].append(entry)

    # Sort each table by cited_by_count descending
    for kind in tables:
        tables[kind].sort(key=lambda x: x.get("cited_by_count") or 0, reverse=True)

    return {
        "tables": dict(tables),
        "metadata": {
            "seed_id": seed_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            **{f"{k}_count": len(v) for k, v in tables.items()},
        },
    }
