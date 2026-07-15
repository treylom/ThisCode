"""
entity_extractor.py — Entity/relationship extraction from vault notes

Theory-based enhancements:
  1. Binary relations (typed wikilinks, tag→belongs_to) — preserved
  2. N-ary relation detection + Reification (event node creation)
     Ref: 메타엣지-하이퍼그래프-구현.md §5.17 (Reification pattern)
  3. Named Graph context: confidence + extracted_date on each relation
  4. Obsidian shared tags → hyperedge cluster seed (co_occurs edges)
  5. LLM placeholders include N-ary prompts
Python 3.12 compatible
"""
from __future__ import annotations

from pathlib import Path as _Path
_PROJECT_DIR = _Path(__file__).resolve().parents[3]
_DEFAULT_DB = str(_PROJECT_DIR / ".team-os/graphrag/index/vault_graph.db")

import glob as _glob
import hashlib
import json
import os
import re
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from graphrag_core import get_connection, close_connection


# ---------------------------------------------------------------------------
# Vault note resolution helper (cached — single NTFS scan at init)
# ---------------------------------------------------------------------------

# Vault root for resolving wikilink targets to actual note files
_VAULT_ROOT = os.environ.get("VAULT_ROOT", "<vault>")

# Pre-built lookup: note stem (filename without .md) → relative path
# Lazily initialized on first call to _resolve_note_path
_NOTE_PATH_CACHE: dict[str, str] | None = None
# Exclude rule — single source of truth in vault_filter.py
from vault_filter import walk_vault_md


def _build_note_path_cache(md_files: list[Path] | None = None) -> dict[str, str]:
    """Build stem→relative_path lookup. Accepts pre-scanned file list to avoid double NTFS scan."""
    global _NOTE_PATH_CACHE
    cache: dict[str, str] = {}
    vault = Path(_VAULT_ROOT)

    if md_files is None:
        # Fallback: scan vault (slow on NTFS)
        md_files = walk_vault_md(vault)

    for md in md_files:
        try:
            rel = md.relative_to(vault)
        except ValueError:
            continue
        stem = md.stem
        if stem not in cache:
            cache[stem] = str(rel)
    _NOTE_PATH_CACHE = cache
    return cache


def set_note_path_cache(md_files: list[Path]) -> None:
    """Pre-populate cache from an external file list (e.g., from bootstrap scan)."""
    _build_note_path_cache(md_files)


def _resolve_note_path(entity_name: str) -> str | None:
    """O(1) lookup from pre-built cache. Falls back to None if not found."""
    global _NOTE_PATH_CACHE
    if _NOTE_PATH_CACHE is None:
        _build_note_path_cache()
    return _NOTE_PATH_CACHE.get(entity_name)


# ---------------------------------------------------------------------------
# Type definitions
# ---------------------------------------------------------------------------

Entity = dict[str, Any]                # id, name, name_ko, type, description, source_note
Relationship = dict[str, Any]          # id, source_id, target_id, type, strength, evidence_text,
                                       # source_note, confidence, extracted_date
ReifiedRelationship = dict[str, Any]   # id, event_type, participant_ids, properties, source_note,
                                       # confidence, extracted_date


# ---------------------------------------------------------------------------
# Deterministic ID helpers
# ---------------------------------------------------------------------------

def _entity_id(name: str) -> str:
    """Stable UUID-v5 from entity name (case-insensitive)."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, name.strip().lower()))


def _rel_id(source_id: str, target_id: str, rel_type: str) -> str:
    key = f"{source_id}:{target_id}:{rel_type}"
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, key))


def _reified_id(event_type: str, participant_ids: list[str]) -> str:
    key = event_type + ":" + ":".join(sorted(participant_ids))
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, key))


# ---------------------------------------------------------------------------
# Wikilink / tag parsing
# ---------------------------------------------------------------------------

_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+?)(?:\|[^\]]+)?\]\]")
_TAG_RE = re.compile(r"(?:^|\s)#([\w/\-]+)", re.MULTILINE)
_FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n?", re.DOTALL)
_FRONTMATTER_BLOCK_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
_FRONTMATTER_KEY_RE = re.compile(r"^([A-Za-z_][\w-]*):\s*(.*)$")
_HEADING_RE = re.compile(r"^#{2,4}\s+(.+?)\s*$")
MAX_ENTITY_NAME_CHARS = 200

# Sentence boundary splitter for N-ary detection
_SENT_RE = re.compile(r"(?<=[.!?。])\s+")

_FM_KEY_TO_REL: dict[str, str] = {
    "parent": "parent",
    "up": "parent",
    "parent_meeting": "parent",
    "parent_moc": "parent",
    "moc": "part_of",
    "source": "sourced_from",
    "sot": "sourced_from",
    "source_post": "sourced_from",
    "report": "derived_from",
    "target_doc": "derived_from",
    "related": "related_to",
    "next": "next",
    "prev": "prev",
    "previous_lesson": "prev",
    "previous_version": "supersedes",
}

_HEADING_TO_REL: dict[str, str] = {
    "상위": "parent",
    "up": "parent",
    "하위": "contains",
    "children": "contains",
    "참고": "references",
    "참고 자료": "references",
    "참고자료": "references",
    "참고 문서": "references",
    "참조": "references",
    "references": "references",
    "출처": "sourced_from",
    "source": "sourced_from",
    "sources": "sourced_from",
    "원문": "sourced_from",
    "근거": "supported_by",
    "관련": "related_to",
    "관련 노트": "related_to",
    "관련 글": "related_to",
    "관련 문서": "related_to",
    "관련 자료": "related_to",
    "관련 링크": "related_to",
    "유사 주제": "related_to",
    "연결": "related_to",
    "링크": "related_to",
    "related": "related_to",
    "related notes": "related_to",
    "see also": "related_to",
    "정합": "aligns_with",
    "다음": "next",
    "이전": "prev",
}


def _strip_frontmatter(content: str) -> str:
    """Return markdown body without YAML frontmatter."""
    return _FRONTMATTER_RE.sub("", content, count=1)


def _extract_frontmatter_block(content: str) -> str:
    m = _FRONTMATTER_BLOCK_RE.match(content)
    return m.group(1) if m else ""


def _is_safe_entity_name(name: str) -> bool:
    name = name.strip()
    if not name:
        return False
    if len(name) == 1 or name.isdigit():
        return False
    if len(name) > MAX_ENTITY_NAME_CHARS:
        return False
    if "\n" in name or "\r" in name:
        return False
    return True


def _extract_wikilinks(content: str) -> list[str]:
    targets: list[str] = []
    for m in _WIKILINK_RE.finditer(content):
        target = m.group(1).strip()
        if _is_safe_entity_name(target):
            targets.append(target)
    return targets


def _extract_frontmatter_typed_links(content: str) -> list[tuple[str, str]]:
    """Extract explicitly typed wikilinks from whitelisted YAML frontmatter keys."""
    frontmatter = _extract_frontmatter_block(content)
    if not frontmatter:
        return []

    links: list[tuple[str, str]] = []
    active_rel: str | None = None
    for raw_line in frontmatter.splitlines():
        line = raw_line.rstrip()
        key_match = _FRONTMATTER_KEY_RE.match(line)
        if key_match:
            key = key_match.group(1).strip().lower()
            active_rel = _FM_KEY_TO_REL.get(key)
            if active_rel:
                for target in _extract_wikilinks(key_match.group(2)):
                    links.append((target, active_rel))
            continue

        stripped = line.strip()
        if active_rel and stripped.startswith("-"):
            for target in _extract_wikilinks(stripped[1:]):
                links.append((target, active_rel))

    return links


def _normalize_heading(heading: str) -> str:
    return heading.strip().strip("#").strip().lower()


def _iter_body_wikilinks_with_relation(content: str) -> list[tuple[str, str]]:
    """Yield body wikilinks classified by the nearest preceding heading."""
    links: list[tuple[str, str]] = []
    active_rel: str | None = None
    for line in content.splitlines():
        heading_match = _HEADING_RE.match(line)
        if heading_match:
            active_rel = _HEADING_TO_REL.get(_normalize_heading(heading_match.group(1)))
            continue
        rel_type = active_rel or "mentions"
        for target in _extract_wikilinks(line):
            links.append((target, rel_type))
    return links


def _extract_tags(content: str) -> list[str]:
    return [m.group(1).strip() for m in _TAG_RE.finditer(content)]


def _note_name_from_path(note_path: str) -> str:
    return Path(note_path).stem


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _ensure_entity(
    entities: list[Entity],
    seen_entity_ids: set[str],
    target_name: str,
) -> str:
    target_id = _entity_id(target_name)
    if target_id not in seen_entity_ids:
        entities.append({
            "id": target_id,
            "name": target_name,
            "name_ko": None,
            "type": "concept",
            "description": None,
            "source_note": _resolve_note_path(target_name),
        })
        seen_entity_ids.add(target_id)
    return target_id


def _relationship(
    source_id: str,
    target_id: str,
    rel_type: str,
    evidence_text: str,
    note_path: str,
    now: str,
    *,
    strength: float,
    confidence: float,
) -> Relationship:
    return {
        "id": _rel_id(source_id, target_id, rel_type),
        "source_id": source_id,
        "target_id": target_id,
        "type": rel_type,
        "strength": strength,
        "evidence_text": evidence_text,
        "source_note": note_path,
        "confidence": confidence,
        "extracted_date": now,
    }


# ---------------------------------------------------------------------------
# LLM placeholder functions
# ---------------------------------------------------------------------------

ENTITY_EXTRACTION_PROMPT = """\
You are a knowledge graph entity extractor for an Obsidian vault (AI/Knowledge Management domain).

TBox entity types: {entity_types}

Given the note content, extract all named entities that match the TBox classes.
For each entity return a JSON object:
  - name: canonical English name
  - name_ko: Korean name if present, else null
  - type: one of the TBox entity types listed above
  - description: one-sentence description

Return a JSON array.

Note content:
---
{text}
---
"""

RELATIONSHIP_EXTRACTION_PROMPT = """\
You are a knowledge graph relationship extractor for an Obsidian vault.

TBox relation types: {relation_types}

Known entities: {entities}

For each relationship, return a JSON object:
  - source: entity name
  - target: entity name
  - type: one of the TBox relation types
  - strength: float 0.0-1.0
  - evidence_text: exact quote (≤ 100 chars)
  - confidence: extraction confidence 0.0-1.0

Return a JSON array.

Note content:
---
{text}
---
"""

NARY_RELATION_PROMPT = """\
You are a knowledge graph N-ary relation extractor.

Given the note content and known entities, identify events or situations where
3 or more entities participate together in a single action or context.

For each N-ary event, return a JSON object:
  - event_type: concise name (e.g. "co_authorship", "shared_project", "joint_discussion")
  - participant_names: list of entity names (3+)
  - properties: dict of additional attributes (e.g. {"date": "...", "context": "..."})
  - evidence_text: supporting quote (≤ 150 chars)
  - confidence: float 0.0-1.0

Return a JSON array. Return [] if no N-ary events found.

Known entities: {entities}

Note content:
---
{text}
---
"""


def extract_entities_llm(text: str, entity_types: list[str] | None = None) -> list[Entity]:
    """
    LLM placeholder — returns empty list.
    Replace with actual LLM call using ENTITY_EXTRACTION_PROMPT.
    """
    # TODO: call LLM with ENTITY_EXTRACTION_PROMPT.format(
    #     text=text,
    #     entity_types=json.dumps(entity_types or [])
    # )
    return []


def extract_relationships_llm(
    text: str,
    entities: list[Entity],
    relation_types: list[str] | None = None,
) -> list[Relationship]:
    """
    LLM placeholder — returns empty list.
    Replace with actual LLM call using RELATIONSHIP_EXTRACTION_PROMPT.
    """
    # TODO: call LLM with RELATIONSHIP_EXTRACTION_PROMPT.format(
    #     text=text,
    #     entities=json.dumps([e["name"] for e in entities]),
    #     relation_types=json.dumps(relation_types or [])
    # )
    return []


def extract_nary_relations_llm(
    text: str,
    entities: list[Entity],
) -> list[ReifiedRelationship]:
    """
    LLM placeholder for N-ary relation extraction.
    Replace with actual LLM call using NARY_RELATION_PROMPT.

    Returns reified relationships (each event as a node).
    """
    # TODO: call LLM with NARY_RELATION_PROMPT.format(
    #     text=text,
    #     entities=json.dumps([e["name"] for e in entities])
    # )
    # Parse JSON response:
    # For each event in response:
    #   participant_ids = [_entity_id(name) for name in event["participant_names"]]
    #   yield ReifiedRelationship(id=_reified_id(event_type, participant_ids), ...)
    return []


# ---------------------------------------------------------------------------
# Rule-based extraction (wikilinks + tags)
# ---------------------------------------------------------------------------

def extract_entities_rule_based(
    note_path: str,
    content: str,
) -> tuple[list[Entity], list[Relationship], list[ReifiedRelationship]]:
    """
    Rule-based extraction:
    1. Frontmatter typed wikilinks → source -typed_relation-> target
    2. Body wikilinks [[Target]] → heading-typed relation or mentions fallback
    3. Tags #tag → source -belongs_to-> tag entity (binary, ABox fact)
    4. Shared tags (2+ wikilinks in same sentence) → Reification as co_occurs event
       (hyperedge cluster seed per 메타엣지-하이퍼그래프-구현.md §5.17)

    All relationships carry Named Graph context (confidence, extracted_date).
    """
    source_name = _note_name_from_path(note_path)
    source_id = _entity_id(source_name)
    now = _now_iso()

    source_entity: Entity = {
        "id": source_id,
        "name": source_name,
        "name_ko": None,
        "type": "concept",
        "description": None,
        "source_note": note_path,
    }

    entities: list[Entity] = [source_entity]
    relationships: list[Relationship] = []
    reified: list[ReifiedRelationship] = []
    seen_entity_ids: set[str] = {source_id}

    extraction_content = _strip_frontmatter(content)
    frontmatter_links = _extract_frontmatter_typed_links(content)
    body_links = _iter_body_wikilinks_with_relation(extraction_content)
    tags = _extract_tags(extraction_content)

    # --- Binary frontmatter relations (explicit typed ABox facts) ---
    for target_name, rel_type in frontmatter_links:
        target_id = _ensure_entity(entities, seen_entity_ids, target_name)
        relationships.append(_relationship(
            source_id, target_id, rel_type, f"[[{target_name}]]", note_path, now,
            strength=1.0, confidence=1.0,
        ))

    # --- Binary body wikilink relations (heading typed or mentions fallback) ---
    for target_name, rel_type in body_links:
        target_id = _ensure_entity(entities, seen_entity_ids, target_name)
        strength = 1.0 if rel_type == "mentions" else 0.9
        confidence = 1.0 if rel_type == "mentions" else 0.85
        relationships.append(_relationship(
            source_id, target_id, rel_type, f"[[{target_name}]]", note_path, now,
            strength=strength, confidence=confidence,
        ))

    # --- Binary tag relations (ABox facts) ---
    tag_entity_ids: list[str] = []
    for tag in tags:
        if not _is_safe_entity_name(tag):
            continue
        tag_id = _entity_id(f"#tag:{tag}")
        if tag_id not in seen_entity_ids:
            entities.append({
                "id": tag_id,
                "name": tag,
                "name_ko": None,
                "type": "concept",
                "description": f"Tag: #{tag}",
                "source_note": None,
            })
            seen_entity_ids.add(tag_id)
        relationships.append({
            "id": _rel_id(source_id, tag_id, "belongs_to"),
            "source_id": source_id,
            "target_id": tag_id,
            "type": "belongs_to",
            "strength": 0.8,
            "evidence_text": f"#{tag}",
            "source_note": note_path,
            "confidence": 0.9,
            "extracted_date": now,
        })
        tag_entity_ids.append(tag_id)

    # --- Hyperedge cluster seed: shared tags as N-ary co_occurs ---
    # When 3+ wikilink targets appear in the same sentence/paragraph,
    # reify as a co_occurs event node (hyperedge per §5.17).
    sentences = _SENT_RE.split(extraction_content)
    for sentence in sentences:
        co_refs = [
            _entity_id(t)
            for t in _extract_wikilinks(sentence)
            if _entity_id(t) in seen_entity_ids and _entity_id(t) != source_id
        ]
        if len(co_refs) >= 2:
            # Include source as participant
            participants = [source_id] + list(dict.fromkeys(co_refs))
            r_id = _reified_id("co_occurs", participants)
            evidence = sentence.strip()[:150]
            reified.append({
                "id": r_id,
                "event_type": "co_occurs",
                "participant_ids": participants,
                "properties": {"sentence": evidence},
                "source_note": note_path,
                "confidence": 0.7,
                "extracted_date": now,
            })

    # Second-pass: resolve source_note for any remaining entities (non-tag) that still have None
    for e in entities:
        if e.get("source_note") is None and e.get("type") != "tag":
            resolved = _resolve_note_path(e["name"])
            if resolved:
                e["source_note"] = resolved

    return entities, relationships, reified


# ---------------------------------------------------------------------------
# Main extraction entry point
# ---------------------------------------------------------------------------

def extract_entities_from_note(
    note_path: str,
    content: str,
    use_llm: bool = False,
    entity_types: list[str] | None = None,
    relation_types: list[str] | None = None,
) -> tuple[list[Entity], list[Relationship], list[ReifiedRelationship]]:
    """
    Extract entities, binary relationships, and reified N-ary relationships.

    Pipeline:
    1. Rule-based: wikilinks, tags, co-occurrence hyperedges (always)
    2. LLM-based: named entity + relation + N-ary extraction (if use_llm=True)

    Named Graph context (confidence, extracted_date) included in all relations.
    """
    entities, relationships, reified = extract_entities_rule_based(note_path, content)

    if use_llm:
        # LLM entity extraction
        llm_entities = extract_entities_llm(content, entity_types)
        for e in llm_entities:
            e.setdefault("id", _entity_id(e["name"]))
            e.setdefault("source_note", note_path)
            if e["id"] not in {ent["id"] for ent in entities}:
                entities.append(e)

        # LLM binary relation extraction
        llm_rels = extract_relationships_llm(content, entities, relation_types)
        now = _now_iso()
        for r in llm_rels:
            if "source_id" not in r and "source" in r:
                r["source_id"] = _entity_id(r.pop("source"))
            if "target_id" not in r and "target" in r:
                r["target_id"] = _entity_id(r.pop("target"))
            r.setdefault("id", _rel_id(r["source_id"], r["target_id"], r["type"]))
            r.setdefault("source_note", note_path)
            r.setdefault("confidence", 0.8)
            r.setdefault("extracted_date", now)
            relationships.append(r)

        # LLM N-ary relation extraction → Reification
        llm_nary = extract_nary_relations_llm(content, entities)
        for nr in llm_nary:
            if "participant_names" in nr and "participant_ids" not in nr:
                nr["participant_ids"] = [_entity_id(n) for n in nr.pop("participant_names")]
            nr.setdefault("id", _reified_id(nr["event_type"], nr["participant_ids"]))
            nr.setdefault("source_note", note_path)
            nr.setdefault("extracted_date", _now_iso())
            reified.append(nr)

    return entities, relationships, reified


# ---------------------------------------------------------------------------
# DB persistence
# ---------------------------------------------------------------------------

def save_to_db(
    conn: sqlite3.Connection,
    entities: list[Entity],
    relationships: list[Relationship],
    note_path: str,
    reified: list[ReifiedRelationship] | None = None,
) -> None:
    """Upsert entities, binary relationships, and reified N-ary relationships."""
    # ABox: entities
    for e in entities:
        conn.execute(
            """
            INSERT INTO entities (id, name, name_ko, type, description, source_note)
            VALUES (:id, :name, :name_ko, :type, :description, :source_note)
            ON CONFLICT(id) DO UPDATE SET
                name        = excluded.name,
                name_ko     = COALESCE(excluded.name_ko, name_ko),
                type        = excluded.type,
                description = COALESCE(excluded.description, description),
                updated_at  = datetime('now')
            """,
            e,
        )

    # ABox: binary relationships (with Named Graph context)
    for r in relationships:
        conn.execute(
            """
            INSERT INTO relationships
                (id, source_id, target_id, type, strength, evidence_text, source_note,
                 confidence, extracted_date)
            VALUES
                (:id, :source_id, :target_id, :type, :strength, :evidence_text, :source_note,
                 :confidence, :extracted_date)
            ON CONFLICT(id) DO UPDATE SET
                strength       = excluded.strength,
                evidence_text  = excluded.evidence_text,
                confidence     = excluded.confidence
            """,
            {
                "id":             r.get("id"),
                "source_id":      r.get("source_id"),
                "target_id":      r.get("target_id"),
                "type":           r.get("type"),
                "strength":       r.get("strength", 1.0),
                "evidence_text":  r.get("evidence_text"),
                "source_note":    r.get("source_note"),
                "confidence":     r.get("confidence", 1.0),
                "extracted_date": r.get("extracted_date", _now_iso()),
            },
        )

    # ABox: reified N-ary relationships
    if reified:
        for nr in reified:
            conn.execute(
                """
                INSERT INTO reified_relationships
                    (id, event_type, participant_ids, properties, source_note,
                     confidence, extracted_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    properties  = excluded.properties,
                    confidence  = excluded.confidence
                """,
                (
                    nr.get("id"),
                    nr.get("event_type"),
                    json.dumps(nr.get("participant_ids", []), ensure_ascii=False),
                    json.dumps(nr.get("properties", {}),     ensure_ascii=False),
                    nr.get("source_note"),
                    nr.get("confidence", 1.0),
                    nr.get("extracted_date", _now_iso()),
                ),
            )

    conn.execute(
        """
        INSERT INTO sync_log (operation, note_path, entity_ids, status, source)
        VALUES ('extract', ?, ?, 'done', 'entity_extractor')
        """,
        (note_path, json.dumps([e["id"] for e in entities])),
    )

    conn.commit()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Extract entities from a note (TBox-aware)")
    parser.add_argument("note", help="Path to markdown note file")
    parser.add_argument("--db", default=_DEFAULT_DB)
    parser.add_argument("--llm", action="store_true", help="Enable LLM extraction (placeholder)")
    parser.add_argument("--dry-run", action="store_true", help="Print extracted data, don't save")
    args = parser.parse_args()

    note_path = Path(args.note)
    if not note_path.exists():
        print(f"Error: note not found: {note_path}", file=sys.stderr)
        sys.exit(1)

    content = note_path.read_text(encoding="utf-8")

    # Load TBox entity/relation types from DB
    entity_types: list[str] | None = None
    relation_types: list[str] | None = None
    if not args.dry_run:
        from graphrag_core import get_valid_entity_types, get_valid_relation_types
        conn_tmp = get_connection(args.db)
        entity_types = get_valid_entity_types(conn_tmp)
        relation_types = get_valid_relation_types(conn_tmp)
        close_connection(conn_tmp)

    entities, relationships, reified = extract_entities_from_note(
        str(note_path), content,
        use_llm=args.llm,
        entity_types=entity_types,
        relation_types=relation_types,
    )

    print(
        f"Extracted: {len(entities)} entities, "
        f"{len(relationships)} relationships, "
        f"{len(reified)} reified N-ary"
    )

    if args.dry_run:
        print(json.dumps(
            {"entities": entities, "relationships": relationships, "reified": reified},
            indent=2, ensure_ascii=False,
        ))
    else:
        conn = get_connection(args.db)
        save_to_db(conn, entities, relationships, str(note_path), reified)
        close_connection(conn)
        print(f"Saved to {args.db}")
