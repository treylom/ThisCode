"""
cli.py — GraphRAG pipeline CLI entry point
Commands: build, update, sync, status, search, bootstrap
Python 3.12 compatible
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_PROJECT_DIR = Path(__file__).resolve().parents[3]
_DEFAULT_DB = str(_PROJECT_DIR / ".team-os/graphrag/index/vault_graph.db")
_DEFAULT_CONFIG = str(_PROJECT_DIR / ".team-os/graphrag/config.yaml")


# ---------------------------------------------------------------------------
# Default config loading
# ---------------------------------------------------------------------------

def _load_config(config_path: str = _DEFAULT_CONFIG) -> dict:
    try:
        import yaml
        p = Path(config_path)
        if p.exists():
            with p.open(encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    except Exception:
        pass
    return {}


def _get_db(config: dict, override: str | None = None) -> str:
    if override:
        return override
    db_path = config.get("database", {}).get("path", _DEFAULT_DB)
    db = Path(db_path).expanduser()
    if not db.is_absolute():
        db = _PROJECT_DIR / db
    return str(db)


def _get_vault(config: dict, override: str | None = None) -> str:
    if override:
        return override
    vault_config = config.get("vault", {})
    # Platform-specific vault path
    if sys.platform == "darwin":
        return (
            vault_config.get("mac_path")
            or vault_config.get("path")
            or "<vault>/AI_Second_Brain"
        )
    elif sys.platform.startswith("linux"):
        # WSL 또는 native Linux
        return (
            vault_config.get("wsl_path")
            or vault_config.get("path")
            or "<vault>"
        )
    else:
        return (
            vault_config.get("path")
            or "<vault>/AI_Second_Brain"
        )


# ---------------------------------------------------------------------------
# Subcommand: build
# ---------------------------------------------------------------------------

def cmd_build(args: argparse.Namespace, config: dict) -> int:
    """Full build: bootstrap → community detection → frontmatter sync (dry-run)."""
    from graphrag_core import get_connection, close_connection
    from bootstrap import bootstrap_from_vault, bootstrap_from_cortex
    from community_detector import build_networkx_graph, run_community_detection

    db = _get_db(config, args.db)
    vault = _get_vault(config, args.vault)

    conn = get_connection(db)

    # 1. Bootstrap
    print("[1/3] Bootstrapping graph index...")
    cortex_path = Path(db).parent / ".cortex.db"
    if cortex_path.exists():
        print(f"  Found cortex.db: {cortex_path}")
        try:
            stats = bootstrap_from_cortex(cortex_path, conn)
            print(f"  Cortex import: {stats}")
        except Exception as e:
            print(f"  Cortex import failed: {e}. Falling back to vault scan.", file=sys.stderr)
            stats = bootstrap_from_vault(vault, conn)
            print(f"  Vault scan: {stats}")
    else:
        stats = bootstrap_from_vault(vault, conn)
        print(f"  Vault scan: {stats}")

    # 2. Community detection (hierarchical C0~C3)
    print("[2/3] Detecting hierarchical communities (C0~C3)...")
    result = run_community_detection(conn, force=True)
    if result.get("skipped"):
        print(f"  Skipped: {result['reason']}")
    else:
        for level_label, count in result.get("communities_per_level", {}).items():
            print(f"    {level_label}: {count} communities")
        tda = result.get("tda", {})
        print(f"  TDA: β₀={tda.get('beta_0')}, β₁={tda.get('beta_1')}, "
              f"χ={tda.get('euler_chi')}, density={tda.get('density')}")

    # 3. Frontmatter sync (dry-run by default)
    print("[3/3] Frontmatter sync (dry-run)...")
    from frontmatter_sync import sync_graph_to_frontmatter
    sync_stats = sync_graph_to_frontmatter(conn, vault, dry_run=not args.apply)
    mode = "APPLIED" if args.apply else "DRY RUN"
    print(f"  [{mode}] {sync_stats}")

    close_connection(conn)
    print("Build complete.")
    return 0


# ---------------------------------------------------------------------------
# Subcommand: update
# ---------------------------------------------------------------------------

def cmd_update(args: argparse.Namespace, config: dict) -> int:
    """Incremental update: detect changes → re-extract → community recalc."""
    from graphrag_core import get_connection, close_connection
    from graphrag_core import create_fts5_tables, populate_fts5
    from incremental import detect_changes, incremental_update
    from community_detector import run_community_detection

    db = _get_db(config, args.db)
    vault = _get_vault(config, args.vault)

    conn = get_connection(db)
    changes = detect_changes(conn, vault)
    total = sum(len(v) for v in changes.values())

    print(f"Changes: added={len(changes['added'])}, "
          f"modified={len(changes['modified'])}, deleted={len(changes['deleted'])}")

    if total == 0:
        print("No changes detected. Up to date.")
        close_connection(conn)
        if args.rebuild_embeddings:
            from embedding_index import build_entity_index, build_index

            index_dir = str(Path(db).parent)
            build_index(vault_path=vault, db_path=db, output_dir=index_dir)
            if not args.skip_entity_embeddings:
                build_entity_index(db_path=db, output_dir=index_dir)
            print(f"Embeddings: rebuilt in {index_dir}")
        return 0

    stats = incremental_update(conn, vault, changes, use_llm=args.llm)
    print(f"Update: {stats}")

    # Recalculate communities if needed
    threshold = config.get("processing", {}).get("community_recalc_threshold", 0.05)
    total_entities = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
    result = run_community_detection(conn, changed_count=total, force=args.force_community)
    print(f"Communities: {result}")

    create_fts5_tables(conn)
    populate_fts5(conn)
    print("FTS5: synced")

    close_connection(conn)

    if args.rebuild_embeddings:
        from embedding_index import build_entity_index, build_index

        index_dir = str(Path(db).parent)
        build_index(vault_path=vault, db_path=db, output_dir=index_dir)
        if not args.skip_entity_embeddings:
            build_entity_index(db_path=db, output_dir=index_dir)
        print(f"Embeddings: rebuilt in {index_dir}")

    return 0


# ---------------------------------------------------------------------------
# Subcommand: sync
# ---------------------------------------------------------------------------

def cmd_sync(args: argparse.Namespace, config: dict) -> int:
    """Sync frontmatter ↔ DB."""
    from graphrag_core import get_connection, close_connection
    from frontmatter_sync import sync_graph_to_frontmatter, sync_frontmatter_to_graph

    db = _get_db(config, args.db)
    vault = _get_vault(config, args.vault)
    conn = get_connection(db)

    if args.direction in ("to-frontmatter", "both"):
        dry_run = not args.apply
        result = sync_graph_to_frontmatter(conn, vault, dry_run=dry_run)
        mode = "APPLIED" if args.apply else "DRY RUN"
        print(f"[DB→Frontmatter {mode}] updated={result['updated']}, "
              f"skipped={result['skipped']}, errors={result['errors']}")

    if args.direction in ("to-db", "both"):
        result = sync_frontmatter_to_graph(conn, vault)
        print(f"[Frontmatter→DB] processed={result['processed']}, errors={result['errors']}")

    close_connection(conn)
    return 0


# ---------------------------------------------------------------------------
# Subcommand: status
# ---------------------------------------------------------------------------

def cmd_status(args: argparse.Namespace, config: dict) -> int:
    """Print DB statistics, TBox info, and TDA metrics."""
    from graphrag_core import get_connection, close_connection, get_db_stats, load_tbox
    from community_detector import build_networkx_graph, compute_betti_numbers

    db = _get_db(config, args.db)
    conn = get_connection(db)
    stats = get_db_stats(conn)

    print(f"GraphRAG DB: {db}")
    print("-" * 40)
    for table, count in stats.items():
        print(f"  {table:30s} {count:>8,} rows")

    # TBox summary
    tbox = load_tbox(conn)
    print(f"\nTBox v{tbox['version']}:")
    print(f"  classes: {[c['name'] for c in tbox['classes']]}")
    print(f"  relation_types: {[r['name'] for r in tbox['relation_types']]}")
    print(f"  axioms: {[a['id'] for a in tbox['axioms']]}")

    # TDA metrics if requested
    if getattr(args, "tda", False):
        G = build_networkx_graph(conn)
        tda = compute_betti_numbers(G)
        print(f"\nTDA Metrics:")
        for k, v in tda.items():
            print(f"  {k:20s}: {v}")

    close_connection(conn)
    return 0


# ---------------------------------------------------------------------------
# Subcommand: search
# ---------------------------------------------------------------------------

def cmd_search(args: argparse.Namespace, config: dict) -> int:
    """Run a graph search query (Global/Local routing + 4 explicit modes)."""
    from graphrag_core import get_connection, close_connection
    from community_detector import build_networkx_graph
    from graph_search import (
        search, global_search, insight_forge, panorama_search,
        quick_search, interview, classify_query_complexity,
    )

    db = _get_db(config, args.db)
    conn = get_connection(db)
    G = build_networkx_graph(conn)

    mode = args.search_mode
    query = args.query

    global_level = getattr(args, "global_level",
                   config.get("search", {}).get("global", {}).get("default_community_level", 1))

    if mode == "auto":
        result = search(conn, G, query, global_community_level=global_level)
    elif mode == "global":
        result = global_search(conn, G, query, community_level=global_level)
    elif mode == "insight":
        result = insight_forge(conn, G, query)
    elif mode == "panorama":
        result = panorama_search(conn, G, query)
    elif mode == "quick":
        hops = getattr(args, "hops", 1)
        result = quick_search(conn, G, query, hops=hops)
    elif mode == "interview":
        result = interview(conn, G, query)
    elif mode == "classify":
        level = classify_query_complexity(query)
        print(f"Query level: {level.name}")
        close_connection(conn)
        return 0
    else:
        print(f"Unknown search mode: {mode}", file=sys.stderr)
        close_connection(conn)
        return 1

    close_connection(conn)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        _pretty_print_search(result)

    return 0


def _pretty_print_search(result: dict) -> None:
    mode = result.get("mode", "unknown")
    print(f"\n=== Search Mode: {mode.upper()} ===")

    if not result.get("found", True):
        print(f"Entity not found: {result.get('entity')}")
        return

    if mode == "insight_forge":
        print(f"Query: {result['query']}")
        print(f"Communities: {len(result.get('communities', []))}")
        print(f"Entities in scope: {result.get('entity_count', 0)}")
        print(f"\nSynthesis:\n{result.get('synthesis', 'N/A')}")

    elif mode == "panorama":
        print(f"Query: {result['query']}")
        print(f"Total communities: {result.get('total_communities', 0)}")
        relevant = result.get("relevant_communities", [])
        print(f"Relevant communities ({len(relevant)}):")
        for c in relevant[:5]:
            print(f"  [{c['level']}] {c['name']} (score={c['score']}, members={c['member_count']})")
            if c.get("summary"):
                print(f"       {c['summary'][:80]}...")

    elif mode == "quick_search":
        e = result.get("entity", {})
        print(f"Entity: {e.get('name')} ({e.get('type')})")
        if result.get("community"):
            print(f"Community: {result['community']['name']}")
        neighbors = result.get("neighbors", [])
        print(f"Neighbors ({len(neighbors)}): {', '.join(n['name'] for n in neighbors[:10])}")

    elif mode == "interview":
        e = result.get("entity", {})
        print(f"Entity: {e.get('name')} ({e.get('type')})")
        print(f"Relationships: {result.get('relationship_count', 0)}")
        print(f"\nPatterns:")
        for p in result.get("patterns", []):
            print(f"  • {p}")
        print(f"\nNarrative:\n{result.get('narrative', 'N/A')}")


# ---------------------------------------------------------------------------
# Subcommand: bootstrap
# ---------------------------------------------------------------------------

def cmd_bootstrap(args: argparse.Namespace, config: dict) -> int:
    """Bootstrap index from cortex.db or vault."""
    from bootstrap import main as bootstrap_main

    db = _get_db(config, args.db)
    vault = _get_vault(config, args.vault)

    if args.force:
        from graphrag_core import get_connection, close_connection
        conn = get_connection(db)
        conn.execute("DELETE FROM entities")
        conn.execute("DELETE FROM relationships")
        conn.execute("DELETE FROM note_graph_state")
        conn.commit()
        close_connection(conn)
        print("DB cleared for forced re-bootstrap.")

    bootstrap_main(vault_path=vault, db_path=db, cortex_db=args.cortex)
    return 0


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="graphrag",
        description="GraphRAG pipeline for Obsidian vault knowledge graph",
    )
    parser.add_argument("--config", default=".team-os/graphrag/config.yaml",
                        help="Path to config.yaml")
    parser.add_argument("--db", default=None, help="Override DB path from config")
    parser.add_argument("--vault", default=None, help="Override vault path from config")

    sub = parser.add_subparsers(dest="command", required=True)

    # build
    p_build = sub.add_parser("build", help="Full build: bootstrap + communities + sync")
    p_build.add_argument("--apply", action="store_true", help="Apply frontmatter sync (default: dry-run)")

    # update
    p_update = sub.add_parser("update", help="Incremental update of changed notes")
    p_update.add_argument("--llm", action="store_true", help="Enable LLM extraction")
    p_update.add_argument("--force-community", action="store_true",
                          help="Force community recalculation")
    p_update.add_argument("--rebuild-embeddings", action="store_true",
                          help="Refresh dense note/entity embeddings after DB update")
    p_update.add_argument("--skip-entity-embeddings", action="store_true",
                          help="With --rebuild-embeddings, skip entity embedding refresh")

    # sync
    p_sync = sub.add_parser("sync", help="Sync frontmatter ↔ DB")
    p_sync.add_argument("--direction",
                        choices=["to-frontmatter", "to-db", "both"],
                        default="to-frontmatter")
    p_sync.add_argument("--apply", action="store_true",
                        help="Apply changes to files (default: dry-run for to-frontmatter)")

    # status
    p_status = sub.add_parser("status", help="Print DB statistics + TBox + TDA")
    p_status.add_argument("--tda", action="store_true",
                          help="Also compute and print TDA metrics (β₀, β₁)")

    # search (supports Global/Local routing + 4 explicit modes)
    p_search = sub.add_parser("search", help="Search the knowledge graph")
    p_search.add_argument("search_mode",
                          choices=["auto", "global", "insight", "panorama",
                                   "quick", "interview", "classify"])
    p_search.add_argument("query", help="Search query or entity name")
    p_search.add_argument("--json", action="store_true", help="Output raw JSON")
    p_search.add_argument("--global-level", type=int, default=1, dest="global_level",
                          help="Community level for global search (0=C0..3=C3, default=1)")
    p_search.add_argument("--hops", type=int, default=1,
                          help="Hop depth for quick search (default=1)")

    # bootstrap
    p_boot = sub.add_parser("bootstrap", help="Bootstrap index from cortex.db or vault scan")
    p_boot.add_argument("--cortex", default=None, help="Path to cortex.db")
    p_boot.add_argument("--force", action="store_true", help="Clear DB and re-bootstrap")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    config = _load_config(args.config)

    dispatch = {
        "build": cmd_build,
        "update": cmd_update,
        "sync": cmd_sync,
        "status": cmd_status,
        "search": cmd_search,
        "bootstrap": cmd_bootstrap,
    }

    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args, config)


if __name__ == "__main__":
    sys.exit(main())
