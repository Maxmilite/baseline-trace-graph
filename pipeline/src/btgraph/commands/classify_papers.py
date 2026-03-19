"""classify-papers: Classify paper types and apply visibility policy."""

import argparse
import json
import logging
import os
from collections import Counter

from btgraph.classifier import classify_paper

logger = logging.getLogger(__name__)


def register(subparsers: argparse._SubParsersAction):
    p = subparsers.add_parser("classify-papers", help="Classify paper types")
    p.add_argument("--input", "-i", default=None,
                   help="Input path (default: <data-dir>/nodes_raw.json)")
    p.add_argument("--output", "-o", default=None,
                   help="Output path (default: <data-dir>/paper_types.json)")
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    """Returns: 0=success, 1=error, 2=partial."""
    input_path = args.input or f"{args.data_dir}/nodes_raw.json"
    output = args.output or f"{args.data_dir}/paper_types.json"

    # 1. Load nodes
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            nodes = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error("Cannot load nodes: %s", e)
        return 1

    logger.info("Classifying %d papers", len(nodes))

    # 2. Classify each paper
    results = {}
    for paper in nodes:
        paper_id = paper.get("id", "")
        result = classify_paper(paper)
        results[paper_id] = result.to_dict()

    # 3. Write output
    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    logger.info("Wrote: %s", output)

    # 4. Summary
    type_counts = Counter(v["paper_type"] for v in results.values())
    main_count = sum(1 for v in results.values() if v["show_in_main_graph"])
    side_count = sum(1 for v in results.values() if v["show_in_side_table"])

    for ptype, count in type_counts.most_common():
        logger.info("  %s: %d", ptype, count)
    logger.info("Main graph: %d, Side tables: %d, Hidden: %d",
                main_count, side_count, len(results) - main_count - side_count)

    return 0
