"""
embedding_index.py — Local semantic embedding index for Obsidian vault notes.

Build:  python embedding_index.py build --vault /path --db /path --output /path
Search: python embedding_index.py search --query "text" --output /path --top-k 20

No LLM API calls. All local computation via sentence-transformers.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
import yaml

# ---------------------------------------------------------------------------
# Model identity — change this string if you swap the embedding model.
# A mismatch with the stored value in embedding_meta.json triggers a full
# rebuild so cached vectors are never mixed with embeddings from a different
# model.
# ---------------------------------------------------------------------------
# 2026-06-16 (코난 autoresearch R-E1): env-configurable for isolated embedding bake-off.
# Default unchanged = no live behavior change. Build a separate --output index with a
# new model via GRAPHRAG_EMBED_MODEL, benchmark on a test port, swap only if it wins.
MODEL_NAME = os.environ.get("GRAPHRAG_EMBED_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")

# ---------------------------------------------------------------------------
# Lazy model loader (avoids slow import at module level when not needed)
# ---------------------------------------------------------------------------
_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer  # type: ignore

        device = os.environ.get("GRAPHRAG_EMBED_DEVICE", "").strip()
        model_kwargs = {"device": device} if device else {}
        _model = SentenceTransformer(MODEL_NAME, **model_kwargs)
    return _model


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Return (frontmatter_dict, body_without_frontmatter)."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    yaml_block = text[3:end].strip()
    body = text[end + 4:].lstrip("\n")
    try:
        fm = yaml.safe_load(yaml_block) or {}
    except yaml.YAMLError:
        fm = {}
    return fm if isinstance(fm, dict) else {}, body


def _extract_tags(fm: dict[str, Any]) -> list[str]:
    raw = fm.get("tags", [])
    if isinstance(raw, str):
        return [t.strip() for t in re.split(r"[,\s]+", raw) if t.strip()]
    if isinstance(raw, list):
        out: list[str] = []
        for item in raw:
            if isinstance(item, str):
                out.extend(t.strip() for t in re.split(r"[,\s]+", item) if t.strip())
        return out
    return []


def _note_text(note_path: Path, vault_path: Path) -> tuple[str, list[str], str]:
    """Return (title, tags, combined_text) for a single note."""
    try:
        raw = note_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return note_path.stem, [], note_path.stem

    fm, body = _parse_frontmatter(raw)
    title = fm.get("title") or note_path.stem
    tags = _extract_tags(fm)
    content_snippet = body[:500]
    combined = f"{title} {' '.join(tags)} {content_snippet}".strip()
    return title, tags, combined


_JSON_SAFE_SCALARS = (str, int, float, bool)
_SMALL_VECTOR_MAX_ITEMS = 4096


def _to_json_safe(value: Any) -> Any:
    """Convert numpy/raw binary values before they reach json.dumps."""
    if isinstance(value, np.ndarray):
        if value.size <= _SMALL_VECTOR_MAX_ITEMS:
            return value.tolist()
        contiguous = np.ascontiguousarray(value)
        return {
            "encoding": "base64",
            "dtype": str(contiguous.dtype),
            "shape": list(contiguous.shape),
            "data": base64.b64encode(contiguous.tobytes()).decode("ascii"),
        }
    if isinstance(value, (bytes, bytearray, memoryview)):
        return base64.b64encode(bytes(value)).decode("ascii")
    if isinstance(value, dict):
        return {str(k): _to_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_json_safe(v) for v in value]
    if value is None:
        return ""
    if isinstance(value, _JSON_SAFE_SCALARS):
        return value
    return str(value)


def _assert_json_safe(value: Any, path: str = "$") -> None:
    """Schema gate for embedding metadata JSON payloads."""
    assert isinstance(value, (list, str, int, float, dict, bool)), (
        f"Non JSON-safe value at {path}: {type(value).__name__}"
    )
    if isinstance(value, dict):
        for key, nested in value.items():
            assert isinstance(key, str), f"Non-string JSON key at {path}: {type(key).__name__}"
            _assert_json_safe(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _assert_json_safe(nested, f"{path}[{index}]")


# ---------------------------------------------------------------------------
# build_index
# ---------------------------------------------------------------------------

def build_index(vault_path: str, db_path: str, output_dir: str) -> None:
    """
    Scan all .md files in vault_path, generate embeddings, and save index.

    Args:
        vault_path: Root directory of the Obsidian vault.
        db_path:    Path to the SQLite DB (used only for path context; not read here).
        output_dir: Directory where embeddings.npy and embedding_meta.json are saved.
    """
    vault = Path(vault_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    embeddings_file = out / "embeddings.npy"
    meta_file = out / "embedding_meta.json"

    # Load existing metadata (for incremental support)
    existing_meta: dict[str, dict[str, Any]] = {}
    existing_embeddings: dict[str, list[float]] = {}

    if meta_file.exists() and embeddings_file.exists():
        try:
            raw_meta = json.loads(meta_file.read_text())
            # Support both old format (bare list) and new format (dict with "model" key)
            if isinstance(raw_meta, dict):
                stored_model = raw_meta.get("model", "")
                stored_notes: list[dict[str, Any]] = raw_meta.get("notes", [])
            else:
                stored_model = ""
                stored_notes = raw_meta  # legacy bare-list format

            if stored_model != MODEL_NAME:
                print(
                    f"[embedding_index] WARNING: stored model '{stored_model}' != "
                    f"current model '{MODEL_NAME}'. Forcing full rebuild.",
                    flush=True,
                )
                # Leave existing_meta / existing_embeddings empty → full rebuild
            else:
                stored_vectors: np.ndarray = np.load(str(embeddings_file))
                for i, entry in enumerate(stored_notes):
                    key = entry.get("note_path", "")
                    existing_meta[key] = entry
                    if i < len(stored_vectors):
                        existing_embeddings[key] = stored_vectors[i].tolist()
        except Exception:
            existing_meta = {}
            existing_embeddings = {}

    # Scan all markdown files — exclude rule in vault_filter.py (single source of truth)
    from vault_filter import walk_vault_md
    md_files = sorted(walk_vault_md(vault))
    print(f"[embedding_index] Found {len(md_files)} .md files in {vault}", flush=True)

    texts_to_encode: list[str] = []
    new_entries: list[dict[str, Any]] = []

    final_meta: list[dict[str, Any]] = []
    final_vectors: list[list[float]] = []

    for md in md_files:
        rel = str(md.relative_to(vault))
        mtime = md.stat().st_mtime

        if rel in existing_meta and existing_meta[rel].get("mtime") == mtime:
            # Unchanged — reuse cached embedding
            final_meta.append(existing_meta[rel])
            final_vectors.append(existing_embeddings[rel])
            continue

        title, tags, combined = _note_text(md, vault)
        entry = {
            "note_path": rel,
            "title": title,
            "tags": tags,
            "mtime": mtime,
        }
        new_entries.append(entry)
        texts_to_encode.append(combined)

    if texts_to_encode:
        model = _get_model()
        print(
            f"[embedding_index] Encoding {len(texts_to_encode)} new/changed notes…",
            flush=True,
        )
        new_vectors: np.ndarray = model.encode(
            texts_to_encode,
            batch_size=int(os.environ.get("GRAPHRAG_EMBED_BATCH", "64")),
            show_progress_bar=True,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        for entry, vec in zip(new_entries, new_vectors):
            final_meta.append(entry)
            final_vectors.append(vec.tolist())
    else:
        print("[embedding_index] All notes up-to-date; nothing to re-encode.", flush=True)

    # Save — meta is stored as {"model": "...", "notes": [...]} so a future model
    # change is detected immediately on the next build run.
    np.save(str(embeddings_file), np.array(final_vectors, dtype=np.float32))
    meta_payload = {"model": MODEL_NAME, "notes": final_meta}
    meta_file.write_text(json.dumps(meta_payload, ensure_ascii=False, indent=2))

    print(
        f"[embedding_index] Index saved: {len(final_meta)} notes → {embeddings_file}",
        flush=True,
    )


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

LoadedIndex = tuple[np.ndarray, list[dict[str, Any]]]


def load_index(output_dir: str) -> LoadedIndex:
    """Load note embedding vectors and metadata once for reuse by the search server."""
    out = Path(output_dir)
    embeddings_file = out / "embeddings.npy"
    meta_file = out / "embedding_meta.json"

    if not embeddings_file.exists() or not meta_file.exists():
        raise FileNotFoundError(
            f"Index not found in {output_dir}. Run `build` first."
        )

    vectors: np.ndarray = np.load(str(embeddings_file))  # (N, 384)
    raw_meta = json.loads(meta_file.read_text())
    meta: list[dict[str, Any]] = (
        raw_meta.get("notes", []) if isinstance(raw_meta, dict) else raw_meta
    )
    return vectors, meta


def _rank_loaded_index(
    query: str,
    loaded_index: LoadedIndex,
    top_k: int,
) -> list[tuple[dict[str, Any], float]]:
    vectors, meta = loaded_index
    k = min(top_k, len(vectors), len(meta))
    if k <= 0:
        return []

    model = _get_model()
    q_vec: np.ndarray = model.encode(
        [query],
        convert_to_numpy=True,
        normalize_embeddings=True,
    )[0]

    scores: np.ndarray = vectors @ q_vec
    top_indices = np.argpartition(scores, -k)[-k:]
    top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]
    return [(meta[idx], float(scores[idx])) for idx in top_indices]


def search_loaded(query: str, loaded_index: LoadedIndex, top_k: int = 20) -> list[dict[str, Any]]:
    """Search a preloaded note embedding index."""
    return [
        {
            "note_path": entry.get("note_path", ""),
            "title": entry.get("title", ""),
            "score": score,
        }
        for entry, score in _rank_loaded_index(query, loaded_index, top_k)
    ]


def search(query: str, output_dir: str, top_k: int = 20) -> list[dict[str, Any]]:
    """
    Search the embedding index for notes similar to query.

    Args:
        query:      Natural-language search string.
        output_dir: Directory containing embeddings.npy and embedding_meta.json.
        top_k:      Number of top results to return.

    Returns:
        List of dicts with keys: note_path, title, score (float, 0–1).
    """
    return search_loaded(query, load_index(output_dir), top_k=top_k)


# ---------------------------------------------------------------------------
# Entity-level Embedding (GraphRAG entities → vector index)
# ---------------------------------------------------------------------------

ENTITY_EMBEDDINGS_FILE = "entity_embeddings.npy"
ENTITY_META_FILE = "entity_meta.json"


def build_entity_index(db_path: str, output_dir: str) -> None:
    """Build embedding index from GraphRAG entities table.

    Creates entity_embeddings.npy + entity_meta.json alongside the note-level index.
    Each entity is embedded as: "{name} {description}".
    """
    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        # Truncate at the DB read so pathological entity text never enters Python
        # and blows up the embedder. An extraction bug produced ~15 entities whose
        # name field is up to ~111MB; with no cap, one such string detonates the
        # bge-m3 tokenizer/attention memory (OOM). p99 entity text = 81 chars, so
        # a 2000-char cap is a no-op for real entities and only clips the garbage.
        "SELECT id, substr(name,1,2000) AS name, "
        "substr(COALESCE(name_ko,''),1,500) AS name_ko, "
        "substr(COALESCE(description,''),1,2000) AS description, "
        "COALESCE(source_note,'') AS source_note, type "
        "FROM entities"
    ).fetchall()
    conn.close()

    if not rows:
        print("[embedding_index] No entities found in DB. Skipping entity index.", flush=True)
        return

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    entity_emb_file = out / ENTITY_EMBEDDINGS_FILE
    entity_meta_file = out / ENTITY_META_FILE

    texts = []
    meta_entries = []
    for row in rows:
        text = f"{row['name']} {row['name_ko']} {row['description']}".strip()
        texts.append(text)
        meta_entries.append(_to_json_safe({
            "id": row["id"],
            "name": row["name"],
            "type": row["type"],
            "source_note": row["source_note"],
        }))

    print(f"[embedding_index] Encoding {len(texts)} entities…", flush=True)
    model = _get_model()
    vectors = model.encode(
        texts,
        batch_size=int(os.environ.get("GRAPHRAG_EMBED_BATCH", "64")),
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    np.save(str(entity_emb_file), vectors.astype(np.float32))
    payload = _to_json_safe({"model": MODEL_NAME, "entities": meta_entries})
    _assert_json_safe(payload)
    entity_meta_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"[embedding_index] Entity index: {len(meta_entries)} entities → {entity_emb_file}", flush=True)


def load_entity_index(output_dir: str) -> LoadedIndex | None:
    """Load entity embedding vectors and metadata once; return None when absent."""
    out = Path(output_dir)
    entity_emb_file = out / ENTITY_EMBEDDINGS_FILE
    entity_meta_file = out / ENTITY_META_FILE

    # v2.3.3: partial index 보호 — emb 파일 있는데 meta 파일 없는 case 안 graceful (CLI / 직접 호출 보호)
    if not entity_emb_file.exists() or not entity_meta_file.exists():
        return None

    vectors = np.load(str(entity_emb_file))
    raw_meta = json.loads(entity_meta_file.read_text(encoding="utf-8"))
    meta = raw_meta.get("entities", raw_meta) if isinstance(raw_meta, dict) else raw_meta
    return vectors, meta


def search_entities_loaded(
    query: str,
    loaded_index: LoadedIndex | None,
    top_k: int = 20,
) -> list[dict[str, Any]]:
    """Semantic search over a preloaded entity embedding index."""
    if loaded_index is None:
        return []
    return [
        {**entry, "score": score}
        for entry, score in _rank_loaded_index(query, loaded_index, top_k)
    ]


def search_entities(query: str, output_dir: str, top_k: int = 20) -> list[dict[str, Any]]:
    """Semantic search over entity embeddings. Returns [{id, name, type, source_note, score}]."""
    return search_entities_loaded(query, load_entity_index(output_dir), top_k=top_k)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cmd_build(args: argparse.Namespace) -> None:
    build_index(
        vault_path=args.vault,
        db_path=args.db,
        output_dir=args.output,
    )


def _cmd_search(args: argparse.Namespace) -> None:
    results = search(
        query=args.query,
        output_dir=args.output,
        top_k=args.top_k,
    )
    print(json.dumps(results, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Local embedding index for Obsidian vault notes."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # --- build ---
    p_build = sub.add_parser("build", help="Build (or update) the embedding index.")
    p_build.add_argument("--vault", required=True, help="Obsidian vault root path.")
    p_build.add_argument(
        "--db",
        default="",
        help="Path to graphrag SQLite DB (optional; used for context only).",
    )
    p_build.add_argument(
        "--output",
        default=".team-os/graphrag/index",
        help="Output directory for index files.",
    )
    p_build.set_defaults(func=_cmd_build)

    # --- search ---
    p_search = sub.add_parser("search", help="Query the embedding index.")
    p_search.add_argument("--query", required=True, help="Search string.")
    p_search.add_argument(
        "--output",
        default=".team-os/graphrag/index",
        help="Directory containing the index files.",
    )
    p_search.add_argument("--top-k", type=int, default=20, help="Number of results.")
    p_search.set_defaults(func=_cmd_search)

    # --- build-entities ---
    p_bent = sub.add_parser("build-entities", help="Build entity embedding index from GraphRAG DB.")
    p_bent.add_argument("--db", required=True, help="Path to vault_graph.db.")
    p_bent.add_argument("--output", default=".team-os/graphrag/index", help="Output directory.")
    p_bent.set_defaults(func=lambda a: build_entity_index(a.db, a.output))

    # --- search-entities ---
    p_sent = sub.add_parser("search-entities", help="Semantic search over entity embeddings.")
    p_sent.add_argument("--query", required=True, help="Search string.")
    p_sent.add_argument("--output", default=".team-os/graphrag/index", help="Index directory.")
    p_sent.add_argument("--top-k", type=int, default=20, help="Number of results.")
    p_sent.set_defaults(func=lambda a: print(json.dumps(search_entities(a.query, a.output, a.top_k), ensure_ascii=False, indent=2)))

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
