"""export-site: Format pruned graph for frontend consumption."""

import argparse
import logging

logger = logging.getLogger(__name__)


def register(subparsers: argparse._SubParsersAction):
    p = subparsers.add_parser("export-site", help="Export graph data for static site")
    p.add_argument("--input", "-i", default=None, help="Input path (default: <data-dir>/graph_pruned.json)")
    p.add_argument("--output", "-o", default=None, help="Output path (default: <data-dir>/site_graph.json)")
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    """Returns: 0=success, 1=error, 2=partial."""
    input_path = args.input or f"{args.data_dir}/graph_pruned.json"
    output = args.output or f"{args.data_dir}/site_graph.json"
    logger.info("export-site: not yet implemented")
    logger.info("  input: %s", input_path)
    logger.info("  output: %s", output)
    return 0
