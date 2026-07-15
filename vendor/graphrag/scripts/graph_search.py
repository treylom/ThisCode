"""
graph_search.py — Global/Local search dichotomy + 4 search modes

Theory-based enhancements:
  1. Query complexity classifier: L0/L1/L2/L3
     Ref: GraphRAG-Global-vs-Local-Search.md §5.4.6
  2. Global search (L3): map-reduce over community summaries (all levels)
  3. Local search (L0-L2): hop-based traversal with depth = f(complexity)
  4. Unified search() entry point: auto-routes to global or local
  5. Original 4 modes preserved: insight_forge, panorama, quick_search, interview
  6. DRIFT-style drill-down for L2 (global overview → local refinement)

Search routing:
  L0 → quick_search (Depth 1, direct lookup)
  L1 → quick_search with 2-hop
  L2 → insight_forge (local, 2-hop + community context)
  L3 → global_search (map-reduce, all communities)

Ref: 6개-분석공간-개요.md (Hierarchy Space, Causal Space)
Python 3.12 compatible
"""
from __future__ import annotations

from pathlib import Path as _Path
_PROJECT_DIR = _Path(__file__).resolve().parents[3]
_DEFAULT_DB = str(_PROJECT_DIR / ".team-os/graphrag/index/vault_graph.db")

import json
import os
import re
import sqlite3
import subprocess
import tempfile
import threading
import time
from enum import Enum
from typing import Any

from graphrag_core import get_connection, close_connection, fts5_search, get_bulk_rel_strengths

# ---------------------------------------------------------------------------
# Lazy NetworkX import — only loaded when graph-based search modes are used
# (search, global_search, insight_forge, panorama_search, quick_search, interview)
# Hybrid search does NOT require NetworkX.
# ---------------------------------------------------------------------------
nx = None  # type: ignore[assignment]


def _get_nx():
    """Lazily import networkx on first use."""
    global nx
    if nx is None:
        try:
            import networkx as _nx
            nx = _nx
        except ImportError:
            raise ImportError("networkx not installed. Run: pip install 'networkx>=3.0'")
    return nx

# ---------------------------------------------------------------------------
# Optional: embedding_index for dense search (graceful degradation)
# ---------------------------------------------------------------------------
try:
    import embedding_index as _embedding_index
    _EMBEDDING_AVAILABLE = True
except ImportError:
    _embedding_index = None  # type: ignore[assignment]
    _EMBEDDING_AVAILABLE = False


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

SearchResult = dict[str, Any]


# ---------------------------------------------------------------------------
# P5: Korean-English cross-lingual mapping for LIKE search
# ---------------------------------------------------------------------------
_CROSS_LINGUAL_MAP: dict[str, list[str]] = {
    # v2 originals
    "에이전트": ["agent"],
    "프롬프트": ["prompt"],
    "얼룩소": ["alookso"],
    "강의": ["lecture"],
    "안전": ["safety"],
    "연구": ["research"],
    "도구": ["tool", "tools"],
    "자동화": ["automation"],
    "워크플로우": ["workflow"],
    "지식": ["knowledge"],
    "그래프": ["graph"],
    "검색": ["search"],
    "임베딩": ["embedding"],
    "벡터": ["vector"],
    "의미": ["semantic", "meaning"],
    "커뮤니티": ["community"],
    "온톨로지": ["ontology"],
    "agent": ["에이전트"],
    "orchestration": ["오케스트레이션", "orchestrator workers"],
    "orchestrator": ["오케스트레이션", "orchestration"],
    "patterns": ["패턴", "pattern"],
    "pattern": ["패턴", "patterns"],
    "worker": ["워커"],
    "workers": ["워커"],
    "prompt": ["프롬프트"],
    "safety": ["안전"],
    "research": ["연구"],
    "knowledge": ["지식"],
    "graph": ["그래프"],
    "search": ["검색"],
    "semantic": ["의미"],
    "meaning": ["의미"],
    "vector": ["벡터"],
    # v3 additions — gap analysis (Q09, Q14, Q16, Q17, Q18)
    "여정": ["journey"],
    "트렌드": ["trend", "trends"],
    "민주주의": ["democracy"],
    "정치": ["politics", "political"],
    "사회": ["society", "social"],
    "군사화": ["military", "militarization"],
    "벤치마크": ["benchmark", "benchmarks"],
    "성능": ["performance"],
    "글쓰기": ["writing"],
    "사례": ["case study", "examples"],
    "동향": ["trend"],
    "페르소나": ["persona"],
    "journey": ["여정"],
    "trend": ["트렌드", "동향"],
    "trends": ["트렌드"],
    "democracy": ["민주주의"],
    "politics": ["정치"],
    "military": ["군사화"],
    "benchmark": ["벤치마크"],
    "performance": ["성능"],
    "writing": ["글쓰기"],
    "persona": ["페르소나"],
    # v4 additions — Q14 gap (cross-lingual for 실무/적용)
    "실무": ["practical", "hands-on"],
    "적용": ["application", "applied"],
    "practical": ["실무"],
    "application": ["적용"],
    "hands-on": ["실무"],
    "applied": ["적용"],
}


def _normalize_phrase_text(text: str) -> str:
    normalized = re.sub(r"[^0-9a-zA-Z가-힣]+", " ", text.casefold())
    return re.sub(r"\s+", " ", normalized).strip()


def _phrase_token_count(phrase: str) -> int:
    normalized = _normalize_phrase_text(phrase)
    return len(normalized.split()) if normalized else 0


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        normalized = _normalize_phrase_text(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def _query_terms_for_phrase(query: str) -> list[str]:
    normalized = _normalize_phrase_text(query)
    return [term for term in normalized.split() if len(term) >= 2]


def _exact_phrase_queries(query: str) -> list[str]:
    terms = _query_terms_for_phrase(query)
    phrases: list[str] = []

    for idx in range(0, max(0, len(terms) - 1)):
        if terms[idx] not in _CROSS_LINGUAL_MAP or terms[idx + 1] not in _CROSS_LINGUAL_MAP:
            continue
        phrases.append(" ".join(terms[idx:idx + 2]))
        left_options = [terms[idx], *_CROSS_LINGUAL_MAP.get(terms[idx], [])]
        right_options = [terms[idx + 1], *_CROSS_LINGUAL_MAP.get(terms[idx + 1], [])]
        for left in left_options:
            for right in right_options:
                phrase = _normalize_phrase_text(f"{left} {right}")
                if _phrase_token_count(phrase) >= 2:
                    phrases.append(phrase)

    return _dedupe_preserve_order([p for p in phrases if _phrase_token_count(p) >= 2])


def _text_matches_exact_phrase(text: str, phrase: str) -> bool:
    normalized_text = _normalize_phrase_text(text)
    normalized_phrase = _normalize_phrase_text(phrase)
    return bool(normalized_phrase and normalized_phrase in normalized_text)


def expand_query_cross_lingual(query: str) -> str:
    """Expand a query string by appending cross-lingual equivalents.

    Used by search_server.py to improve entity embedding search recall
    when the query contains Korean terms with English equivalents or vice versa.
    Returns the original query with appended translations, or original if no expansions found.
    """
    tokens = query.lower().split()
    expansions: list[str] = []
    for token in tokens:
        for mapped in _CROSS_LINGUAL_MAP.get(token, []):
            if mapped.lower() not in query.lower():
                expansions.append(mapped)
    if expansions:
        return f"{query} {' '.join(expansions)}"
    return query


# ---------------------------------------------------------------------------
# M1: LLM Query Expansion via CLIProxyAPI
# ---------------------------------------------------------------------------

_QE_API_BASE = "http://127.0.0.1:8317"
_QE_API_KEY = "codex-hybrid-team"
_QE_CACHE: dict[str, dict[str, Any]] = {}
_QE_CACHE_LOCK = threading.Lock()  # v2.3.3: cache get/set/evict 안 race 차단
_QE_CACHE_MAX = 200

_QE_DEFAULT = {"expanded_terms": [], "english_query": "", "intent": "lookup"}

# 2026-06-16 (코난, 재경님 (나) 승인): env-gated precomputed expansion file. When
# GRAPHRAG_QE_CACHE_FILE points to a JSON {query: {expanded_terms, english_query, intent}},
# expand_query_llm serves from it (no HTTP) — lets us prove the expansion FEATURE in
# isolation before standing up the shared CLIProxyAPI backend. Default unset = unchanged
# HTTP behavior (live 8400 safe).
_QE_FILE_CACHE: dict[str, dict[str, Any]] | None = None


def _normalize_query_cache_key(query: str) -> str:
    """Normalize query identity without changing the query sent to retrieval."""
    return query.strip().casefold()


def _load_qe_file_cache() -> dict[str, dict[str, Any]] | None:
    global _QE_FILE_CACHE
    if _QE_FILE_CACHE is not None:
        return _QE_FILE_CACHE
    path = os.environ.get("GRAPHRAG_QE_CACHE_FILE")
    if not path:
        return None
    try:
        with open(path, encoding="utf-8") as f:
            _QE_FILE_CACHE = json.load(f)
    except Exception:
        _QE_FILE_CACHE = {}
    return _QE_FILE_CACHE


def expand_query_llm(query: str) -> dict[str, Any]:
    """LLM-based query expansion. Returns expanded_terms, english_query, intent.

    Uses CLIProxyAPI (Anthropic-compatible) with LRU cache and 5s timeout.
    Falls back to empty expansion on any failure.
    """
    cache_key = _normalize_query_cache_key(query)
    if cache_key in _QE_CACHE:
        return _QE_CACHE[cache_key]

    # 2026-06-16: precomputed expansion file (isolated experiment backend, env-gated)
    _file_cache = _load_qe_file_cache()
    if _file_cache is not None:
        hit = _file_cache.get(query)
        if hit:
            result = {
                "expanded_terms": hit.get("expanded_terms", []),
                "english_query": hit.get("english_query", query),
                "intent": hit.get("intent", "lookup"),
            }
        else:
            result = {**_QE_DEFAULT, "english_query": query}
        _QE_CACHE[cache_key] = result
        return result

    try:
        import httpx  # type: ignore
    except ImportError:
        return {**_QE_DEFAULT, "english_query": query}

    prompt = (
        "Given this Korean knowledge vault search query, expand it for better retrieval.\n"
        f"Query: {query}\n\n"
        "Return JSON only:\n"
        '{"expanded_terms": ["term1", "term2", "term3"],\n'
        ' "english_query": "English translation",\n'
        ' "intent": "lookup|comparison|synthesis|causal"}'
    )

    try:
        resp = httpx.post(
            f"{_QE_API_BASE}/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": _QE_API_KEY,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 200,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=5.0,
        )
        resp.raise_for_status()
        # Find the first text block (skip thinking blocks)
        content_blocks = resp.json().get("content", [])
        text = ""
        for block in content_blocks:
            if block.get("type") == "text":
                text = block.get("text", "")
                break
        if not text:
            raise ValueError("No text block in response")
        # Extract JSON from response (handle markdown code blocks)
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        result = json.loads(text.strip())
        # Validate structure
        result.setdefault("expanded_terms", [])
        result.setdefault("english_query", query)
        result.setdefault("intent", "lookup")
        if result["intent"] not in ("lookup", "comparison", "synthesis", "causal"):
            result["intent"] = "lookup"
    except Exception:
        result = {**_QE_DEFAULT, "english_query": query}

    # Cache with LRU eviction
    if len(_QE_CACHE) >= _QE_CACHE_MAX:
        oldest_key = next(iter(_QE_CACHE))
        del _QE_CACHE[oldest_key]
    _QE_CACHE[cache_key] = result
    return result


# ---------------------------------------------------------------------------
# Query complexity classification
# Ref: GraphRAG-Global-vs-Local-Search.md §5.4.6
# ---------------------------------------------------------------------------

class QueryLevel(Enum):
    L0 = 0   # Direct entity lookup ("What is X?", "Where is X?")
    L1 = 1   # 1-2 hop relationship ("Who created X?", "What does X extend?")
    L2 = 2   # Multi-hop + community context ("How does X relate to Y's impact on Z?")
    L3 = 3   # Corpus-wide thematic question (global map-reduce)


# Keyword patterns for L3 (global queries)
_GLOBAL_PATTERNS = re.compile(
    r"\b(전체|모든|종합|전반|주요 테마|가장 많이|공통적|전체적으로|주요 논점|"
    r"핵심적인|전체 여정|어떻게 연결|체계|종합|"
    r"overview|overall|across all|most common|main themes?|comprehensive|"
    r"what are the|what is the main|summarize|corpus|dataset|collection)\b",
    re.IGNORECASE,
)

# Keyword patterns for L0 (direct lookup)
_L0_PATTERNS = re.compile(
    r"^(what is|what are|where is|who is|when is|어디|언제|무엇|누구)\b",
    re.IGNORECASE,
)

# Keyword patterns for multi-hop (L1/L2)
_MULTI_HOP_PATTERNS = re.compile(
    r"\b(how does|why does|impact|effect|relationship|connection|between|"
    r"어떻게|왜|영향|관계|연결|차이|비교|에 대해|에서.*쓴|에서.*글|관련|대한|미치는|발전|과정|전략)\b",
    re.IGNORECASE,
)

_DOMAIN_KEYWORDS = re.compile(
    r"\b(민주주의|AI|에이전트|프롬프트|얼룩소|강의|플랫폼)\b",
    re.IGNORECASE,
)


def classify_query_complexity(query: str) -> QueryLevel:
    """
    Classify query into L0/L1/L2/L3 for routing to local or global search.

    L3 (global): corpus-wide thematic → map-reduce over communities
    L2: multi-hop + complex relationships → insight_forge
    L1: 1-2 hop relationships → quick_search (2-hop)
    L0: direct entity lookup → quick_search (1-hop)

    Ref: GraphRAG-Global-vs-Local-Search.md §5.4.6 (search strategy selection)
    """
    q = query.strip()
    word_count = len(q.split())
    has_relationship_keyword = bool(_MULTI_HOP_PATTERNS.search(q))
    has_domain_keyword = bool(_DOMAIN_KEYWORDS.search(q))

    # L3: global/thematic query patterns
    if _GLOBAL_PATTERNS.search(q):
        return QueryLevel.L3

    # L2: complex multi-hop relationship with domain + relationship context
    if has_domain_keyword and has_relationship_keyword and word_count > 6:
        return QueryLevel.L2

    # L2: longer multi-hop relationship queries
    if has_relationship_keyword and word_count > 8:
        return QueryLevel.L2

    # L1: single relationship query
    if has_relationship_keyword:
        return QueryLevel.L1

    # Default: L0 (direct lookup)
    return QueryLevel.L0


# Depth mapping for local search
_DEPTH_MAP: dict[QueryLevel, int] = {
    QueryLevel.L0: 1,
    QueryLevel.L1: 2,
    QueryLevel.L2: 3,
}


# ---------------------------------------------------------------------------
# LLM synthesis/map helpers
# ---------------------------------------------------------------------------

INSIGHT_SYNTHESIS_PROMPT = """\
You are a knowledge graph analyst (Local Search — Hierarchy Space context).

Query: {query}
Search depth: {depth} hops (L{level})

Community summaries (context):
{communities}

Related entities ({entity_count} within {depth} hops):
{entities}

Key relationships:
{relationships}

Provide structured insight: Overview, Key themes, Notable connections, Gaps/questions.
"""

GLOBAL_SYNTHESIS_PROMPT = """\
You are a knowledge graph analyst (Global Search — Map-Reduce).

Query: {query}
Community level analyzed: C{community_level}

Intermediate answers from {community_count} communities:
{community_answers}

Synthesize the top answers (ranked by relevance score) into a comprehensive response.
Structure: Overview → Key themes → Cross-community patterns → Conclusions
"""

INTERVIEW_NARRATIVE_PROMPT = """\
You are analyzing a knowledge graph node.

Entity: {entity_name} (type: {entity_type})
Description: {description}

All relationships ({rel_count}):
{relationships}

Detected patterns:
{patterns}

Write a 3-4 paragraph narrative 'interview' of this entity — its role, connections, and significance.
"""

MAP_ANSWER_PROMPT = """\
You are a knowledge graph analyst.

Query: {query}

Community: {community_name} (level C{level}, {member_count} members)
Community summary: {summary}

Key members and relationships:
{context}

Answer the query based on this community's content.
Return a JSON object:
  - answer: concise answer (1-2 sentences)
  - relevance_score: float 0.0-1.0
  - key_entities: list of entity names supporting the answer
"""


_LLM_DEFAULT_MODEL = "claude-haiku-4-5-20251001"
_LLM_DEFAULT_TIMEOUT = 10.0
_LLM_DEFAULT_PROVIDER = "http"
_LLM_CODEX_DEFAULT_MODEL = "gpt-5.5"
_LLM_CODEX_CLI_CWD = "/tmp"
_LLM_CODEX_CLI_MAX_CONCURRENCY_DEFAULT = 1
_LLM_CODEX_CLI_MAX_OUTPUT_CHARS_DEFAULT = 20000
_GLOBAL_MAX_COMMUNITIES_DEFAULT = 50
_LLM_SYNTHESIS_FALLBACK = "[LLM synthesis unavailable — set GRAPHRAG_LLM_ENABLED=1 and configure provider]"
_LLM_MAP_FALLBACK = {"answer": "[map unavailable]", "relevance_score": 0.0, "key_entities": []}
_llm_codex_cli_semaphore_lock = threading.Lock()
_llm_codex_cli_semaphore: tuple[int, threading.BoundedSemaphore] | None = None


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    try:
        value = float(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _env_int(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _extract_text_block(payload: dict[str, Any]) -> str:
    for block in payload.get("content", []):
        if block.get("type") == "text":
            return str(block.get("text", "")).strip()
    return ""


def _strip_json_fence(text: str) -> str:
    text = text.strip()
    if "```" not in text:
        return text
    fenced = text.split("```", 2)[1].strip()
    return fenced[4:].strip() if fenced.startswith("json") else fenced


def _get_codex_cli_semaphore() -> threading.BoundedSemaphore:
    limit = _env_int("GRAPHRAG_LLM_CODEX_MAX_CONCURRENCY", _LLM_CODEX_CLI_MAX_CONCURRENCY_DEFAULT)
    global _llm_codex_cli_semaphore
    with _llm_codex_cli_semaphore_lock:
        if _llm_codex_cli_semaphore is None or _llm_codex_cli_semaphore[0] != limit:
            _llm_codex_cli_semaphore = (limit, threading.BoundedSemaphore(limit))
        return _llm_codex_cli_semaphore[1]

def _llm_completion_codex_cli(prompt: str, *, max_tokens: int) -> str | None:
    """Call Codex non-interactive mode through the already-authenticated CLI."""
    del max_tokens  # Codex CLI completion provider captures the final answer via -o.
    model = (
        os.environ.get("GRAPHRAG_LLM_CODEX_MODEL")
        or os.environ.get("GRAPHRAG_LLM_MODEL")
        or _LLM_CODEX_DEFAULT_MODEL
    ).strip() or _LLM_CODEX_DEFAULT_MODEL
    timeout = _env_float("GRAPHRAG_LLM_TIMEOUT", _LLM_DEFAULT_TIMEOUT)
    binary = os.environ.get("GRAPHRAG_LLM_CODEX_BIN", "codex").strip() or "codex"
    cwd = os.environ.get("GRAPHRAG_LLM_CODEX_CWD", _LLM_CODEX_CLI_CWD).strip() or _LLM_CODEX_CLI_CWD
    max_output_chars = _env_int(
        "GRAPHRAG_LLM_CODEX_MAX_OUTPUT_CHARS",
        _LLM_CODEX_CLI_MAX_OUTPUT_CHARS_DEFAULT,
    )
    output_path: str | None = None
    env = os.environ.copy()
    env.pop("OPENAI_API_KEY", None)
    env.pop("ANTHROPIC_API_KEY", None)

    try:
        with tempfile.NamedTemporaryFile(prefix="graphrag-codex-", suffix=".txt", delete=False) as output_file:
            output_path = output_file.name
        cmd = [
            binary,
            "exec",
            "--ephemeral",
            "--skip-git-repo-check",
            "--ignore-user-config",
            "--ignore-rules",
            "--sandbox",
            "read-only",
            "-C",
            cwd,
            "-m",
            model,
            "-o",
            output_path,
            "-",
        ]
        with _get_codex_cli_semaphore():
            result = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
                env=env,
            )
        if result.returncode != 0:
            return None
        text = _Path(output_path).read_text(encoding="utf-8", errors="replace").strip()
        if not text or len(text) > max_output_chars:
            return None
        return text
    except Exception:
        return None
    finally:
        if output_path:
            try:
                _Path(output_path).unlink(missing_ok=True)
            except Exception:
                pass


def _llm_completion(prompt: str, *, max_tokens: int) -> str | None:
    """Call the configured low-cost model provider when explicitly enabled."""
    if not _env_flag("GRAPHRAG_LLM_ENABLED"):
        return None

    provider = os.environ.get("GRAPHRAG_LLM_PROVIDER", _LLM_DEFAULT_PROVIDER).strip().lower()
    if provider in {"codex_cli", "codex-cli", "codex"}:
        return _llm_completion_codex_cli(prompt, max_tokens=max_tokens)
    if provider not in {"http", "anthropic", "proxy"}:
        return None

    try:
        import httpx  # type: ignore
    except ImportError:
        return None

    api_base = os.environ.get("GRAPHRAG_LLM_API_BASE", _QE_API_BASE).rstrip("/")
    api_key = os.environ.get("GRAPHRAG_LLM_API_KEY", _QE_API_KEY)
    model = os.environ.get("GRAPHRAG_LLM_MODEL", _LLM_DEFAULT_MODEL)
    timeout = _env_float("GRAPHRAG_LLM_TIMEOUT", _LLM_DEFAULT_TIMEOUT)

    try:
        resp = httpx.post(
            f"{api_base}/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        text = _extract_text_block(resp.json())
        return text or None
    except Exception:
        return None


def _llm_synthesize(prompt: str) -> str:
    """Run synthesis when enabled; otherwise preserve graceful fallback."""
    return _llm_completion(prompt, max_tokens=700) or _LLM_SYNTHESIS_FALLBACK


def _llm_map_answer(prompt: str) -> dict[str, Any]:
    """Run map step when enabled; otherwise preserve zero-relevance fallback."""
    text = _llm_completion(prompt, max_tokens=300)
    if not text:
        return dict(_LLM_MAP_FALLBACK)
    try:
        result = json.loads(_strip_json_fence(text))
    except Exception:
        return dict(_LLM_MAP_FALLBACK)
    answer = str(result.get("answer", "")).strip()
    try:
        relevance_score = float(result.get("relevance_score", 0.0))
    except (TypeError, ValueError):
        relevance_score = 0.0
    key_entities = result.get("key_entities", [])
    if not isinstance(key_entities, list):
        key_entities = []
    return {
        "answer": answer or _LLM_MAP_FALLBACK["answer"],
        "relevance_score": max(0.0, min(1.0, relevance_score)),
        "key_entities": [str(entity) for entity in key_entities],
    }


# ---------------------------------------------------------------------------
# Helper: fetch entity by name or ID
# ---------------------------------------------------------------------------

def _get_entity(conn: sqlite3.Connection, entity_name: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM entities WHERE LOWER(name) = LOWER(?) OR id = ?",
        (entity_name, entity_name),
    ).fetchone()
    return dict(row) if row else None


def _get_neighbors(G: "nx.Graph", node_id: str, hops: int = 1) -> set[str]:
    """Return node IDs within `hops` of node_id (excluding node itself)."""
    if node_id not in G:
        return set()
    neighbors: set[str] = set()
    frontier = {node_id}
    for _ in range(hops):
        next_frontier: set[str] = set()
        for n in frontier:
            for nb in G.neighbors(n):
                if nb != node_id and nb not in neighbors:
                    next_frontier.add(nb)
        neighbors.update(next_frontier)
        frontier = next_frontier
    return neighbors


# ---------------------------------------------------------------------------
# Unified entry point: search()
# Auto-routes to global or local based on query complexity
# ---------------------------------------------------------------------------

def search(
    conn: sqlite3.Connection,
    G: "nx.Graph",
    query: str,
    force_level: QueryLevel | None = None,
    global_community_level: int = 1,
) -> SearchResult:
    """
    Unified search entry point with automatic Global/Local routing.

    Routing table (per GraphRAG-Global-vs-Local-Search.md §5.4.6):
      L3 → global_search (map-reduce across communities)
      L2 → insight_forge (local, 3-hop + community context)
      L1 → quick_search (local, 2-hop)
      L0 → quick_search (local, 1-hop)

    Args:
      force_level: Override auto-detection with specific QueryLevel
      global_community_level: Community level to use for global search (0=C0 .. 3=C3)
    """
    level = force_level if force_level is not None else classify_query_complexity(query)

    if level == QueryLevel.L3:
        result = global_search(conn, G, query, community_level=global_community_level)
    elif level == QueryLevel.L2:
        result = insight_forge(conn, G, query, top_communities=5)
        result["search_depth"] = _DEPTH_MAP[QueryLevel.L2]
    elif level == QueryLevel.L1:
        # Try entity-based local search first
        entity = _get_entity(conn, query.split()[0]) if query.split() else None
        if entity:
            result = quick_search(conn, G, query.split()[0], hops=2)
        else:
            result = insight_forge(conn, G, query, top_communities=3)
        result["search_depth"] = _DEPTH_MAP[QueryLevel.L1]
    else:  # L0
        result = quick_search(conn, G, query, hops=1)
        result["search_depth"] = _DEPTH_MAP[QueryLevel.L0]

    result["query_level"] = level.name
    return result


# ---------------------------------------------------------------------------
# Global Search — Map-Reduce over community summaries
# Ref: GraphRAG-Global-vs-Local-Search.md §5.4.6 (Global Search)
# ---------------------------------------------------------------------------

def global_search(
    conn: sqlite3.Connection,
    G: "nx.Graph",
    query: str,
    community_level: int = 1,
    top_k: int = 10,
) -> SearchResult:
    """
    Global search: map-reduce over community summaries at given level.

    1. Fetch all communities at specified level
    2. MAP: generate intermediate answer + relevance score for each community
    3. REDUCE: rank by relevance, synthesize top-k answers

    C0 (level=0): coarsest, cheapest, broad strokes
    C3 (level=3): finest, most expensive, high precision

    Ref: GraphRAG-Global-vs-Local-Search.md §5.4.6
    """
    query_lower = query.lower()

    # Fetch communities at specified level
    communities = [
        dict(row)
        for row in conn.execute(
            """SELECT id, name, summary, member_entity_ids, level
               FROM communities WHERE level = ?
               ORDER BY id""",
            (community_level,),
        )
    ]

    if not communities:
        # Fallback to any available level
        communities = [
            dict(row)
            for row in conn.execute(
                "SELECT id, name, summary, member_entity_ids, level FROM communities LIMIT 50"
            )
        ]

    max_communities = _env_int("GRAPHRAG_GLOBAL_MAX_COMMUNITIES", _GLOBAL_MAX_COMMUNITIES_DEFAULT)
    communities = communities[:max_communities]

    # MAP: score each community, generate intermediate answer
    map_results: list[dict[str, Any]] = []
    for comm in communities:
        try:
            member_ids = json.loads(comm.get("member_entity_ids") or "[]")
        except (json.JSONDecodeError, TypeError):
            member_ids = []

        # Keyword relevance score (heuristic map step)
        score = 0.0
        if query_lower in (comm.get("name") or "").lower():
            score += 0.3
        if query_lower in (comm.get("summary") or "").lower():
            score += 0.2

        # Fetch key members for LLM map context
        if member_ids:
            ph = ",".join("?" * min(len(member_ids), 5))
            sample_members = [
                dict(row)
                for row in conn.execute(
                    f"SELECT name, type, description FROM entities WHERE id IN ({ph})",
                    member_ids[:5],
                )
            ]
        else:
            sample_members = []

        # LLM map step (placeholder)
        llm_result = _llm_map_answer(
            MAP_ANSWER_PROMPT.format(
                query=query,
                community_name=comm.get("name", ""),
                level=community_level,
                member_count=len(member_ids),
                summary=comm.get("summary") or "",
                context=json.dumps(sample_members, ensure_ascii=False),
            )
        )

        combined_score = score + llm_result.get("relevance_score", 0.0)
        if combined_score > 0 or score > 0:
            map_results.append({
                "community_id":   comm["id"],
                "community_name": comm.get("name", ""),
                "community_level": comm.get("level", community_level),
                "summary":        comm.get("summary", ""),
                "answer":         llm_result.get("answer", ""),
                "relevance_score": combined_score,
                "key_entities":   llm_result.get("key_entities", []),
                "member_count":   len(member_ids),
            })

    # REDUCE: sort by relevance, take top_k
    map_results.sort(key=lambda x: x["relevance_score"], reverse=True)
    top_answers = map_results[:top_k]

    # LLM reduce step (synthesis)
    synthesis = _llm_synthesize(
        GLOBAL_SYNTHESIS_PROMPT.format(
            query=query,
            community_level=community_level,
            community_count=len(top_answers),
            community_answers=json.dumps(
                [{"name": r["community_name"], "answer": r["answer"],
                  "score": r["relevance_score"]}
                 for r in top_answers],
                ensure_ascii=False,
            ),
        )
    )

    return {
        "mode": "global_search",
        "query": query,
        "community_level": community_level,
        "communities_analyzed": len(communities),
        "top_communities": top_answers,
        "synthesis": synthesis,
    }


# ---------------------------------------------------------------------------
# Search Mode 1: InsightForge (Local, L2)
# ---------------------------------------------------------------------------

def insight_forge(
    conn: sqlite3.Connection,
    G: "nx.Graph",
    query: str,
    top_communities: int = 3,
) -> SearchResult:
    """
    InsightForge: community context + N-hop graph traversal + LLM synthesis.
    Local search mode, best for complex multi-hop queries (L2).
    """
    query_lower = query.lower()

    # Find relevant communities across all levels
    communities = []
    for row in conn.execute(
        "SELECT id, name, summary, member_entity_ids, level FROM communities ORDER BY level"
    ):
        score = 0
        if query_lower in (row["name"] or "").lower():
            score += 2
        if query_lower in (row["summary"] or "").lower():
            score += 1
        if score > 0:
            communities.append({"score": score, **dict(row)})

    communities.sort(key=lambda x: x["score"], reverse=True)
    top = communities[:top_communities]

    # Collect seed entities from top communities
    seed_ids: set[str] = set()
    for c in top:
        try:
            seed_ids.update(json.loads(c["member_entity_ids"] or "[]"))
        except (json.JSONDecodeError, TypeError):
            pass

    # Also keyword-match entities directly
    for row in conn.execute(
        "SELECT id FROM entities WHERE LOWER(name) LIKE ? OR LOWER(description) LIKE ?",
        (f"%{query_lower}%", f"%{query_lower}%"),
    ):
        seed_ids.add(row["id"])

    # 2-hop neighbors
    neighbor_ids: set[str] = set()
    for sid in seed_ids:
        neighbor_ids.update(_get_neighbors(G, sid, hops=2))
    all_entity_ids = seed_ids | neighbor_ids

    # Fetch entity details
    entities = []
    if all_entity_ids:
        ph = ",".join("?" * len(all_entity_ids))
        entities = [
            dict(row)
            for row in conn.execute(
                f"SELECT id, name, type, description, centrality_score FROM entities WHERE id IN ({ph})",
                list(all_entity_ids),
            )
        ]

    # Fetch relationships (with confidence from Named Graph)
    relationships = []
    if all_entity_ids:
        ph = ",".join("?" * len(all_entity_ids))
        relationships = [
            dict(row)
            for row in conn.execute(
                f"""SELECT r.type, e1.name AS source, e2.name AS target,
                           r.strength, r.evidence_text, r.confidence
                    FROM relationships r
                    JOIN entities e1 ON r.source_id = e1.id
                    JOIN entities e2 ON r.target_id = e2.id
                    WHERE r.source_id IN ({ph}) AND r.target_id IN ({ph})
                    ORDER BY r.strength * r.confidence DESC LIMIT 50""",
                list(all_entity_ids) * 2,
            )
        ]

    synthesis = _llm_synthesize(
        INSIGHT_SYNTHESIS_PROMPT.format(
            query=query,
            depth=2,
            level=2,
            communities=json.dumps(
                [{"name": c["name"], "summary": c["summary"]} for c in top],
                ensure_ascii=False,
            ),
            entity_count=len(entities),
            entities=json.dumps(
                [{"name": e["name"], "type": e["type"]} for e in entities[:20]],
                ensure_ascii=False,
            ),
            relationships=json.dumps(
                [{"source": r["source"], "target": r["target"],
                  "type": r["type"], "confidence": r.get("confidence", 1.0)}
                 for r in relationships[:20]],
                ensure_ascii=False,
            ),
        )
    )

    return {
        "mode": "insight_forge",
        "query": query,
        "communities": [{"name": c["name"], "summary": c["summary"], "level": c.get("level", 0)}
                        for c in top],
        "entity_count": len(entities),
        "relationship_count": len(relationships),
        "synthesis": synthesis,
    }


# ---------------------------------------------------------------------------
# Search Mode 2: Panorama
# ---------------------------------------------------------------------------

def panorama_search(
    conn: sqlite3.Connection,
    G: "nx.Graph",
    query: str,
) -> SearchResult:
    """
    Panorama: Full community landscape across all levels.
    Best for: broad overview of a topic domain.
    """
    query_lower = query.lower()

    scored_communities = []
    for row in conn.execute(
        "SELECT id, name, summary, member_entity_ids, level, resolution FROM communities ORDER BY level"
    ):
        score = sum([
            2 if query_lower in (row["name"] or "").lower() else 0,
            1 if query_lower in (row["summary"] or "").lower() else 0,
        ])
        try:
            member_ids = json.loads(row["member_entity_ids"] or "[]")
        except (json.JSONDecodeError, TypeError):
            member_ids = []
        scored_communities.append({
            "score":        score,
            "id":           row["id"],
            "name":         row["name"],
            "summary":      row["summary"],
            "level":        row["level"],
            "resolution":   row["resolution"],
            "member_count": len(member_ids),
        })

    scored_communities.sort(key=lambda x: (-x["score"], x["level"], -x["member_count"]))

    top_entities = [
        dict(row)
        for row in conn.execute(
            """SELECT name, type, community_id, centrality_score
               FROM entities
               WHERE LOWER(name) LIKE ? OR LOWER(description) LIKE ?
               ORDER BY centrality_score DESC LIMIT 30""",
            (f"%{query_lower}%", f"%{query_lower}%"),
        )
    ]

    # Group by level for Hierarchy Space overview
    by_level: dict[int, list[dict]] = {}
    for c in scored_communities:
        by_level.setdefault(c["level"], []).append(c)

    return {
        "mode": "panorama",
        "query": query,
        "total_communities": len(scored_communities),
        "relevant_communities": [c for c in scored_communities if c["score"] > 0],
        "communities_by_level": {
            f"C{lvl}": len(comms) for lvl, comms in sorted(by_level.items())
        },
        "top_entities": top_entities,
    }


# ---------------------------------------------------------------------------
# Search Mode 3: Quick Search (Local, L0/L1)
# ---------------------------------------------------------------------------

def quick_search(
    conn: sqlite3.Connection,
    G: "nx.Graph",
    entity_name: str,
    hops: int = 1,
) -> SearchResult:
    """
    Quick Search: Entity details + N-hop neighbors.
    Local search for L0 (hops=1) and L1 (hops=2).
    """
    entity = _get_entity(conn, entity_name)
    if entity is None:
        return {"mode": "quick_search", "entity": entity_name, "found": False}

    entity_id = entity["id"]
    neighbor_ids = _get_neighbors(G, entity_id, hops=hops)

    neighbors = []
    if neighbor_ids:
        ph = ",".join("?" * len(neighbor_ids))
        neighbors = [
            dict(row)
            for row in conn.execute(
                f"SELECT id, name, type, description FROM entities WHERE id IN ({ph})",
                list(neighbor_ids),
            )
        ]

    # Direct relationships (with Named Graph confidence)
    direct_rels = [
        dict(row)
        for row in conn.execute(
            """SELECT r.type, e1.name AS source, e2.name AS target,
                      r.strength, r.evidence_text, r.confidence
               FROM relationships r
               JOIN entities e1 ON r.source_id = e1.id
               JOIN entities e2 ON r.target_id = e2.id
               WHERE r.source_id = ? OR r.target_id = ?
               ORDER BY r.strength * r.confidence DESC""",
            (entity_id, entity_id),
        )
    ]

    # Community info (all levels)
    community_info = []
    if entity.get("community_id"):
        # Get the entity's C3 community and walk up the hierarchy
        current_id = entity["community_id"]
        while current_id:
            row = conn.execute(
                "SELECT id, name, summary, level, parent_id FROM communities WHERE id = ?",
                (current_id,),
            ).fetchone()
            if row:
                community_info.append(dict(row))
                current_id = row["parent_id"]
            else:
                break

    # Check for reified N-ary relations involving this entity
    reified_rels = [
        dict(row)
        for row in conn.execute(
            """SELECT id, event_type, participant_ids, properties, confidence
               FROM reified_relationships
               WHERE participant_ids LIKE ?""",
            (f'%"{entity_id}"%',),
        )
    ]

    return {
        "mode": "quick_search",
        "found": True,
        "hops": hops,
        "entity": entity,
        "community_hierarchy": community_info,
        "neighbors": neighbors,
        "relationships": direct_rels,
        "reified_relationships": reified_rels,
    }


# ---------------------------------------------------------------------------
# Search Mode 4: Interview
# ---------------------------------------------------------------------------

def interview(
    conn: sqlite3.Connection,
    G: "nx.Graph",
    entity_name: str,
) -> SearchResult:
    """
    Interview: Full edge traversal → pattern detection → LLM narrative.
    Deep understanding of a single entity's role (local search).
    """
    entity = _get_entity(conn, entity_name)
    if entity is None:
        return {"mode": "interview", "entity": entity_name, "found": False}

    entity_id = entity["id"]

    all_rels = [
        dict(row)
        for row in conn.execute(
            """SELECT r.type, e1.name AS source, e2.name AS target,
                      r.strength, r.evidence_text, r.source_note, r.confidence
               FROM relationships r
               JOIN entities e1 ON r.source_id = e1.id
               JOIN entities e2 ON r.target_id = e2.id
               WHERE r.source_id = ? OR r.target_id = ?
               ORDER BY r.strength * r.confidence DESC""",
            (entity_id, entity_id),
        )
    ]

    # Pattern detection
    rel_type_counts: dict[str, int] = {}
    for r in all_rels:
        rel_type_counts[r["type"]] = rel_type_counts.get(r["type"], 0) + 1

    patterns = [
        f"Primarily connects via '{rtype}' ({count} times)"
        for rtype, count in sorted(rel_type_counts.items(), key=lambda x: -x[1])
    ]

    degree = G.degree(entity_id) if entity_id in G else 0
    centrality = entity.get("centrality_score", 0.0)
    patterns.append(f"Degree: {degree}, Centrality: {centrality:.4f}")

    # Check for reified N-ary relations
    reified_rels = [
        dict(row)
        for row in conn.execute(
            "SELECT event_type, participant_ids, properties, confidence FROM reified_relationships "
            "WHERE participant_ids LIKE ?",
            (f'%"{entity_id}"%',),
        )
    ]
    if reified_rels:
        patterns.append(f"Participates in {len(reified_rels)} N-ary events (reified)")

    narrative = _llm_synthesize(
        INTERVIEW_NARRATIVE_PROMPT.format(
            entity_name=entity["name"],
            entity_type=entity["type"],
            description=entity.get("description") or "N/A",
            rel_count=len(all_rels),
            relationships=json.dumps(
                [{"source": r["source"], "target": r["target"],
                  "type": r["type"], "confidence": r.get("confidence", 1.0)}
                 for r in all_rels[:30]],
                ensure_ascii=False,
            ),
            patterns="\n".join(patterns),
        )
    )

    return {
        "mode": "interview",
        "found": True,
        "entity": entity,
        "relationship_count": len(all_rels),
        "reified_relationship_count": len(reified_rels),
        "patterns": patterns,
        "narrative": narrative,
        "all_relationships": all_rels,
    }


# ---------------------------------------------------------------------------
# Hybrid search constants
# ---------------------------------------------------------------------------

# 2026-06-16 (코난 R-V1 deploy): default channel weights env-configurable so the live
# deploy can set the winner profile (dense0.5) without code change. Default values =
# current/unchanged (live 8400 safe until launchd env is set). Per-query params still override.
DEFAULT_DENSE_WEIGHT: float = float(os.environ.get("GRAPHRAG_DENSE_WEIGHT", "0.3"))   # semantic similarity weight
DEFAULT_SPARSE_WEIGHT: float = float(os.environ.get("GRAPHRAG_SPARSE_WEIGHT", "0.4"))  # keyword (FTS5) weight — Korean domain terminology
DEFAULT_DECOMPOSED_WEIGHT: float = float(os.environ.get("GRAPHRAG_DECOMPOSED_WEIGHT", "0.15"))  # query decomposition for multi-term matching
DEFAULT_ENTITY_WEIGHT: float = float(os.environ.get("GRAPHRAG_ENTITY_WEIGHT", "0.15"))  # entity embedding for MOC/hub note surfacing
# 2026-07-03 (코난 B-layer): concept-hop channel — query→concept(bge-m3)→concept_note_edges→note.
# Additive RRF term (does not alter _rrf_score signature/cache). weight=0 disables (fail-safe rollback).
DEFAULT_CONCEPT_WEIGHT: float = float(os.environ.get("GRAPHRAG_CONCEPT_WEIGHT", "0.10"))
DEFAULT_INDEX_DIR: str = ".team-os/graphrag/index"
RRF_K: int = 60
_QUERY_SPLIT_PATTERN = re.compile(
    r"\s*(?:,|/|;)\s*|\s+(?:and|or|와|및|그리고|과)\s+",
    re.IGNORECASE,
)
_QUERY_STOPWORDS = {
    "and", "or", "the", "a", "an", "of", "to", "in", "on", "for", "with",
    "와", "및", "그리고", "과",
}


# ---------------------------------------------------------------------------
# Cross-encoder (reranker) — lazy singleton
# ---------------------------------------------------------------------------

_cross_encoder = None
_cross_encoder_lock = threading.Lock()


def _get_cross_encoder():
    """Lazily load BAAI/bge-reranker-base (singleton).

    R9 upgraded from cross-encoder/ms-marco-MiniLM-L-12-v2 (English-only) to
    bge-reranker-base for Korean support. This multilingual XLM-RoBERTa base
    model is 0.3B params and about 1.1GB on disk. It returns raw logits like
    MiniLM, so structural boosts remain calibrated. First-run download and
    warmup take about 90s.

    R10 (DISCARDED): bge-reranker-v2-m3 regressed top-1 8→7. Base model
    retained as the local sweet spot.
    """
    global _cross_encoder
    if _cross_encoder is not None:
        return _cross_encoder
    with _cross_encoder_lock:
        if _cross_encoder is None:
            from sentence_transformers import CrossEncoder  # type: ignore
            # R9: Upgraded MiniLM→bge-reranker-base for multilingual (Korean) content
            # 2026-06-16 (코난 autoresearch R-B1): reranker model env-configurable for
            # isolated bake-off (default unchanged = no live behavior change).
            _model_id = os.environ.get("GRAPHRAG_RERANKER_MODEL", "BAAI/bge-reranker-base")
            # 2026-06-16 (코난 R-B2): empirically the current sentence-transformers
            # defaults BOTH bge-reranker-base AND v2-m3 to Sigmoid (relevant pair ~0.001
            # for base) — so the L1248 "raw logits" comment is stale and the live pipeline
            # is structural-boost-dominated (ce_score ~0). v2-m3 with Identity gives a 10.7
            # logit spread (3x base's 3.3) = a genuinely useful neural signal. Env-gated
            # raw-logit mode (default off = exact current Sigmoid behavior, live 8400 safe).
            if os.environ.get("GRAPHRAG_RERANKER_RAW_LOGITS", "0") == "1":
                import torch  # type: ignore
                _cross_encoder = CrossEncoder(_model_id, activation_fn=torch.nn.Identity())
            else:
                _cross_encoder = CrossEncoder(_model_id)
    return _cross_encoder


# ---------------------------------------------------------------------------
# Hybrid search helpers
# ---------------------------------------------------------------------------


def _decompose_query(query: str) -> list[str]:
    """Return up to 5 sub-queries for an independent decomposed sparse channel."""
    normalized = re.sub(r"\s+", " ", query.strip())
    if not normalized:
        return []

    parts = [
        re.sub(r"[\"'()\[\]{}]", " ", part).strip(" -_")
        for part in _QUERY_SPLIT_PATTERN.split(normalized)
        if part.strip()
    ]

    candidates: list[str] = []
    for part in parts:
        if part and part.casefold() != normalized.casefold():
            candidates.append(part)

    phrase_sources = candidates[:] if candidates else [normalized]
    for source in phrase_sources:
        tokens = [
            token for token in re.split(r"\s+", source)
            if token and token.casefold() not in _QUERY_STOPWORDS
        ]
        if len(tokens) <= 1:
            continue
        sizes = (2, 3) if len(tokens) > 3 else (len(tokens),)
        for size in sizes:
            if size <= 1 or len(tokens) < size:
                continue
            for idx in range(len(tokens) - size + 1):
                phrase = " ".join(tokens[idx: idx + size]).strip()
                if phrase and phrase.casefold() != normalized.casefold():
                    candidates.append(phrase)

    unique: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = candidate.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
        if len(unique) == 5:
            break

    return unique if len(unique) >= 2 else []



def _normalize_channel_weights(
    channel_weights: dict[str, float],
    channel_presence: dict[str, bool],
) -> dict[str, float]:
    """Redistribute missing-channel weight across active channels proportionally."""
    requested_total = sum(max(weight, 0.0) for weight in channel_weights.values())
    available = {
        name: max(weight, 0.0)
        for name, weight in channel_weights.items()
        if max(weight, 0.0) > 0 and channel_presence.get(name, False)
    }
    available_total = sum(available.values())

    if requested_total <= 0 or available_total <= 0:
        return {name: 0.0 for name in channel_weights}

    return {
        name: (requested_total * available[name] / available_total) if name in available else 0.0
        for name in channel_weights
    }



def _aggregate_ranked_results(
    result_sets: list[list[dict[str, Any]]],
    key_field: str = "name",
    k: int = RRF_K,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Merge ranked lists into a single rank map without polluting outer-channel RRF."""
    aggregated: dict[str, dict[str, Any]] = {}
    for results in result_sets:
        for rank, result in enumerate(results, start=1):
            key = str(result.get(key_field, "")).strip()
            if not key:
                continue
            payload = aggregated.setdefault(
                key,
                {"score": 0.0, "best_rank": rank, "result": result},
            )
            payload["score"] += 1.0 / (k + rank)
            if rank < payload["best_rank"]:
                payload["best_rank"] = rank
                payload["result"] = result

    ordered = sorted(
        aggregated.items(),
        key=lambda item: (-float(item[1]["score"]), int(item[1]["best_rank"]), item[0].casefold()),
    )
    merged_results = [payload["result"] for _, payload in ordered]
    rank_map = {name: idx + 1 for idx, (name, _) in enumerate(ordered)}
    return merged_results, rank_map


# ---------------------------------------------------------------------------
# RRF helper
# ---------------------------------------------------------------------------

def _rrf_score(
    dense_rank: "int | None",
    sparse_rank: "int | None",
    decomposed_rank: "int | None" = None,
    entity_rank: "int | None" = None,
    dense_weight: float = DEFAULT_DENSE_WEIGHT,
    sparse_weight: float = DEFAULT_SPARSE_WEIGHT,
    decomposed_weight: float = DEFAULT_DECOMPOSED_WEIGHT,
    entity_weight: float = DEFAULT_ENTITY_WEIGHT,
    k: int = RRF_K,
    sparse_bm25: "float | None" = None,
) -> float:
    """Reciprocal Rank Fusion scoring for up to 4 independent ranked channels."""
    score = 0.0
    channels = (
        (dense_rank, dense_weight),
        (sparse_rank, sparse_weight),
        (decomposed_rank, decomposed_weight),
        (entity_rank, entity_weight),
    )
    for rank, weight in channels:
        if rank is not None and weight > 0:
            score += weight / (k + rank)
    EXACT_MATCH_BM25_THRESHOLD = -15.0  # FTS5: more negative = better match
    EXACT_MATCH_BOOST = 0.05
    if (
        sparse_bm25 is not None
        and sparse_rank == 1
        and sparse_bm25 <= EXACT_MATCH_BM25_THRESHOLD
        and sparse_weight > 0
    ):
        confidence = min(1.0, abs(sparse_bm25) / 20.0)
        score += EXACT_MATCH_BOOST * confidence * (sparse_weight / 0.4)
    return score


# ---------------------------------------------------------------------------
# Concept-hop channel (B-layer, 2026-07-03) — query → concept(bge-m3) → note
# Isolated: reads concept_* tables + concept_embeddings.npy. Absent/error = empty (fail-safe).
# ---------------------------------------------------------------------------
_CONCEPT_INDEX: "dict[str, Any] | None" = None
_CONCEPT_INDEX_LOCK = threading.Lock()
_CONCEPT_FLOOR = 0.55  # query↔concept min sim to consider (below = noise)

def _load_concept_index(conn: sqlite3.Connection, output_dir: str) -> "dict[str, Any] | None":
    global _CONCEPT_INDEX
    if _CONCEPT_INDEX is not None:
        return _CONCEPT_INDEX or None
    with _CONCEPT_INDEX_LOCK:
        if _CONCEPT_INDEX is not None:
            return _CONCEPT_INDEX or None
        try:
            import numpy as _np
            emb_path = os.path.join(output_dir, "concept_embeddings.npy")
            if not os.path.exists(emb_path):
                _CONCEPT_INDEX = {}
                return None
            emb = _np.load(emb_path).astype("float32")
            emb /= (_np.linalg.norm(emb, axis=1, keepdims=True) + 1e-9)
            rows = conn.execute(
                "SELECT id, canonical_name, embedding_ref, low_priority FROM concept_entities WHERE layer='B-2026-07'"
            ).fetchall()
            by_row = {r[2]: {"cid": r[0], "name": r[1], "low": r[3]} for r in rows}
            _CONCEPT_INDEX = {"emb": emb, "by_row": by_row}
            return _CONCEPT_INDEX
        except Exception:
            _CONCEPT_INDEX = {}
            return None

def _concept_channel_search(conn: sqlite3.Connection, query: str, output_dir: str, top_k: int) -> list[dict[str, Any]]:
    """query→concept(bge-m3, reuse note embed model)→concept_note_edges→note entities. Ranked note-entity dicts."""
    if DEFAULT_CONCEPT_WEIGHT <= 0:
        return []
    idx = _load_concept_index(conn, output_dir)
    if not idx or not idx.get("by_row"):
        return []
    try:
        import numpy as _np
        model = _embedding_index._get_model()  # same bge-m3 space as concept_embeddings
        qv = _np.asarray(model.encode([query], normalize_embeddings=True)[0], dtype="float32")
        sims = idx["emb"] @ qv
        order = _np.argsort(-sims)[: max(top_k, 10)]
        note_best: dict[str, float] = {}
        for ri in order:
            s = float(sims[int(ri)])
            if s < _CONCEPT_FLOOR:
                break
            meta = idx["by_row"].get(int(ri))
            if not meta:
                continue
            lp = 0.5 if meta["low"] else 1.0
            for neid, econf in conn.execute(
                "SELECT note_entity_id, confidence FROM concept_note_edges WHERE concept_cid=? AND layer='B-2026-07'",
                (meta["cid"],),
            ):
                w = s * float(econf) * lp
                if w > note_best.get(neid, 0.0):
                    note_best[neid] = w
        if not note_best:
            return []
        top_ids = sorted(note_best, key=lambda k: -note_best[k])[:top_k]
        out: list[dict[str, Any]] = []
        for neid in top_ids:
            row = conn.execute(
                "SELECT id, name, type, description, source_note, centrality_score FROM entities WHERE id=?",
                (neid,),
            ).fetchone()
            if row:
                d = dict(row)
                d["_concept_weight"] = note_best[neid]
                out.append(d)
        return out
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Hybrid Search (Dense + Sparse + RRF)
# ---------------------------------------------------------------------------

_HYBRID_CACHE: dict[tuple[str, int, tuple[float, float, float, float]], list[SearchResult]] = {}
_HYBRID_CACHE_LOCK = threading.Lock()  # v2.3.3: background warmup + /reload + concurrent /api/search race 차단
_HYBRID_CACHE_MAX = 100
_ALIAS_RERANK_BOOST = 1.0  # C-3b: frontmatter aliases are exact user-authored recall hints.
_EXACT_PHRASE_BOOST = 0.03  # E-2: multi-token exact phrase hits are high-precision recall hints.
_EXACT_PHRASE_RERANK_BOOST = 2.0
RERANK_POOL_MULTIPLIER = int(os.environ.get("GRAPHRAG_RERANK_POOL_MULT", "3"))  # R12b: sparse-only 3x expansion. 2026-06-16 (코난 R-E1d): env-configurable for pool-depth sweep (default 3 = unchanged).


def _is_exact_alias_query(query: str, matched_alias: str | None) -> bool:
    return bool(matched_alias and query.strip().casefold() == matched_alias.strip().casefold())


def _exact_phrase_search(conn: sqlite3.Connection, query: str, limit: int) -> list[dict[str, Any]]:
    phrases = _exact_phrase_queries(query)
    if not phrases:
        return []

    results: list[dict[str, Any]] = []
    seen_names: set[str] = set()

    for phrase in phrases:
        tokens = phrase.split()
        if len(tokens) < 2:
            continue

        phrase_token_count = len(tokens)

        # Alias/frontmatter phrases are curated user-authored recall hints, so
        # collect them before generic entity text hits.
        alias_conditions = " AND ".join(["LOWER(a.alias_name) LIKE ?"] * len(tokens))
        alias_params = [f"%{token}%" for token in tokens]
        try:
            alias_rows = [
                dict(row)
                for row in conn.execute(
                    f"SELECT e.id, e.name, e.type, e.description, e.source_note, e.centrality_score, a.alias_name "
                    f"FROM entity_aliases a JOIN entities e ON a.entity_id = e.id "
                    f"WHERE {alias_conditions} "
                    f"ORDER BY e.centrality_score DESC LIMIT ?",
                    (*alias_params, max(limit, 50)),
                )
            ]
        except Exception:
            alias_rows = []

        for row in alias_rows:
            name = row.get("name", "")
            alias_name = str(row.get("alias_name") or "")
            if name and name not in seen_names and _text_matches_exact_phrase(alias_name, phrase):
                row["phrase_matched"] = True
                row["matched_phrase"] = phrase
                row["alias_matched"] = True
                row["matched_alias"] = alias_name
                row["_phrase_token_count"] = phrase_token_count
                row["_phrase_alias_hit"] = True
                results.append(row)
                seen_names.add(name)

        entity_text = "COALESCE(name, '') || ' ' || COALESCE(source_note, '') || ' ' || COALESCE(description, '')"
        entity_conditions = " AND ".join([f"LOWER({entity_text}) LIKE ?"] * len(tokens))
        entity_params = [f"%{token}%" for token in tokens]
        try:
            entity_rows = [
                dict(row)
                for row in conn.execute(
                    f"SELECT id, name, type, description, source_note, centrality_score "
                    f"FROM entities WHERE {entity_conditions} "
                    f"ORDER BY centrality_score DESC LIMIT ?",
                    (*entity_params, max(limit, 50)),
                )
            ]
        except Exception:
            entity_rows = []

        for row in entity_rows:
            name = row.get("name", "")
            haystack = " ".join(
                str(row.get(key) or "") for key in ("name", "source_note", "description")
            )
            if name and name not in seen_names and _text_matches_exact_phrase(haystack, phrase):
                row["phrase_matched"] = True
                row["matched_phrase"] = phrase
                row["_phrase_token_count"] = phrase_token_count
                row["_phrase_alias_hit"] = False
                results.append(row)
                seen_names.add(name)

    results.sort(
        key=lambda row: (
            -int(row.get("_phrase_token_count") or 0),
            not bool(row.get("_phrase_alias_hit")),
            -float(row.get("centrality_score") or 0.0),
            str(row.get("name") or "").casefold(),
        )
    )
    for row in results:
        row.pop("_phrase_token_count", None)
        row.pop("_phrase_alias_hit", None)
    return results[:limit]


def clear_hybrid_cache() -> None:
    """Clear cached hybrid search results."""
    # v2.3.3: lock wrap — concurrent /api/search + /reload TOCTOU 차단
    with _HYBRID_CACHE_LOCK:
        _HYBRID_CACHE.clear()


def hybrid_search(
    conn: "sqlite3.Connection | None",
    query: str,
    output_dir: str = DEFAULT_INDEX_DIR,
    top_k: int = 20,
    dense_weight: float = DEFAULT_DENSE_WEIGHT,
    sparse_weight: float = DEFAULT_SPARSE_WEIGHT,
    decomposed_weight: float = DEFAULT_DECOMPOSED_WEIGHT,
    entity_weight: float = DEFAULT_ENTITY_WEIGHT,
    note_index: Any | None = None,
    entity_index: Any | None = None,
    timings: dict[str, float] | None = None,
) -> list[SearchResult]:
    """
    Hybrid search combining up to 4 independent channels via RRF.

    Defaults preserve the current 2-channel behavior:
    1. Dense: embedding_index.search() — cosine similarity over vault notes
    2. Sparse: graphrag_core.fts5_search() — FTS5 BM25 over entities
    Optional channels (weight > 0):
    3. Decomposed sparse: FTS5 over sub-queries from _decompose_query()
    4. Entity dense: embedding_index.search_entities() over entity descriptions
    """
    # v2.3.3: function-level conn=None guard — CLI 경로 / 직접 호출 / future caller 보호
    if conn is None:
        return []

    weights = (dense_weight, sparse_weight, decomposed_weight, entity_weight)
    cache_key = (_normalize_query_cache_key(query), top_k, weights)
    with _HYBRID_CACHE_LOCK:  # v2.3.3: get atomic
        cached_results = _HYBRID_CACHE.get(cache_key)
    if cached_results is not None:
        if timings is not None:
            timings["cache_hit"] = 1.0
        return [dict(result) for result in cached_results]

    if timings is not None:
        timings["cache_hit"] = 0.0

    rerank_pool_limit = top_k * RERANK_POOL_MULTIPLIER

    # M1: LLM Query Expansion — expand before all channels
    phase_started = time.perf_counter()
    qe = expand_query_llm(query)
    if timings is not None:
        timings["qe"] = round((time.perf_counter() - phase_started) * 1000, 3)
    qe_terms = qe.get("expanded_terms", [])
    qe_english = qe.get("english_query", "")
    qe_intent = qe.get("intent", "lookup")

    dense_results: list[dict[str, Any]] = []
    sparse_results: list[dict[str, Any]] = []
    decomposed_results: list[dict[str, Any]] = []
    entity_dense_results: list[dict[str, Any]] = []
    phrase_results: list[dict[str, Any]] = []

    phase_started = time.perf_counter()
    if _EMBEDDING_AVAILABLE:
        try:
            if note_index is not None:
                dense_results = _embedding_index.search_loaded(query, note_index, top_k=rerank_pool_limit)
            else:
                dense_results = _embedding_index.search(query, output_dir, top_k=rerank_pool_limit)
        except (FileNotFoundError, Exception):
            dense_results = []
        # M1: Also search with english_query for cross-lingual recall
        if qe_english and qe_english.lower() != query.lower() and _EMBEDDING_AVAILABLE:
            try:
                if note_index is not None:
                    en_results = _embedding_index.search_loaded(qe_english, note_index, top_k=rerank_pool_limit)
                else:
                    en_results = _embedding_index.search(qe_english, output_dir, top_k=rerank_pool_limit)
                seen_paths = {r.get("note_path") for r in dense_results}
                for r in en_results:
                    if r.get("note_path") not in seen_paths:
                        dense_results.append(r)
                        seen_paths.add(r.get("note_path"))
            except Exception:
                pass
    if timings is not None:
        timings["dense"] = round((time.perf_counter() - phase_started) * 1000, 3)

    try:
        sparse_results = fts5_search(conn, query, limit=rerank_pool_limit)
    except Exception:
        sparse_results = []

    # M1: Expand FTS5 sparse results with LLM-generated terms
    if qe_terms:
        sparse_seen = {r["name"] for r in sparse_results}
        for term in qe_terms[:5]:
            try:
                term_results = fts5_search(conn, term, limit=10)
                for r in term_results:
                    if r["name"] not in sparse_seen:
                        sparse_results.append(r)
                        sparse_seen.add(r["name"])
            except Exception:
                continue

    subqueries: list[str] = []
    if decomposed_weight > 0:
        subqueries = _decompose_query(query)
        if subqueries:
            subquery_results: list[list[dict[str, Any]]] = []
            for subquery in subqueries:
                try:
                    results = fts5_search(conn, subquery, limit=rerank_pool_limit)
                except Exception:
                    continue
                if results:
                    subquery_results.append(results)
            if subquery_results:
                decomposed_results, decomposed_rank_map = _aggregate_ranked_results(subquery_results)
            else:
                decomposed_rank_map = {}
        else:
            decomposed_rank_map = {}
    else:
        decomposed_rank_map = {}

    if entity_weight > 0 and _EMBEDDING_AVAILABLE:
        entity_queries = [query]
        expanded_entity_query = expand_query_cross_lingual(query)
        if expanded_entity_query != query:
            entity_queries.append(expanded_entity_query)
        entity_seen_names: set[str] = set()
        for entity_query in entity_queries:
            try:
                if entity_index is not None:
                    entity_rows = _embedding_index.search_entities_loaded(
                        entity_query,
                        entity_index,
                        top_k=rerank_pool_limit,
                    )
                else:
                    entity_rows = _embedding_index.search_entities(entity_query, output_dir, top_k=rerank_pool_limit)
                for row in entity_rows:
                    name = row.get("name")
                    if name and name not in entity_seen_names:
                        entity_dense_results.append(row)
                        entity_seen_names.add(name)
            except (FileNotFoundError, Exception):
                continue

    # B-layer concept-hop channel (additive; empty when weight=0 or tables absent)
    concept_results: list[dict[str, Any]] = []
    try:
        concept_results = _concept_channel_search(conn, query, output_dir, rerank_pool_limit)
    except Exception:
        concept_results = []

    channel_weights = {
        "dense": dense_weight,
        "sparse": sparse_weight,
        "decomposed": decomposed_weight,
        "entity": entity_weight,
    }
    channel_presence = {
        "dense": bool(dense_results),
        "sparse": bool(sparse_results),
        "decomposed": bool(decomposed_rank_map),
        "entity": bool(entity_dense_results),
    }
    effective_weights = _normalize_channel_weights(channel_weights, channel_presence)

    query_lower = query.lower()
    # 5th channel: SQL LIKE search on entity names + descriptions (always active)
    # This catches MOC/hub notes that FTS5 trigram and dense embedding miss
    like_results: list[dict[str, Any]] = []
    # Strip Korean postpositions (조사) before LIKE search
    _KO_POSTPOSITIONS = re.compile(
        r"(에서|에게|으로|에 대해|에 대한|에 관한|부터|까지|처럼|만큼|"
        r"이라는|라는|이란|란|에서의|에서는|에서도|으로의|으로는|"
        r"은|는|이|가|을|를|의|와|과|로|에|도|만|서|께)$"
    )
    raw_terms = [t.strip() for t in query_lower.split() if len(t.strip()) >= 2]
    query_terms = []
    for t in raw_terms:
        stripped = _KO_POSTPOSITIONS.sub("", t)
        if len(stripped) >= 2:
            query_terms.append(stripped)
        elif len(t) >= 2:
            query_terms.append(t)
    # P5: Cross-lingual expansion — add English/Korean equivalents
    expanded_terms = list(query_terms)  # copy original
    for t in query_terms:
        if t in _CROSS_LINGUAL_MAP:
            expanded_terms.extend(_CROSS_LINGUAL_MAP[t])
    query_terms = list(dict.fromkeys(expanded_terms))  # deduplicate, preserve order
    like_conditions = " OR ".join(
        ["LOWER(name) LIKE ? OR LOWER(description) LIKE ?"] * len(query_terms)
    ) if query_terms else "LOWER(name) LIKE ? OR LOWER(description) LIKE ?"
    like_params = []
    for term in (query_terms if query_terms else [query_lower]):
        like_params.extend([f"%{term}%", f"%{term}%"])
    like_results = [
        dict(row)
        for row in conn.execute(
            f"SELECT id, name, type, description, source_note, centrality_score "
            f"FROM entities WHERE {like_conditions} "
            f"ORDER BY centrality_score DESC LIMIT ?",
            (*like_params, rerank_pool_limit),
        )
        ]

    # Also search entity_aliases table — catches cross-lingual / shorthand queries
    alias_terms = query_terms if query_terms else [query_lower]
    alias_conditions = " OR ".join(["LOWER(a.alias_name) LIKE ?"] * len(alias_terms))
    alias_params = [f"%{t}%" for t in alias_terms]
    alias_matched_names: set[str] = set()
    alias_matched_by_name: dict[str, str] = {}
    try:
        alias_rows = [
            dict(row)
            for row in conn.execute(
                f"SELECT e.id, e.name, e.type, e.description, e.source_note, e.centrality_score, a.alias_name "
                f"FROM entity_aliases a JOIN entities e ON a.entity_id = e.id "
                f"WHERE {alias_conditions} "
                f"ORDER BY e.centrality_score DESC LIMIT ?",
                (*alias_params, rerank_pool_limit),
            )
        ]
        seen_names = {r["name"] for r in like_results}
        for ar in alias_rows:
            matched_alias = ar.get("alias_name", "")
            ar["alias_matched"] = True
            ar["matched_alias"] = matched_alias
            alias_matched_names.add(ar["name"])
            if matched_alias:
                alias_matched_by_name.setdefault(ar["name"], matched_alias)
            if ar["name"] not in seen_names:
                like_results.append(ar)
                seen_names.add(ar["name"])
    except Exception:
        pass  # entity_aliases table may not exist on older DBs

    phrase_results = _exact_phrase_search(conn, query, rerank_pool_limit)

    dense_rank_map: dict[str, int] = {
        r["note_path"]: idx + 1 for idx, r in enumerate(dense_results)
    }
    sparse_rank_map: dict[str, int] = {
        r["name"]: idx + 1 for idx, r in enumerate(sparse_results)
    }
    sparse_bm25_map = {r["name"]: r.get("rank") for r in sparse_results}
    entity_rank_map: dict[str, int] = {
        r["name"]: idx + 1 for idx, r in enumerate(entity_dense_results)
    }
    concept_rank_map: dict[str, int] = {
        r["name"]: idx + 1 for idx, r in enumerate(concept_results)
    }
    like_rank_map: dict[str, int] = {
        r["name"]: idx + 1 for idx, r in enumerate(like_results)
    }
    phrase_rank_map: dict[str, int] = {
        r["name"]: idx + 1 for idx, r in enumerate(phrase_results)
    }
    phrase_matched_by_name: dict[str, str] = {
        r["name"]: r.get("matched_phrase", "") for r in phrase_results if r.get("matched_phrase")
    }

    # P6: Community-based search — inject top centrality entities from largest communities
    # For L3 corpus-wide queries, also inject global top-centrality entities
    community_results: list[dict[str, Any]] = []
    try:
        # Get top communities with most entities
        top_communities = conn.execute(
            "SELECT c.id, c.level, c.summary, COUNT(e.id) as entity_count "
            "FROM communities c JOIN entities e ON e.community_id = c.id "
            "WHERE c.level <= 1 "
            "GROUP BY c.id ORDER BY entity_count DESC LIMIT 5"
        ).fetchall()

        for comm in top_communities:
            # Get top centrality entities from each community
            comm_entities = [
                dict(row) for row in conn.execute(
                    "SELECT id, name, type, description, source_note, centrality_score "
                    "FROM entities WHERE community_id = ? "
                    "ORDER BY centrality_score DESC LIMIT 3",
                    (comm["id"],),
                )
            ]
            community_results.extend(comm_entities)

        # v3: For L3/meta queries ONLY, inject global top-centrality hub entities
        # This helps corpus-wide synthesis (Q16) without polluting L0-L2 queries
        query_level = classify_query_complexity(query)
        if query_level == QueryLevel.L3:
            global_hubs = [
                dict(row) for row in conn.execute(
                    "SELECT id, name, type, description, source_note, centrality_score "
                    "FROM entities WHERE centrality_score > 0.01 "
                    "ORDER BY centrality_score DESC LIMIT 10"
                )
            ]
            seen = {r["name"] for r in community_results}
            for hub in global_hubs:
                if hub["name"] not in seen:
                    community_results.append(hub)
                    seen.add(hub["name"])
    except Exception:
        pass  # communities table may be empty

    # Add community entities to candidates with low but non-zero rank
    community_rank_map: dict[str, int] = {}
    if community_results:
        community_rank_map = {
            r["name"]: idx + 1 for idx, r in enumerate(community_results)
        }

    candidates: dict[str, dict[str, Any]] = {}

    for r in dense_results:
        note_path = r.get("note_path", "")
        title = r.get("title", note_path)
        entity_row = conn.execute(
            "SELECT id, name, type, description, source_note, centrality_score "
            "FROM entities WHERE LOWER(name) = LOWER(?) OR source_note LIKE ?",
            (title, f"%{note_path}%"),
        ).fetchone()
        if entity_row:
            name = entity_row["name"]
            if name not in candidates:
                candidates[name] = dict(entity_row)
                candidates[name]["_note_path"] = note_path
        elif title not in candidates:
            candidates[title] = {
                "name": title,
                "type": "note",
                "description": "",
                "source_note": note_path,
                "centrality_score": 0.0,
                "_note_path": note_path,
            }

    for result_set in (sparse_results, decomposed_results, entity_dense_results, like_results, phrase_results, community_results, concept_results):
        for r in result_set:
            name = r.get("name", "")
            if not name:
                continue
            if name not in candidates:
                candidates[name] = r
            else:
                if r.get("alias_matched"):
                    candidates[name]["alias_matched"] = True
                    candidates[name]["matched_alias"] = r.get("matched_alias", candidates[name].get("matched_alias", ""))
                if r.get("phrase_matched"):
                    candidates[name]["phrase_matched"] = True
                    candidates[name]["matched_phrase"] = r.get("matched_phrase", candidates[name].get("matched_phrase", ""))

    # M5: Bulk-fetch relationship strengths for all candidate entities
    candidate_names = list(candidates.keys())
    rel_strengths = get_bulk_rel_strengths(conn, candidate_names)

    scored: list[dict[str, Any]] = []
    for name, info in candidates.items():
        note_path = info.get("_note_path") or info.get("source_note", "")
        d_rank = dense_rank_map.get(note_path)
        s_rank = sparse_rank_map.get(name)
        ds_rank = decomposed_rank_map.get(name)
        e_rank = entity_rank_map.get(name)
        l_rank = like_rank_map.get(name)
        p_rank = phrase_rank_map.get(name)

        rrf = _rrf_score(
            d_rank,
            s_rank,
            ds_rank,
            e_rank,
            effective_weights["dense"],
            effective_weights["sparse"],
            effective_weights["decomposed"],
            effective_weights["entity"],
            sparse_bm25=sparse_bm25_map.get(name),
        )
        # Add LIKE channel contribution (weight 0.1 — lightweight fallback)
        if l_rank is not None:
            rrf += 0.1 / (60 + l_rank)
        if p_rank is not None:
            rrf += 0.15 / (60 + p_rank)

        # Add community channel to RRF (low weight for structural diversity)
        c_rank = community_rank_map.get(name)
        if c_rank is not None:
            rrf += 0.05 / (60 + c_rank)

        # B-layer concept-hop channel (additive; DEFAULT_CONCEPT_WEIGHT=0 disables → fail-safe rollback)
        concept_r = concept_rank_map.get(name)
        if concept_r is not None and DEFAULT_CONCEPT_WEIGHT > 0:
            rrf += DEFAULT_CONCEPT_WEIGHT / (RRF_K + concept_r)

        sources = []
        if d_rank is not None:
            sources.append("dense")
        if s_rank is not None:
            sources.append("sparse")
        if ds_rank is not None:
            sources.append("decomposed")
        if e_rank is not None:
            sources.append("entity")
        if l_rank is not None:
            sources.append("like")
        if p_rank is not None:
            sources.append("phrase")
        if c_rank is not None:
            sources.append("community")
        if not sources:
            sources.append("like")

        # Centrality boost: hub/MOC notes with high centrality get a score bonus
        centrality = float(info.get("centrality_score") or 0.0)
        centrality_boost = min(centrality * 50, 0.02)  # cap at 0.02 to avoid domination

        # MOC name boost: MOC hub notes get explicit bonus (Sparse N-gram inspired IDF-like)
        moc_boost = 0.01 if ("MOC" in name or name.endswith("-MOC")) else 0.0

        # Multi-channel bonus: entities found by 3+ channels are more likely relevant
        channel_count = sum(1 for r in [d_rank, s_rank, ds_rank, e_rank] if r is not None)
        multi_channel_boost = 0.005 * max(0, channel_count - 1)

        # M5: Relationship strength boost — well-connected entities rank higher
        entity_rel_strength = rel_strengths.get(name, 0.0)
        rel_strength_boost = min(entity_rel_strength * 0.03, 0.015)  # cap at 0.015

        alias_matched = bool(info.get("alias_matched") or name in alias_matched_names)
        matched_alias = info.get("matched_alias") or alias_matched_by_name.get(name, "")
        phrase_matched = bool(info.get("phrase_matched") or name in phrase_matched_by_name)
        matched_phrase = info.get("matched_phrase") or phrase_matched_by_name.get(name, "")
        alias_boost = (
            _ALIAS_RERANK_BOOST
            if alias_matched and l_rank is not None and _is_exact_alias_query(query, matched_alias)
            else 0.0
        )
        phrase_boost = _EXACT_PHRASE_BOOST if phrase_matched and p_rank is not None else 0.0

        additive_boost_total = min(moc_boost + multi_channel_boost + rel_strength_boost, 0.03)
        boosted_rrf = rrf + centrality_boost + additive_boost_total + alias_boost + phrase_boost

        scored.append({
            "entity": name,
            "type": info.get("type", ""),
            "description": info.get("description", ""),
            "source_note": info.get("source_note", ""),
            "centrality_score": centrality,
            "score": boosted_rrf,
            "rrf_raw": rrf,
            "centrality_boost": centrality_boost,
            "moc_boost": moc_boost,
            "multi_channel_boost": multi_channel_boost,
            "rel_strength_boost": rel_strength_boost,
            "alias_boost": alias_boost,
            "phrase_boost": phrase_boost,
            "rel_strength": entity_rel_strength,
            "dense_rank": d_rank,
            "sparse_rank": s_rank,
            "decomposed_rank": ds_rank,
            "entity_rank": e_rank,
            "phrase_rank": p_rank,
            "source": "+".join(sources),
            "alias_matched": alias_matched,
            "matched_alias": matched_alias,
            "phrase_matched": phrase_matched,
            "matched_phrase": matched_phrase,
            "qe_intent": qe_intent,
        })

    scored.sort(
        key=lambda x: (
            -x["score"],
            x.get("dense_rank") or 10**9,
            x.get("sparse_rank") or 10**9,
            x.get("decomposed_rank") or 10**9,
            x.get("entity_rank") or 10**9,
            x.get("phrase_rank") or 10**9,
            x["entity"].casefold(),
        )
    )
    # R14: slice to top_k * 2 (middle ground between R12 [:top_k]=20 top-1=11/top-10=13
    # and R13 [:rerank_pool_limit=60] top-1=8/top-10=15). Target: 40 candidates preserves
    # enough top-ranked RRF items for top-1 while giving rerank room to surface new candidates.
    # 2026-06-16 (코난 R-B2): slice mult env-configurable (default 2 = unchanged). Pairs with
    # GRAPHRAG_RERANK_FUSION so a deeper slice can surface base-ranked golds (Q04/Q08) without
    # the reranker displacing well-base-ranked golds (Q09/Q12/Q13/Q24).
    rerank_slice_size = top_k * int(os.environ.get("GRAPHRAG_RERANK_SLICE_MULT", "2"))
    results = scored[:rerank_slice_size]

    # Guarantee top sparse match is included (FTS5 precision > centrality popularity)
    if sparse_results:
        top_sparse_name = sparse_results[0]["name"]
        if not any(r.get("entity") == top_sparse_name for r in results):
            # Find it in the full scored list and inject at position 2 (after top result)
            for s in scored:
                if s.get("entity") == top_sparse_name:
                    results.insert(min(2, len(results)), s)
                    results = results[:rerank_slice_size]
                    break

    # v2.3.3: evict + set atomic — TOCTOU race 차단 (next(iter(_HYBRID_CACHE)) 안 StopIteration / del 안 KeyError)
    with _HYBRID_CACHE_LOCK:
        if len(_HYBRID_CACHE) >= _HYBRID_CACHE_MAX:
            try:
                oldest_key = next(iter(_HYBRID_CACHE))
                del _HYBRID_CACHE[oldest_key]
            except (StopIteration, KeyError):
                pass
        _HYBRID_CACHE[cache_key] = [dict(result) for result in results]
    return results


# ---------------------------------------------------------------------------
# Reranker (cross-encoder)
# ---------------------------------------------------------------------------

def _confidence_level(rerank_score: float) -> dict[str, str]:
    """Map adjusted rerank score to a human-readable confidence indicator.

    P4 recalibration: thresholds lowered to account for structural boosts
    (centrality up to +2.0, MOC +1.5, multi-source +0.5) added in R12.
    """
    if rerank_score > 6.5:
        return {"level": "high", "label": "높은 확신", "emoji": "🟢"}
    if rerank_score > 3.5:
        return {"level": "medium", "label": "관련 추정", "emoji": "🟡"}
    if rerank_score > 1.0:
        return {"level": "low", "label": "약한 연관", "emoji": "🟠"}
    return {"level": "very_low", "label": "최소 관련", "emoji": "🔴"}


def rerank(
    query: str,
    candidates: list[dict],
    top_k: int = 5,
) -> list[dict]:
    """
    Rerank candidates using BAAI/bge-reranker-base.

    Pairs each candidate (entity name + description) with the query,
    scores them with the cross-encoder, and returns top_k sorted by score.
    Falls back to returning candidates[:top_k] if model unavailable.
    """
    if not candidates:
        return []

    try:
        ce = _get_cross_encoder()
    except ImportError:
        return candidates[:top_k]

    pairs = []
    for c in candidates:
        # Enrich reranker input: structured prefix + name + alias + source_note + description
        parts = []
        # M5: Relationship strength structured prefix (v4 lesson: structured > free-form)
        rel_str = c.get("rel_strength", 0.0)
        if rel_str > 0:
            parts.append(f"[rel_strength: {rel_str:.2f}]")
        parts.append(c.get("entity", ""))
        if c.get("alias_matched") and c.get("matched_alias"):
            parts.insert(1 if rel_str > 0 else 0, f"[alias: {c['matched_alias']}]")
        if c.get("phrase_matched") and c.get("matched_phrase"):
            parts.insert(1 if rel_str > 0 else 0, f"[phrase: {c['matched_phrase']}]")
        if c.get("source_note"):
            parts.append(c["source_note"])
        if c.get("description"):
            parts.append(c["description"])
        pairs.append((query, " ".join(parts).strip()))

    scores = ce.predict(pairs)

    # Combine cross-encoder score with structural signals
    adjusted = []
    for candidate, ce_score in zip(candidates, scores):
        adj = float(ce_score)
        # R109 apr13: entity_rank=1 bonus only for compact NON-MOC entities (avoid MOC bonus stacking)
        ent_name = candidate.get("entity", "")
        if candidate.get("entity_rank") == 1 and ent_name.count("-") <= 1 and "MOC" not in ent_name:
            adj += 2.0
        alias_boost = 0.0
        # R3b autoresearch apr13: paragraph-entity heavy demotion. Sentence-like
        # entities (Repost filenames, quoted passages) have 3+ spaces; MOCs/notes
        # use hyphens. Raw CE favors paragraphs topically, so a -5.0 adj is needed
        # to push them below MOCs that had CE ~3-5 points lower.
        entity_name = candidate.get("entity", "")
        if entity_name.count(" ") >= 3:
            adj -= 5.0
            candidate["paragraph_penalty"] = True
        # Centrality boost: hub nodes get reranker protection
        # R20 apr13: cap 2.0→1.0 to limit broad-MOC dominance (Q13/Q14 blockers are high-centrality mega-hubs)
        centrality = float(candidate.get("centrality_score") or 0.0)
        adj += min(centrality * 5, 1.0)  # R53 apr13: multiplier 10→5 (gentler centrality contribution)
        # MOC boost: explicit hub note protection
        # R15 apr13: 1.5→2.5 to push Q13/Q14 gold MOCs from pos 2 → pos 1
        if "MOC" in candidate.get("entity", ""):
            adj += 2.5
        # R16 apr13: reward exact query-token overlap with hyphen/space-delimited entity name segments.
        # R21a DISCARD: dict over/under-selection broke even on top-1 (Q13 gain = elsewhere loss)
        _KO_EN_MAP = {}  # R21/R21a reverted. R22 prefers structural ratio over lexical translation.
        query_tokens = set()
        for token in re.split(r"[\s\-_/.,:;()\[\]{}]+", query):
            if not token:
                continue
            t = token.casefold()
            if t in _QUERY_STOPWORDS:
                continue
            query_tokens.add(t)
            if t in _KO_EN_MAP:
                query_tokens.add(_KO_EN_MAP[t])
        entity_segments = {
            segment.casefold()
            for segment in re.split(r"[\s\-_/.,:;()\[\]{}]+", entity_name)
            if segment
        }
        overlap_count = len(query_tokens & entity_segments)
        if overlap_count:
            # R17 apr13: 0.3→0.8 per match (cap 0.9→2.4) to push Q13/Q14 gold past competitor MOCs with 0 overlap
            adj += min(overlap_count * 0.8, 2.4)  # R18 (overlap 1.2) saturated at same top-1=11, reverted to R17 0.8
            # R25-R28 DISCARD: compact-non-MOC bonus swept 0.3/0.6/1.2 — top-3 14 hard floor, Q09 only >= 0.6.
        elif query_tokens and entity_segments:
            # R30 apr13: penalty for entities with NO query-token overlap.
            # R31 apr13: 0.5→1.0 (KEEP). R32 (1.5) same result — revert to R31.
            adj -= 1.0
        # R38 DISCARD apr13: bigram bonus (+1.5 if consecutive query tokens as contiguous name substring)
        # hit too many entities; top-3/5/10 all regressed -1 without top-1 gain. Removed.
        # R39/R41 DISCARD apr13: phrase-containment bonus (cap 3.0 and 1.0) both gave same pattern:
        # top-3 +1 but top-1 -1. Magnitude-agnostic structural effect — one untracked query always
        # loses top-1 when any candidate with phrase-substring match gets any boost.
        # Deep-research 권고 방향이나 현재 파이프라인에서는 local optimum 이동만 발생.
        # R19 apr13: description-match bonus. Some queries (Q14) have Korean tokens that don't
        # appear in English entity names (agent vs 에이전트). Description may carry the Korean text.
        description_text = (candidate.get("description") or "").lower()
        if description_text and query_tokens:
            desc_matches = sum(1 for t in query_tokens if t in description_text)
            if desc_matches:
                adj += min(desc_matches * 0.3, 1.2)
        # Multi-source bonus: found by multiple search channels = more relevant
        source_count = len(candidate.get("source", "").split("+"))
        if source_count >= 2:
            adj += 0.5
        # Alias boost: protect alias-matched LIKE results from being buried by CE score alone
        if (
            candidate.get("alias_matched")
            and "like" in candidate.get("source", "").split("+")
            and _is_exact_alias_query(query, candidate.get("matched_alias"))
        ):
            alias_boost = _ALIAS_RERANK_BOOST
            adj += alias_boost
        phrase_boost = 0.0
        if (
            candidate.get("phrase_matched")
            and candidate.get("matched_phrase")
            and candidate.get("alias_matched")
            and candidate.get("matched_alias")
        ):
            phrase_boost = _EXACT_PHRASE_RERANK_BOOST
            adj += phrase_boost
        adjusted.append((candidate, float(ce_score), adj, alias_boost, phrase_boost))

    # 2026-06-16 (코난 R-B2): rank-fusion of base-RRF order + reranker order.
    # Diagnostic (pool sweep): the cross-encoder displaces well-base-ranked golds
    # (Q09/Q12/Q13/Q24) and buries golds the base retrieval ranks 1-2 (Q04/Q08).
    # Pure-adj sort throws away the base signal. Fusion hedges: a gold at base_rank 0
    # but rerank_rank 15 still gets lifted by the base term. Env-gated, default off =
    # current pure-adj behavior unchanged (live 8400 safe + recoverable).
    if os.environ.get("GRAPHRAG_RERANK_FUSION", "0") == "1":
        _fk = float(os.environ.get("GRAPHRAG_RERANK_FUSION_K", "60"))
        _wb = float(os.environ.get("GRAPHRAG_RERANK_FUSION_WBASE", "1.0"))
        _wr = float(os.environ.get("GRAPHRAG_RERANK_FUSION_WRR", "1.0"))
        # base_rank = index in adjusted (candidates arrive in base-RRF order).
        _adj_order = sorted(range(len(adjusted)), key=lambda i: adjusted[i][2], reverse=True)
        _rr_rank = {orig: r for r, orig in enumerate(_adj_order)}
        _fused = sorted(
            range(len(adjusted)),
            key=lambda i: _wb / (_fk + i) + _wr / (_fk + _rr_rank[i]),
            reverse=True,
        )
        adjusted = [adjusted[i] for i in _fused]
    else:
        adjusted.sort(key=lambda x: x[2], reverse=True)

    results = []
    for candidate, ce_score, adj_score, alias_boost, phrase_boost in adjusted[:top_k]:
        result = dict(candidate)
        result["rerank_score"] = ce_score
        result["adj_score"] = adj_score  # R4 apr13: expose adj for downstream rescoring
        result["alias_boost"] = alias_boost
        result["phrase_boost"] = phrase_boost
        result["confidence"] = _confidence_level(adj_score)
        results.append(result)
    # Protect sparse-channel matches from cross-encoder override before filtering.
    for r in results:
        if r.get("sparse_rank") is not None and r.get("rerank_score", 0) < 0:
            r["rerank_score"] = max(r.get("rerank_score", 0), 0.0)

    # Filter negative rerank but guarantee minimum 3 results (DA safeguard)
    filtered = [r for r in results if r.get("rerank_score", 0) >= 0]
    if len(filtered) < 3 and len(results) >= 3:
        filtered = sorted(results, key=lambda r: r.get("rerank_score", 0), reverse=True)[:3]
    results = filtered if filtered else results[:3]
    return results


# ---------------------------------------------------------------------------
# M6: Community Re-scoring — coherence boost for L1/L2
# ---------------------------------------------------------------------------

def community_rescore(
    results: list[dict],
    conn: sqlite3.Connection,
    query_level: "QueryLevel | None" = None,
) -> list[dict]:
    """Re-score results based on community coherence (M6).

    For L1+ queries, boost results that share community membership
    with other results — entities from the same community cluster
    are more likely to form coherent answer sets.

    L0 is skipped (direct lookup, no community context needed).
    """
    if not results or len(results) < 2:
        return results

    # Skip L0 — direct lookups don't benefit from community coherence
    if query_level == QueryLevel.L0:
        return results

    # Look up community memberships for each result entity
    entity_names = [r.get("entity", "") for r in results]
    entity_communities: dict[str, set[str]] = {}

    try:
        for name in entity_names:
            row = conn.execute(
                "SELECT community_id FROM entities WHERE name = ?",
                (name,),
            ).fetchone()
            if row and row[0]:
                entity_communities[name] = {row[0]}
                # Also check parent community for hierarchy-aware overlap
                parent = conn.execute(
                    "SELECT parent_id FROM communities WHERE id = ?",
                    (row[0],),
                ).fetchone()
                if parent and parent[0]:
                    entity_communities[name].add(parent[0])
            else:
                entity_communities[name] = set()
    except (sqlite3.OperationalError, AttributeError):
        # v2.3.3: AttributeError catch — conn=None case 안 'NoneType' has no attribute 'execute' 차단
        return results  # communities table may not exist 또는 conn=None

    # Calculate community overlap score for each result
    for r in results:
        name = r.get("entity", "")
        my_communities = entity_communities.get(name, set())
        # Coherence boost: 0 if no community, else 0.3 * overlap count
        if my_communities:
            overlap_count = sum(
                1 for other_name in entity_names
                if other_name != name
                and entity_communities.get(other_name, set()) & my_communities
            )
            # R6 apr13: bump 0.3→0.6 to lift Q15/Q17/Q18 (gold MOCs clustered w/ passing MOCs at pos 3-4)
            coherence_boost = overlap_count * 0.6
        else:
            coherence_boost = 0.0
        r["community_coherence"] = coherence_boost

        # Apply coherence boost. R4 apr13: use adj_score (with structural boosts:
        # MOC, centrality, paragraph penalty) instead of raw rerank_score, so
        # community_rescore doesn't discard reranker's structural signals.
        # DA HIGH fix: always assign _adj_score (even community-less) so sort
        # doesn't treat them as 0.
        base_score = r.get("adj_score")
        if base_score is None:
            base_score = r.get("rerank_score", r.get("score", 0))
        r["_adj_score"] = base_score + coherence_boost

    # Re-sort by adjusted score
    results.sort(key=lambda r: r.get("_adj_score", 0), reverse=True)

    # Clean up temporary key
    for r in results:
        r.pop("_adj_score", None)

    return results


# ---------------------------------------------------------------------------
# R1: Typed relation re-scoring — explicit edge boost for L1/L2
# ---------------------------------------------------------------------------

# v2 (2026-07-02 재설계 — 24q A/B v1: 0.6/edge 누적이 rerank_score 스케일(0.003~0.58, 인접격차 ~0.1)을
# 지배해 12/24로 붕괴. 처방: high-class 2종만 소비·δ=rerank 격차의 ~1/5·per-result cap.)
_TYPED_RELATION_BOOSTS: dict[str, float] = {
    "parent": 0.02,
    "contains": 0.0,
    "sourced_from": 0.02,
    "supported_by": 0.0,
    "references": 0.0,
    "part_of": 0.0,
    "aligns_with": 0.0,
    "next": 0.0,
    "prev": 0.0,
    "supersedes": 0.0,
    "derived_from": 0.0,
    "related_to": 0.0,
    "mentions": 0.0,
}

# 한 결과가 받을 수 있는 typed boost 총량 상한 (edge 다수 누적 방지)
_TYPED_RESCORE_CAP: float = 0.04


def _is_l0_query_level(query_level: "QueryLevel | str | None") -> bool:
    if query_level == QueryLevel.L0:
        return True
    return str(query_level) in {"QueryLevel.L0", "L0", "0"}


def typed_relation_rescore(
    results: list[dict],
    conn: sqlite3.Connection,
    query_level: "QueryLevel | None" = None,
) -> list[dict]:
    """Re-score results using explicit typed relations among top result entities."""
    if not results or len(results) < 2:
        return results
    if _is_l0_query_level(query_level):
        return results

    entity_names = [r.get("entity", "") for r in results if r.get("entity")]
    entity_names = list(dict.fromkeys(entity_names))
    if len(entity_names) < 2:
        return results

    placeholders = ",".join("?" * len(entity_names))
    typed_boosts = {name: 0.0 for name in entity_names}
    typed_types: dict[str, set[str]] = {name: set() for name in entity_names}

    try:
        rows = conn.execute(
            f"""
            SELECT e1.name AS source_name, e2.name AS target_name, r.type AS rel_type,
                   COALESCE(r.strength, 1.0) AS strength
              FROM relationships r
              JOIN entities e1 ON e1.id = r.source_id
              JOIN entities e2 ON e2.id = r.target_id
             WHERE e1.name IN ({placeholders})
               AND e2.name IN ({placeholders})
               AND e1.name != e2.name
            """,
            entity_names + entity_names,
        ).fetchall()
    except (sqlite3.OperationalError, AttributeError):
        return results

    for row in rows:
        rel_type = row["rel_type"] if isinstance(row, sqlite3.Row) else row[2]
        source_name = row["source_name"] if isinstance(row, sqlite3.Row) else row[0]
        target_name = row["target_name"] if isinstance(row, sqlite3.Row) else row[1]
        strength = row["strength"] if isinstance(row, sqlite3.Row) else row[3]
        boost = _TYPED_RELATION_BOOSTS.get(str(rel_type), 0.0) * float(strength or 1.0)
        if boost <= 0:
            continue
        for name in (source_name, target_name):
            typed_boosts[name] = typed_boosts.get(name, 0.0) + boost
            typed_types.setdefault(name, set()).add(str(rel_type))

    for r in results:
        name = r.get("entity", "")
        base_score = r.get("_adj_score")
        if base_score is None:
            base_score = r.get("adj_score")
        if base_score is None:
            base_score = r.get("rerank_score", r.get("score", 0))
        community_boost = float(r.get("community_coherence") or 0.0)
        boost = min(typed_boosts.get(name, 0.0), _TYPED_RESCORE_CAP)
        r["typed_relation_boost"] = boost
        r["typed_relation_types"] = sorted(typed_types.get(name, set()))
        r["_adj_score"] = float(base_score or 0.0) + community_boost + boost

    results.sort(key=lambda r: r.get("_adj_score", 0), reverse=True)
    for r in results:
        r.pop("_adj_score", None)

    return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="GraphRAG search (Global/Local routing)")
    parser.add_argument("--db", default=_DEFAULT_DB)
    sub = parser.add_subparsers(dest="mode", required=True)

    # Unified search (auto-routes)
    p_search = sub.add_parser("search", help="Auto-route: classify → global or local")
    p_search.add_argument("query")
    p_search.add_argument("--global-level", type=int, default=1,
                          help="Community level for global search (0=C0..3=C3)")
    p_search.add_argument("--hybrid", action=argparse.BooleanOptionalAction, default=True,
                          help="Enable hybrid (dense+sparse) search (default: on)")
    p_search.add_argument("--rerank", action=argparse.BooleanOptionalAction, default=True,
                          help="Enable cross-encoder reranking (default: on)")
    p_search.add_argument("--dense-weight", type=float, default=DEFAULT_DENSE_WEIGHT,
                          help=f"RRF dense weight (default: {DEFAULT_DENSE_WEIGHT})")
    p_search.add_argument("--sparse-weight", type=float, default=DEFAULT_SPARSE_WEIGHT,
                          help=f"RRF sparse weight (default: {DEFAULT_SPARSE_WEIGHT})")
    p_search.add_argument("--decomposed-weight", type=float, default=DEFAULT_DECOMPOSED_WEIGHT,
                          help=f"RRF decomposed sparse weight (default: {DEFAULT_DECOMPOSED_WEIGHT})")
    p_search.add_argument("--entity-weight", type=float, default=DEFAULT_ENTITY_WEIGHT,
                          help=f"RRF entity dense weight (default: {DEFAULT_ENTITY_WEIGHT})")
    p_search.add_argument("--index-dir", default=DEFAULT_INDEX_DIR,
                          help="Embedding index directory")

    # Explicit modes
    p_insight = sub.add_parser("insight", help="InsightForge: deep thematic (L2 local)")
    p_insight.add_argument("query")

    p_global = sub.add_parser("global", help="Global search: map-reduce over communities (L3)")
    p_global.add_argument("query")
    p_global.add_argument("--level", type=int, default=1)

    p_panorama = sub.add_parser("panorama", help="Panorama: broad community landscape")
    p_panorama.add_argument("query")

    p_quick = sub.add_parser("quick", help="Quick: single entity + N-hop (L0/L1)")
    p_quick.add_argument("entity")
    p_quick.add_argument("--hops", type=int, default=1)

    p_interview = sub.add_parser("interview", help="Interview: full entity narrative")
    p_interview.add_argument("entity")

    # Hybrid search + rerank pipeline
    p_hybrid = sub.add_parser("hybrid", help="Hybrid search (dense+sparse+rerank)")
    p_hybrid.add_argument("query")
    p_hybrid.add_argument("--top-k", type=int, default=10)
    p_hybrid.add_argument("--rerank", action="store_true",
                          help="Enable cross-encoder reranking explicitly")
    p_hybrid.add_argument("--json", action="store_true",
                          help="Accepted for compatibility; hybrid output is JSON")
    p_hybrid.add_argument("--dense-weight", type=float, default=DEFAULT_DENSE_WEIGHT)
    p_hybrid.add_argument("--sparse-weight", type=float, default=DEFAULT_SPARSE_WEIGHT)
    p_hybrid.add_argument("--decomposed-weight", type=float, default=DEFAULT_DECOMPOSED_WEIGHT)
    p_hybrid.add_argument("--entity-weight", type=float, default=DEFAULT_ENTITY_WEIGHT)
    p_hybrid.add_argument("--no-rerank", action="store_true",
                          help="Skip cross-encoder reranking")
    p_hybrid.add_argument("--index-dir", default=DEFAULT_INDEX_DIR)

    # Classify only
    p_classify = sub.add_parser("classify", help="Classify query complexity level")
    p_classify.add_argument("query")

    args = parser.parse_args()

    if args.mode == "classify":
        level = classify_query_complexity(args.query)
        print(f"Query: {args.query!r}")
        print(f"Complexity: {level.name} (depth={_DEPTH_MAP.get(level, 'map-reduce')})")
        sys.exit(0)

    conn = get_connection(args.db)

    # Lazy graph build — only needed for non-hybrid modes
    _graph_cache = [None]

    def _ensure_graph():
        if _graph_cache[0] is None:
            from community_detector import build_networkx_graph
            _graph_cache[0] = build_networkx_graph(conn)
        return _graph_cache[0]

    if args.mode == "search":
        if getattr(args, "hybrid", True):
            hybrid_candidates = hybrid_search(
                conn, args.query,
                output_dir=getattr(args, "index_dir", DEFAULT_INDEX_DIR),
                top_k=20,
                dense_weight=getattr(args, "dense_weight", DEFAULT_DENSE_WEIGHT),
                sparse_weight=getattr(args, "sparse_weight", DEFAULT_SPARSE_WEIGHT),
                decomposed_weight=getattr(args, "decomposed_weight", DEFAULT_DECOMPOSED_WEIGHT),
                entity_weight=getattr(args, "entity_weight", DEFAULT_ENTITY_WEIGHT),
            )
            if getattr(args, "rerank", True) and hybrid_candidates:
                final_candidates = rerank(args.query, hybrid_candidates, top_k=10)
                search_type = "hybrid+rerank"
            else:
                final_candidates = hybrid_candidates[:10]
                search_type = "hybrid"
            # Merge hybrid context into standard search result
            base = search(conn, _ensure_graph(), args.query, global_community_level=args.global_level)
            base["hybrid_results"] = final_candidates
            base["search_type"] = search_type
            result = base
        else:
            result = search(conn, _ensure_graph(), args.query, global_community_level=args.global_level)
    elif args.mode == "hybrid":
        hybrid_candidates = hybrid_search(
            conn, args.query,
            output_dir=args.index_dir,
            top_k=args.top_k,
            dense_weight=args.dense_weight,
            sparse_weight=args.sparse_weight,
            decomposed_weight=args.decomposed_weight,
            entity_weight=args.entity_weight,
        )
        if not args.no_rerank and hybrid_candidates:
            final_candidates = rerank(args.query, hybrid_candidates, top_k=args.top_k)
            search_type = "hybrid+rerank"
        else:
            final_candidates = hybrid_candidates
            search_type = "hybrid"
        close_connection(conn)
        print(json.dumps({
            "query": args.query,
            "results": final_candidates,
            "search_type": search_type,
        }, indent=2, ensure_ascii=False))
        sys.exit(0)
    elif args.mode == "insight":
        result = insight_forge(conn, _ensure_graph(), args.query)
    elif args.mode == "global":
        result = global_search(conn, _ensure_graph(), args.query, community_level=args.level)
    elif args.mode == "panorama":
        result = panorama_search(conn, _ensure_graph(), args.query)
    elif args.mode == "quick":
        result = quick_search(conn, _ensure_graph(), args.entity, hops=args.hops)
    elif args.mode == "interview":
        result = interview(conn, _ensure_graph(), args.entity)
    else:
        parser.print_help()
        close_connection(conn)
        sys.exit(1)

    close_connection(conn)
    print(json.dumps(result, indent=2, ensure_ascii=False))
