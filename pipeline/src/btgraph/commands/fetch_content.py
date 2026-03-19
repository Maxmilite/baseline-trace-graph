"""fetch-content: Download open-access full text for eligible papers."""

import argparse
import json
import logging
import os
from collections import Counter

from btgraph.content import ContentFetcher

logger = logging.getLogger(__name__)


def register(subparsers: argparse._SubParsersAction):
    p = subparsers.add_parser("fetch-content", help="Fetch open-access full text")
    p.add_argument("--input", "-i", default=None,
                   help="Input path (default: <data-dir>/nodes_raw.json)")
    p.add_argument("--types", default=None,
                   help="Paper types path (default: <data-dir>/paper_types.json)")
    p.add_argument("--output", "-o", default=None,
                   help="Output path (default: <data-dir>/content_manifest.json)")
    p.add_argument("--content-dir", default=None,
                   help="Content cache directory (default: <data-dir>/content/)")
    p.add_argument("--daily-limit", type=int, default=200,
                   help="Max downloads per day (default: 200)")
    p.add_argument("--no-skip-hidden", action="store_true",
                   help="Also fetch hidden papers (default: skip)")
    p.set_defaults(func=run)


def _load_json(path: str) -> dict | list | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error("Cannot load %s: %s", path, e)
        return None


def run(args: argparse.Namespace) -> int:
    """Returns: 0=success, 1=error, 2=partial."""
    data_dir = args.data_dir
    input_path = args.input or f"{data_dir}/nodes_raw.json"
    types_path = args.types or f"{data_dir}/paper_types.json"
    output_path = args.output or f"{data_dir}/content_manifest.json"
    content_dir = args.content_dir or f"{data_dir}/content"
    skip_hidden = not args.no_skip_hidden

    # 1. Load nodes
    nodes = _load_json(input_path)
    if nodes is None:
        return 1
    logger.info("Loaded %d papers from %s", len(nodes), input_path)

    # 2. Load paper types
    paper_types = _load_json(types_path)
    if paper_types is None:
        return 1

    # 3. Build lookup: paper_id -> node dict
    node_map = {n["id"]: n for n in nodes if "id" in n}

    # 4. Load existing manifest for checkpoint/resume
    manifest: dict = {}
    if os.path.exists(output_path):
        existing = _load_json(output_path)
        if isinstance(existing, dict):
            manifest = existing
            logger.info("Resuming from existing manifest (%d entries)", len(manifest))

    # 5. Determine candidates
    candidates = []
    for paper_id, node in node_map.items():
        type_info = paper_types.get(paper_id, {})
        in_main = type_info.get("show_in_main_graph", False)
        in_side = type_info.get("show_in_side_table", False)

        if skip_hidden and not in_main and not in_side:
            # Record as skipped if not already in manifest
            if paper_id not in manifest:
                manifest[paper_id] = {
                    "status": "skipped",
                    "content_type": None,
                    "content_path": None,
                    "content_size": 0,
                    "url": node.get("open_access_url"),
                    "fetched_at": None,
                    "error": "hidden paper",
                }
            continue

        oa_url = node.get("open_access_url")
        if not oa_url:
            if paper_id not in manifest:
                manifest[paper_id] = {
                    "status": "skipped_no_url",
                    "content_type": None,
                    "content_path": None,
                    "content_size": 0,
                    "url": None,
                    "fetched_at": None,
                    "error": None,
                }
            continue

        # Skip already-successful entries (checkpoint/resume)
        prev = manifest.get(paper_id, {})
        if prev.get("status") == "success":
            continue

        candidates.append((paper_id, oa_url))

    logger.info("Candidates to fetch: %d (skipped %d already done)",
                len(candidates), len(node_map) - len(candidates))

    # 6. Fetch
    fetcher = ContentFetcher(
        content_dir=content_dir,
        daily_limit=args.daily_limit,
    )

    fetched = 0
    failed = 0
    skipped_limit = 0

    for i, (paper_id, url) in enumerate(candidates):
        if fetcher.at_daily_limit():
            # Mark remaining as skipped_limit
            for pid, u in candidates[i:]:
                if pid not in manifest or manifest[pid].get("status") != "success":
                    manifest[pid] = {
                        "status": "skipped_limit",
                        "content_type": None,
                        "content_path": None,
                        "content_size": 0,
                        "url": u,
                        "fetched_at": None,
                        "error": None,
                    }
                    skipped_limit += 1
            break

        result = fetcher.fetch(paper_id, url)
        manifest[paper_id] = result.to_dict()

        if result.status == "success":
            fetched += 1
        elif result.status == "skipped_limit":
            skipped_limit += 1
        else:
            failed += 1
            logger.warning("Failed %s: %s", paper_id, result.error)

        # Periodic save every 20 downloads
        if (i + 1) % 20 == 0:
            _save_manifest(manifest, output_path)
            logger.info("Progress: %d/%d (fetched=%d, failed=%d)",
                        i + 1, len(candidates), fetched, failed)

    # 7. Final save
    _save_manifest(manifest, output_path)

    # 8. Summary
    statuses = Counter(v["status"] for v in manifest.values())
    logger.info("Content manifest: %d papers", len(manifest))
    for s, c in statuses.most_common():
        logger.info("  %s: %d", s, c)
    if skipped_limit > 0:
        logger.info("Daily limit reached. Run again tomorrow to continue.")

    return 2 if failed > 0 else 0


def _save_manifest(manifest: dict, path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
