"""prune-graph: Apply edge strength and node type filters to produce final graph."""

import argparse
import logging

logger = logging.getLogger(__name__)


def register(subparsers: argparse._SubParsersAction):
    p = subparsers.add_parser("prune-graph", help="Prune graph by edge strength and node type")
    p.add_argument("--data-dir-override", default=None, help="Override data dir for inputs")
    p.add_argument("--output", "-o", default=None, help="Output path (default: <data-dir>/graph_pruned.json)")
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    """Returns: 0=success, 1=error, 2=partial."""
    data = args.data_dir_override or args.data_dir
    output = args.output or f"{args.data_dir}/graph_pruned.json"
    logger.info("prune-graph: not yet implemented")
    logger.info("  reading from: %s/", data)
    logger.info("  output: %s", output)
    return 0
