"""
FastAPI server for GraphRAG search — keeps models resident in memory.
Usage: uvicorn search_server:app --host 127.0.0.1 --port 8400
"""
from __future__ import annotations

import os
import json
import sqlite3
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from queue import Full, Queue
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

import embedding_index
import graph_search
from community_detector import build_networkx_graph
from community_detector import run_community_detection
from frontmatter_sync import sync_frontmatter_to_graph
from graphrag_core import close_connection, create_fts5_tables, get_connection, populate_fts5
from incremental import detect_changes, incremental_update

PROJECT_DIR = Path(__file__).resolve().parents[3]
# v2.3.1: env override + CI fresh env 안 graceful start (vault_graph.db anchor 없어도 server up)
DEFAULT_DB_PATH = Path(os.environ.get(
    "GRAPHRAG_DB_PATH",
    str(PROJECT_DIR / ".team-os/graphrag/index/vault_graph.db"),
))
DEFAULT_INDEX_DIR = Path(os.environ.get(
    "GRAPHRAG_INDEX_DIR",
    str(PROJECT_DIR / graph_search.DEFAULT_INDEX_DIR),
))
DEFAULT_VAULT_PATH = Path(os.environ.get(
    "GRAPHRAG_VAULT_PATH",
    "<vault>",
))
ALLOWED_ORIGINS = [
    "http://127.0.0.1:3748",
    "http://localhost:3748",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]
VALID_SEARCH_MODES = {"hybrid", "quick", "deep"}
# akwiki 공개 인스턴스(8401) 전용 가드 — 기본 0 = 기존(내부 8400) 동작 완전 무변 (2026-07-07 손석희 serving 리뷰 finding 3·4)
PUBLIC_MODE = os.environ.get("GRAPHRAG_PUBLIC_MODE", "0") == "1"
QUERY_LOG_DIR = Path(os.environ.get(
    "GRAPHRAG_QUERY_LOG_DIR",
    str(PROJECT_DIR / ".team-os/graphrag/logs"),
))
EMBEDDING_WORKER_STATUS_PATH = Path(os.environ.get(
    "GRAPHRAG_EMBED_WORKER_STATUS",
    str(PROJECT_DIR / ".team-os/graphrag/index-generations/status.json"),
))

# P1: Readiness gate — search blocks until models are loaded
_models_ready = threading.Event()
_index_update_lock = threading.Lock()
_index_update_status_lock = threading.Lock()
_INDEX_UPDATE_STATUS_DEFAULT = {
    "update_in_progress": False,
    "phase": "idle",
    "started_at": None,
    "finished_at": None,
    "last_result": None,
    "last_error": None,
}
_index_update_status: dict[str, Any] = dict(_INDEX_UPDATE_STATUS_DEFAULT)
_KST = ZoneInfo("Asia/Seoul")
_QUERY_LOG_QUEUE: Queue[dict[str, Any]] = Queue(maxsize=1000)
_QUERY_LOG_THREAD_LOCK = threading.Lock()
_QUERY_LOG_THREAD_STARTED = False


def _typed_relation_rescore_enabled() -> bool:
    return os.environ.get("GRAPHRAG_TYPED_RESCORE", "0") == "1"


def _kst_timestamp() -> str:
    return datetime.now(_KST).isoformat(timespec="seconds")


def _reset_index_update_status() -> None:
    with _index_update_status_lock:
        _index_update_status.clear()
        _index_update_status.update(_INDEX_UPDATE_STATUS_DEFAULT)


def _set_index_update_status(**changes: Any) -> None:
    with _index_update_status_lock:
        _index_update_status.update(changes)


def _get_index_update_status() -> dict[str, Any]:
    with _index_update_status_lock:
        status = dict(_index_update_status)
        if isinstance(status.get("last_result"), dict):
            status["last_result"] = dict(status["last_result"])
        return status


def _get_embedding_worker_status() -> dict[str, Any]:
    try:
        payload = json.loads(EMBEDDING_WORKER_STATUS_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"phase": "not_configured"}
    return payload if isinstance(payload, dict) else {"phase": "invalid_status"}


def _safe_tsv_field(value: Any) -> str:
    return str(value).replace("\t", " ").replace("\r", " ").replace("\n", " ")


def _caller_from_request(request: Request) -> dict[str, str]:
    client = request.client.host if request.client else ""
    return {
        "user_agent": request.headers.get("user-agent", "")[:200],
        "x_caller": request.headers.get("x-caller", "")[:120],
        "remote_addr": client[:80],
    }


def _write_query_log_record(record: dict[str, Any], log_dir: Path | None = None) -> None:
    target_dir = Path(log_dir) if log_dir is not None else QUERY_LOG_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    query_log_path = target_dir / "query-log.jsonl"
    with query_log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    if not record.get("failure_type"):
        return

    failed_path = target_dir / "failed-queries.tsv"
    needs_header = not failed_path.exists() or failed_path.stat().st_size == 0
    with failed_path.open("a", encoding="utf-8") as handle:
        if needs_header:
            handle.write("timestamp_kst\tfailure_type\tstatus_code\tresult_count\telapsed_ms\tquery\n")
        fields = [
            record.get("timestamp_kst", ""),
            record.get("failure_type", ""),
            record.get("status_code", ""),
            record.get("result_count", ""),
            record.get("elapsed_ms", ""),
            record.get("query", ""),
        ]
        handle.write("\t".join(_safe_tsv_field(field) for field in fields) + "\n")


def _query_log_worker() -> None:
    while True:
        record = _QUERY_LOG_QUEUE.get()
        try:
            _write_query_log_record(record)
        except Exception:
            pass
        finally:
            _QUERY_LOG_QUEUE.task_done()


def _ensure_query_log_worker() -> None:
    global _QUERY_LOG_THREAD_STARTED
    if _QUERY_LOG_THREAD_STARTED:
        return
    with _QUERY_LOG_THREAD_LOCK:
        if _QUERY_LOG_THREAD_STARTED:
            return
        threading.Thread(target=_query_log_worker, daemon=True).start()
        _QUERY_LOG_THREAD_STARTED = True


def _enqueue_query_log(record: dict[str, Any]) -> None:
    _ensure_query_log_worker()
    try:
        _QUERY_LOG_QUEUE.put_nowait(record)
    except Full:
        pass


def _clear_model_caches() -> None:
    embedding_index._model = None
    graph_search._cross_encoder = None
    graph_search.clear_hybrid_cache()


def _warm_models() -> None:
    embedding_index._get_model()
    try:
        graph_search._get_cross_encoder()
    except ImportError:
        pass


def _open_readonly_connection(db_path: Path | str) -> sqlite3.Connection:
    db = Path(db_path)
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _load_runtime_state(
    db_path: Path = DEFAULT_DB_PATH,
    index_dir: Path = DEFAULT_INDEX_DIR,
) -> dict[str, Any]:
    # v2.3.1: db_path 안 graceful — anchor 없으면 conn = None (CI fresh env / vault 미index 환경 안 startup 통과)
    db_p = Path(db_path)
    conn = _open_readonly_connection(db_p) if db_p.exists() else None
    note_index = None
    entity_index = None
    if conn is not None:
        try:
            note_index = embedding_index.load_index(str(index_dir))
        except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError, AttributeError):
            note_index = None
        try:
            entity_index = embedding_index.load_entity_index(str(index_dir))
        except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError, AttributeError):
            entity_index = None
    # P1: Don't call _warm_models() here — moved to background thread
    return {
        "db_path": str(db_p),
        "index_dir": str(index_dir),
        "conn": conn,
        "graph": None,
        "note_index": note_index,
        "entity_index": entity_index,
    }


def _get_graph(app: FastAPI):
    # v2.3.2: conn=None graceful — graph build requires DB anchor
    if getattr(app.state, "conn", None) is None:
        raise HTTPException(
            status_code=503,
            detail="GraphRAG index not built. Run vault index build first, then POST /reload or restart server.",
        )
    if getattr(app.state, "graph", None) is None:
        app.state.graph = build_networkx_graph(app.state.conn)
    return app.state.graph


def _replace_runtime_state(app: FastAPI, state: dict[str, Any]) -> None:
    old_conn = getattr(app.state, "conn", None)
    if old_conn is not None:
        close_connection(old_conn)
    for key, value in state.items():
        setattr(app.state, key, value)


def _run_incremental_index_update(
    *,
    db_path: Path | str,
    vault_path: Path | str,
    index_dir: Path | str,
    use_llm: bool = False,
    rebuild_embeddings: bool = True,
    rebuild_entities: bool = True,
) -> dict[str, Any]:
    db_p = Path(db_path)
    vault_p = Path(vault_path)
    index_p = Path(index_dir)

    _set_index_update_status(phase="detect_changes")
    conn = get_connection(str(db_p))
    try:
        changes = detect_changes(conn, vault_p)
        total_changes = sum(len(paths) for paths in changes.values())
        stats = {"added": 0, "modified": 0, "deleted": 0, "errors": 0}
        communities: dict[str, Any] | None = None
        frontmatter_alias_sync: dict[str, int] = {"processed": 0, "errors": 0}

        if total_changes:
            _set_index_update_status(phase="graph_update")
            stats = incremental_update(conn, vault_p, changes, use_llm=use_llm)
            frontmatter_alias_sync = sync_frontmatter_to_graph(conn, vault_p)
            communities = run_community_detection(
                conn,
                changed_count=total_changes,
                force=False,
            )

        if total_changes:
            _set_index_update_status(phase="fts")
            create_fts5_tables(conn)
            populate_fts5(conn)
    finally:
        close_connection(conn)

    effective_rebuild_embeddings = rebuild_embeddings and total_changes > 0
    effective_rebuild_entities = rebuild_entities and total_changes > 0

    if effective_rebuild_embeddings:
        _set_index_update_status(phase="note_embeddings")
        embedding_index.build_index(
            vault_path=str(vault_p),
            db_path=str(db_p),
            output_dir=str(index_p),
        )
    if effective_rebuild_entities:
        _set_index_update_status(phase="entity_embeddings")
        embedding_index.build_entity_index(
            db_path=str(db_p),
            output_dir=str(index_p),
        )

    return {
        "status": "updated" if total_changes else "up_to_date",
        "db_path": str(db_p),
        "vault_path": str(vault_p),
        "index_dir": str(index_p),
        "changes": changes,
        "stats": stats,
        "total_changes": total_changes,
        "frontmatter_alias_sync": frontmatter_alias_sync,
        "communities": communities,
        "embedding_rebuilt": effective_rebuild_embeddings,
        "entity_embedding_rebuilt": effective_rebuild_entities,
    }


def _execute_index_update_background(
    *,
    db_path: Path,
    vault_path: Path,
    index_dir: Path,
    use_llm: bool,
    rebuild_embeddings: bool,
    rebuild_entities: bool,
    reload_runtime: bool,
) -> None:
    _set_index_update_status(update_in_progress=True, phase="running")
    try:
        result = _run_incremental_index_update(
            db_path=db_path,
            vault_path=vault_path,
            index_dir=index_dir,
            use_llm=use_llm,
            rebuild_embeddings=rebuild_embeddings,
            rebuild_entities=rebuild_entities,
        )

        should_reload_runtime = reload_runtime and result.get("total_changes", 0) > 0
        if should_reload_runtime:
            _set_index_update_status(phase="reload_runtime")
            graph_search.clear_hybrid_cache()
            new_state = _load_runtime_state(db_path)
            _replace_runtime_state(app, new_state)

        result["runtime_reloaded"] = should_reload_runtime
        app.state.last_index_update = result
        _set_index_update_status(
            update_in_progress=False,
            phase="completed",
            finished_at=_kst_timestamp(),
            last_result={
                "status": result.get("status"),
                "total_changes": result.get("total_changes", 0),
                "embedding_rebuilt": result.get("embedding_rebuilt", False),
                "entity_embedding_rebuilt": result.get("entity_embedding_rebuilt", False),
                "runtime_reloaded": should_reload_runtime,
            },
            last_error=None,
        )
    except Exception as exc:
        app.state.last_index_update = {
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
            "db_path": str(db_path),
            "vault_path": str(vault_path),
            "index_dir": str(index_dir),
        }
        _set_index_update_status(
            update_in_progress=False,
            phase="error",
            finished_at=_kst_timestamp(),
            last_error=f"{type(exc).__name__}: {exc}",
        )
        raise
    finally:
        _index_update_lock.release()


@asynccontextmanager
async def lifespan(app: FastAPI):
    state = _load_runtime_state()
    _replace_runtime_state(app, state)

    # P1+P2: Background model warmup + diverse query warmup for CV stability
    def _background_warmup():
        # v2.3.1: conn None 시 (anchor 없음, CI fresh env) early return — server 는 up, warmup skip
        if state["conn"] is None:
            _models_ready.set()
            return
        _warm_models()
        # P2: Run diverse warmup queries to prime FTS5/embedding/reranker caches
        warmup_queries = ["GraphRAG", "프롬프트 엔지니어링", "AI 에이전트", "얼룩소"]
        try:
            warmup_conn = _open_readonly_connection(state["db_path"])
            for wq in warmup_queries:
                results = graph_search.hybrid_search(
                    warmup_conn, wq,
                    output_dir=state["index_dir"], top_k=5,
                    note_index=state["note_index"],
                    entity_index=state["entity_index"],
                )
                if results:
                    graph_search.rerank(wq, results, top_k=5)
            close_connection(warmup_conn)
        except Exception:
            pass
        _models_ready.set()

    threading.Thread(target=_background_warmup, daemon=True).start()

    yield
    conn = getattr(app.state, "conn", None)
    if conn is not None:
        close_connection(conn)


app = FastAPI(title="GraphRAG Search Server", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    # v2.3.2: liveness only — process up 확인용. readiness gate 아님.
    # CI / Docker healthcheck 는 /ready 사용 의무.
    db_ready = getattr(app.state, "conn", None) is not None
    search_ready = db_ready and _models_ready.is_set()
    return {
        "status": "ok",
        "models_ready": _models_ready.is_set(),
        "db_ready": db_ready,
        "search_ready": search_ready,
        "index_update": _get_index_update_status(),
    }


@app.get("/ready")
async def ready():
    # v2.3.2: readiness gate 별도 endpoint — CI / Docker HEALTHCHECK 의무 URL.
    # axis C 2-round debate (codex R2) 권고: /health 가 liveness-only false-positive readiness 차단.
    if getattr(app.state, "conn", None) is None:
        raise HTTPException(
            status_code=503,
            detail={"ready": False, "reason": "db_not_ready", "hint": "vault index not built — run vault index build + POST /reload"},
        )
    if not _models_ready.is_set():
        raise HTTPException(
            status_code=503,
            detail={"ready": False, "reason": "warmup_in_progress"},
        )
    return {"ready": True, "db_path": app.state.db_path}


@app.get("/api/index/status")
async def index_update_status():
    """Expose update lifecycle so monitors do not kill a healthy rebuild."""
    status = _get_index_update_status()
    status["embedding_worker"] = _get_embedding_worker_status()
    return status


def _is_local_request(request: Request) -> bool:
    host = request.client.host if request.client else ""
    return host in {"127.0.0.1", "::1", "localhost", "testclient"}


@app.post("/api/index/activate")
async def activate_index(request: Request):
    """Reload verified generation files without evicting resident ML models."""
    if PUBLIC_MODE or not _is_local_request(request):
        raise HTTPException(status_code=403, detail="local activation only")
    db_path = Path(getattr(app.state, "db_path", str(DEFAULT_DB_PATH)))
    index_dir = Path(getattr(app.state, "index_dir", str(DEFAULT_INDEX_DIR)))
    new_state = _load_runtime_state(db_path, index_dir)
    if new_state.get("conn") is None or new_state.get("note_index") is None:
        new_conn = new_state.get("conn")
        if new_conn is not None:
            close_connection(new_conn)
        raise HTTPException(status_code=503, detail="verified runtime index unavailable")
    graph_search.clear_hybrid_cache()
    _replace_runtime_state(app, new_state)
    return {
        "status": "activated",
        "db_path": app.state.db_path,
        "index_dir": app.state.index_dir,
    }


@app.post("/reload")
async def reload_models():
    if PUBLIC_MODE:
        raise HTTPException(status_code=403, detail="disabled in public mode")
    # v2.3.2: reload 시 models_ready clear + background warmup re-start
    _clear_model_caches()
    _models_ready.clear()
    new_state = _load_runtime_state(Path(app.state.db_path))
    _replace_runtime_state(app, new_state)

    # background warmup re-execution (lifespan 안 logic 동등)
    def _reload_warmup():
        if new_state["conn"] is None:
            _models_ready.set()
            return
        _warm_models()
        _models_ready.set()

    threading.Thread(target=_reload_warmup, daemon=True).start()

    return {
        "status": "reloaded",
        "db_path": app.state.db_path,
        "index_dir": app.state.index_dir,
        "db_ready": new_state["conn"] is not None,
    }


@app.post("/api/index/update")
async def update_index(
    background_tasks: BackgroundTasks,
    vault_path: str | None = Query(None),
    rebuild_embeddings: bool = Query(True),
    rebuild_entities: bool = Query(True),
    use_llm: bool = Query(False),
    reload_runtime: bool = Query(True),
):
    if PUBLIC_MODE:
        raise HTTPException(status_code=403, detail="disabled in public mode")
    if not _index_update_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=409,
            detail={"error": "index_update_in_progress"},
        )

    try:
        db_path = Path(getattr(app.state, "db_path", str(DEFAULT_DB_PATH)))
        index_dir = Path(getattr(app.state, "index_dir", str(DEFAULT_INDEX_DIR)))
        vault = Path(vault_path) if vault_path else DEFAULT_VAULT_PATH

        background_tasks.add_task(
            _execute_index_update_background,
            db_path=db_path,
            vault_path=vault,
            index_dir=index_dir,
            use_llm=use_llm,
            rebuild_embeddings=rebuild_embeddings,
            rebuild_entities=rebuild_entities,
            reload_runtime=reload_runtime,
        )
        _set_index_update_status(
            update_in_progress=True,
            phase="queued",
            started_at=_kst_timestamp(),
            finished_at=None,
            last_error=None,
        )
        return {
            "status": "accepted",
            "update_in_progress": True,
            "db_path": str(db_path),
            "vault_path": str(vault),
            "index_dir": str(index_dir),
            "rebuild_embeddings_requested": rebuild_embeddings,
            "rebuild_entities_requested": rebuild_entities,
            "reload_runtime_requested": reload_runtime,
        }
    except Exception:
        _index_update_lock.release()
        raise


@app.get("/api/search")
async def search(
    request: Request,
    q: str = Query(..., min_length=1),
    mode: str = Query("hybrid"),
    top_k: int = Query(20, ge=1, le=100),
    dense_weight: float = Query(graph_search.DEFAULT_DENSE_WEIGHT),
    sparse_weight: float = Query(graph_search.DEFAULT_SPARSE_WEIGHT),
    decomposed_weight: float = Query(graph_search.DEFAULT_DECOMPOSED_WEIGHT),
    entity_weight: float = Query(graph_search.DEFAULT_ENTITY_WEIGHT),
    rerank: bool = Query(True),
):
    start_time = time.perf_counter()
    status_code = 200
    result_count = 0
    failure_type: str | None = None
    phase_timings_ms = {
        "cache_hit": 0.0,
        "qe": 0.0,
        "dense": 0.0,
        "hybrid_total": 0.0,
        "rerank": 0.0,
        "rescore": 0.0,
    }

    try:
        if mode not in VALID_SEARCH_MODES:
            status_code = 400
            raise HTTPException(
                status_code=400,
                detail=f"Invalid mode: {mode}. Valid: {sorted(VALID_SEARCH_MODES)}",
            )

        # v2.3.2: conn=None graceful — DB anchor 없으면 503 (fresh env / vault index 미build)
        if app.state.conn is None:
            status_code = 503
            failure_type = "http_5xx"
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "GraphRAG index not built",
                    "message": "Vault index has not been built. Build index first, then POST /reload or restart server.",
                    "db_path": getattr(app.state, "db_path", str(DEFAULT_DB_PATH)),
                },
            )

        # P1: Wait for background model warmup (up to 60s)
        if not _models_ready.wait(timeout=60):
            status_code = 503
            failure_type = "timeout"
            raise HTTPException(
                status_code=503,
                detail={"error": "models_warmup_timeout", "message": "Search models did not become ready within 60s."},
            )

        phase_started = time.perf_counter()
        results = graph_search.hybrid_search(
            app.state.conn,
            q,
            output_dir=app.state.index_dir,
            top_k=top_k,
            dense_weight=dense_weight,
            sparse_weight=sparse_weight,
            decomposed_weight=decomposed_weight,
            entity_weight=entity_weight,
            note_index=getattr(app.state, "note_index", None),
            entity_index=getattr(app.state, "entity_index", None),
            timings=phase_timings_ms,
        )
        phase_timings_ms["hybrid_total"] = round((time.perf_counter() - phase_started) * 1000, 3)
        phase_started = time.perf_counter()
        final_results = graph_search.rerank(q, results, top_k=top_k) if rerank and results else results
        phase_timings_ms["rerank"] = round((time.perf_counter() - phase_started) * 1000, 3)
        # M6: Community re-scoring for L1+ queries
        phase_started = time.perf_counter()
        if final_results and len(final_results) >= 2:
            query_level = graph_search.classify_query_complexity(q)
            final_results = graph_search.community_rescore(final_results, app.state.conn, query_level)
            if _typed_relation_rescore_enabled():
                final_results = graph_search.typed_relation_rescore(final_results, app.state.conn, query_level)
        phase_timings_ms["rescore"] = round((time.perf_counter() - phase_started) * 1000, 3)
        result_count = len(final_results)
        if result_count == 0:
            failure_type = "zero_results"
        search_type = "hybrid+rerank" if rerank and results else "hybrid"
        return {
            "query": q,
            "results": final_results,
            "total": result_count,
            "source": "hybrid",
            "search_type": search_type,
        }
    except TimeoutError as exc:
        status_code = 504
        failure_type = "timeout"
        raise HTTPException(
            status_code=504,
            detail={"error": "search_timeout", "message": str(exc)},
        ) from exc
    except HTTPException as exc:
        status_code = exc.status_code
        if exc.status_code >= 500 and failure_type is None:
            failure_type = "http_5xx"
        raise
    except Exception:
        status_code = 500
        failure_type = "http_5xx"
        raise
    finally:
        _enqueue_query_log({
            "timestamp_kst": _kst_timestamp(),
            # PUBLIC_MODE: 방문자 발화 원문 저장 ❌ ("대화 내용 저장 안 함" 공지 정합 — 손석희 finding 3)
            "query": (f"sha256:{__import__('hashlib').sha256(q.encode()).hexdigest()[:16]} len={len(q)}" if PUBLIC_MODE else q),
            "mode": mode,
            "top_k": top_k,
            "rerank": rerank,
            "caller": _caller_from_request(request),
            "elapsed_ms": round((time.perf_counter() - start_time) * 1000, 3),
            "phase_timings_ms": phase_timings_ms,
            "result_count": result_count,
            "status_code": status_code,
            "failure_type": failure_type,
        })


@app.get("/api/search/entities")
async def search_entities(
    q: str = Query(..., min_length=1),
    top_k: int = Query(10, ge=1, le=100),
):
    # v2.3.2: entity index 파일 부분 corrupt / missing 시 graceful 503 (uncaught 500 방지)
    try:
        # P3: Cross-lingual query expansion for entity search
        expanded_q = graph_search.expand_query_cross_lingual(q)
        entity_index = getattr(app.state, "entity_index", None)
        if entity_index is not None:
            raw_results = embedding_index.search_entities_loaded(
                expanded_q,
                entity_index,
                top_k=top_k,
            )
        else:
            raw_results = embedding_index.search_entities(expanded_q, app.state.index_dir, top_k=top_k)
    except (FileNotFoundError, ImportError, ValueError, OSError) as exc:
        # entity_embeddings.npy / entity_meta.json missing / corrupt / load fail
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Entity index not built",
                "message": f"Entity index unavailable: {type(exc).__name__}. Build index first, then POST /reload.",
                "index_dir": str(app.state.index_dir),
            },
        )
    results = [
        {
            **row,
            "entity": row.get("entity") or row.get("name", ""),
            "name": row.get("name") or row.get("entity", ""),
        }
        for row in raw_results
    ]
    return {
        "query": q,
        "expanded_query": expanded_q if expanded_q != q else None,
        "results": results,
        "total": len(results),
        "source": "entity",
    }
