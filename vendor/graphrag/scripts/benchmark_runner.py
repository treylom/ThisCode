"""
benchmark_runner.py — GraphRAG evaluation harness
Runs test queries against search_server.py, measures latency, collects results.
Usage: python benchmark_runner.py [--server http://127.0.0.1:8400] [--runs 3] [--output results.json]
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

try:
    import httpx
except ImportError:
    print("httpx required: pip install httpx", file=sys.stderr)
    sys.exit(1)

# ── 18 test queries with metadata ──────────────────────────────────────

QUERIES: list[dict[str, Any]] = [
    # L0 — Direct Lookup (5)
    {"id": "Q01", "level": "L0", "query": "GraphRAG",
     "gold_notes": ["GraphRAG-Theory-MOC", "Obsidian-GraphRAG-Journey-MOC"]},
    {"id": "Q02", "level": "L0", "query": "프롬프트 엔지니어링",
     "gold_notes": ["프롬프트-작성법-종합-가이드-MOC-2026-02", "AI-프롬프트-마스터클래스-MOC"]},
    {"id": "Q03", "level": "L0", "query": "얼룩소 아카이브",
     "gold_notes": ["얼룩소-아카이브-MOC"]},
    {"id": "Q04", "level": "L0", "query": "Claude Code 스킬",
     "gold_notes": ["Claude-Code-Skills-2.0-MOC"]},
    {"id": "Q05", "level": "L0", "query": "김재경",
     "gold_notes": ["김재경-aboutme-MOC", "tofukyung-persona-MOC"]},

    # L1 — Relationship Exploration (5)
    {"id": "Q06", "level": "L1", "query": "얼룩소에서 AI에 대해 쓴 글",
     "gold_notes": ["AI-기술-MOC", "얼룩소-아카이브-MOC"]},
    {"id": "Q07", "level": "L1", "query": "에이전트 팀 구성하는 방법",
     # 2026-06-16 (코난, 재경님 (b) 승인): + 실전 사용사례 노트(agent-teams 태그). ⚠️ 가장 borderline — query는 '구성법', 노트는 'use-case'. 재경님/팀 재판단 여지. 원 gold 보존.
     "gold_notes": ["Agent-Teams-실전사례-시리즈", "Knowledge-Manager-Agent-Teams-Guide-2026-02", "AI-에이전트-팀-실전-사용사례-4선-2026-03-03"]},
    {"id": "Q08", "level": "L1", "query": "성우하이텍 마스터 강의 내용",
     # 2026-06-16 (코난, 재경님 (b)): + 성우하이텍 마스터과정 MOC(질의와 토픽 정확 일치, 실 강의노트 hub). 원 gold(AI강의-MOC) 보존. 실독 검증 GREEN.
     "gold_notes": ["성우하이텍-AI강의-MOC", "성우하이텍-마스터과정-MOC"]},
    {"id": "Q09", "level": "L1", "query": "Anthropic AI Safety 관련 연구",
     # 2026-06-16 (코난, 재경님 (b)): "AI-Safety" = vault 부재(stale) 제거 + Claude-Mythos-RSP-안전평가(Anthropic 안전연구 실물, tags AI-Safety/RSP/Anthropic, source anthropic.com) 추가. Pentagon(tangential) 보존.
     "gold_notes": ["Anthropic-Pentagon-AI-군사화-대치-2026-02-MOC", "Claude-Mythos-RSP-안전평가"]},
    {"id": "Q10", "level": "L1", "query": "Obsidian 자동화 워크플로우",
     "gold_notes": ["Obsidian-GraphRAG-Journey-MOC"]},

    # L2 — Multi-hop Analysis (5)
    {"id": "Q11", "level": "L2", "query": "AI가 민주주의에 미치는 영향에 대해 내가 쓴 글",
     "gold_notes": ["AI-기술-MOC", "정치-민주주의-MOC"]},
    {"id": "Q12", "level": "L2", "query": "프롬프트 설계가 에이전트 성능에 미치는 영향",
     "gold_notes": ["프롬프트-작성법-종합-가이드-MOC-2026-02", "Efficient-Agents-Benchmarks-MOC"]},
    {"id": "Q13", "level": "L2", "query": "Knowledge Manager에서 GraphRAG까지 발전 과정",
     "gold_notes": ["Obsidian-GraphRAG-Journey-MOC"]},
    {"id": "Q14", "level": "L2", "query": "2026년 AI 에이전트 트렌드와 실무 적용 사례",
     "gold_notes": ["Google-AI-Agent-Trends-2026-MOC", "Agent-Teams-실전사례-시리즈"]},
    {"id": "Q15", "level": "L2", "query": "얼룩소 플랫폼 분석과 콘텐츠 전략 인사이트",
     "gold_notes": ["플랫폼-미디어-MOC"]},

    # L3 — Corpus-wide Synthesis (3)
    {"id": "Q16", "level": "L3", "query": "내 지식 체계에서 가장 핵심적인 주제 3가지와 그 연결 관계",
     "gold_notes": ["얼룩소-아카이브-MOC", "AI-기술-MOC", "정치-민주주의-MOC"]},
    {"id": "Q17", "level": "L3", "query": "AI 연구부터 강의, 실무 적용까지의 전체 여정",
     "gold_notes": ["AI-기술-MOC", "성우하이텍-AI강의-MOC", "Obsidian-GraphRAG-Journey-MOC"]},
    {"id": "Q18", "level": "L3", "query": "정치/사회 글쓰기와 AI 기술 연구가 어떻게 연결되는가",
     "gold_notes": ["얼룩소-아카이브-MOC", "AI-기술-MOC", "정치-민주주의-MOC"]},

    # Conan verified additions — 2026-06-06, phantom gold check passed
    {"id": "Q19", "level": "L0", "query": "MCP",
     "gold_notes": ["MCP-생태계-현재와-미래-MOC", "MCP-Model-Context-Protocol"]},
    {"id": "Q20", "level": "L1", "query": "RAG와 GraphRAG의 차이",
     "gold_notes": ["GraphRAG-Theory-MOC", "Journey-05-GraphRAG-Theory-Foundation"]},
    {"id": "Q21", "level": "L1", "query": "reranker 재정렬 원리",
     # 2026-06-16 (코난, 재경님 (b)): + Reranker-검색-재정렬-기법(질의의 캐노니컬 정답 — 제목 "Reranker, 검색결과 정밀 재평가", 본문 "1차 후보군 재점수·재배열"). 원 gold(Journey dev로그) 보존.
     "gold_notes": ["Journey-13-Search-v2-4Channel-Server", "Journey-16-Autoresearch-v4-CE-Mastery", "Reranker-검색-재정렬-기법"]},
    {"id": "Q22", "level": "L1", "query": "벡터 임베딩 의미 검색",
     "gold_notes": ["Journey-12-Hybrid-Search-Upgrade", "Journey-13-Search-v2-4Channel-Server"]},
    {"id": "Q23", "level": "L1", "query": "agent orchestration patterns",
     "gold_notes": ["Agent-Teams-아키텍처", "Building-Effective-Agents-Orchestrator-Workers", "Claude-46-Subagent-Orchestration"]},
    {"id": "Q24", "level": "L1", "query": "Embedding Vector Space Geometry",
     "gold_notes": ["임베딩과-벡터공간-기하학"]},
]


def _result_name(result: dict[str, Any]) -> str:
    return str(result.get("entity", result.get("name", result.get("note_path", ""))))


def _basename_without_suffix(value: str) -> str:
    name = Path(value).name
    return name[:-3] if name.endswith(".md") else name


def _matches_gold(result_name: str, gold_name: str) -> bool:
    return bool(result_name and gold_name and _basename_without_suffix(result_name).casefold() == gold_name.casefold())


def retrieval_metrics(result_names: list[str], gold_notes: list[str], k: int = 5) -> dict[str, Any]:
    """Compute model-independent retrieval metrics from ordered result names."""
    if not gold_notes:
        return {"hit_at_5": False, "precision_at_5": 0.0, "first_gold_rank": None, "mrr": 0.0}

    top_k_names = result_names[:k]
    relevant_at_k = sum(
        1 for name in top_k_names
        if any(_matches_gold(name, gold_name) for gold_name in gold_notes)
    )
    first_gold_rank = None
    for idx, name in enumerate(result_names, start=1):
        if any(_matches_gold(name, gold_name) for gold_name in gold_notes):
            first_gold_rank = idx
            break

    return {
        "hit_at_5": first_gold_rank is not None and first_gold_rank <= 5,
        "precision_at_5": round(relevant_at_k / k, 3),
        "first_gold_rank": first_gold_rank,
        "mrr": round(1 / first_gold_rank, 3) if first_gold_rank else 0.0,
    }


def _search_params(q: dict, search_options: dict[str, Any] | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {"q": q["query"], "mode": "hybrid", "top_k": 10, "rerank": "true"}
    for key, value in (search_options or {}).items():
        if value is None:
            continue
        if key == "rerank" and isinstance(value, bool):
            params[key] = "true" if value else "false"
        else:
            params[key] = value
    return params


def run_single_query(
    client: httpx.Client,
    server: str,
    q: dict,
    search_options: dict[str, Any] | None = None,
) -> dict:
    """Run one query, return results + latency."""
    url = f"{server}/api/search"
    params = _search_params(q, search_options)
    start = time.perf_counter()
    try:
        resp = client.get(url, params=params, timeout=60.0)
        elapsed_ms = (time.perf_counter() - start) * 1000
        if resp.status_code == 200:
            data = resp.json()
            return {
                "status": "ok",
                "latency_ms": round(elapsed_ms, 1),
                "results": data.get("results", []),
                "total": data.get("total", 0),
                "search_type": data.get("search_type", "unknown"),
            }
        else:
            return {"status": "error", "latency_ms": round(elapsed_ms, 1),
                    "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return {"status": "error", "latency_ms": round(elapsed_ms, 1), "error": str(e)[:200]}


def run_benchmark(server: str, runs: int = 3, search_options: dict[str, Any] | None = None) -> dict:
    """Run all benchmark queries × N runs, return structured results."""
    all_results: list[dict] = []

    with httpx.Client() as client:
        # Health check — wait for models_ready
        for _ in range(120):
            try:
                resp = client.get(f"{server}/health", timeout=5.0)
                if resp.status_code == 200:
                    health = resp.json()
                    if health.get("models_ready", True):
                        break
            except Exception:
                pass
            time.sleep(0.5)
        else:
            return {"error": "Server did not become ready in 60s"}

        # Warmup pass: run each query once (untimed) to prime caches
        for q in QUERIES:
            run_single_query(client, server, q, search_options=search_options)

        for q in QUERIES:
            query_runs: list[dict] = []
            for run_idx in range(runs):
                result = run_single_query(client, server, q, search_options=search_options)
                result["run"] = run_idx + 1
                query_runs.append(result)

            # Aggregate latencies
            latencies = [r["latency_ms"] for r in query_runs if r["status"] == "ok"]
            latency_stats = {}
            if latencies:
                latency_stats = {
                    "p50_ms": round(statistics.median(latencies), 1),
                    "mean_ms": round(statistics.mean(latencies), 1),
                    "stdev_ms": round(statistics.stdev(latencies), 1) if len(latencies) > 1 else 0,
                    "cv": round(statistics.stdev(latencies) / statistics.mean(latencies), 3) if len(latencies) > 1 and statistics.mean(latencies) > 0 else 0,
                    "min_ms": round(min(latencies), 1),
                    "max_ms": round(max(latencies), 1),
                }

            # Best result set (from run with median latency)
            ok_runs = [r for r in query_runs if r["status"] == "ok"]
            best_results = ok_runs[len(ok_runs) // 2]["results"] if ok_runs else []

            # Gold note check
            gold = q["gold_notes"]
            result_names = [_result_name(r) for r in best_results[:10]]
            gold_found = []
            gold_missing = []
            for g in gold:
                found = any(_matches_gold(name, g) for name in result_names)
                if found:
                    gold_found.append(g)
                else:
                    gold_missing.append(g)
            metrics = retrieval_metrics(result_names, gold, k=5)

            all_results.append({
                "id": q["id"],
                "level": q["level"],
                "query": q["query"],
                "gold_notes": gold,
                "gold_found": gold_found,
                "gold_missing": gold_missing,
                "gold_hit_rate": len(gold_found) / len(gold) if gold else 1.0,
                "hit_at_5": metrics["hit_at_5"],
                "precision_at_5": metrics["precision_at_5"],
                "first_gold_rank": metrics["first_gold_rank"],
                "mrr": metrics["mrr"],
                "coverage": 1 if best_results else 0,
                "latency_p50_ms": latency_stats.get("p50_ms"),
                "latency": latency_stats,
                "top5_ids": result_names[:5],
                "top_5_results": [
                    {"rank": i + 1, "name": _result_name(r) or "?",
                     "score": r.get("score", r.get("rrf_score", 0)),
                     "confidence": r.get("confidence", "unknown")}
                    for i, r in enumerate(best_results[:5])
                ],
                "total_results": len(best_results),
                "runs": query_runs,
                "success_rate": len(ok_runs) / len(query_runs),
            })

    # Global speed stats
    all_latencies = []
    for qr in all_results:
        for run in qr["runs"]:
            if run["status"] == "ok":
                all_latencies.append(run["latency_ms"])

    speed_summary = {}
    if all_latencies:
        all_latencies_sorted = sorted(all_latencies)
        p95_idx = int(len(all_latencies_sorted) * 0.95)
        speed_summary = {
            "total_measurements": len(all_latencies),
            "p50_ms": round(statistics.median(all_latencies), 1),
            "p95_ms": round(all_latencies_sorted[min(p95_idx, len(all_latencies_sorted) - 1)], 1),
            "mean_ms": round(statistics.mean(all_latencies), 1),
            "min_ms": round(min(all_latencies), 1),
            "max_ms": round(max(all_latencies), 1),
        }

    # Per-level speed
    level_speed: dict[str, dict] = {}
    for level in ["L0", "L1", "L2", "L3"]:
        lats = []
        for qr in all_results:
            if qr["level"] == level:
                for run in qr["runs"]:
                    if run["status"] == "ok":
                        lats.append(run["latency_ms"])
        if lats:
            lats_sorted = sorted(lats)
            level_speed[level] = {
                "p50_ms": round(statistics.median(lats), 1),
                "p95_ms": round(lats_sorted[int(len(lats_sorted) * 0.95)], 1),
                "mean_ms": round(statistics.mean(lats), 1),
            }

    # Coverage
    queries_with_results = sum(1 for qr in all_results if qr["total_results"] > 0)
    coverage = queries_with_results / len(all_results)
    mean_precision_at_5 = statistics.mean(qr["precision_at_5"] for qr in all_results) if all_results else 0.0
    mean_mrr = statistics.mean(qr["mrr"] for qr in all_results) if all_results else 0.0
    hit_at_5_count = sum(1 for qr in all_results if qr["hit_at_5"])

    # Completeness (gold note hit rate)
    total_gold = sum(len(qr["gold_notes"]) for qr in all_results)
    found_gold = sum(len(qr["gold_found"]) for qr in all_results)
    completeness = found_gold / total_gold if total_gold > 0 else 0

    return {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "server": server,
        "runs_per_query": runs,
        "query_count": len(all_results),
        "coverage_count": queries_with_results,
        "speed_summary": speed_summary,
        "level_speed": level_speed,
        "coverage": round(coverage, 3),
        "completeness": round(completeness, 3),
        "retrieval_metrics": {
            "hit_at_5_count": hit_at_5_count,
            "mean_precision_at_5": round(mean_precision_at_5, 3),
            "mean_mrr": round(mean_mrr, 3),
        },
        "queries": all_results,
    }


def measure_cold_start(server_cmd: str = "uvicorn search_server:app --host 127.0.0.1 --port 8400",
                        runs: int = 3) -> dict:
    """Measure cold start time (server restart → first response). Manual invocation only."""
    # This is called separately — requires server restart between runs
    # Returns placeholder; actual measurement done by orchestrator
    return {"note": "Cold start measurement requires manual server restart. Run separately."}


def main():
    parser = argparse.ArgumentParser(description="GraphRAG Benchmark Runner")
    parser.add_argument("--server", default="http://127.0.0.1:8400")
    parser.add_argument("--runs", type=int, default=3, help="Runs per query (default 3)")
    parser.add_argument("--top-k", type=int, default=10, help="Search top_k sent to /api/search")
    parser.add_argument("--rerank", action=argparse.BooleanOptionalAction, default=True, help="Enable reranking")
    parser.add_argument("--dense-weight", type=float, default=None, help="RRF dense weight override")
    parser.add_argument("--sparse-weight", type=float, default=None, help="RRF sparse weight override")
    parser.add_argument("--decomposed-weight", type=float, default=None, help="RRF decomposed sparse weight override")
    parser.add_argument("--entity-weight", type=float, default=None, help="RRF entity dense weight override")
    parser.add_argument("--output", default=None, help="Output JSON path (default: stdout)")
    args = parser.parse_args()

    search_options = {
        "top_k": args.top_k,
        "rerank": args.rerank,
        "dense_weight": args.dense_weight,
        "sparse_weight": args.sparse_weight,
        "decomposed_weight": args.decomposed_weight,
        "entity_weight": args.entity_weight,
    }
    results = run_benchmark(args.server, runs=args.runs, search_options=search_options)

    output = json.dumps(results, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Results saved to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
