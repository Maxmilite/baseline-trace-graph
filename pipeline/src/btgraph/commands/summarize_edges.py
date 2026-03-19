"""summarize-edges: Generate human-readable summary for each edge."""

import argparse
import json
import logging
import os
from collections import Counter

from btgraph.summary import generate_summary

logger = logging.getLogger(__name__)


def register(subparsers: argparse._SubParsersAction):
    p = subparsers.add_parser("summarize-edges", help="Summarize edge evidence into readable descriptions")
    p.add_argument("--input", "-i", default=None,
                   help="Edge evidence path (default: <data-dir>/edge_evidence.json)")
    p.add_argument("--nodes", "-n", default=None,
                   help="Nodes path (default: <data-dir>/nodes_raw.json)")
    p.add_argument("--output", "-o", default=None,
                   help="Output path (default: <data-dir>/edge_summaries.json)")
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
    evidence_path = args.input or f"{data_dir}/edge_evidence.json"
    nodes_path = args.nodes or f"{data_dir}/nodes_raw.json"
    output_path = args.output or f"{data_dir}/edge_summaries.json"

    # 1. Load inputs
    edge_evidence = _load_json(evidence_path)
    if edge_evidence is None:
        return 1
    nodes = _load_json(nodes_path)
    if nodes is None:
        return 1

    # 2. Build node lookup
    node_map = {n["id"]: n for n in nodes if "id" in n}
    logger.info("Loaded %d edge evidence entries, %d nodes", len(edge_evidence), len(node_map))

    # 3. Generate summaries
    results: dict[str, dict] = {}
    skipped = 0

    for edge_key, ev in edge_evidence.items():
        source_id = ev.get("source", "")
        target_id = ev.get("target", "")

        source_paper = node_map.get(source_id)
        target_paper = node_map.get(target_id)
        if not source_paper or not target_paper:
            skipped += 1
            continue

        s = generate_summary(source_paper, target_paper, ev)
        results[edge_key] = s.to_dict()

    # 4. Write output
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    logger.info("Wrote: %s", output_path)

    # 5. Summary
    types = Counter(v["relation_type"] for v in results.values())
    logger.info("Edge summaries: %d generated, %d skipped", len(results), skipped)
    for t, c in types.most_common():
        logger.info("  %s: %d", t, c)

    return 0
