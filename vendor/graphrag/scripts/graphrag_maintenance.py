"""
graphrag_maintenance.py — bounded post-build hygiene helpers.

Deletes only rotating logs and old sync_log rows. Stale DB-like files are
reported for a separate human-approved deletion pass.
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _sqlite_timestamp(dt: datetime) -> str:
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def prune_sync_log(
    conn: sqlite3.Connection,
    *,
    keep_days: int = 30,
    now: datetime | None = None,
    dry_run: bool = False,
) -> int:
    cutoff = (now or _utc_now()) - timedelta(days=keep_days)
    cutoff_text = _sqlite_timestamp(cutoff)
    if dry_run:
        row = conn.execute(
            "SELECT COUNT(*) FROM sync_log WHERE timestamp < ?",
            (cutoff_text,),
        ).fetchone()
        return int(row[0]) if row else 0
    cur = conn.execute(
        "DELETE FROM sync_log WHERE timestamp < ?",
        (cutoff_text,),
    )
    conn.commit()
    return int(cur.rowcount if cur.rowcount is not None else 0)


def rotate_logs(
    log_dir: str | Path,
    *,
    keep_days: int = 7,
    now: datetime | None = None,
    dry_run: bool = False,
) -> list[str]:
    root = Path(log_dir)
    if not root.exists():
        return []
    cutoff = (now or _utc_now()).timestamp() - (keep_days * 24 * 60 * 60)
    removed: list[str] = []
    for log_file in sorted(root.glob("*.log")):
        try:
            if log_file.stat().st_mtime >= cutoff:
                continue
            removed.append(str(log_file))
            if not dry_run:
                log_file.unlink()
        except FileNotFoundError:
            continue
    return removed


def _graphrag_dir(project_dir: str | Path) -> Path:
    project = Path(project_dir)
    nested = project / ".team-os" / "graphrag"
    return nested if nested.exists() else project


def find_stale_index_files(project_dir: str | Path) -> list[str]:
    graphrag_dir = _graphrag_dir(project_dir)
    index_dir = graphrag_dir / "index"
    candidates: list[Path] = []

    root_db = graphrag_dir / "vault_graph.db"
    if root_db.exists():
        try:
            if root_db.stat().st_size == 0:
                candidates.append(root_db)
        except FileNotFoundError:
            pass

    if index_dir.exists():
        patterns = (
            "vault_graph.bak.work*",
            "vault_graph.db.bak*",
            "vault_graph.db.broken-*",
            "vault_graph.db.corrupted-*",
            "vault_graph.db.empty-*",
            "vault_graph.r2-discarded.db*",
        )
        for pattern in patterns:
            candidates.extend(index_dir.glob(pattern))

    return sorted({str(path) for path in candidates})


def run_maintenance(
    *,
    db_path: str | Path,
    log_dir: str | Path,
    project_dir: str | Path,
    sync_log_days: int = 30,
    log_days: int = 7,
    dry_run: bool = False,
) -> dict[str, object]:
    conn = sqlite3.connect(str(db_path))
    try:
        pruned = prune_sync_log(conn, keep_days=sync_log_days, dry_run=dry_run)
    finally:
        conn.close()
    rotated = rotate_logs(log_dir, keep_days=log_days, dry_run=dry_run)
    stale = find_stale_index_files(project_dir)
    return {
        "sync_log_pruned": pruned,
        "logs_rotated": rotated,
        "stale_index_files_report_only": stale,
        "dry_run": dry_run,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="GraphRAG post-build hygiene")
    parser.add_argument("--db", required=True)
    parser.add_argument("--logs", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--sync-log-days", type=int, default=30)
    parser.add_argument("--log-days", type=int, default=7)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result = run_maintenance(
        db_path=args.db,
        log_dir=args.logs,
        project_dir=args.project,
        sync_log_days=args.sync_log_days,
        log_days=args.log_days,
        dry_run=args.dry_run,
    )
    print(f"sync_log_pruned={result['sync_log_pruned']}")
    print(f"logs_rotated={len(result['logs_rotated'])}")
    for path in result["logs_rotated"]:
        print(f"  rotated: {path}")
    stale = result["stale_index_files_report_only"]
    print(f"stale_index_files_report_only={len(stale)}")
    for path in stale:
        print(f"  stale: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
