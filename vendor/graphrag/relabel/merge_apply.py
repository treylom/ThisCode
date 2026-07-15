"""트랙① merge — 최종 의미 라벨을 relationships.type 에 반영 (코난 GO 2026-07-15)

전제: com.strange.graphrag-incremental 정지 상태 (실행 전 사람이 확인).
공정: sqlite backup API 백업 → 최종 라벨셋(1차 + pass2 override, 3규칙+0.7컷) 계산
      → UPDATE ... WHERE id=? AND type='related_to' (이중 가드) → 전후 카운트 검증 → manifest.
롤백: vault_graph.pre-track1-merge.db 복원.
"""
import json, sqlite3, os, sys, time

# 범용화 (2026-07-15): 경로 env 주입, 기본값 없음 = 명시 강제
DB = os.environ.get("T1_DB", "")
HERE = os.environ.get("T1_OUT", os.path.dirname(os.path.abspath(__file__)))
BACKUP = os.path.join(HERE, "vault_graph.pre-track1-merge.db")
CONF_CUT = float(os.environ.get("T1_CONF_CUT", "0.7"))

def final_labels():
    main = {json.loads(l)['rid']: json.loads(l) for l in open(os.path.join(HERE, 'pilot-results-full22794.jsonl'))}
    p2   = {json.loads(l)['rid']: json.loads(l) for l in open(os.path.join(HERE, 'pilot-results-pass2.jsonl'))}
    out = {}
    for rid, a in main.items():
        v = p2.get(rid, a)  # pass2 = override 층 (3규칙: 동일유지/luna채택/related_to환원 모두 이 대입으로 표현됨)
        if v['type'] != 'related_to' and v['confidence'] >= CONF_CUT:
            out[rid] = v['type']
    return out

def main():
    labels = final_labels()
    print(f"최종 라벨셋 = {len(labels)}")

    src = sqlite3.connect(DB)
    dst = sqlite3.connect(BACKUP)
    src.backup(dst)
    dst.close()
    print(f"백업 완료 → {BACKUP} ({os.path.getsize(BACKUP)/1e6:.0f}MB)")

    cur = src.cursor()
    before = dict(cur.execute("SELECT type, COUNT(*) FROM relationships GROUP BY type"))
    applied = skipped = 0
    for rid, ty in labels.items():
        cur.execute("UPDATE relationships SET type=? WHERE id=? AND type='related_to'", (ty, rid))
        if cur.rowcount == 1:
            applied += 1
        else:
            skipped += 1
    src.commit()
    after = dict(cur.execute("SELECT type, COUNT(*) FROM relationships GROUP BY type"))
    src.close()

    delta_related = before.get('related_to', 0) - after.get('related_to', 0)
    manifest = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "conf_cut": CONF_CUT,
        "target": len(labels), "applied": applied, "skipped": skipped,
        "related_to_before": before.get('related_to', 0), "related_to_after": after.get('related_to', 0),
        "delta_related_to": delta_related,
        "consistency": (applied == delta_related == len(labels) - skipped),
        "after_type_counts": {k: after[k] for k in sorted(after, key=lambda x: -after[x])},
        "backup": BACKUP,
    }
    with open(os.path.join(HERE, "merge-manifest.json"), "w") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print(json.dumps(manifest, ensure_ascii=False, indent=1))
    assert manifest["consistency"], "전후 카운트 불일치 — 백업 복원 검토"

if __name__ == "__main__":
    if not DB:
        sys.exit("T1_DB(vault_graph.db 경로) env 필수 — 증분 색인 정지 상태에서만 실행할 것")
    main()
