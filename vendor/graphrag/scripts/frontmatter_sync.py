"""
frontmatter_sync.py — Bidirectional sync between GraphRAG DB and Obsidian frontmatter
Python 3.12 compatible

3 managed fields: graph_entity, graph_community, graph_connections
DB is the source of truth; user manual additions are preserved.
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

import yaml

from graphrag_core import (
    get_connection,
    close_connection,
    compute_frontmatter_hash,
)

_PROJECT_DIR = Path(__file__).resolve().parents[3]
_DEFAULT_DB = str(_PROJECT_DIR / ".team-os/graphrag/index/vault_graph.db")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GRAPH_FIELDS = {"graph_entity", "graph_community", "graph_connections"}
BATCH_SIZE = 100
BATCH_DELAY_SEC = 2
MAX_CONNECTIONS_DISPLAY = 5
MAX_GRAPH_ENTITY_CHARS = 200
MAX_GRAPH_CONNECTION_CHARS = 240
_ESCAPE_SEQUENCE_RE = re.compile(r"\\\\|\\[nrt]|\\x[0-9A-Fa-f]{2}|\\u[0-9A-Fa-f]{4}")
_GRAPH_CONNECTION_RE = re.compile(r"^(.+?)\s*\((\w+)\)\s*$")


# ---------------------------------------------------------------------------
# Frontmatter parsing helpers
# ---------------------------------------------------------------------------

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body_text). body_text excludes the YAML block."""
    m = _FM_RE.match(content)
    if not m:
        return {}, content
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        fm = {}
    body = content[m.end():]
    return fm, body


def _serialize_frontmatter(fm: dict) -> str:
    """Render frontmatter dict back to YAML block."""
    return "---\n" + yaml.dump(fm, allow_unicode=True, sort_keys=False, default_flow_style=False) + "---\n"


def _rebuild_content(fm: dict, body: str) -> str:
    if not fm:
        return body
    return _serialize_frontmatter(fm) + body


def _is_safe_graph_entity_name(name: str) -> bool:
    if not isinstance(name, str):
        return False
    if not name:
        return False
    if len(name) > MAX_GRAPH_ENTITY_CHARS:
        return False
    if "\n" in name or "\r" in name:
        return False
    if _ESCAPE_SEQUENCE_RE.search(name):
        return False
    return True


def _is_safe_graph_connection(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    if len(value) > MAX_GRAPH_CONNECTION_CHARS:
        return False
    if "\n" in value or "\r" in value:
        return False
    if _ESCAPE_SEQUENCE_RE.search(value):
        return False
    m = _GRAPH_CONNECTION_RE.match(value.strip())
    if not m:
        return False
    target_name, rel_type = m.group(1).strip(), m.group(2).strip()
    return _is_safe_graph_entity_name(target_name) and bool(rel_type)


def _sanitize_graph_connections(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [value.strip() for value in values if _is_safe_graph_connection(value)]


def _extract_aliases(fm: dict[str, Any]) -> list[str]:
    """Extract safe Obsidian frontmatter aliases."""
    raw = fm.get("aliases", [])
    if isinstance(raw, str):
        candidates = [raw]
    elif isinstance(raw, list):
        candidates = [item for item in raw if isinstance(item, str)]
    else:
        candidates = []

    aliases: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        alias = candidate.strip()
        if alias in seen:
            continue
        if not _is_safe_graph_entity_name(alias):
            continue
        aliases.append(alias)
        seen.add(alias)
    return aliases


def _find_entity_id_for_note_name(conn: sqlite3.Connection, note_path: str) -> str | None:
    """Find the entity whose name matches the Obsidian note stem."""
    note_name = Path(note_path).stem
    row = conn.execute(
        """
        SELECT id
          FROM entities
         WHERE name = ?
         ORDER BY
           CASE
             WHEN source_note = ? THEN 0
             WHEN source_note IS NULL OR source_note = '' THEN 1
             ELSE 2
           END,
           COALESCE(centrality_score, 0) DESC
         LIMIT 1
        """,
        (note_name, note_path),
    ).fetchone()
    return row["id"] if row else None


def _sync_frontmatter_aliases_to_db(
    conn: sqlite3.Connection,
    note_path: str,
    fm: dict[str, Any],
) -> bool:
    """Refresh frontmatter aliases for one note/entity."""
    entity_id = _find_entity_id_for_note_name(conn, note_path)
    if entity_id is None:
        return False

    existing = conn.execute(
        """
        SELECT COUNT(*)
          FROM entity_aliases
         WHERE entity_id = ? AND alias_type = 'frontmatter'
        """,
        (entity_id,),
    ).fetchone()[0]
    aliases = _extract_aliases(fm)

    conn.execute(
        "DELETE FROM entity_aliases WHERE entity_id = ? AND alias_type = 'frontmatter'",
        (entity_id,),
    )
    conn.executemany(
        """
        INSERT OR IGNORE INTO entity_aliases(entity_id, alias_name, alias_type)
        VALUES (?, ?, 'frontmatter')
        """,
        [(entity_id, alias) for alias in aliases],
    )
    conn.commit()
    return bool("aliases" in fm or existing or aliases)


# ---------------------------------------------------------------------------
# DB → frontmatter field builders
# ---------------------------------------------------------------------------

def _build_graph_entity_field(conn: sqlite3.Connection, note_path: str) -> str | None:
    """Return the primary entity name for this note, or None."""
    row = conn.execute(
        "SELECT name FROM entities WHERE source_note = ? ORDER BY centrality_score DESC LIMIT 1",
        (note_path,),
    ).fetchone()
    return row["name"] if row else None


def _build_graph_community_field(conn: sqlite3.Connection, note_path: str) -> str | None:
    """Return the community name for the primary entity of this note."""
    row = conn.execute(
        """SELECT c.name FROM entities e
           JOIN communities c ON e.community_id = c.id
           WHERE e.source_note = ?
           ORDER BY e.centrality_score DESC LIMIT 1""",
        (note_path,),
    ).fetchone()
    return row["name"] if row else None


def _build_graph_connections_field(
    conn: sqlite3.Connection,
    note_path: str,
    max_connections: int = MAX_CONNECTIONS_DISPLAY,
) -> list[str]:
    """Return top-N typed connections: ['EntityName (rel_type)', ...]."""
    rows = conn.execute(
        """SELECT e2.name AS target_name, r.type AS rel_type, r.strength
           FROM entities e1
           JOIN relationships r ON r.source_id = e1.id
           JOIN entities e2 ON r.target_id = e2.id
           WHERE e1.source_note = ?
           UNION
           SELECT e1.name AS target_name, r.type AS rel_type, r.strength
           FROM entities e2
           JOIN relationships r ON r.target_id = e2.id
           JOIN entities e1 ON r.source_id = e1.id
           WHERE e2.source_note = ?
           ORDER BY strength DESC LIMIT ?""",
        (note_path, note_path, max_connections * 10),
    ).fetchall()
    values: list[str] = []
    for row in rows:
        value = f"{row['target_name']} ({row['rel_type']})"
        if _is_safe_graph_connection(value):
            values.append(value)
        if len(values) >= max_connections:
            break
    return values


# ---------------------------------------------------------------------------
# Conflict resolution
# ---------------------------------------------------------------------------

def resolve_conflict(
    db_value: Any,
    fm_value: Any,
    source: str | None,
) -> Any:
    """
    DB is the source of truth.
    If source == 'user' (manually added), preserve manual additions.
    For lists (connections), union DB list with user additions.
    """
    if source == "system_update":
        # Ignore system-written values — DB wins
        return db_value

    if isinstance(db_value, list) and isinstance(fm_value, list):
        # Preserve user additions not in DB list
        extra = [v for v in fm_value if v not in db_value]
        return db_value + extra

    # Scalar: DB wins
    return db_value


# ---------------------------------------------------------------------------
# DB → frontmatter sync
# ---------------------------------------------------------------------------

def sync_graph_to_frontmatter(
    conn: sqlite3.Connection,
    vault_path: str | Path,
    dry_run: bool = True,
) -> dict[str, int]:
    """
    Sync graph DB fields → Obsidian note frontmatter.
    Processes in batches of 100, 2-second delay between batches.

    Returns: {"updated": int, "skipped": int, "errors": int}
    """
    vault = Path(vault_path)
    stats = {"updated": 0, "skipped": 0, "errors": 0}

    # Get all notes that have graph data
    notes = [
        dict(row)
        for row in conn.execute(
            "SELECT note_path, frontmatter_hash FROM note_graph_state WHERE graph_synced = 0 OR graph_synced IS NULL"
        )
    ]

    for batch_start in range(0, len(notes), BATCH_SIZE):
        batch = notes[batch_start: batch_start + BATCH_SIZE]

        for note_state in batch:
            note_path = note_state["note_path"]
            abs_path = vault / note_path if not Path(note_path).is_absolute() else Path(note_path)

            if not abs_path.exists():
                stats["skipped"] += 1
                continue

            try:
                content = abs_path.read_text(encoding="utf-8")
                fm, body = _parse_frontmatter(content)

                # Build DB values
                db_entity = _build_graph_entity_field(conn, note_path)
                db_community = _build_graph_community_field(conn, note_path)
                db_connections = _build_graph_connections_field(conn, note_path)

                if db_entity is None and not db_connections:
                    stats["skipped"] += 1
                    continue

                # Resolve conflicts
                new_fm = dict(fm)
                if db_entity is not None:
                    new_fm["graph_entity"] = resolve_conflict(
                        db_entity, fm.get("graph_entity"), source=None
                    )
                if db_community is not None:
                    new_fm["graph_community"] = resolve_conflict(
                        db_community, fm.get("graph_community"), source=None
                    )
                if db_connections:
                    new_fm["graph_connections"] = resolve_conflict(
                        db_connections, fm.get("graph_connections", []), source=None
                    )
                    new_fm["graph_connections"] = _sanitize_graph_connections(
                        new_fm["graph_connections"]
                    )

                # Check if frontmatter actually changed
                new_fm_hash = compute_frontmatter_hash(new_fm)
                if new_fm_hash == note_state.get("frontmatter_hash"):
                    stats["skipped"] += 1
                    continue

                if not dry_run:
                    new_content = _rebuild_content(new_fm, body)
                    abs_path.write_text(new_content, encoding="utf-8")

                    # Update state — mark as synced with new hash
                    conn.execute(
                        """UPDATE note_graph_state
                           SET frontmatter_hash = ?, graph_synced = 1
                           WHERE note_path = ?""",
                        (new_fm_hash, note_path),
                    )
                    conn.execute(
                        """INSERT INTO sync_log (operation, note_path, status, source)
                           VALUES ('fm_sync_db_to_fm', ?, 'done', 'system_update')""",
                        (note_path,),
                    )
                    conn.commit()

                stats["updated"] += 1

            except Exception as e:
                stats["errors"] += 1
                # Log but continue
                try:
                    conn.execute(
                        """INSERT INTO sync_log (operation, note_path, status, source)
                           VALUES ('fm_sync_db_to_fm', ?, 'error', ?)""",
                        (note_path, str(e)),
                    )
                    conn.commit()
                except Exception:
                    pass

        # Batch delay (skip if last batch)
        if batch_start + BATCH_SIZE < len(notes):
            time.sleep(BATCH_DELAY_SEC)

    return stats


# ---------------------------------------------------------------------------
# frontmatter → DB sync
# ---------------------------------------------------------------------------

def sync_frontmatter_to_graph(
    conn: sqlite3.Connection,
    vault_path: str | Path,
) -> dict[str, int]:
    """
    Sync user-edited frontmatter → graph DB.
    Ignores entries with source='system_update' (not user edits).
    Returns: {"processed": int, "errors": int}
    """
    vault = Path(vault_path)
    stats = {"processed": 0, "errors": 0}

    # Exclude rule — single source of truth in vault_filter.py
    from vault_filter import walk_vault_md
    for md_file in walk_vault_md(vault):
        rel_path = str(md_file.relative_to(vault))

        # Skip if last sync was by system
        last_sync = conn.execute(
            """SELECT source FROM sync_log
               WHERE note_path = ? AND operation = 'fm_sync_db_to_fm'
               ORDER BY id DESC LIMIT 1""",
            (rel_path,),
        ).fetchone()

        if last_sync and last_sync["source"] == "system_update":
            # Check if file changed since last system write
            state = conn.execute(
                "SELECT frontmatter_hash FROM note_graph_state WHERE note_path = ?",
                (rel_path,),
            ).fetchone()

            try:
                content = md_file.read_text(encoding="utf-8")
                fm, _ = _parse_frontmatter(content)
                current_hash = compute_frontmatter_hash(fm)
                if state and state["frontmatter_hash"] == current_hash:
                    if _sync_frontmatter_aliases_to_db(conn, rel_path, fm):
                        stats["processed"] += 1
                    continue  # No user edits since last system write
            except Exception:
                continue

        try:
            content = md_file.read_text(encoding="utf-8")
            fm, _ = _parse_frontmatter(content)
            aliases_processed = _sync_frontmatter_aliases_to_db(conn, rel_path, fm)

            graph_fields = {k: fm[k] for k in GRAPH_FIELDS if k in fm}
            if not graph_fields:
                if aliases_processed:
                    stats["processed"] += 1
                continue

            # Push user-added connections back to DB
            if "graph_connections" in graph_fields:
                _sync_user_connections_to_db(conn, rel_path, graph_fields["graph_connections"])

            stats["processed"] += 1

        except Exception as e:
            stats["errors"] += 1

    return stats


def _sync_user_connections_to_db(
    conn: sqlite3.Connection,
    note_path: str,
    connections: list[str],
) -> None:
    """Parse user-added connections and ensure entities/relationships exist in DB."""
    import uuid

    source_row = conn.execute(
        "SELECT id FROM entities WHERE source_note = ? LIMIT 1", (note_path,)
    ).fetchone()
    if source_row is None:
        return

    source_id = source_row["id"]
    for conn_str in connections:
        if not _is_safe_graph_connection(conn_str):
            continue
        m = _GRAPH_CONNECTION_RE.match(conn_str.strip())
        if not m:
            continue
        target_name, rel_type = m.group(1).strip(), m.group(2).strip()

        # Ensure target entity exists
        target_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, target_name.lower()))
        conn.execute(
            """INSERT INTO entities (id, name, type) VALUES (?, ?, 'concept')
               ON CONFLICT(id) DO NOTHING""",
            (target_id, target_name),
        )

        # Ensure relationship exists
        rel_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{source_id}:{target_id}:{rel_type}"))
        conn.execute(
            """INSERT INTO relationships (id, source_id, target_id, type, strength, source_note)
               VALUES (?, ?, ?, ?, 0.5, ?)
               ON CONFLICT(id) DO NOTHING""",
            (rel_id, source_id, target_id, rel_type, note_path),
        )

    conn.commit()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Frontmatter ↔ GraphRAG DB sync")
    parser.add_argument("--db", default=_DEFAULT_DB)
    parser.add_argument("--vault", default="<vault>")
    sub = parser.add_subparsers(dest="direction", required=True)

    p_to_fm = sub.add_parser("to-frontmatter", help="DB → frontmatter (default dry-run)")
    p_to_fm.add_argument("--apply", action="store_true", help="Actually write files (default: dry-run)")

    sub.add_parser("to-db", help="frontmatter → DB (user edits)")

    args = parser.parse_args()
    conn = get_connection(args.db)

    if args.direction == "to-frontmatter":
        dry_run = not args.apply
        result = sync_graph_to_frontmatter(conn, args.vault, dry_run=dry_run)
        mode = "DRY RUN" if dry_run else "APPLIED"
        print(f"[{mode}] updated={result['updated']}, skipped={result['skipped']}, errors={result['errors']}")
    elif args.direction == "to-db":
        result = sync_frontmatter_to_graph(conn, args.vault)
        print(f"processed={result['processed']}, errors={result['errors']}")

    close_connection(conn)
