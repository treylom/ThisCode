"""
community_detector.py — Hierarchical community detection + TDA-based analysis

Theory-based enhancements:
  1. Hierarchical C0~C3 partitions via multi-resolution Louvain
     Ref: GraphRAG-Global-vs-Local-Search.md §5.4.6
          6개-분석공간-개요.md (Hierarchy Space = C0~C3)
  2. 6 Analysis Spaces mapping:
     - Hierarchy Space  → community hierarchy levels C0~C3
     - Structural Space → graph topology (betweenness centrality, density)
  3. TDA analysis: β₀ (connected components), β₁ (loop count)
     Ref: TDA-위상적-데이터-분석.md §F08
  4. Parent-child community links across levels

Community level convention (aligned with theory notes):
  C0 = coarsest / root (resolution 0.5) — global overview
  C1 = medium-coarse (resolution 1.0)
  C2 = medium-fine   (resolution 2.0)
  C3 = finest / leaf (resolution 4.0)  — local precision

Python 3.12 compatible
"""
from __future__ import annotations

from pathlib import Path as _Path
_PROJECT_DIR = _Path(__file__).resolve().parents[3]
_DEFAULT_DB = str(_PROJECT_DIR / ".team-os/graphrag/index/vault_graph.db")

import json
import re
import sqlite3
from typing import Any

# v2.3.2: import-time raise 제거 — server import 자체 fail 차단.
# Missing dep 는 build_networkx_graph() 등 caller 안 RuntimeError 안 명시 (lazy guard).
try:
    import networkx as nx
except ImportError:
    nx = None  # type: ignore[assignment]

try:
    import community as community_louvain  # python-louvain
except ImportError:
    community_louvain = None  # type: ignore[assignment]


def _require_networkx() -> None:
    if nx is None:
        raise RuntimeError(
            "networkx not installed. Run: pip install 'networkx>=3.0' (또는 bash scripts/install-graphrag.sh --apply)"
        )


def _require_louvain() -> None:
    if community_louvain is None:
        raise RuntimeError(
            "python-louvain not installed. Run: pip install 'python-louvain>=0.16' (또는 bash scripts/install-graphrag.sh --apply)"
        )

from graphrag_core import get_connection, close_connection


# ---------------------------------------------------------------------------
# Community level definitions
# Aligned with GraphRAG-Global-vs-Local-Search.md §5.4.6
# ---------------------------------------------------------------------------

# (level_index, resolution, label)
COMMUNITY_LEVELS: list[tuple[int, float, str]] = [
    (0, 0.5, "C0-global"),   # coarsest — global search target
    (1, 1.0, "C1-medium"),
    (2, 2.0, "C2-fine"),
    (3, 4.0, "C3-local"),    # finest — local search target
]

MOC_TOKEN_RE = re.compile(r"(^|[-_/])moc($|[-_/\s.(])", re.IGNORECASE)
MOC_RESIDUAL_RESOLUTION = 0.5
MOC_RESIDUAL_TARGET_BUCKETS = 64


def _has_moc_marker(value: str | None) -> bool:
    text = (value or "").replace("\\", "/")
    return bool(MOC_TOKEN_RE.search(text))


def is_moc_seed_entity(entity: dict[str, Any] | sqlite3.Row) -> bool:
    """Return True when an entity represents an MOC note/seed."""
    name = (entity["name"] or "").strip()
    source_note = (entity["source_note"] or "").strip()
    if name.lower() == "moc" and not source_note:
        return False
    return _has_moc_marker(name) or _has_moc_marker(source_note)


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_networkx_graph(conn: sqlite3.Connection) -> "nx.Graph":
    """Build an undirected weighted NetworkX graph from entities + relationships."""
    _require_networkx()
    G = nx.Graph()

    for row in conn.execute(
        "SELECT id, name, type, community_id, centrality_score FROM entities"
    ):
        G.add_node(
            row["id"],
            name=row["name"],
            type=row["type"],
            community_id=row["community_id"],
            centrality=row["centrality_score"] or 0.0,
        )

    for row in conn.execute(
        "SELECT source_id, target_id, type, strength, confidence FROM relationships"
    ):
        # Edge weight = strength * confidence (Named Graph quality)
        weight = (row["strength"] or 1.0) * (row["confidence"] or 1.0)
        G.add_edge(
            row["source_id"],
            row["target_id"],
            rel_type=row["type"],
            weight=weight,
        )

    return G


# ---------------------------------------------------------------------------
# TDA analysis — β₀ and β₁ (Betti numbers)
# Ref: TDA-위상적-데이터-분석.md §F08
# β₀ = connected components count (cluster structure)
# β₁ = cycle/loop count (circular relationship patterns)
# ---------------------------------------------------------------------------

def compute_betti_numbers(G: "nx.Graph") -> dict[str, int | float]:
    """
    Compute topological invariants of the graph (Betti numbers).

    β₀ = number of connected components
         Small β₀ → well-connected knowledge graph
         Large β₀ → fragmented clusters (isolated topic islands)

    β₁ = cycle rank = |E| - |V| + β₀
         Counts independent loops in the graph.
         High β₁ → rich interconnection patterns

    χ (Euler characteristic) = β₀ - β₁

    Ref: TDA-위상적-데이터-분석.md §F08
    """
    if G.number_of_nodes() == 0:
        return {"beta_0": 0, "beta_1": 0, "euler_chi": 0, "density": 0.0}

    V = G.number_of_nodes()
    E = G.number_of_edges()

    # β₀: number of connected components (Structural Space metric)
    beta_0 = nx.number_connected_components(G)

    # β₁: cycle rank = E - V + β₀
    beta_1 = E - V + beta_0

    # Euler characteristic: χ = β₀ - β₁
    euler_chi = beta_0 - beta_1

    # Graph density
    density = nx.density(G)

    return {
        "beta_0": beta_0,     # connected component count
        "beta_1": beta_1,     # loop/cycle count
        "euler_chi": euler_chi,
        "density": round(density, 6),
        "nodes": V,
        "edges": E,
    }


# ---------------------------------------------------------------------------
# Multi-resolution community detection
# ---------------------------------------------------------------------------

def detect_communities_at_level(
    G: "nx.Graph",
    resolution: float,
) -> dict[str, int]:
    """
    Run Louvain at given resolution.
    Lower resolution → fewer, larger communities (coarser = C0).
    Higher resolution → more, smaller communities (finer = C3).
    Returns: {node_id: community_label}
    """
    if G.number_of_nodes() == 0:
        return {}
    return community_louvain.best_partition(G, weight="weight", resolution=resolution)


def detect_hierarchical_communities(
    G: "nx.Graph",
    levels: list[tuple[int, float, str]] = COMMUNITY_LEVELS,
) -> dict[int, dict[str, int]]:
    """
    Run Louvain at all resolution levels.
    Returns: {level_index: {node_id: community_label}}

    C0 (resolution=0.5) → coarsest, fewest communities
    C3 (resolution=4.0) → finest, most communities
    """
    result: dict[int, dict[str, int]] = {}
    for level_idx, resolution, _label in levels:
        result[level_idx] = detect_communities_at_level(G, resolution)
    return result


def _load_moc_seed_entities(conn: sqlite3.Connection, G: "nx.Graph") -> list[dict[str, Any]]:
    rows = [
        dict(row)
        for row in conn.execute("SELECT id, name, source_note FROM entities")
        if row["id"] in G and is_moc_seed_entity(row)
    ]
    rows.sort(key=lambda row: ((row.get("name") or ""), row["id"]))
    return rows


def _split_residual_nodes(
    G: "nx.Graph",
    residual_nodes: list[str],
    start_label: int,
    target_buckets: int = MOC_RESIDUAL_TARGET_BUCKETS,
) -> tuple[dict[str, int], dict[int, str], dict[str, int]]:
    """Split only the unseeded C0 residual with a Louvain sub-pass."""
    if not residual_nodes:
        return {}, {}, {"raw_residual_subcommunities": 0, "residual_subcommunities": 0}

    target_buckets = max(1, target_buckets)
    residual_graph = G.subgraph(residual_nodes).copy()
    raw_partition = community_louvain.best_partition(
        residual_graph,
        weight="weight",
        resolution=MOC_RESIDUAL_RESOLUTION,
        random_state=42,
    )

    raw_groups: dict[int, list[str]] = {}
    for node_id, raw_label in raw_partition.items():
        raw_groups.setdefault(raw_label, []).append(node_id)
    ordered_groups = sorted(
        (sorted(nodes) for nodes in raw_groups.values()),
        key=lambda nodes: (-len(nodes), nodes[0]),
    )

    bucket_count = min(target_buckets, len(ordered_groups))
    buckets: list[list[str]] = [[] for _ in range(bucket_count)]
    bucket_sizes = [0] * bucket_count

    for group in ordered_groups:
        bucket_idx = min(range(bucket_count), key=lambda idx: (bucket_sizes[idx], idx))
        buckets[bucket_idx].extend(group)
        bucket_sizes[bucket_idx] += len(group)

    partition: dict[str, int] = {}
    names: dict[int, str] = {}
    for idx, nodes in enumerate(buckets):
        label = start_label + idx
        for node_id in nodes:
            partition[node_id] = label
        names[label] = f"[C0-global] Unseeded residual {idx + 1:02d}"

    return partition, names, {
        "raw_residual_subcommunities": len(raw_groups),
        "residual_subcommunities": bucket_count,
    }


def build_moc_seeded_c0_partition(
    conn: sqlite3.Connection,
    G: "nx.Graph",
    fallback_partition: dict[str, int],
) -> tuple[dict[str, int], dict[int, str], dict[str, int]]:
    """
    Rebuild C0 around MOC seed neighborhoods.

    MOC seed entities keep their coarse Louvain label. Directly linked targets
    are assigned to the MOC seed label with the strongest outgoing evidence.
    Nodes in coarse Louvain communities that already contain a MOC seed keep
    that label. Remaining unseeded nodes are split by a residual-only Louvain
    sub-pass; C1~C3 still preserve local detail.
    """
    moc_rows = _load_moc_seed_entities(conn, G)
    if not moc_rows:
        return dict(fallback_partition), {}, {
            "moc_seed_count": 0,
            "moc_seed_communities": 0,
            "direct_targets_assigned": 0,
            "orphan_nodes": 0,
        }

    seed_ids = {row["id"] for row in moc_rows}
    next_label = (max(fallback_partition.values()) + 1) if fallback_partition else 0
    seed_label: dict[str, int] = {}
    moc_names_by_label: dict[int, list[str]] = {}
    for row in moc_rows:
        label = fallback_partition.get(row["id"], next_label)
        if row["id"] not in fallback_partition:
            next_label += 1
        seed_label[row["id"]] = label
        moc_names_by_label.setdefault(label, []).append(row["name"])

    moc_labels = set(seed_label.values())
    target_votes: dict[str, dict[int, float]] = {}
    for row in conn.execute(
        """
        SELECT source_id, target_id, strength, confidence
          FROM relationships
         WHERE source_id IN ({})
        """.format(",".join("?" * len(seed_ids))),
        tuple(seed_ids),
    ):
        target_id = row["target_id"]
        if target_id not in G or target_id in seed_ids:
            continue
        label = seed_label[row["source_id"]]
        weight = (row["strength"] or 1.0) * (row["confidence"] or 1.0)
        target_votes.setdefault(target_id, {})
        target_votes[target_id][label] = target_votes[target_id].get(label, 0.0) + weight

    partition: dict[str, int] = {}
    residual_nodes: list[str] = []
    direct_targets_assigned = 0
    orphan_nodes = 0

    for node_id in G.nodes():
        if node_id in seed_label:
            partition[node_id] = seed_label[node_id]
        elif node_id in target_votes:
            votes = target_votes[node_id]
            partition[node_id] = min(votes, key=lambda label: (-votes[label], label))
            direct_targets_assigned += 1
        else:
            fallback_label = fallback_partition.get(node_id, next_label)
            if fallback_label in moc_labels:
                partition[node_id] = fallback_label
            else:
                residual_nodes.append(node_id)
                orphan_nodes += 1

    residual_partition, residual_names, residual_stats = _split_residual_nodes(
        G,
        residual_nodes,
        start_label=next_label,
    )
    partition.update(residual_partition)

    community_names: dict[int, str] = {}
    for label, names in moc_names_by_label.items():
        top_names = sorted(names)[:2]
        suffix = f" +{len(names) - 2} MOCs" if len(names) > 2 else ""
        community_names[label] = f"[C0-MOC] {' / '.join(top_names)}{suffix}"
    community_names.update(residual_names)

    return partition, community_names, {
        "moc_seed_count": len(seed_ids),
        "moc_seed_communities": len(moc_labels),
        "direct_targets_assigned": direct_targets_assigned,
        "orphan_nodes": orphan_nodes,
        **residual_stats,
    }


def should_recalculate(
    conn: sqlite3.Connection,
    changed_count: int,
    total_count: int,
    threshold: float = 0.05,
) -> bool:
    """Return True if change ratio > threshold (default 5%)."""
    if total_count == 0:
        return False
    return (changed_count / total_count) > threshold


# ---------------------------------------------------------------------------
# LLM placeholder
# ---------------------------------------------------------------------------

COMMUNITY_SUMMARY_PROMPT = """\
You are a knowledge graph analyst (Hierarchy Space analysis).

Community level: {level_label} (C{level}: {level_desc})

Given the following community of entities and their relationships, write a concise 2-3 sentence
summary describing what this community represents and its key themes.

Abstraction guidance:
  - C0 (global): Focus on broad domain themes and major topic clusters
  - C1/C2 (medium): Describe specific subject areas and their connections
  - C3 (local): Detail fine-grained topic clusters with specific entity roles

Community members:
{members}

Key relationships:
{edges}

Summary:
"""


def summarize_community_llm(
    members: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    level: int = 0,
) -> str:
    """
    LLM placeholder — returns generic summary.
    Replace with actual LLM call using COMMUNITY_SUMMARY_PROMPT.
    """
    # TODO: call LLM with COMMUNITY_SUMMARY_PROMPT.format(...)
    level_desc = ["global overview", "medium-coarse", "medium-fine", "local detail"][min(level, 3)]
    names = ", ".join(m["name"] for m in members[:5])
    suffix = " and others." if len(members) > 5 else "."
    return f"[C{level} {level_desc}] Community containing: {names}{suffix}"


# ---------------------------------------------------------------------------
# Centrality computation
# ---------------------------------------------------------------------------

def update_entity_centrality(conn: sqlite3.Connection, G: "nx.Graph") -> None:
    """Compute blended centrality and update DB (Structural Space metric)."""
    if G.number_of_nodes() == 0:
        return

    try:
        pr = nx.pagerank(G, alpha=0.85, weight="weight", max_iter=200, tol=1e-6)
    except nx.PowerIterationFailedConvergence:
        try:
            pr = nx.pagerank(G, alpha=0.85, weight="weight", max_iter=1000, tol=1e-4)
        except nx.PowerIterationFailedConvergence:
            pr = {n: 0.0 for n in G.nodes()}
    deg = dict(G.degree(weight="weight"))
    max_deg = max(deg.values()) if deg else 1
    if max_deg == 0:
        max_deg = 1
    centrality = {
        n: 0.6 * pr.get(n, 0.0) + 0.4 * (deg.get(n, 0) / max_deg)
        for n in G.nodes()
    }

    conn.executemany(
        "UPDATE entities SET centrality_score = ?, updated_at = datetime('now') WHERE id = ?",
        [(score, node_id) for node_id, score in centrality.items()],
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Save hierarchical communities to DB
# ---------------------------------------------------------------------------

def save_communities_at_level(
    conn: sqlite3.Connection,
    partition: dict[str, int],
    G: "nx.Graph",
    level: int,
    resolution: float,
    level_label: str,
    parent_partitions: dict[int, dict[str, int]] | None = None,
    community_names: dict[int, str] | None = None,
) -> int:
    """
    Save one level's community partition to DB.
    Sets parent_id by finding which C(level-1) community contains most members.
    Returns count of communities saved.
    """
    # Group nodes by community label
    community_map: dict[int, list[str]] = {}
    for node_id, label in partition.items():
        community_map.setdefault(label, []).append(node_id)

    # Clear old communities at this level (disable FK to avoid parent_id constraint)
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("DELETE FROM communities WHERE level = ?", (level,))
    conn.execute("PRAGMA foreign_keys = ON")

    saved = 0
    for label, member_ids in community_map.items():
        comm_id = f"comm-{level}-{label}"

        # Fetch member entity info
        placeholders = ",".join("?" * len(member_ids))
        members = [
            dict(row)
            for row in conn.execute(
                f"SELECT id, name, type, description FROM entities WHERE id IN ({placeholders})",
                member_ids,
            )
        ]

        # Fetch intra-community edges
        edges = [
            {
                "source": G.nodes[u].get("name", u),
                "target": G.nodes[v].get("name", v),
                "type": d.get("rel_type", "related_to"),
            }
            for u, v, d in G.edges(data=True)
            if u in partition and v in partition
            and partition[u] == label and partition[v] == label
        ]

        summary = summarize_community_llm(members, edges, level=level)
        name = (
            community_names[label]
            if community_names and label in community_names
            else (
                f"[{level_label}] {members[0]['name']} et al."
                if members
                else f"[{level_label}] Community {label}"
            )
        )

        # Determine parent_id from level - 1
        parent_id: str | None = None
        if parent_partitions and level > 0:
            parent_level = level - 1
            parent_partition = parent_partitions.get(parent_level)
            if parent_partition:
                # Find which parent community contains the most members of this child
                parent_votes: dict[int, int] = {}
                for eid in member_ids:
                    plabel = parent_partition.get(eid)
                    if plabel is not None:
                        parent_votes[plabel] = parent_votes.get(plabel, 0) + 1
                if parent_votes:
                    best_parent_label = max(parent_votes, key=lambda k: parent_votes[k])
                    parent_id = f"comm-{parent_level}-{best_parent_label}"

        conn.execute(
            """
            INSERT INTO communities
                (id, name, summary, member_entity_ids, parent_id, level, resolution)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name              = excluded.name,
                summary           = excluded.summary,
                member_entity_ids = excluded.member_entity_ids,
                parent_id         = excluded.parent_id,
                resolution        = excluded.resolution,
                updated_at        = datetime('now')
            """,
            (comm_id, name, summary, json.dumps(member_ids), parent_id, level, resolution),
        )

        # Update entity community_id to the finest level (C3) community
        if level == max(l for l, _, _ in COMMUNITY_LEVELS):
            conn.executemany(
                "UPDATE entities SET community_id = ?, updated_at = datetime('now') WHERE id = ?",
                [(comm_id, eid) for eid in member_ids],
            )

        saved += 1

    conn.commit()
    return saved


# ---------------------------------------------------------------------------
# High-level pipeline
# ---------------------------------------------------------------------------

def run_community_detection(
    conn: sqlite3.Connection,
    changed_count: int = 0,
    force: bool = False,
    levels: list[tuple[int, float, str]] = COMMUNITY_LEVELS,
) -> dict[str, Any]:
    """
    Full hierarchical community detection pipeline:
    1. Check if recalculation needed
    2. Build graph
    3. Detect communities at C0~C3 levels (multi-resolution Louvain)
    4. Save with parent-child hierarchy
    5. Update centrality
    6. Compute TDA metrics (β₀, β₁)

    Hierarchy Space: levels map to GraphRAG C0~C3
    Structural Space: graph topology via centrality + Betti numbers
    Ref: 6개-분석공간-개요.md Mode G 적용 포인트 #1, #4
    """
    total_count = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]

    if not force and not should_recalculate(conn, changed_count, total_count):
        return {
            "skipped": True,
            "reason": f"change ratio below threshold ({changed_count}/{total_count})",
        }

    G = build_networkx_graph(conn)

    if G.number_of_nodes() == 0:
        return {"skipped": True, "reason": "No entities in graph"}

    # TDA: topological structure of the graph
    tda_metrics = compute_betti_numbers(G)

    # Multi-resolution community detection (Hierarchy Space)
    all_partitions = detect_hierarchical_communities(G, levels)
    community_name_overrides: dict[int, dict[int, str]] = {}
    moc_seed_stats: dict[str, int] | None = None
    if 0 in all_partitions:
        c0_partition, c0_names, moc_seed_stats = build_moc_seeded_c0_partition(
            conn,
            G,
            all_partitions[0],
        )
        all_partitions[0] = c0_partition
        community_name_overrides[0] = c0_names

    # Save from coarsest (C0) to finest (C3) to set parent_id correctly
    community_counts: dict[str, int] = {}
    for level_idx, resolution, level_label in sorted(levels, key=lambda x: x[0]):
        partition = all_partitions[level_idx]
        count = save_communities_at_level(
            conn=conn,
            partition=partition,
            G=G,
            level=level_idx,
            resolution=resolution,
            level_label=level_label,
            parent_partitions=all_partitions,
            community_names=community_name_overrides.get(level_idx),
        )
        community_counts[level_label] = count

    # Centrality (Structural Space)
    update_entity_centrality(conn, G)

    return {
        "skipped": False,
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "communities_per_level": community_counts,
        "moc_seed_stats": moc_seed_stats,
        # TDA metrics (β₀, β₁, Euler characteristic)
        "tda": tda_metrics,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Run hierarchical community detection (C0~C3) on vault graph"
    )
    parser.add_argument("--db", default=_DEFAULT_DB)
    parser.add_argument("--force", action="store_true",
                        help="Force recalculation regardless of threshold")
    parser.add_argument("--changed", type=int, default=0,
                        help="Number of changed notes since last run")
    parser.add_argument("--tda", action="store_true",
                        help="Print TDA metrics (β₀, β₁) only, don't save")
    args = parser.parse_args()

    conn = get_connection(args.db)

    if args.tda:
        G = build_networkx_graph(conn)
        metrics = compute_betti_numbers(G)
        print("TDA Metrics:")
        for k, v in metrics.items():
            print(f"  {k:20s}: {v}")
        close_connection(conn)
        sys.exit(0)

    result = run_community_detection(conn, changed_count=args.changed, force=args.force)
    close_connection(conn)

    if result.get("skipped"):
        print(f"Skipped: {result['reason']}", file=sys.stderr)
    else:
        print(
            f"Hierarchical communities (C0~C3): nodes={result['nodes']}, "
            f"edges={result['edges']}"
        )
        for level_label, count in result.get("communities_per_level", {}).items():
            print(f"  {level_label}: {count} communities")
        tda = result.get("tda", {})
        print(
            f"TDA: β₀={tda.get('beta_0')}, β₁={tda.get('beta_1')}, "
            f"χ={tda.get('euler_chi')}, density={tda.get('density')}"
        )
