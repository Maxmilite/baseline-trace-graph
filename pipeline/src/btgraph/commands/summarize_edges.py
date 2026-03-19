"""summarize-edges: Generate human-readable summary for each edge."""

import argparse
import logging

logger = logging.getLogger(__name__)


def register(subparsers: argparse._SubParsersAction):
    p = subparsers.add_parser("summarize-edges", help="Summarize edge evidence into readable descriptions")
    p.add_argument("--input", "-i", default=None, help="Input path (default: <data-dir>/edge_evidence.json)")
    p.add_argument("--output", "-o", default=None, help="Output path (default: <data-dir>/edge_summaries.json)")
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    """Returns: 0=success, 1=error, 2=partial."""
    input_path = args.input or f"{args.data_dir}/edge_evidence.json"
    output = args.output or f"{args.data_dir}/edge_summaries.json"
    logger.info("summarize-edges: not yet implemented")
    logger.info("  input: %s", input_path)
    logger.info("  output: %s", output)
    return 0
