"""extract-evidence: Find evidence snippets that justify each edge."""

import argparse
import json
import logging
import os
from collections import Counter
from pathlib import Path

from btgraph.evidence import extract_edge_evidence, extract_text

logger = logging.getLogger(__name__)


def register(subparsers: argparse._SubParsersAction):
    p = subparsers.add_parser("extract-evidence", help="Extract edge evidence from paper content")
    p.add_argument("--input", "-i", default=None,
                   help="Content manifest path (default: <data-dir>/content_manifest.json)")
    p.add_argument("--edges", "-e", default=None,
                   help="Edges path (default: <data-dir>/edges_raw.json)")
    p.add_argument("--nodes", "-n", default=None,
                   help="Nodes path (default: <data-dir>/nodes_raw.json)")
    p.add_argument("--types", default=None,
                   help="Paper types path (default: <data-dir>/paper_types.json)")
    p.add_argument("--output", "-o", default=None,
                   help="Output path (default: <data-dir>/edge_evidence.json)")
    p.add_argument("--content-dir", default=None,
                   help="Content directory (default: <data-dir>/content/)")
    p.add_argument("--skip-hidden", action="store_true", default=True,
                   help="Skip edges where target is hidden (default: true)")
    p.set_defaults(func=run)


def _load_json(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error("Cannot load %s: %s", path, e)
        return None


def _load_text(paper_id: str, manifest: dict, data_dir: str, content_dir: str) -> str | None:
    """Load full text for a paper from content cache."""
    entry = manifest.get(paper_id, {})
    if entry.get("status") != "success":
        return None
    content_path = entry.get("content_path")
    if not content_path:
        return None
    content_type = entry.get("content_type", "unknown")

    # content_path is relative like "content/W123.html"
    full_path = str(Path(data_dir) / content_path)
    return extract_text(full_path, content_type)


def run(args: argparse.Namespace) -> int:
    """Returns: 0=success, 1=error, 2=partial."""
    data_dir = args.data_dir
    manifest_path = args.input or f"{data_dir}/content_manifest.json"
    edges_path = args.edges or f"{data_dir}/edges_raw.json"
    nodes_path = args.nodes or f"{data_dir}/nodes_raw.json"
    types_path = args.types or f"{data_dir}/paper_types.json"
    output_path = args.output or f"{data_dir}/edge_evidence.json"
    content_dir = args.content_dir or f"{data_dir}/content"

    # 1. Load inputs
    edges = _load_json(edges_path)
    if edges is None:
        return 1
    nodes = _load_json(nodes_path)
    if nodes is None:
        return 1

    manifest = _load_json(manifest_path)
    if manifest is None:
        # Content fetching may not have run — proceed with abstracts only
        logger.warning("No content manifest found, will use abstracts only")
        manifest = {}

    paper_types = _load_json(types_path)
    if paper_types is None:
        paper_types = {}

    # 2. Build node lookup
    node_map = {n["id"]: n for n in nodes if "id" in n}
    logger.info("Loaded %d edges, %d nodes, %d content entries",
                len(edges), len(node_map), len(manifest))

    # 3. Pre-load text cache (target paper_id → text)
    # Only load once per target paper, since many edges share the same target
    text_cache: dict[str, str | None] = {}

    def get_text(paper_id: str) -> str | None:
        if paper_id not in text_cache:
            text_cache[paper_id] = _load_text(paper_id, manifest, data_dir, content_dir)
        return text_cache[paper_id]

    # 4. Process edges
    results: dict[str, dict] = {}
    skipped = 0

    for i, edge in enumerate(edges):
        source_id = edge["source"]
        target_id = edge["target"]
        edge_key = f"{source_id}->{target_id}"

        # Skip if target is hidden
        if args.skip_hidden:
            tinfo = paper_types.get(target_id, {})
            if not tinfo.get("show_in_main_graph", True) and not tinfo.get("show_in_side_table", False):
                skipped += 1
                continue

        source_paper = node_map.get(source_id)
        target_paper = node_map.get(target_id)
        if not source_paper or not target_paper:
            skipped += 1
            continue

        # Get target text (full text or abstract fallback)
        target_text = get_text(target_id)

        # Extract evidence
        ev = extract_edge_evidence(source_paper, target_paper, target_text)
        results[edge_key] = ev.to_dict()

        if (i + 1) % 100 == 0:
            logger.info("Progress: %d/%d edges processed", i + 1, len(edges))

    # 5. Write output
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    logger.info("Wrote: %s", output_path)

    # 6. Summary
    levels = Counter(v["edge_level"] for v in results.values())
    logger.info("Edge evidence: %d edges processed, %d skipped", len(results), skipped)
    for level, count in levels.most_common():
        logger.info("  %s: %d", level, count)

    # Stats on text availability
    with_text = sum(1 for pid in text_cache if text_cache[pid] is not None)
    logger.info("Text available for %d/%d unique target papers", with_text, len(text_cache))

    has_evidence = sum(1 for v in results.values() if v["evidence"])
    logger.info("Edges with at least one evidence snippet: %d/%d", has_evidence, len(results))

    return 0
