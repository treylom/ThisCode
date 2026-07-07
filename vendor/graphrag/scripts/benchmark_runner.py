"""
benchmark_runner.py — GraphRAG evaluation harness
Runs 18 test queries against search_server.py, measures latency, collects results.
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
    {"id": "Q05", "level": "L0", "query": "프롬프트 엔지니어링 가이드",
     "gold_notes": ["Prompt-Engineering-MOC"]},

    # L1 — Relationship Exploration (5)
    {"id": "Q06", "level": "L1", "query": "얼룩소에서 AI에 대해 쓴 글",
     "gold_notes": ["AI-기술-MOC", "얼룩소-아카이브-MOC"]},
    {"id": "Q07", "level": "L1", "query": "에이전트 팀 구성하는 방법",
     "gold_notes": ["Agent-Teams-실전사례-시리즈", "Knowledge-Manager-Agent-Teams-Guide-2026-02"]},
    {"id": "Q08", "level": "L1", "query": "transformer architecture 핵심 개념",
     "gold_notes": ["AI-기술-MOC"]},
    {"id": "Q09", "level": "L1", "query": "Anthropic AI Safety 관련 연구",
     "gold_notes": ["Anthropic-Pentagon-AI-군사화-대치-2026-02-MOC", "AI-Safety"]},
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
    {"id": "Q17", "level": "L3", "query": "AI 연구부터 실무 적용까지의 전체 여정",
     "gold_notes": ["AI-기술-MOC", "Obsidian-GraphRAG-Journey-MOC"]},
    {"id": "Q18", "level": "L3", "query": "정치/사회 글쓰기와 AI 기술 연구가 어떻게 연결되는가",
     "gold_notes": ["얼룩소-아카이브-MOC", "AI-기술-MOC", "정치-민주주의-MOC"]},
]


def run_single_query(client: httpx.Client, server: str, q: dict) -> dict:
    """Run one query, return results + latency."""
    url = f"{server}/api/search"
    params = {"q": q["query"], "mode": "hybrid", "top_k": 10, "rerank": "true"}
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


def run_benchmark(server: str, runs: int = 3) -> dict:
    """Run all 18 queries × N runs, return structured results."""
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
            run_single_query(client, server, q)

        for q in QUERIES:
            query_runs: list[dict] = []
            for run_idx in range(runs):
                result = run_single_query(client, server, q)
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
            result_names = [r.get("entity", r.get("name", r.get("note_path", ""))) for r in best_results[:10]]
            gold_found = []
            gold_missing = []
            for g in gold:
                found = any(g.lower() in name.lower() for name in result_names)
                if found:
                    gold_found.append(g)
                else:
                    gold_missing.append(g)

            all_results.append({
                "id": q["id"],
                "level": q["level"],
                "query": q["query"],
                "gold_notes": gold,
                "gold_found": gold_found,
                "gold_missing": gold_missing,
                "gold_hit_rate": len(gold_found) / len(gold) if gold else 1.0,
                "latency": latency_stats,
                "top_5_results": [
                    {"rank": i + 1, "name": r.get("entity", r.get("name", r.get("note_path", "?"))),
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

    # Completeness (gold note hit rate)
    total_gold = sum(len(qr["gold_notes"]) for qr in all_results)
    found_gold = sum(len(qr["gold_found"]) for qr in all_results)
    completeness = found_gold / total_gold if total_gold > 0 else 0

    return {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "server": server,
        "runs_per_query": runs,
        "query_count": len(all_results),
        "speed_summary": speed_summary,
        "level_speed": level_speed,
        "coverage": round(coverage, 3),
        "completeness": round(completeness, 3),
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
    parser.add_argument("--output", default=None, help="Output JSON path (default: stdout)")
    args = parser.parse_args()

    results = run_benchmark(args.server, runs=args.runs)

    output = json.dumps(results, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Results saved to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
