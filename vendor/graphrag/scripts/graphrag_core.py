"""
graphrag_core.py — SQLite schema, connection helpers, hash utilities

TBox/ABox separation based on domain ontology theory:
  TBox (Terminological Box): entity type classes, properties, relation types, axioms
  ABox (Assertional Box): entities (instances) + relationships (facts)
  Named Graph support: each relationship carries source, confidence, extracted_date context

Ref: 온톨로지-TBox와-ABox.md §5.7, §5.10 | 도메인-온톨로지-구축-5단계.md §6.7
Python 3.12 compatible
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Optional


class _DateSafeEncoder(json.JSONEncoder):
    """Handle date/datetime objects in YAML frontmatter."""
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)


# ---------------------------------------------------------------------------
# Path validation
# ---------------------------------------------------------------------------

def validate_db_path(db_path: str | Path) -> Path:
    """Reject NTFS paths (/mnt/c/); only WSL ext4 allowed."""
    p = Path(db_path)
    resolved = str(p.resolve())
    if resolved.startswith("/mnt/c/") or resolved.startswith("/mnt/d/"):
        raise ValueError(
            f"DB path must be on WSL ext4, not NTFS: {resolved}\n"
            "Use a path under /home/ or the project directory."
        )
    return p


# ---------------------------------------------------------------------------
# Hash helpers
# ---------------------------------------------------------------------------

_GRAPH_FIELDS = {"graph_entity", "graph_community", "graph_connections"}


def compute_content_hash(content: str, frontmatter: dict) -> str:
    """SHA256 of note content, excluding graph_* frontmatter fields."""
    clean_fm = {k: v for k, v in frontmatter.items() if k not in _GRAPH_FIELDS}
    payload = json.dumps(clean_fm, sort_keys=True, ensure_ascii=False, cls=_DateSafeEncoder) + "\n" + content
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_frontmatter_hash(frontmatter: dict) -> str:
    """SHA256 of graph_* frontmatter fields only."""
    graph_fm = {k: v for k, v in frontmatter.items() if k in _GRAPH_FIELDS}
    payload = json.dumps(graph_fm, sort_keys=True, ensure_ascii=False, cls=_DateSafeEncoder)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Schema DDL — TBox/ABox Architecture
#
# TBox (schema/ontology layer):
#   tbox — classes, properties, relation_types, axioms (4 components per §6.7)
#
# ABox (instance/fact layer):
#   entities     — individual entity instances
#   relationships — relationship facts with Named Graph context (source, confidence, date)
#   reified_relationships — N-ary relations represented via Reification pattern
#
# Infrastructure:
#   communities  — hierarchical C0-C3 community partitions
#   note_graph_state, sync_log — change tracking
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- ============================================================
-- TBox: Terminological Box (ontology schema)
-- Defines WHAT EXISTS in the domain — class hierarchy, property
-- definitions, relation types, axioms.
-- Ref: 도메인-온톨로지-구축-5단계.md §6.7 (4 components)
-- ============================================================

CREATE TABLE IF NOT EXISTS tbox (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    -- 4 ontology components:
    classes         TEXT NOT NULL DEFAULT '[]',      -- JSON: [{name, description, parent?, aliases}]
    properties      TEXT NOT NULL DEFAULT '[]',      -- JSON: [{name, domain_class, range, description}]
    relation_types  TEXT NOT NULL DEFAULT '[]',      -- JSON: [{name, domain, range, is_symmetric, is_transitive}]
    axioms          TEXT NOT NULL DEFAULT '[]',      -- JSON: [{id, rule_text, applies_to_class, priority}]
    version         INTEGER DEFAULT 1,
    updated_at      TEXT DEFAULT (datetime('now'))
);

-- ============================================================
-- ABox: Assertional Box — individual entity instances
-- Each row = one named individual in the TBox class hierarchy
-- ============================================================

CREATE TABLE IF NOT EXISTS entities (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    name_ko         TEXT,
    type            TEXT NOT NULL,          -- TBox class reference
    description     TEXT,
    source_note     TEXT,
    centrality_score REAL DEFAULT 0.0,
    community_id    TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

-- ============================================================
-- ABox: Assertional Box — relationship facts (binary)
-- Named Graph context: confidence + extracted_date per relationship
-- Ref: 메타엣지-하이퍼그래프-구현.md §5.17 (Named Graph / Quad)
-- ============================================================

CREATE TABLE IF NOT EXISTS relationships (
    id              TEXT PRIMARY KEY,
    source_id       TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    target_id       TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    type            TEXT NOT NULL,          -- TBox relation_type reference
    strength        REAL DEFAULT 1.0,
    evidence_text   TEXT,
    source_note     TEXT,
    -- Named Graph context (Quad extension):
    confidence      REAL DEFAULT 1.0,       -- extraction confidence [0.0-1.0]
    extracted_date  TEXT DEFAULT (datetime('now')),  -- when this fact was extracted
    created_at      TEXT DEFAULT (datetime('now'))
);

-- ============================================================
-- ABox: Reified N-ary relationships
-- When 3+ entities participate in a single event, we create a
-- Reification node (event_type + participant_ids) instead of
-- decomposing into lossy binary relations.
-- Ref: 메타엣지-하이퍼그래프-구현.md §5.17 (Reification pattern)
-- ============================================================

CREATE TABLE IF NOT EXISTS reified_relationships (
    id              TEXT PRIMARY KEY,
    event_type      TEXT NOT NULL,          -- e.g. "co_authorship", "meeting", "shared_context"
    participant_ids TEXT NOT NULL DEFAULT '[]',  -- JSON array of entity IDs (3+)
    properties      TEXT NOT NULL DEFAULT '{}',  -- JSON: extra attributes of the event
    source_note     TEXT,
    confidence      REAL DEFAULT 1.0,
    extracted_date  TEXT DEFAULT (datetime('now')),
    created_at      TEXT DEFAULT (datetime('now'))
);

-- ============================================================
-- Communities — hierarchical C0~C3 partitions
-- C0 = coarsest (global, root), C3 = finest (local, leaf)
-- Ref: GraphRAG-Global-vs-Local-Search.md §5.4.6
--      6개-분석공간-개요.md (Hierarchy Space = C0~C3)
-- ============================================================

CREATE TABLE IF NOT EXISTS communities (
    id              TEXT PRIMARY KEY,
    name            TEXT,
    summary         TEXT,
    member_entity_ids TEXT NOT NULL DEFAULT '[]',  -- JSON array
    parent_id       TEXT REFERENCES communities(id),
    level           INTEGER DEFAULT 0,      -- 0=coarsest(C0) .. 3=finest(C3)
    resolution      REAL DEFAULT 1.0,       -- Louvain resolution parameter used
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

-- ============================================================
-- Infrastructure tables
-- ============================================================

CREATE TABLE IF NOT EXISTS note_graph_state (
    note_path       TEXT PRIMARY KEY,
    content_hash    TEXT,
    frontmatter_hash TEXT,
    last_indexed    TEXT DEFAULT (datetime('now')),
    graph_synced    INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sync_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT DEFAULT (datetime('now')),
    operation       TEXT NOT NULL,
    note_path       TEXT,
    entity_ids      TEXT DEFAULT '[]',
    status          TEXT NOT NULL DEFAULT 'pending',
    source          TEXT
);

-- ============================================================
-- Indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);
CREATE INDEX IF NOT EXISTS idx_entities_community ON entities(community_id);
CREATE INDEX IF NOT EXISTS idx_relationships_source ON relationships(source_id);
CREATE INDEX IF NOT EXISTS idx_relationships_target ON relationships(target_id);
CREATE INDEX IF NOT EXISTS idx_relationships_type ON relationships(type);
CREATE INDEX IF NOT EXISTS idx_relationships_confidence ON relationships(confidence);
CREATE INDEX IF NOT EXISTS idx_reified_event_type ON reified_relationships(event_type);
CREATE INDEX IF NOT EXISTS idx_communities_level ON communities(level);
CREATE INDEX IF NOT EXISTS idx_communities_parent ON communities(parent_id);
CREATE INDEX IF NOT EXISTS idx_sync_log_status ON sync_log(status);
CREATE INDEX IF NOT EXISTS idx_sync_log_note ON sync_log(note_path);

-- ============================================================
-- Entity aliases — cross-lingual / shorthand name mappings
-- ============================================================

CREATE TABLE IF NOT EXISTS entity_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT NOT NULL REFERENCES entities(id),
    alias_name TEXT NOT NULL,
    alias_type TEXT DEFAULT 'manual',
    UNIQUE(entity_id, alias_name)
);
CREATE INDEX IF NOT EXISTS idx_alias_name ON entity_aliases(alias_name);
"""


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def get_connection(db_path: str | Path, validate: bool = True) -> sqlite3.Connection:
    """Open (and initialize) a SQLite connection with WAL mode."""
    if validate:
        db_path = validate_db_path(db_path)
    else:
        db_path = Path(db_path)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_SCHEMA_SQL)
    create_fts5_tables(conn)
    conn.commit()
    return conn


def _strip_frontmatter(content: str) -> str:
    """Strip YAML frontmatter (--- ... ---) from markdown content."""
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            return content[end + 4:].lstrip()
    return content


def close_connection(conn: sqlite3.Connection) -> None:
    """Safely close a connection."""
    try:
        conn.close()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# FTS5 full-text search — entities_fts virtual table
# Tokenizer: trigram — substring matching, good for Korean text
# entity_id stored as UNINDEXED column for safe id-based join back to entities
# ---------------------------------------------------------------------------

def create_fts5_tables(conn: sqlite3.Connection) -> None:
    """Create FTS5 virtual table for full-text search on entities."""
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE VIRTUAL TABLE IF NOT EXISTS entities_fts USING fts5(
            entity_id UNINDEXED, name, name_ko, description, source_note,
            tokenize='trigram'
        );
    """)
    conn.commit()


def populate_fts5(conn: sqlite3.Connection) -> int:
    """Sync entities table → entities_fts. Rebuilds index from scratch.

    Returns count of rows indexed.
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute("DELETE FROM entities_fts")
        conn.execute("""
            INSERT INTO entities_fts(entity_id, name, name_ko, description, source_note)
            SELECT
                id,
                name,
                COALESCE(name_ko, ''),
                COALESCE(description, ''),
                COALESCE(source_note, '')
            FROM entities
        """)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    row = conn.execute("SELECT COUNT(*) FROM entities_fts").fetchone()
    return row[0] if row else 0


def _expand_query_with_aliases(conn: sqlite3.Connection, query: str) -> str:
    """Expand FTS5 query using entity_aliases table (M2a).

    Manual aliases keep the historical partial-term expansion. Frontmatter
    aliases are only eligible when the full query exactly matches the alias;
    otherwise broad aliases such as "AI..." pull unrelated entities into OR.
    """
    terms = [t.strip() for t in query.split() if len(t.strip()) >= 2]
    if not terms:
        return query

    expanded = set(terms)
    try:
        for term in terms:
            aliases = conn.execute(
                "SELECT DISTINCT a2.alias_name FROM entity_aliases a1 "
                "JOIN entity_aliases a2 ON a1.entity_id = a2.entity_id "
                "WHERE COALESCE(a1.alias_type, 'manual') != 'frontmatter' "
                "AND a1.alias_name LIKE ?",
                (f"%{term}%",),
            ).fetchall()
            for a in aliases:
                alias_name = a[0]
                if alias_name and len(alias_name) >= 2:
                    expanded.add(alias_name)

        exact_frontmatter_aliases = conn.execute(
            "SELECT DISTINCT a2.alias_name FROM entity_aliases a1 "
            "JOIN entity_aliases a2 ON a1.entity_id = a2.entity_id "
            "WHERE a1.alias_type = 'frontmatter' "
            "AND LOWER(a1.alias_name) = LOWER(?)",
            (query.strip(),),
        ).fetchall()
        for a in exact_frontmatter_aliases:
            alias_name = a[0]
            if alias_name and len(alias_name) >= 2:
                expanded.add(alias_name)
    except sqlite3.OperationalError:
        pass  # entity_aliases table may not exist

    if len(expanded) <= len(terms):
        return query  # no expansion found

    # Build OR query for FTS5 (quote each term for exact matching)
    fts_query = " OR ".join(f'"{t}"' for t in expanded)
    return fts_query


def _short_token_like_search(conn: sqlite3.Connection, query: str, limit: int) -> list[dict]:
    def _escape_like(s):
        return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    short_tokens = [t.strip() for t in query.split() if 0 < len(t.strip()) < 3]
    if not short_tokens:
        return []
    try:
        clauses = ["(name LIKE ? ESCAPE '\\' OR COALESCE(name_ko, '') LIKE ? ESCAPE '\\')"] * len(short_tokens)
        params = []
        for token in short_tokens:
            like_token = f'%{_escape_like(token)}%'
            params.extend([like_token, like_token])
        rows = conn.execute(
            f'SELECT id, name, name_ko, type, description, source_note, centrality_score, community_id, 0.0 as rank FROM entities WHERE {" AND ".join(clauses)} LIMIT ?',
            (*params, limit),
        ).fetchall()
        return [dict(row) for row in rows]
    except Exception:
        return []


def fts5_search(conn: sqlite3.Connection, query: str, limit: int = 20) -> list[dict]:
    """Full-text search over entities using FTS5.

    Joins FTS5 results back to entities on entity_id (unique, avoids name collisions).
    Returns list of entity dicts with an added 'rank' key (lower = more relevant).

    M2a: Auto-expands query using entity_aliases table.
    M2c: MOC 1.5x boost, Bug 0.5x penalty.
    """
    # M2a: Expand query with aliases
    expanded_query = _expand_query_with_aliases(conn, query)

    # Fetch more than limit to allow re-sorting to surface boosted entities
    fetch_limit = min(limit * 3, 60)

    # Search with both original and expanded queries, merge results
    all_results: dict[str, dict] = {}
    for q in [query, expanded_query] if expanded_query != query else [query]:
        try:
            rows = conn.execute(
                """
                SELECT e.id, e.name, e.name_ko, e.type, e.description,
                       e.source_note, e.centrality_score, e.community_id,
                       f.rank
                FROM entities_fts f
                JOIN entities e ON e.id = f.entity_id
                WHERE entities_fts MATCH ?
                ORDER BY f.rank
                LIMIT ?
                """,
                (q, fetch_limit),
            ).fetchall()
            for row in rows:
                r = dict(row)
                name = r["name"]
                if name not in all_results or r["rank"] < all_results[name]["rank"]:
                    all_results[name] = r
        except Exception:
            continue

    # R24 apr13: trigger < 5 (was < limit=20) — fire only for starved queries to avoid OR flood
    if len(all_results) < 5:
        tokens = [t for t in query.split() if len(t.strip()) >= 2]
        or_query = " OR ".join(f'"{t}"' for t in tokens if t)
        if or_query:
            try:
                rows = conn.execute(
                    """
                    SELECT e.id, e.name, e.name_ko, e.type, e.description,
                           e.source_note, e.centrality_score, e.community_id,
                           f.rank
                    FROM entities_fts f
                    JOIN entities e ON e.id = f.entity_id
                    WHERE entities_fts MATCH ?
                    ORDER BY f.rank
                    LIMIT ?
                    """,
                    (or_query, 200),  # R35 apr13: OR LIMIT 60→200. Gold for starved queries may be at BM25 rank 60+ among OR-matched entities.
                ).fetchall()
                for row in rows:
                    r = dict(row)
                    name = r["name"]
                    if name not in all_results:
                        # R37 apr13: ratio-weighted OR penalty. High-ratio entities (matched/total >= 0.5)
                        # where entity name is mostly query tokens (e.g. "AI-Safety") get boost.
                        # Low-ratio broad entities get strong penalty.
                        import re as _re37
                        name_lower = (name or "").lower()
                        name_segs = {s for s in _re37.split(r"[\s\-_/.,:;()\[\]{}]+", name_lower) if s}
                        q_toks = {t.lower() for t in query.split() if t and len(t) >= 2}
                        ov = len(name_segs & q_toks)
                        if name_segs and ov >= 2 and ov / len(name_segs) >= 0.5:
                            r["rank"] *= 0.85  # focused gold-like
                        else:
                            r["rank"] *= 0.4  # broad noise, strong penalty
                        all_results[name] = r
            except Exception:
                pass

    short_hits = _short_token_like_search(conn, query, fetch_limit)  # R8: Short-token LIKE fallback (trigram cannot index < 3-char tokens like AI / 팀)
    for hit in short_hits:
        hit["rank"] = -0.5
        if hit["name"] not in all_results:
            all_results[hit["name"]] = hit

    results = list(all_results.values())

    # Apply entity-type score adjustments (FTS5 rank is negative; more negative = better)
    for r in results:
        raw_rank = r["rank"]
        name = r.get("name", "")
        if "MOC" in name or name.endswith("-MOC") or r.get("type") == "MOC":
            r["rank"] = raw_rank * 0.67  # boost: more negative
        elif name.startswith("Bug-"):
            r["rank"] = raw_rank * 2.0  # penalty: less negative

    results.sort(key=lambda r: r["rank"])
    return results[:limit]


# ---------------------------------------------------------------------------
# Entity description enrichment — fill NULL/empty descriptions from vault notes
# ---------------------------------------------------------------------------

def enrich_entity_descriptions(conn: sqlite3.Connection, vault_path: str | Path) -> int:
    """Enrich entities where description is NULL or empty.

    For each such entity, reads source_note from vault, strips frontmatter,
    and stores the first 200 chars as the description.  Intended to run
    during cron build — not at query time.

    Returns count of entities enriched.
    """
    vault_path = Path(vault_path)
    rows = conn.execute(
        """
        SELECT id, source_note
        FROM entities
        WHERE (description IS NULL OR description = '')
          AND source_note IS NOT NULL
          AND source_note != ''
        """
    ).fetchall()

    enriched = 0
    for row in rows:
        entity_id: str = row[0]
        source_note: str = row[1]

        note_path = vault_path / source_note
        if not note_path.exists():
            continue

        try:
            content = note_path.read_text(encoding="utf-8")
            text = _strip_frontmatter(content)
            description = text[:200].strip()
            if description:
                conn.execute(
                    "UPDATE entities SET description = ?, updated_at = datetime('now') WHERE id = ?",
                    (description, entity_id),
                )
                enriched += 1
        except (OSError, UnicodeDecodeError):
            continue

    conn.commit()
    return enriched


def get_db_stats(conn: sqlite3.Connection) -> dict:
    """Return row counts for all tables."""
    tables = [
        "entities", "relationships", "reified_relationships",
        "communities", "tbox", "note_graph_state", "sync_log",
        "entities_fts",
    ]
    stats: dict[str, int] = {}
    for table in tables:
        row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        stats[table] = row[0] if row else 0
    return stats


# ---------------------------------------------------------------------------
# TBox helpers — Terminological Box operations
# ---------------------------------------------------------------------------

# Default TBox definition (Knowledge Manager domain ontology)
# Derived from vault structure analysis per 도메인-온톨로지-구축-5단계.md §6.7
_DEFAULT_TBOX: dict = {
    "classes": [
        {"name": "concept",       "description": "Abstract idea or topic", "aliases": []},
        {"name": "person",        "description": "Human individual", "aliases": ["author", "researcher"]},
        {"name": "tool",          "description": "Software or methodology tool", "aliases": ["library", "framework"]},
        {"name": "project",       "description": "Bounded initiative or work package", "aliases": []},
        {"name": "series",        "description": "Ordered sequence of articles/lectures", "aliases": []},
        {"name": "event",         "description": "Time-bound occurrence (meeting, publication)", "aliases": []},
        {"name": "organization",  "description": "Institution, team, or company", "aliases": ["team", "company"]},
        {"name": "technique",     "description": "Methodology or algorithmic approach", "aliases": ["method", "algorithm"]},
        {"name": "model",         "description": "ML/AI model or theoretical model", "aliases": []},
        {"name": "paper",         "description": "Academic publication", "aliases": ["article", "research"]},
    ],
    "properties": [
        {"name": "name",          "domain_class": "*",       "range": "string",  "description": "Canonical name"},
        {"name": "name_ko",       "domain_class": "*",       "range": "string",  "description": "Korean name"},
        {"name": "description",   "domain_class": "*",       "range": "string",  "description": "One-sentence description"},
        {"name": "source_note",   "domain_class": "*",       "range": "string",  "description": "Originating vault note path"},
        {"name": "centrality",    "domain_class": "*",       "range": "float",   "description": "Betweenness centrality score"},
    ],
    "relation_types": [
        {"name": "belongs_to",    "domain": "*", "range": "*", "is_symmetric": False, "is_transitive": True},
        {"name": "parent",        "domain": "*", "range": "*", "is_symmetric": False, "is_transitive": True},
        {"name": "contains",      "domain": "*", "range": "*", "is_symmetric": False, "is_transitive": True},
        {"name": "part_of",       "domain": "*", "range": "*", "is_symmetric": False, "is_transitive": True},
        {"name": "references",    "domain": "*", "range": "*", "is_symmetric": False, "is_transitive": False},
        {"name": "sourced_from",  "domain": "*", "range": "*", "is_symmetric": False, "is_transitive": False},
        {"name": "derived_from",  "domain": "*", "range": "*", "is_symmetric": False, "is_transitive": False},
        {"name": "supported_by",  "domain": "*", "range": "*", "is_symmetric": False, "is_transitive": False},
        {"name": "related_to",    "domain": "*", "range": "*", "is_symmetric": True,  "is_transitive": False},
        {"name": "aligns_with",   "domain": "*", "range": "*", "is_symmetric": True,  "is_transitive": False},
        {"name": "next",          "domain": "*", "range": "*", "is_symmetric": False, "is_transitive": False},
        {"name": "prev",          "domain": "*", "range": "*", "is_symmetric": False, "is_transitive": False},
        {"name": "supersedes",    "domain": "*", "range": "*", "is_symmetric": False, "is_transitive": False},
        {"name": "mentions",      "domain": "*", "range": "*", "is_symmetric": False, "is_transitive": False},
        {"name": "co_occurs",     "domain": "*", "range": "*", "is_symmetric": True,  "is_transitive": False},
    ],
    "axioms": [
        {"id": "A1", "rule_text": "Every entity must have a non-empty name", "applies_to_class": "*",         "priority": 1},
        {"id": "A2", "rule_text": "belongs_to is transitive: if A belongs_to B and B belongs_to C then A belongs_to C",
                     "applies_to_class": "*", "priority": 2},
        {"id": "A3", "rule_text": "co_occurs edges originate from shared Obsidian tags (hyperedge seed)",
                     "applies_to_class": "*", "priority": 3},
    ],
}


def load_tbox(conn: sqlite3.Connection) -> dict:
    """Return the latest TBox definition as a dict with 4 components."""
    row = conn.execute(
        "SELECT classes, properties, relation_types, axioms, version FROM tbox ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return {
            "classes": [],
            "properties": [],
            "relation_types": [],
            "axioms": [],
            "version": 0,
        }
    return {
        "classes":        json.loads(row["classes"]),
        "properties":     json.loads(row["properties"]),
        "relation_types": json.loads(row["relation_types"]),
        "axioms":         json.loads(row["axioms"]),
        "version":        row["version"],
    }


def save_tbox(
    conn: sqlite3.Connection,
    classes: list[dict],
    properties: list[dict],
    relation_types: list[dict],
    axioms: list[dict],
) -> int:
    """Insert a new TBox version. Returns new version number."""
    row = conn.execute("SELECT version FROM tbox ORDER BY id DESC LIMIT 1").fetchone()
    version = (row["version"] + 1) if row else 1
    conn.execute(
        """INSERT INTO tbox (classes, properties, relation_types, axioms, version)
           VALUES (?, ?, ?, ?, ?)""",
        (
            json.dumps(classes,        ensure_ascii=False),
            json.dumps(properties,     ensure_ascii=False),
            json.dumps(relation_types, ensure_ascii=False),
            json.dumps(axioms,         ensure_ascii=False),
            version,
        ),
    )
    conn.commit()
    return version


def ensure_default_tbox(conn: sqlite3.Connection) -> None:
    """Seed TBox with default domain ontology if none exists."""
    existing = conn.execute("SELECT COUNT(*) FROM tbox").fetchone()[0]
    if existing == 0:
        save_tbox(
            conn,
            _DEFAULT_TBOX["classes"],
            _DEFAULT_TBOX["properties"],
            _DEFAULT_TBOX["relation_types"],
            _DEFAULT_TBOX["axioms"],
        )


def get_valid_entity_types(conn: sqlite3.Connection) -> list[str]:
    """Return list of valid entity type names from TBox classes."""
    tbox = load_tbox(conn)
    return [c["name"] for c in tbox.get("classes", [])]


def get_valid_relation_types(conn: sqlite3.Connection) -> list[str]:
    """Return list of valid relation type names from TBox."""
    tbox = load_tbox(conn)
    return [r["name"] for r in tbox.get("relation_types", [])]


# ---------------------------------------------------------------------------
# Legacy ontology helpers (backward compat — maps to TBox)
# ---------------------------------------------------------------------------

def load_ontology(conn: sqlite3.Connection) -> dict:
    """Backward-compatible ontology loader. Maps TBox to legacy format."""
    tbox = load_tbox(conn)
    return {
        "entity_types": [c["name"] for c in tbox.get("classes", [])],
        "edge_types":   [r["name"] for r in tbox.get("relation_types", [])],
        "version":      tbox.get("version", 0),
    }


def save_ontology(conn: sqlite3.Connection, entity_types: list[str],
                  edge_types: list[str]) -> None:
    """Backward-compatible save — converts to TBox format."""
    classes = [{"name": t, "description": "", "aliases": []} for t in entity_types]
    rel_types = [
        {"name": r, "domain": "*", "range": "*", "is_symmetric": False, "is_transitive": False}
        for r in edge_types
    ]
    save_tbox(conn, classes, [], rel_types, [])


# ---------------------------------------------------------------------------
# Relationship Strength (M5) — pre-computed per-entity connection quality
# ---------------------------------------------------------------------------

_REL_STRENGTH_DDL = """
CREATE TABLE IF NOT EXISTS entity_rel_strength (
    entity_id   TEXT PRIMARY KEY REFERENCES entities(id) ON DELETE CASCADE,
    pagerank    REAL DEFAULT 0.0,
    bidir_ratio REAL DEFAULT 0.0,
    avg_confidence REAL DEFAULT 0.0,
    rel_strength REAL DEFAULT 0.0,
    updated_at  TEXT DEFAULT (datetime('now'))
);
"""


def ensure_rel_strength_table(conn: sqlite3.Connection) -> None:
    """Create entity_rel_strength table if it doesn't exist."""
    conn.executescript(_REL_STRENGTH_DDL)


def compute_relationship_strengths(conn: sqlite3.Connection) -> int:
    """Pre-compute per-entity relationship strength scores.

    4-signal composite (design doc M5):
    - PageRank (0.3): from networkx on the relationship graph
    - Bidirectional ratio (0.2): fraction of relationships that are reciprocated
    - Avg confidence (0.2): mean confidence across entity's relationships
    - Degree centrality (0.3): normalized degree in the graph

    Returns count of entities scored.
    """
    try:
        import networkx as nx  # type: ignore
    except ImportError:
        return 0

    ensure_rel_strength_table(conn)

    # Build directed graph from relationships
    edges = conn.execute(
        "SELECT source_id, target_id, confidence FROM relationships"
    ).fetchall()
    if not edges:
        return 0

    G = nx.DiGraph()
    for row in edges:
        G.add_edge(row[0], row[1], confidence=row[2] or 1.0)

    # Compute PageRank
    try:
        pagerank = nx.pagerank(G, alpha=0.85, max_iter=100)
    except nx.PowerIterationFailedConvergence:
        pagerank = {n: 1.0 / G.number_of_nodes() for n in G.nodes()}

    # Normalize PageRank to [0, 1]
    max_pr = max(pagerank.values()) if pagerank else 1.0
    if max_pr > 0:
        pagerank = {k: v / max_pr for k, v in pagerank.items()}

    # Degree centrality (normalized)
    degree_cent = nx.degree_centrality(G)

    # Per-entity: bidirectional ratio and avg confidence
    entity_ids = list(G.nodes())
    records = []
    for eid in entity_ids:
        # Bidirectional ratio
        out_neighbors = set(G.successors(eid))
        in_neighbors = set(G.predecessors(eid))
        total_neighbors = out_neighbors | in_neighbors
        bidir = len(out_neighbors & in_neighbors)
        bidir_ratio = bidir / len(total_neighbors) if total_neighbors else 0.0

        # Avg confidence of connected relationships
        confidences = []
        for _, _, d in G.edges(eid, data=True):
            confidences.append(d.get("confidence", 1.0))
        for _, _, d in G.in_edges(eid, data=True):
            confidences.append(d.get("confidence", 1.0))
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

        pr = pagerank.get(eid, 0.0)
        dc = degree_cent.get(eid, 0.0)

        # 4-signal composite
        strength = 0.3 * pr + 0.2 * bidir_ratio + 0.2 * avg_conf + 0.3 * dc

        records.append((eid, pr, bidir_ratio, avg_conf, strength))

    # Upsert into table
    conn.execute("DELETE FROM entity_rel_strength")
    conn.executemany(
        "INSERT INTO entity_rel_strength (entity_id, pagerank, bidir_ratio, avg_confidence, rel_strength) "
        "VALUES (?, ?, ?, ?, ?)",
        records,
    )
    conn.commit()
    return len(records)


def get_entity_rel_strength(conn: sqlite3.Connection, entity_name: str) -> float:
    """Look up pre-computed relationship strength for an entity by name.

    Returns 0.0 if not found or table doesn't exist.
    """
    try:
        row = conn.execute(
            "SELECT rs.rel_strength FROM entity_rel_strength rs "
            "JOIN entities e ON e.id = rs.entity_id "
            "WHERE e.name = ?",
            (entity_name,),
        ).fetchone()
        return float(row[0]) if row else 0.0
    except sqlite3.OperationalError:
        return 0.0


def get_bulk_rel_strengths(conn: sqlite3.Connection, entity_names: list[str]) -> dict[str, float]:
    """Look up relationship strengths for multiple entities at once.

    Returns dict mapping entity name → strength (0.0 if not found).
    Gracefully returns all zeros if table doesn't exist yet.
    """
    if not entity_names:
        return {}
    result = {name: 0.0 for name in entity_names}
    try:
        placeholders = ",".join("?" * len(entity_names))
        rows = conn.execute(
            f"SELECT e.name, rs.rel_strength FROM entity_rel_strength rs "
            f"JOIN entities e ON e.id = rs.entity_id "
            f"WHERE e.name IN ({placeholders})",
            entity_names,
        ).fetchall()
        for row in rows:
            result[row[0]] = float(row[1])
    except sqlite3.OperationalError:
        pass  # table not yet created
    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="GraphRAG Core — DB init & stats (TBox/ABox)")
    _DEFAULT_DB = str(Path(__file__).resolve().parents[3] / ".team-os/graphrag/index/vault_graph.db")
    parser.add_argument("--db", default=_DEFAULT_DB,
                        help="SQLite DB path (default: PROJECT_DIR/.team-os/graphrag/index/vault_graph.db)")
    parser.add_argument("--stats", action="store_true", help="Print table stats")
    parser.add_argument("--tbox", action="store_true", help="Print TBox definition")
    parser.add_argument("--init-tbox", action="store_true", help="Seed default TBox if empty")
    args = parser.parse_args()

    conn = get_connection(args.db)
    print(f"DB initialized: {args.db}", file=sys.stderr)

    if args.init_tbox:
        ensure_default_tbox(conn)
        print("TBox seeded with default domain ontology.")

    if args.stats:
        stats = get_db_stats(conn)
        for table, count in stats.items():
            print(f"  {table:30s} {count:>8d} rows")

    if args.tbox:
        tbox = load_tbox(conn)
        print(f"\nTBox v{tbox['version']}:")
        print(f"  Classes ({len(tbox['classes'])}): {[c['name'] for c in tbox['classes']]}")
        print(f"  Properties ({len(tbox['properties'])}): {[p['name'] for p in tbox['properties']]}")
        print(f"  Relation types ({len(tbox['relation_types'])}): {[r['name'] for r in tbox['relation_types']]}")
        print(f"  Axioms ({len(tbox['axioms'])}): {[a['id'] for a in tbox['axioms']]}")

    close_connection(conn)
