#!/usr/bin/env python3
"""Stop — cutover review gate.

Behavior: if the last assistant turn *declares* a cutover/deploy/go-live as
completed, but no reviewer verdict (PASS/GREEN in a review context) is
recorded anywhere in the session transcript, emit
{"decision":"block","reason":...} once to bounce the Stop — asking the
agent to record (or actually obtain) the review verdict first.

Why: "solo deploys" are a recurring friction class — an agent ships a UI or
service change and announces completion while the designated reviewer's
verdict exists nowhere in the session. A completion *declaration* is cheap;
this gate makes the declaration require recorded evidence, in the same
spirit as the verify-gate ("done" needs verification after the change).

Scope guards against false positives:
- only fires on completion-tense declarations ("cutover complete",
  "deployed", "went live") — plans/questions ("will deploy tomorrow") pass;
- any reviewer verdict seen earlier in the session (including inbound
  messages from reviewer bots/humans) satisfies the gate;
- capped at one bounce per turn via stop_hook_active; fail-open on any
  parse error or missing transcript.

Env:
  CUTOVER_GATE_OFF=1        disable entirely
  CUTOVER_KW_EXTRA=regex    extend the declaration pattern
  REVIEW_KW_EXTRA=regex     extend the review-verdict pattern
"""
import json, os, re, sys

def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if data.get("stop_hook_active"):
        return 0
    if os.environ.get("CUTOVER_GATE_OFF") == "1":
        return 0
    path = data.get("transcript_path") or ""
    if not path or not os.path.isfile(path):
        return 0

    cut_pat = r"(cutover|deploy(?:ed|ment)?|go[- ]?live|went live|release[d]?)[^\n]{0,30}(complete[d]?|done|finished|shipped|live now)"
    rev_pat = r"(visual|review|verifier|verdict|QA)[^\n]{0,40}(PASS|GREEN|approved)|(PASS|GREEN)[^\n]{0,25}(review|verdict)"
    extra_c = os.environ.get("CUTOVER_KW_EXTRA")
    extra_r = os.environ.get("REVIEW_KW_EXTRA")
    CUTOVER = re.compile(cut_pat + ("|" + extra_c if extra_c else ""), re.I)
    REVIEW = re.compile(rev_pat + ("|" + extra_r if extra_r else ""), re.I)

    declared = False
    reviewed = False
    try:
        lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    except OSError:
        return 0
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        try:
            m = json.loads(ln)
        except Exception:
            continue
        if m.get("type") not in ("user", "assistant"):
            continue
        msg = m.get("message", {})
        if not isinstance(msg, dict):
            continue
        role, content = msg.get("role"), msg.get("content")
        if role == "user":
            blob = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
            declared = False  # only the declaration after the last inbound gates the stop
            if REVIEW.search(blob):
                reviewed = True  # reviewer verdicts arriving as inbound count
        elif role == "assistant":
            blobs = []
            if isinstance(content, list):
                for b in content:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "text":
                        blobs.append(str(b.get("text", "")))
                    elif b.get("type") == "tool_use":
                        inp = b.get("input", {}) or {}
                        blobs.append(str(inp.get("text", ""))[:2000])
            blob = "\n".join(blobs)
            if CUTOVER.search(blob):
                declared = True
            if REVIEW.search(blob):
                reviewed = True
    if declared and not reviewed:
        print(json.dumps({
            "decision": "block",
            "reason": "[cutover review gate] You declared a cutover/deploy as complete, but no "
                      "reviewer verdict (PASS/GREEN) is recorded in this session. Obtain or record "
                      "the review verdict before declaring completion. If this is a false positive "
                      "(e.g. quoting a document), you may ignore this once.",
        }))
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)  # fail-open
