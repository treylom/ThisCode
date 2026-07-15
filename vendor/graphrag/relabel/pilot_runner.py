"""트랙① 파일럿 러너 — related_to 재분류 (DB 무기록 예행)

공정: DB(ro)에서 degree 상위 related_to 쌍 선별 → vault 노트 본문에서 링크 주변 문맥 조달
      → gpt-5.5(codex CLI 키리스·격리) 배치5 분류 → JSONL + 통계.
설계 합의: meetings/2026-07-15-graphrag-3d-viz 스레드 (코난 ①~④ + 페이커 정찰 ①~③).
증분 race 가드는 merge 티어 별건 — 본 러너는 DB write 0.
"""
import sqlite3, json, os, re, subprocess, tempfile, time, sys, threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# 경로는 env/CLI 로 주입 (범용화 2026-07-15 — 타 기기 이식·공개 배포 겸용, 기본값 없음 = 명시 강제)
DB = os.environ.get("T1_DB", "")
VAULT = os.environ.get("T1_VAULT", "")
OUT_DIR = os.environ.get("T1_OUT", os.path.dirname(os.path.abspath(__file__)))
MODEL = os.environ.get("T1_MODEL", "gpt-5.5")
EFFORT = os.environ.get("T1_EFFORT", "")  # 예: xhigh → -c model_reasoning_effort 주입
BATCH = int(os.environ.get("T1_BATCH", "5"))
WORKERS = 4
CALL_TIMEOUT = int(os.environ.get("T1_TIMEOUT", "120"))

LABELS = {
    "cites": "타깃을 인용·근거로 삼음",
    "parent": "타깃이 소스의 상위 개념/분류(MOC)",
    "belongs_to": "소스가 타깃 분류·시리즈에 속함",
    "sourced_from": "소스 내용이 타깃에서 유래",
    "implements": "소스가 타깃(설계·스펙)을 구현",
    "depends_on": "소스가 타깃에 기능적으로 의존",
    "used_by": "소스를 타깃이 사용함",
    "contrasts": "둘을 대비·비교함",
    "precedes": "소스가 타깃보다 시간상 선행",
    "extends": "소스가 타깃을 확장·발전",
    "created_by": "소스를 타깃이 만듦",
    "inspires": "소스가 타깃에 영감·계기 제공",
    "criticizes": "소스가 타깃을 비판·반박",
    "related_to": "위 어느 것도 확신 못함 — 유지(기본값)",
}

def build_basename_index():
    idx = {}
    for root, dirs, files in os.walk(VAULT):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            if f.endswith(".md") and f not in idx:
                idx[f] = os.path.join(root, f)
    return idx

def note_path(source_note, bidx):
    p = os.path.join(VAULT, source_note)
    if os.path.isfile(p):
        return p
    return bidx.get(os.path.basename(source_note))

def link_context(note_text, target_name, budget=650):
    """타깃 위키링크가 등장하는 문단(±0) 추출, 실패 시 제목부 폴백."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", note_text) if p.strip()]
    key = target_name[:40]
    for p in paras:
        if f"[[{key}" in p or key in p:
            return p[:budget]
    return "\n\n".join(paras[:2])[:budget]

def make_prompt(batch):
    items = []
    for k, it in enumerate(batch, 1):
        items.append(
            f"### 쌍 {k}\n소스 노트: {it['src']}\n타깃 문서: {it['tgt']}\n"
            f"발췌(소스 노트에서 타깃을 링크한 부근):\n{it['ctx']}\n")
    labels = "\n".join(f"- {k}: {v}" for k, v in LABELS.items())
    return f"""당신은 지식그래프 관계 분류기다. 각 쌍에 대해 [소스 노트]→[타깃 문서] 링크의 의미 유형을 판정하라.

허용 라벨(이 목록 외 금지):
{labels}

규칙:
- 방향은 항상 소스→타깃.
- 발췌에서 확신할 수 없으면 related_to 유지가 정답(억지 라벨 = 오답).
- 단, 발췌에 명확한 근거(상위 목차·시리즈 연속·인용·유래·비교 등)가 있으면 적극 분류하라 — 근거가 있는데 related_to 로 남기는 것도 오답이다.
- evidence는 판정 근거가 된 발췌 속 구절(30자 이내), related_to 유지면 빈 문자열.

출력: 아래 형식의 JSON 배열만. 설명·코드펜스 금지.
[{{"i":1,"type":"...","confidence":0.85,"evidence":"..."}}, ...]

{chr(10).join(items)}"""

def call_codex(prompt):
    output_path = None
    try:
        with tempfile.NamedTemporaryFile(prefix="track1-codex-", suffix=".txt", delete=False) as f:
            output_path = f.name
        cmd = ["codex", "exec", "--ephemeral", "--skip-git-repo-check", "--ignore-user-config",
               "--ignore-rules", "--sandbox", "read-only", "-C", "/tmp", "-m", MODEL]
        if EFFORT:
            cmd += ["-c", f'model_reasoning_effort="{EFFORT}"']
        cmd += ["-o", output_path, "-"]
        env = os.environ.copy()
        env.pop("OPENAI_API_KEY", None); env.pop("ANTHROPIC_API_KEY", None)
        r = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                           timeout=CALL_TIMEOUT, cwd="/tmp", env=env)
        if r.returncode != 0:
            return None, f"rc={r.returncode} {r.stderr[:120]}"
        text = Path(output_path).read_text(encoding="utf-8", errors="replace").strip()
        return text, None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"
    finally:
        if output_path:
            Path(output_path).unlink(missing_ok=True)

def parse_verdicts(text, n):
    if not text:
        return None
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return None
    try:
        arr = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    out = {}
    for v in arr:
        i = v.get("i")
        ty = str(v.get("type", "")).strip()
        if isinstance(i, int) and 1 <= i <= n and ty in LABELS:
            out[i] = {"type": ty, "confidence": float(v.get("confidence", 0) or 0),
                      "evidence": str(v.get("evidence", ""))[:80]}
    return out if out else None

def main(limit=500, sample="top", tag="", workers=WORKERS):
    t_start = time.time()
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=10)
    cur = conn.cursor()
    deg = defaultdict(int)
    for s, t in cur.execute("SELECT source_id, target_id FROM relationships"):
        deg[s] += 1; deg[t] += 1
    rows = cur.execute("""
        SELECT r.id, e1.name, e2.name, r.source_note, r.source_id, r.target_id
        FROM relationships r
        JOIN entities e1 ON e1.id = r.source_id
        JOIN entities e2 ON e2.id = r.target_id
        WHERE r.type = 'related_to' AND r.source_note IS NOT NULL AND r.source_note != ''
    """).fetchall()
    conn.close()
    if sample == "rids":  # 지정 rid 만 재판정 (2차 패스 — T1_RIDS_FILE 필수)
        want = set(Path(os.environ["T1_RIDS_FILE"]).read_text().split())
        rows = [r for r in rows if r[0] in want]
        print(f"rids 모드: 지정 {len(want)} → DB 매칭 {len(rows)}", flush=True)
    elif sample == "random":
        import random
        random.Random(42).shuffle(rows)  # 고정 seed = 재현 가능 표본
    else:  # top / full — degree 내림차순(고가치 쌍 선판정)
        rows.sort(key=lambda r: -(deg[r[4]] + deg[r[5]]))
    rows = rows[:limit]

    # resume: 기존 산출 JSONL의 판정 완료 rid 는 skip (3h 본run 중단 대비)
    out_jsonl = os.path.join(OUT_DIR, f"pilot-results{tag}.jsonl")
    done_rids = set()
    if os.path.exists(out_jsonl):
        with open(out_jsonl) as f:
            for line in f:
                try:
                    done_rids.add(json.loads(line)["rid"])
                except (json.JSONDecodeError, KeyError):
                    pass
    if done_rids:
        before = len(rows)
        rows = [r for r in rows if r[0] not in done_rids]
        print(f"resume: 기판정 {len(done_rids)} rid → 잔여 {len(rows)}/{before}", flush=True)

    bidx = build_basename_index()
    items, ctx_fail = [], 0
    for rid, src, tgt, snote, _, _ in rows:
        p = note_path(snote, bidx)
        if not p:
            ctx_fail += 1
            continue
        try:
            text = re.sub(r"^---\n.*?\n---\n", "", Path(p).read_text(encoding="utf-8", errors="replace"), count=1, flags=re.S)
        except OSError:
            ctx_fail += 1
            continue
        items.append({"rid": rid, "src": src[:60], "tgt": tgt[:60], "note": snote,
                      "ctx": link_context(text, tgt)})

    batches = [items[i:i+BATCH] for i in range(0, len(items), BATCH)]
    print(f"대상 {len(items)}쌍 (문맥 실패 {ctx_fail}) → {len(batches)} 배치 × {workers} 워커", flush=True)

    results, call_times, fails = [], [], []
    lock = threading.Lock()
    outf = open(out_jsonl, "a")  # 스트리밍 append — 중단돼도 기판정분 보존
    def work(bi, batch):
        t0 = time.time()
        text, err = call_codex(make_prompt(batch))
        dt = time.time() - t0
        verdicts = parse_verdicts(text, len(batch)) if text else None
        with lock:
            call_times.append(dt)
            if verdicts is None:
                fails.append({"batch": bi, "err": err or "parse_fail", "raw_head": (text or "")[:150]})
                return
            for k, it in enumerate(batch, 1):
                v = verdicts.get(k)
                r = {**{kk: it[kk] for kk in ("rid","src","tgt","note")},
                     **(v or {"type": "related_to", "confidence": 0, "evidence": "(무판정)"})}
                results.append(r)
                outf.write(json.dumps(r, ensure_ascii=False) + "\n")
            outf.flush()
            done = len(call_times)
            if done % 10 == 0:
                print(f"  {done}/{len(batches)} 배치 · 평균 {sum(call_times)/len(call_times):.1f}s/콜", flush=True)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(work, i, b) for i, b in enumerate(batches)]
        for f in as_completed(futs):
            f.result()
    outf.close()

    conv = [r for r in results if r["type"] != "related_to"]
    dist = defaultdict(int)
    for r in conv:
        dist[r["type"]] += 1
    stats = {
        "sample": sample,
        "n_pairs": len(items), "n_batches": len(batches), "n_fail_batches": len(fails),
        "judged": len(results), "converted": len(conv),
        "conversion_rate": round(len(conv)/max(1,len(results)), 3),
        "avg_call_sec": round(sum(call_times)/max(1,len(call_times)), 1),
        "p90_call_sec": round(sorted(call_times)[int(len(call_times)*0.9)] if call_times else 0, 1),
        "wall_sec": round(time.time()-t_start, 1),
        "type_dist": dict(sorted(dist.items(), key=lambda x: -x[1])),
        "avg_confidence_converted": round(sum(r["confidence"] for r in conv)/max(1,len(conv)), 2),
        "fails": fails[:5],
    }
    with open(os.path.join(OUT_DIR, f"pilot-stats{tag}.json"), "w") as f:
        json.dump(stats, f, ensure_ascii=False, indent=1)
    print(json.dumps(stats, ensure_ascii=False, indent=1), flush=True)

if __name__ == "__main__":
    if not DB or not VAULT:
        sys.exit("T1_DB(vault_graph.db 경로)·T1_VAULT(라이브 vault 경로) env 필수 — 예: "
                 "T1_DB=~/.../index/vault_graph.db T1_VAULT=~/.../MyVault python3 pilot_runner.py 100 random")
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    mode = sys.argv[2] if len(sys.argv) > 2 else "top"
    w = int(sys.argv[3]) if len(sys.argv) > 3 else WORKERS
    t = "-pass2" if mode == "rids" else (f"-{mode}{n}" if mode != "top" else "")
    main(n, sample=mode, tag=t, workers=w)
