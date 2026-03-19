"""expand-candidates: BFS expansion of citing works from seed paper."""

import argparse
import json
import logging
import os
import tempfile
from collections import deque
from datetime import datetime, timezone

from btgraph.cache import FileCache
from btgraph.models import Paper
from btgraph.openalex import OpenAlexClient, OpenAlexError

logger = logging.getLogger(__name__)


def _fresh_stats() -> dict:
    return {
        "nodes_discovered": 0,
        "edges_discovered": 0,
        "nodes_expanded": 0,
        "nodes_failed": 0,
        "nodes_skipped_depth": 0,
        "pages_fetched": 0,
        "depth_reached": 0,
    }


def _save_checkpoint(path: str, seed_id: str, config: dict,
                     visited: set[str], frontier: deque,
                     nodes: dict, edges: list, stats: dict) -> None:
    """Atomically save BFS state to checkpoint file."""
    data = {
        "version": 1,
        "seed_id": seed_id,
        "config": config,
        "visited": list(visited),
        "frontier": list(frontier),
        "nodes": nodes,
        "edges": edges,
        "stats": stats,
    }
    dir_name = os.path.dirname(path) or "."
    with tempfile.NamedTemporaryFile(mode="w", dir=dir_name, suffix=".tmp",
                                     delete=False, encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
        tmp_path = f.name
    os.replace(tmp_path, path)
    logger.debug("Checkpoint saved: %d nodes, %d edges", len(nodes), len(edges))


def _load_checkpoint(path: str, seed_id: str, config: dict):
    """Load checkpoint if it exists and matches seed/config. Returns None if no valid checkpoint."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Corrupt checkpoint, starting fresh: %s", e)
        return None

    if data.get("seed_id") != seed_id:
        logger.warning("Checkpoint seed mismatch (%s vs %s), starting fresh",
                       data.get("seed_id"), seed_id)
        return None
    if data.get("config") != config:
        logger.warning("Checkpoint config mismatch, starting fresh")
        return None

    logger.info("Resuming from checkpoint: %d nodes, %d edges, %d frontier",
                len(data.get("nodes", {})), len(data.get("edges", [])),
                len(data.get("frontier", [])))
    return data


def register(subparsers: argparse._SubParsersAction):
    p = subparsers.add_parser("expand-candidates", help="Expand candidate papers from seed")
    p.add_argument("--input", "-i", default=None,
                   help="Input path (default: <data-dir>/seed_resolved.json)")
    p.add_argument("--output", "-o", default=None,
                   help="Output dir (default: <data-dir>/)")
    p.add_argument("--max-depth", type=int, default=3,
                   help="Max BFS depth from seed (default: 3)")
    p.add_argument("--max-nodes", type=int, default=500,
                   help="Max total nodes to collect (default: 500)")
    p.add_argument("--max-pages", type=int, default=5,
                   help="Max pagination pages per node (default: 5, ~1000 citers)")
    p.add_argument("--api-key", default=None,
                   help="OpenAlex API key (from https://openalex.org/settings/api)")
    p.add_argument("--resume", action="store_true", default=True,
                   help="Resume from checkpoint if available (default)")
    p.add_argument("--no-resume", dest="resume", action="store_false",
                   help="Start fresh, ignore checkpoint")
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    """Returns: 0=success, 1=error, 2=partial."""
    input_path = args.input or f"{args.data_dir}/seed_resolved.json"
    output_dir = args.output or args.data_dir
    cache_dir = os.path.join(args.data_dir, "cache", "openalex")
    checkpoint_path = os.path.join(output_dir, "expand_checkpoint.json")
    started_at = datetime.now(timezone.utc)

    # 1. Load seed
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            seed_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error("Cannot load seed: %s", e)
        return 1

    seed_id = seed_data["id"]
    logger.info("Seed: %s (%s)", seed_data.get("title", ""), seed_id)

    # 2. Build client
    cache = FileCache(cache_dir)
    api_key = getattr(args, "api_key", None)
    client = OpenAlexClient(cache=cache, api_key=api_key)

    # 3. Config for checkpoint matching
    config = {
        "max_depth": args.max_depth,
        "max_nodes": args.max_nodes,
        "max_pages": args.max_pages,
    }

    # 4. Initialize or resume
    checkpoint = None
    if args.resume:
        checkpoint = _load_checkpoint(checkpoint_path, seed_id, config)

    if checkpoint:
        visited = set(checkpoint["visited"])
        frontier = deque(tuple(x) for x in checkpoint["frontier"])
        nodes = checkpoint["nodes"]
        edges = checkpoint["edges"]
        stats = checkpoint["stats"]
    else:
        visited = {seed_id}
        frontier = deque([(seed_id, 0)])
        nodes = {seed_id: seed_data}
        edges = []
        stats = _fresh_stats()
        stats["nodes_discovered"] = 1

    # 5. BFS loop
    while frontier:
        current_id, current_depth = frontier.popleft()

        if current_depth >= args.max_depth:
            stats["nodes_skipped_depth"] += 1
            continue

        logger.info("Expanding %s (depth %d, %d/%d nodes)",
                    current_id, current_depth, len(nodes), args.max_nodes)

        try:
            works, total = client.get_citing_works(
                current_id, max_pages=args.max_pages
            )
        except OpenAlexError as e:
            logger.warning("Failed to expand %s: %s", current_id, e)
            stats["nodes_failed"] += 1
            _save_checkpoint(checkpoint_path, seed_id, config,
                           visited, frontier, nodes, edges, stats)
            continue

        stats["nodes_expanded"] += 1
        stats["depth_reached"] = max(stats["depth_reached"], current_depth + 1)

        for work in works:
            try:
                child = Paper.from_openalex(work)
            except Exception as e:
                logger.warning("Failed to parse work: %s", e)
                continue

            # Record edge (even if node already visited)
            edges.append({
                "source": current_id,
                "target": child.id,
                "strength": "candidate",
            })
            stats["edges_discovered"] += 1

            # Dedup on nodes
            if child.id in visited:
                continue

            visited.add(child.id)
            nodes[child.id] = child.to_dict()
            stats["nodes_discovered"] += 1

            # Only add to frontier if under node cap
            if len(nodes) < args.max_nodes:
                frontier.append((child.id, current_depth + 1))
            else:
                logger.debug("Node cap reached, not queuing %s", child.id)

        _save_checkpoint(checkpoint_path, seed_id, config,
                       visited, frontier, nodes, edges, stats)

    # 6. Dedup edges by (source, target)
    seen_edges = set()
    unique_edges = []
    for e in edges:
        key = (e["source"], e["target"])
        if key not in seen_edges:
            seen_edges.add(key)
            unique_edges.append(e)
    edges = unique_edges

    # 7. Write outputs
    os.makedirs(output_dir, exist_ok=True)

    # nodes_raw.json — seed first
    nodes_list = [nodes[seed_id]] + [v for k, v in nodes.items() if k != seed_id]
    nodes_path = os.path.join(output_dir, "nodes_raw.json")
    with open(nodes_path, "w", encoding="utf-8") as f:
        json.dump(nodes_list, f, indent=2, ensure_ascii=False)
    logger.info("Wrote %s (%d nodes)", nodes_path, len(nodes_list))

    # edges_raw.json
    edges_path = os.path.join(output_dir, "edges_raw.json")
    with open(edges_path, "w", encoding="utf-8") as f:
        json.dump(edges, f, indent=2, ensure_ascii=False)
    logger.info("Wrote %s (%d edges)", edges_path, len(edges))

    # 8. Update run manifest
    finished_at = datetime.now(timezone.utc)
    manifest_path = os.path.join(output_dir, "run_manifest.json")
    manifest = {}
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    manifest.setdefault("run_id", started_at.strftime("%Y%m%dT%H%M%SZ"))
    manifest.setdefault("seed", {
        "input_query": seed_data.get("title", seed_id),
        "resolved_id": seed_id,
    })
    manifest.setdefault("config", {"data_source": "openalex"})
    manifest.setdefault("stages", {})
    manifest.setdefault("created_at", started_at.isoformat())

    manifest["stages"]["expand-candidates"] = {
        "status": "success",
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "output_file": "nodes_raw.json",
        "error": None,
        "stats": stats,
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    logger.info("Wrote %s", manifest_path)

    # 9. Clean up checkpoint
    if os.path.exists(checkpoint_path):
        os.remove(checkpoint_path)

    # 10. Summary
    logger.info("Expansion complete: %d nodes, %d edges, depth %d, %d failed",
                len(nodes_list), len(edges), stats["depth_reached"],
                stats["nodes_failed"])
    return 0
