"""
incremental.py — Incremental update: detect changes, re-extract, sync frontmatter hash
Python 3.12 compatible
"""
from __future__ import annotations

from pathlib import Path as _PathBootstrap
_PROJECT_DIR = _PathBootstrap(__file__).resolve().parents[3]
_DEFAULT_DB = str(_PROJECT_DIR / ".team-os/graphrag/index/vault_graph.db")

import json
import sqlite3
from pathlib import Path
from typing import Any

from graphrag_core import (
    get_connection,
    close_connection,
    compute_content_hash,
    compute_frontmatter_hash,
)

try:
    import yaml
except ImportError:
    raise ImportError("pyyaml not installed. Run: pip install 'pyyaml>=6.0'")

import re

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    m = _FM_RE.match(content)
    if not m:
        return {}, content
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        fm = {}
    return fm, content[m.end():]


# ---------------------------------------------------------------------------
# Change detection
# ---------------------------------------------------------------------------

def detect_changes(
    conn: sqlite3.Connection,
    vault_path: str | Path,
) -> dict[str, list[str]]:
    """
    Compare vault .md files against note_graph_state.
    Returns: {"added": [...], "modified": [...], "deleted": [...]}
    """
    vault = Path(vault_path)
    changes: dict[str, list[str]] = {"added": [], "modified": [], "deleted": []}

    # Build set of all current .md files — exclude rule in vault_filter.py
    from vault_filter import walk_vault_md
    current_files: dict[str, Path] = {}
    for f in walk_vault_md(vault):
        rel = str(f.relative_to(vault))
        current_files[rel] = f

    # Fetch all known states
    known_states: dict[str, str] = {
        row["note_path"]: row["content_hash"]
        for row in conn.execute("SELECT note_path, content_hash FROM note_graph_state")
    }

    for rel_path, abs_path in current_files.items():
        try:
            content = abs_path.read_text(encoding="utf-8")
            fm, body = _parse_frontmatter(content)
            current_hash = compute_content_hash(body, fm)
        except Exception:
            continue

        if rel_path not in known_states:
            changes["added"].append(rel_path)
        elif known_states[rel_path] != current_hash:
            changes["modified"].append(rel_path)

    # Deleted: in DB but not on disk
    for rel_path in known_states:
        if rel_path not in current_files:
            changes["deleted"].append(rel_path)

    return changes


# ---------------------------------------------------------------------------
# Incremental update
# ---------------------------------------------------------------------------

def incremental_update(
    conn: sqlite3.Connection,
    vault_path: str | Path,
    changes: dict[str, list[str]],
    use_llm: bool = False,
) -> dict[str, Any]:
    """
    Process only changed notes:
    - added/modified: re-extract entities + relationships, update state
    - deleted: remove entities sourced from deleted notes

    After each note: immediately update frontmatter_hash to prevent infinite loop.
    """
    from entity_extractor import extract_entities_from_note, save_to_db

    vault = Path(vault_path)
    stats = {"added": 0, "modified": 0, "deleted": 0, "errors": 0}

    # Process added + modified
    for rel_path in changes.get("added", []) + changes.get("modified", []):
        abs_path = vault / rel_path
        if not abs_path.exists():
            stats["errors"] += 1
            continue

        try:
            content = abs_path.read_text(encoding="utf-8")
            fm, body = _parse_frontmatter(content)

            content_hash = compute_content_hash(body, fm)
            fm_hash = compute_frontmatter_hash(fm)

            # Remove old extractions from this note.
            # track① guard (2026-07-15): only delete GENERIC relations so that
            # semantically re-labeled relations (parent/precedes/cites/... from the
            # track① merge) survive incremental re-extraction. Re-extraction still
            # regenerates generic (related_to/mentions) from wikilink rules as before.
            # NOTE: the deleted-note cleanup below (L~182) must stay unguarded —
            # full delete is correct there (guarding it would leave orphan relations).
            conn.execute(
                "DELETE FROM relationships WHERE source_note = ? "
                "AND type IN ('related_to','mentions')",
                (rel_path,),
            )
            # Only remove entities that originated from this note and aren't referenced elsewhere
            conn.execute(
                """DELETE FROM entities WHERE source_note = ?
                   AND id NOT IN (
                       SELECT DISTINCT source_id FROM relationships WHERE source_note != ?
                       UNION
                       SELECT DISTINCT target_id FROM relationships WHERE source_note != ?
                   )""",
                (rel_path, rel_path, rel_path),
            )

            # Re-extract (entities + binary rels + reified N-ary)
            entities, relationships, reified = extract_entities_from_note(
                rel_path, content, use_llm=use_llm
            )
            save_to_db(conn, entities, relationships, rel_path, reified)

            # G6: Immediately update frontmatter_hash to prevent infinite sync loop
            conn.execute(
                """INSERT INTO note_graph_state (note_path, content_hash, frontmatter_hash, graph_synced)
                   VALUES (?, ?, ?, 0)
                   ON CONFLICT(note_path) DO UPDATE SET
                       content_hash     = excluded.content_hash,
                       frontmatter_hash = excluded.frontmatter_hash,
                       last_indexed     = datetime('now'),
                       graph_synced     = 0""",
                (rel_path, content_hash, fm_hash),
            )
            conn.commit()

            if rel_path in changes.get("added", []):
                stats["added"] += 1
            else:
                stats["modified"] += 1

        except Exception as e:
            stats["errors"] += 1
            try:
                conn.execute(
                    "INSERT INTO sync_log (operation, note_path, status, source) VALUES ('incremental_update', ?, 'error', ?)",
                    (rel_path, str(e)),
                )
                conn.commit()
            except Exception:
                pass

    # Process deleted
    for rel_path in changes.get("deleted", []):
        try:
            conn.execute("DELETE FROM relationships WHERE source_note = ?", (rel_path,))
            conn.execute(
                """DELETE FROM entities WHERE source_note = ?
                   AND id NOT IN (
                       SELECT DISTINCT source_id FROM relationships
                       UNION
                       SELECT DISTINCT target_id FROM relationships
                   )""",
                (rel_path,),
            )
            conn.execute("DELETE FROM note_graph_state WHERE note_path = ?", (rel_path,))
            conn.execute(
                "INSERT INTO sync_log (operation, note_path, status, source) VALUES ('delete', ?, 'done', 'incremental')",
                (rel_path,),
            )
            conn.commit()
            stats["deleted"] += 1
        except Exception as e:
            stats["errors"] += 1

    return stats


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Incremental GraphRAG update")
    parser.add_argument("--db", default=_DEFAULT_DB)
    parser.add_argument("--vault", default="<vault>")
    parser.add_argument("--llm", action="store_true", help="Enable LLM extraction")
    parser.add_argument("--dry-run", action="store_true", help="Detect changes only, don't update")
    args = parser.parse_args()

    conn = get_connection(args.db)
    changes = detect_changes(conn, args.vault)

    total_changes = sum(len(v) for v in changes.values())
    print(f"Changes detected: added={len(changes['added'])}, "
          f"modified={len(changes['modified'])}, deleted={len(changes['deleted'])}")

    if args.dry_run or total_changes == 0:
        if total_changes == 0:
            print("No changes. Nothing to do.")
        close_connection(conn)
        sys.exit(0)

    stats = incremental_update(conn, args.vault, changes, use_llm=args.llm)
    print(f"Update complete: {stats}")
    close_connection(conn)
