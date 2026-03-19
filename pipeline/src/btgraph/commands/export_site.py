"""export-site: Copy pruned graph data to site/public/ for frontend consumption."""

import argparse
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

# Files to copy: (source relative to data_dir, dest filename)
_FILES = [
    ("graph_pruned.json", "graph_pruned.json"),
    ("side_tables.json", "side_tables.json"),
]


def register(subparsers: argparse._SubParsersAction):
    p = subparsers.add_parser("export-site", help="Export graph data for static site")
    p.add_argument(
        "--site-dir",
        default=None,
        help="Path to site/public/ directory (default: auto-detect)",
    )
    p.set_defaults(func=run)


def _find_site_public(data_dir: str) -> Path:
    """Walk up from data_dir to find site/public/."""
    current = Path(data_dir).resolve()
    for _ in range(5):
        candidate = current.parent / "site" / "public"
        if candidate.is_dir():
            return candidate
        current = current.parent
    # Fallback: assume data_dir is at project_root/data
    return Path(data_dir).resolve().parent / "site" / "public"


def run(args: argparse.Namespace) -> int:
    """Copy graph_pruned.json and side_tables.json to site/public/.

    Returns: 0=success, 1=error, 2=partial.
    """
    data_dir = Path(args.data_dir)

    if args.site_dir:
        site_public = Path(args.site_dir)
    else:
        site_public = _find_site_public(args.data_dir)

    site_public.mkdir(parents=True, exist_ok=True)

    copied = 0
    missing = []

    for src_name, dst_name in _FILES:
        src = data_dir / src_name
        dst = site_public / dst_name
        if not src.exists():
            logger.warning("Source file not found: %s", src)
            missing.append(src_name)
            continue
        shutil.copy2(src, dst)
        logger.info("Copied %s -> %s", src, dst)
        copied += 1

    logger.info("Exported %d/%d files to %s", copied, len(_FILES), site_public)

    if missing:
        logger.warning("Missing files: %s", ", ".join(missing))
        if copied == 0:
            return 1
        return 2

    return 0
