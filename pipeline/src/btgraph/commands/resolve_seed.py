"""resolve-seed: Resolve a DOI / arXiv ID / title to a canonical paper record."""

import argparse
import logging

logger = logging.getLogger(__name__)


def register(subparsers: argparse._SubParsersAction):
    p = subparsers.add_parser("resolve-seed", help="Resolve seed paper identifier")
    p.add_argument("query", help="DOI, arXiv ID, or paper title")
    p.add_argument("--output", "-o", default=None, help="Output path (default: <data-dir>/seed_resolved.json)")
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    """Returns: 0=success, 1=error, 2=partial."""
    output = args.output or f"{args.data_dir}/seed_resolved.json"
    logger.info("resolve-seed: not yet implemented")
    logger.info("  query: %s", args.query)
    logger.info("  output: %s", output)
    return 0
