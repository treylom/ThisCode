"""Vault file filter — central exclude rule for archive/duplicate dirs.

Single source of truth for `vault.rglob("*.md")` filtering across the
GraphRAG ingest pipeline. Edit `EXCLUDE_DIRS` / `EXCLUDE_PREFIXES` here
to change actual ingest behavior in every script.

Why centralized:
- bootstrap.py / entity_extractor.py / embedding_index.py /
  frontmatter_sync.py / incremental.py / repair_search_quality.py all
  walked the vault separately; some had drift (frontmatter_sync,
  incremental had no exclude rule at all). Drift caused archive
  duplicates in the entity index.
- 2026-05-03 vault path duplicate cleanup cycle — see
  `feedback_vault_path_normalization.md` for the full incident.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

# Exact directory names to exclude (any depth)
EXCLUDE_DIRS = {
    "obsidian-ai-vault",        # outer git source root, rsync target
    ".obsidian",                # Obsidian app config
    ".trash",
    ".tmp.drivedownload",
    ".tmp.driveupload",
    "AI_Second_Brain",          # nested duplicate vault copy
    "Second_Brain",             # nested duplicate vault copy
    # 2026-06-16 WSL≠Mac 색인 divergence dedup (재경님 옵션2 GO, meetings/2026-06-16-wsl-mac-index-divergence/).
    # 무번호 parallel = symlink/rsync 분기 (vault-ops §1: 번호철자 020-/090-/010-가 정본).
    # 측정(dup_measure): Library∩020-Library=3434 dup / Resources⊂090-Resources(고유0) / Mine=venv정크20.
    "Library",                  # = 020-Library 중복본 (정본=020-Library; Library 고유 6 Reposts만 collateral)
    "Resources",                # = 090-Resources 부분집합 (unique 손실 0)
    "Mine",                     # = 010-Mine 무번호 (Mine 20개=전부 .venv LICENSE 정크, 실노트 0)
    # build/venv 정크 (어디 depth든) — venv LICENSE/패키지 md 가 노트로 오색인되던 노이즈 차단
    ".venv",
    "node_modules",
    "site-packages",
}

# Directory name prefixes to exclude (e.g. "_archive-2026-04",
# "_archive_per_session_20260412_002123", "_attachments")
EXCLUDE_PREFIXES = (
    "_archive",
    "_attachments",
)


def is_excluded_path(rel_parts: Iterable[str]) -> bool:
    """True if any path part matches an exclude rule (set or prefix)."""
    for part in rel_parts:
        if part in EXCLUDE_DIRS:
            return True
        if any(part.startswith(prefix) for prefix in EXCLUDE_PREFIXES):
            return True
    return False


def filter_md_files(md_files: Iterable[Path], vault: Path) -> list[Path]:
    """Filter list of .md Path objects, excluding archive/duplicate dirs
    and unresolvable entries (broken symlinks)."""
    out: list[Path] = []
    for f in md_files:
        try:
            rel = f.relative_to(vault)
        except ValueError:
            continue
        if is_excluded_path(rel.parts):
            continue
        # The vault is a symlink farm (Obsidian /search exposure); rglob yields
        # dangling symlinks by name. Skip anything that doesn't resolve so a
        # single broken link can't abort a consumer's whole index build.
        try:
            if not f.exists():
                continue
        except OSError:
            continue
        out.append(f)
    return out


# Filename substrings marking a content-duplicate copy. Pair-safe: dropped ONLY
# when the canonical twin (same name without the marker) is also present.
DUP_FILENAME_MARKERS = (" (zet-version)",)


def _drop_dup_twins(files: list[Path], vault: Path) -> list[Path]:
    """Set-based dedup pass applied AFTER dir/prefix filtering (2026-06-16 WSL≠Mac
    색인 divergence dedup — meetings/2026-06-16-wsl-mac-index-divergence/).
    Both rules are safe-by-construction (never drop a unique note):
      (a) "(zet-version)" filename copies dropped IFF the canonical twin
          (same path without the marker) is also in the kept set.
      (b) "Tofu_Wiki/<inner>" dropped IFF "<inner>" exists as a non-Tofu_Wiki note
          (Tofu_Wiki mirror of another dir). Tofu_Wiki-unique notes are kept.
    Canonical = the non-marker / non-Tofu_Wiki copy (matches Mac index = Tofu_Wiki 0)."""
    rel = {str(f.relative_to(vault)): f for f in files}
    relset = set(rel)
    out: list[Path] = []
    for r, f in rel.items():
        # (a) zet-version pair-safe drop
        if any(m in r and r.replace(m, "") in relset for m in DUP_FILENAME_MARKERS):
            continue
        # (b) Tofu_Wiki mirror drop (twin exists outside Tofu_Wiki)
        if r.startswith("Tofu_Wiki/") and r[len("Tofu_Wiki/"):] in relset:
            continue
        out.append(f)
    return out


def walk_vault_md(vault: Path) -> list[Path]:
    """Walk vault for .md files with exclude rule applied. Most common entry point."""
    return _drop_dup_twins(filter_md_files(vault.rglob("*.md"), vault), vault)
