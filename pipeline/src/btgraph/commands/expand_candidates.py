"""expand-candidates: Recursively find citing papers from seed."""

import argparse
import logging

logger = logging.getLogger(__name__)


def register(subparsers: argparse._SubParsersAction):
    p = subparsers.add_parser("expand-candidates", help="Expand candidate papers from seed")
    p.add_argument("--input", "-i", default=None, help="Input path (default: <data-dir>/seed_resolved.json)")
    p.add_argument("--output", "-o", default=None, help="Output dir (default: <data-dir>/)")
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    """Returns: 0=success, 1=error, 2=partial."""
    input_path = args.input or f"{args.data_dir}/seed_resolved.json"
    output_dir = args.output or args.data_dir
    logger.info("expand-candidates: not yet implemented")
    logger.info("  input: %s", input_path)
    logger.info("  output: %s/nodes_raw.json, %s/edges_raw.json", output_dir, output_dir)
    return 0
