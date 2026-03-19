"""prune-graph: Apply edge strength and node type filters to produce final graph."""

import argparse
import json
import logging
import os

from btgraph.pruning import prune_graph, DEFAULT_WEIGHTS

logger = logging.getLogger(__name__)


def register(subparsers: argparse._SubParsersAction):
    p = subparsers.add_parser("prune-graph", help="Prune graph by edge strength and node type")
    p.add_argument("--edges", default=None,
                   help="Edges path (default: <data-dir>/edges_raw.json)")
    p.add_argument("--nodes", default=None,
                   help="Nodes path (default: <data-dir>/nodes_raw.json)")
    p.add_argument("--types", default=None,
                   help="Paper types path (default: <data-dir>/paper_types.json)")
    p.add_argument("--evidence", default=None,
                   help="Edge evidence path (default: <data-dir>/edge_evidence.json)")
    p.add_argument("--summaries", default=None,
                   help="Edge summaries path (default: <data-dir>/edge_summaries.json)")
    p.add_argument("--seed", default=None,
                   help="Seed resolved path (default: <data-dir>/seed_resolved.json)")
    p.add_argument("--output", "-o", default=None,
                   help="Output path (default: <data-dir>/graph_pruned.json)")
    p.add_argument("--side-tables", default=None,
                   help="Side tables output path (default: <data-dir>/side_tables.json)")
    p.add_argument("--top-k", type=int, default=5,
                   help="Max default-visible children per parent (default: 5)")
    p.add_argument("--no-medium", action="store_true",
                   help="Exclude medium edges from output")
    p.add_argument("--weights", default=None,
                   help='JSON string for custom weights, e.g. \'{"strength":0.5,"relevance":0.2,"branch":0.1,"recency":0.2}\'')
    p.set_defaults(func=run)


def _load_json(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error("Cannot load %s: %s", path, e)
        return None


def run(args: argparse.Namespace) -> int:
    """Returns: 0=success, 1=error, 2=partial."""
    data_dir = args.data_dir
    edges_path = args.edges or f"{data_dir}/edges_raw.json"
    nodes_path = args.nodes or f"{data_dir}/nodes_raw.json"
    types_path = args.types or f"{data_dir}/paper_types.json"
    evidence_path = args.evidence or f"{data_dir}/edge_evidence.json"
    summaries_path = args.summaries or f"{data_dir}/edge_summaries.json"
    seed_path = args.seed or f"{data_dir}/seed_resolved.json"
    output_path = args.output or f"{data_dir}/graph_pruned.json"
    side_tables_path = args.side_tables or f"{data_dir}/side_tables.json"

    # 1. Load required inputs
    edges = _load_json(edges_path)
    if edges is None:
        return 1
    nodes = _load_json(nodes_path)
    if nodes is None:
        return 1
    paper_types = _load_json(types_path)
    if paper_types is None:
        return 1
    seed_data = _load_json(seed_path)
    if seed_data is None:
        return 1

    seed_id = seed_data.get("id", "")
    if not seed_id:
        logger.error("No seed ID found in %s", seed_path)
        return 1

    # 2. Load optional inputs
    edge_evidence = _load_json(evidence_path)
    if edge_evidence is None:
        logger.warning("No edge evidence found at %s. All edges will be filtered out.", evidence_path)
        logger.warning("Run 'btgraph extract-evidence' first to populate edge evidence.")
        edge_evidence = {}

    edge_summaries = _load_json(summaries_path)
    if edge_summaries is None:
        logger.warning("No edge summaries found at %s. Summaries will be null.", summaries_path)
        edge_summaries = {}

    logger.info("Loaded: %d nodes, %d edges, %d evidence, %d summaries, seed=%s",
                len(nodes), len(edges), len(edge_evidence), len(edge_summaries), seed_id)

    # 3. Parse weights
    weights = dict(DEFAULT_WEIGHTS)
    if args.weights:
        try:
            custom = json.loads(args.weights)
            weights.update(custom)
        except json.JSONDecodeError as e:
            logger.error("Invalid weights JSON: %s", e)
            return 1

    # 4. Prune
    graph_pruned, side_tables = prune_graph(
        nodes=nodes,
        edges=edges,
        paper_types=paper_types,
        edge_evidence=edge_evidence,
        edge_summaries=edge_summaries,
        seed_id=seed_id,
        top_k=args.top_k,
        weights=weights,
        include_medium=not args.no_medium,
    )

    # 5. Write outputs
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(graph_pruned, f, indent=2, ensure_ascii=False)
    logger.info("Wrote: %s", output_path)

    os.makedirs(os.path.dirname(side_tables_path) or ".", exist_ok=True)
    with open(side_tables_path, "w", encoding="utf-8") as f:
        json.dump(side_tables, f, indent=2, ensure_ascii=False)
    logger.info("Wrote: %s", side_tables_path)

    # 6. Summary
    meta = graph_pruned["metadata"]
    logger.info("Pruned graph: %d nodes, %d edges (strong=%d, medium=%d)",
                meta["node_count"], meta["edge_count"],
                meta["strong_edge_count"], meta["medium_edge_count"])

    visible = sum(1 for e in graph_pruned["edges"] if e.get("default_visible"))
    logger.info("Default visible edges: %d (top-%d per parent)", visible, args.top_k)

    st_meta = side_tables.get("metadata", {})
    for key, val in st_meta.items():
        if key.endswith("_count"):
            logger.info("Side table %s: %d", key.replace("_count", ""), val)

    if not edge_evidence:
        logger.warning("Graph is empty because no edge evidence was available.")
        return 2

    return 0
