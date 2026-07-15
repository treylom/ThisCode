"""
benchmark_scorer.py — Apply autoresearch rubric to benchmark results.
Takes benchmark_runner.py output + optional judge scores → composite score.

Usage:
  python benchmark_scorer.py benchmark_results.json [--judges judges.json] [--output scores.json]

Without --judges: computes speed + automated quality metrics only.
With --judges: merges human/LLM judge scores for full composite.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


# ── Speed scoring thresholds (per level) ──────────────────────────────

SPEED_THRESHOLDS: dict[str, list[tuple[float, int]]] = {
    # (max_ms, points) — evaluated top-down, first match wins
    "L0": [(200, 15), (500, 12), (700, 9), (1000, 6), (float("inf"), 3)],
    "L1": [(500, 15), (700, 12), (1000, 9), (1500, 6), (float("inf"), 3)],
    "L2": [(2000, 15), (3000, 12), (5000, 9), (7000, 6), (float("inf"), 3)],
    "L3": [(10000, 15), (15000, 12), (20000, 9), (30000, 6), (float("inf"), 3)],
}

P95_THRESHOLDS = [(1000, 10), (1500, 8), (2000, 6), (3000, 4), (float("inf"), 2)]
COLD_START_THRESHOLDS = [(3000, 10), (5000, 8), (8000, 6), (12000, 4), (float("inf"), 2)]
CV_THRESHOLDS = [(0.1, 5), (0.15, 4), (0.2, 3), (0.3, 2), (float("inf"), 1)]

# ── Quality scoring ───────────────────────────────────────────────────

# "Higher is better" thresholds — use _threshold_score_gte()
COVERAGE_THRESHOLDS = [(1.0, 10), (17 / 18, 8), (16 / 18, 6), (15 / 18, 4), (0, 2)]
COMPLETENESS_THRESHOLDS = [(0.95, 10), (0.85, 8), (0.75, 6), (0.65, 4), (0, 2)]
CONFIDENCE_ACC_THRESHOLDS = [(0.9, 5), (0.8, 4), (0.7, 3), (0.6, 2), (0, 1)]

# ── Level weights for composite ───────────────────────────────────────

LEVEL_SPEED_QUALITY_RATIO = {
    "L0": (0.6, 0.4),
    "L1": (0.45, 0.55),
    "L2": (0.25, 0.75),
    "L3": (0.10, 0.90),
}

LEVEL_GROUP_WEIGHTS = {"L0": 1.0, "L1": 1.3, "L2": 1.2, "L3": 0.8}


def _threshold_score(value: float, thresholds: list[tuple[float, int]]) -> int:
    """Lower-is-better scoring (speed, CV). First threshold matched wins."""
    for threshold, score in thresholds:
        if value <= threshold:
            return score
    return thresholds[-1][1]


def _threshold_score_gte(value: float, thresholds: list[tuple[float, int]]) -> int:
    """Higher-is-better scoring (coverage, completeness, confidence). First threshold matched wins."""
    for threshold, score in thresholds:
        if value >= threshold:
            return score
    return thresholds[-1][1]


def score_speed(benchmark: dict) -> dict:
    """Score speed metrics (40 points max)."""
    speed = benchmark.get("speed_summary", {})
    level_speed = benchmark.get("level_speed", {})

    # p50 — use per-level thresholds, average across levels
    p50_scores = []
    for level in ["L0", "L1", "L2", "L3"]:
        ls = level_speed.get(level, {})
        p50 = ls.get("p50_ms", 99999)
        s = _threshold_score(p50, SPEED_THRESHOLDS.get(level, SPEED_THRESHOLDS["L2"]))
        p50_scores.append({"level": level, "p50_ms": p50, "score": s})

    p50_avg = sum(s["score"] for s in p50_scores) / len(p50_scores) if p50_scores else 0
    p50_final = round(min(p50_avg, 15))

    # p95
    p95 = speed.get("p95_ms", 99999)
    p95_score = _threshold_score(p95, P95_THRESHOLDS)

    # Cold start (placeholder — requires manual measurement)
    cold_start_score = 0  # filled by orchestrator

    # Stability (CV)
    cvs = []
    for q in benchmark.get("queries", []):
        cv = q.get("latency", {}).get("cv", 1.0)
        cvs.append(cv)
    avg_cv = sum(cvs) / len(cvs) if cvs else 1.0
    cv_score = _threshold_score(avg_cv, CV_THRESHOLDS)

    total = p50_final + p95_score + cold_start_score + cv_score

    return {
        "total": total,
        "max": 40,
        "breakdown": {
            "p50": {"score": p50_final, "max": 15, "details": p50_scores},
            "p95": {"score": p95_score, "max": 10, "value_ms": p95},
            "cold_start": {"score": cold_start_score, "max": 10, "note": "requires manual measurement"},
            "stability_cv": {"score": cv_score, "max": 5, "avg_cv": round(avg_cv, 3)},
        },
    }


def score_quality_automated(benchmark: dict) -> dict:
    """Score automated quality metrics (coverage + completeness). Max 20/60 without judges."""
    queries = benchmark.get("queries", [])

    # Coverage
    with_results = sum(1 for q in queries if q.get("total_results", 0) > 0)
    query_count = int(benchmark.get("query_count") or len(queries))
    coverage_ratio = with_results / query_count if query_count else 0.0
    coverage_score = _threshold_score_gte(coverage_ratio, COVERAGE_THRESHOLDS)

    # Completeness (gold note hit rate)
    completeness = benchmark.get("completeness", 0)
    completeness_score = _threshold_score_gte(completeness, COMPLETENESS_THRESHOLDS)

    return {
        "total": coverage_score + completeness_score,
        "max": 60,
        "note": "Partial score — relevance/ranking/confidence require judge input",
        "breakdown": {
            "coverage": {"score": coverage_score, "max": 10, "value": f"{with_results}/{query_count}"},
            "completeness": {"score": completeness_score, "max": 10, "value": round(completeness, 3)},
            "relevance": {"score": 0, "max": 20, "note": "requires judges"},
            "ranking": {"score": 0, "max": 15, "note": "requires judges"},
            "confidence_accuracy": {"score": 0, "max": 5, "note": "requires judges"},
        },
    }


def score_quality_with_judges(benchmark: dict, judge_scores: dict) -> dict:
    """Full quality scoring with judge input (60 points max)."""
    auto = score_quality_automated(benchmark)

    # Extract judge scores per query
    relevance_total = 0
    ranking_total = 0
    confidence_matches = 0
    confidence_total = 0
    query_count = 0

    for q_id, scores in judge_scores.get("queries", {}).items():
        # Average of Opus and GPT-5.4 scores
        opus = scores.get("opus", {})
        gpt = scores.get("gpt54", {})

        rel_opus = opus.get("relevance_avg", 0)
        rel_gpt = gpt.get("relevance_avg", 0)
        relevance_total += (rel_opus + rel_gpt) / 2

        rank_opus = opus.get("ranking", 0)
        rank_gpt = gpt.get("ranking", 0)
        ranking_total += (rank_opus + rank_gpt) / 2

        conf_opus = opus.get("confidence_matches", 0)
        conf_gpt = gpt.get("confidence_matches", 0)
        confidence_matches += (conf_opus + conf_gpt) / 2
        confidence_total += scores.get("result_count", 5)

        query_count += 1

    # Normalize to rubric scale
    relevance_avg = relevance_total / query_count if query_count else 0
    ranking_avg = ranking_total / query_count if query_count else 0
    confidence_acc = confidence_matches / confidence_total if confidence_total else 0

    # Relevance@5 → 20 points
    if relevance_avg >= 8.0: rel_score = 20
    elif relevance_avg >= 7.0: rel_score = 16
    elif relevance_avg >= 6.0: rel_score = 12
    elif relevance_avg >= 5.0: rel_score = 8
    elif relevance_avg >= 4.0: rel_score = 6
    else: rel_score = 3

    # Ranking → 15 points
    if ranking_avg >= 8.0: rank_score = 15
    elif ranking_avg >= 7.0: rank_score = 12
    elif ranking_avg >= 6.0: rank_score = 9
    elif ranking_avg >= 5.0: rank_score = 6
    elif ranking_avg >= 4.0: rank_score = 4
    else: rank_score = 2

    # Confidence accuracy → 5 points
    conf_score = _threshold_score_gte(confidence_acc, CONFIDENCE_ACC_THRESHOLDS)

    total = (auto["breakdown"]["coverage"]["score"] +
             auto["breakdown"]["completeness"]["score"] +
             rel_score + rank_score + conf_score)

    return {
        "total": total,
        "max": 60,
        "breakdown": {
            "coverage": auto["breakdown"]["coverage"],
            "completeness": auto["breakdown"]["completeness"],
            "relevance": {"score": rel_score, "max": 20, "avg": round(relevance_avg, 2)},
            "ranking": {"score": rank_score, "max": 15, "avg": round(ranking_avg, 2)},
            "confidence_accuracy": {"score": conf_score, "max": 5, "accuracy": round(confidence_acc, 3)},
        },
    }


def compute_composite(speed: dict, quality: dict, benchmark: dict) -> dict:
    """Compute weighted composite score (100 points)."""
    queries = benchmark.get("queries", [])

    # Per-level breakdown
    level_scores = {}
    for level in ["L0", "L1", "L2", "L3"]:
        level_queries = [q for q in queries if q["level"] == level]
        if not level_queries:
            continue

        speed_ratio, quality_ratio = LEVEL_SPEED_QUALITY_RATIO[level]
        # Normalize speed and quality to 0-10 scale for per-level
        speed_norm = (speed["total"] / speed["max"]) * 10
        quality_norm = (quality["total"] / quality["max"]) * 10

        level_score = speed_norm * speed_ratio + quality_norm * quality_ratio
        level_scores[level] = {
            "raw_score": round(level_score, 2),
            "weight": LEVEL_GROUP_WEIGHTS[level],
            "weighted": round(level_score * LEVEL_GROUP_WEIGHTS[level], 2),
            "query_count": len(level_queries),
        }

    # Weighted sum → normalize to 100
    total_weighted = sum(ls["weighted"] for ls in level_scores.values())
    total_weight = sum(LEVEL_GROUP_WEIGHTS[l] for l in level_scores)
    normalized = (total_weighted / (total_weight * 10)) * 100 if total_weight > 0 else 0

    return {
        "composite": round(normalized, 1),
        "max": 100,
        "speed_total": speed["total"],
        "quality_total": quality["total"],
        "level_breakdown": level_scores,
        "pass": normalized >= 80,
    }


def main():
    parser = argparse.ArgumentParser(description="GraphRAG Benchmark Scorer")
    parser.add_argument("benchmark", help="benchmark_runner.py output JSON")
    parser.add_argument("--judges", default=None, help="Judge scores JSON")
    parser.add_argument("--cold-start-ms", type=float, default=None, help="Cold start measurement (ms)")
    parser.add_argument("--output", default=None, help="Output JSON path")
    args = parser.parse_args()

    benchmark = json.loads(Path(args.benchmark).read_text(encoding="utf-8"))

    speed = score_speed(benchmark)
    if args.cold_start_ms is not None:
        speed["breakdown"]["cold_start"]["score"] = _threshold_score(args.cold_start_ms, COLD_START_THRESHOLDS)
        speed["breakdown"]["cold_start"]["value_ms"] = args.cold_start_ms
        speed["total"] = sum(v["score"] for v in speed["breakdown"].values())

    if args.judges:
        judge_scores = json.loads(Path(args.judges).read_text(encoding="utf-8"))
        quality = score_quality_with_judges(benchmark, judge_scores)
    else:
        quality = score_quality_automated(benchmark)

    composite = compute_composite(speed, quality, benchmark)

    result = {
        "timestamp": benchmark.get("timestamp", "unknown"),
        "speed": speed,
        "quality": quality,
        "composite": composite,
    }

    output = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Scores saved to {args.output}", file=sys.stderr)
    else:
        print(output)

    # Summary
    print(f"\n{'='*50}", file=sys.stderr)
    print(f"Speed:     {speed['total']}/{speed['max']}", file=sys.stderr)
    print(f"Quality:   {quality['total']}/{quality['max']}", file=sys.stderr)
    print(f"Composite: {composite['composite']}/{composite['max']}", file=sys.stderr)
    print(f"Pass:      {'YES' if composite['pass'] else 'NO'}", file=sys.stderr)
    print(f"{'='*50}", file=sys.stderr)


if __name__ == "__main__":
    main()
