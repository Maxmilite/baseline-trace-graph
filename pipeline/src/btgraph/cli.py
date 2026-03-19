"""Main CLI dispatcher for btgraph pipeline."""

import argparse
import logging
import sys

from btgraph.commands import (
    resolve_seed,
    expand_candidates,
    classify_papers,
    fetch_content,
    extract_evidence,
    summarize_edges,
    prune_graph,
    export_site,
)


def main():
    parser = argparse.ArgumentParser(
        prog="btgraph",
        description="Baseline-trace graph pipeline CLI",
    )
    parser.add_argument("--data-dir", default="data", help="Directory for pipeline outputs (default: data)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")

    subparsers = parser.add_subparsers(dest="command", required=True)

    resolve_seed.register(subparsers)
    expand_candidates.register(subparsers)
    classify_papers.register(subparsers)
    fetch_content.register(subparsers)
    extract_evidence.register(subparsers)
    summarize_edges.register(subparsers)
    prune_graph.register(subparsers)
    export_site.register(subparsers)

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
