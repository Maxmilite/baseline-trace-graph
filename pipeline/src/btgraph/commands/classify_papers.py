"""classify-papers: Classify paper types (technical, survey, dataset, etc.)."""

import argparse
import logging

logger = logging.getLogger(__name__)


def register(subparsers: argparse._SubParsersAction):
    p = subparsers.add_parser("classify-papers", help="Classify paper types")
    p.add_argument("--input", "-i", default=None, help="Input path (default: <data-dir>/nodes_raw.json)")
    p.add_argument("--output", "-o", default=None, help="Output path (default: <data-dir>/paper_types.json)")
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    """Returns: 0=success, 1=error, 2=partial."""
    input_path = args.input or f"{args.data_dir}/nodes_raw.json"
    output = args.output or f"{args.data_dir}/paper_types.json"
    logger.info("classify-papers: not yet implemented")
    logger.info("  input: %s", input_path)
    logger.info("  output: %s", output)
    return 0
