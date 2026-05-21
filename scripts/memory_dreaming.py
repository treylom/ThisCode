#!/usr/bin/env python3
"""memory_dreaming.py — reversible memory archival (move, never delete).

Implements spec v1.0 LOCKED:
  docs/superpowers/specs/2026-05-16-memory-dreaming-design.md

Core: archival (NOT deletion). Stale memory is MOVED to an out-of-WD cold
store; --restore brings it back losslessly. One tier-agnostic rubric.

7 hardenings (independent review rounds + 2-track verification):
  H1 recency never uses raw fs mtime; recency-unknown = keep (not archivable)
  H2 A1(ii) superseded_by must be non-empty AND resolvable
  H3 A1 structural only — INDEX-line marker, never file-body free-text
  H4 --apply precondition: corpus_baseline drift => refuse + --recalibrate
  H5 crash-safe ordering: copy→tombstone→INDEX-line-remove→unlink (idempotent)
  H6 fcntl flock single-flight; manifest parse failure = fail-closed
  H7 SessionStart renderer merges overdue + compact INDEX + archived tombstones

stdlib only. dry-run is the default; --apply is gated by dry_run_cycles.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

HOME = os.path.expanduser("~")
ARCHIVE_ROOT = os.environ.get(
    "MEMORY_DREAMING_ARCHIVE_ROOT", os.path.join(HOME, ".claude-memory-archive")
)
LOCK_PATH = os.path.join(ARCHIVE_ROOT, ".dreaming.lock")
SCHEDULE_PATH = os.path.join(ARCHIVE_ROOT, "dreaming-schedule.yaml")
ARCHIVED_INDEX = os.path.join(ARCHIVE_ROOT, "ARCHIVED-INDEX.md")
RUNS_DIR = os.path.join(ARCHIVE_ROOT, "_runs")
RECALIB_PATH = os.path.join(ARCHIVE_ROOT, "recalibration.json")

CODEX_HOT_BUDGET = 65536  # ref: ~/.codex/config.toml project_doc_max_bytes

INDEX_NAMES = {
    "MEMORY.md", "SHARED-INDEX.md", "MAC-INDEX.md", "WSL-INDEX.md",
    "README.md", "principles-MOC.md", "bot-roster.yaml", "INDEX.md",
}
# K6: silent-degradation classes (Phase3-blind) — never auto-band, human-surface
K6_PATTERNS = re.compile(
    r"(voice|persona|echo[_-]?drift|tone|어투|말투|페르소나)", re.I)
TERMINAL_STATUS = re.compile(
    r"(deactivat|shutdown|중단|폐기|환불|롤백|\bpaused\b|\bcompleted\b|"
    r"\bdeprecated\b|\bshut\s*down\b)", re.I)
DATESTAMP = re.compile(r"\b(20\d{2})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\b")
WIKILINK = re.compile(r"\[\[[^\]]+\]\]")
FM_BOUND = re.compile(r"^---\s*$")
# independent 2-track review refinement: cumulative/append log files are not
# "duplicate-of-a-newer-memory" — A5 must not fire on them (keep-default).
LOG_RE = re.compile(r"(^_.*log.*\.md$|[-_]log\.md$|(^|/)_km-log\.md$)", re.I)


def _iso(ts: float | None = None) -> str:
    return datetime.fromtimestamp(
        time.time() if ts is None else ts, tz=timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# minimal strict flat-YAML (schema is flat scalars only). H6: any anomaly
# raises -> caller treats as fail-closed. No external yaml dependency.
# ---------------------------------------------------------------------------
class ManifestError(Exception):
    pass


def read_manifest(path: str) -> dict:
    if not os.path.isfile(path):
        raise ManifestError("manifest absent")
    out: dict = {}
    with open(path, "r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if ":" not in line:
                raise ManifestError(f"bad line: {line!r}")
            k, v = line.split(":", 1)
            k, v = k.strip(), v.strip()
            if not re.fullmatch(r"[a-z_]+", k):
                raise ManifestError(f"bad key: {k!r}")
            if v in ("null", ""):
                out[k] = None
            elif v in ("true", "false"):
                out[k] = (v == "true")
            elif re.fullmatch(r"-?\d+", v):
                out[k] = int(v)
            else:
                out[k] = v.strip('"').strip("'")
    return out


def write_manifest(path: str, data: dict) -> None:
    tmp = path + ".tmp"
    order = ["cadence", "day_of_week", "hour_utc", "last_run_iso",
             "next_due_iso", "dry_run_cycles_remaining", "rubric_version",
             "enforced", "corpus_baseline_fingerprint", "corpus_file_count"]
    lines = ["# memory_dreaming schedule manifest (spec v1.0 §8)"]
    for k in order:
        if k not in data:
            continue
        v = data[k]
        v = "null" if v is None else ("true" if v is True else (
            "false" if v is False else str(v)))
        lines.append(f"{k}: {v}")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    _fsync_dir(os.path.dirname(path))


def _fsync_dir(d: str) -> None:
    try:
        fd = os.open(d, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# parsing helpers
# ---------------------------------------------------------------------------
def split_frontmatter(text: str):
    lines = text.split("\n")
    if not lines or not FM_BOUND.match(lines[0]):
        return {}, text
    fm: dict = {}
    end = None
    for i in range(1, len(lines)):
        if FM_BOUND.match(lines[i]):
            end = i
            break
    if end is None:
        return {}, text
    for ln in lines[1:end]:
        if ":" in ln and not ln.lstrip().startswith("#"):
            k, v = ln.split(":", 1)
            fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm, "\n".join(lines[end + 1:])


def git_last_commit_iso(path: str) -> str | None:
    repo = path
    while repo != "/" and not os.path.isdir(os.path.join(repo, ".git")):
        repo = os.path.dirname(repo)
    if repo == "/":
        return None
    try:
        r = subprocess.run(
            ["git", "-C", repo, "log", "-1", "--format=%cI", "--", path],
            capture_output=True, text=True, timeout=15)
        out = r.stdout.strip()
        return out or None
    except (subprocess.SubprocessError, OSError):
        return None


def recency_iso(path: str, fm: dict, body: str) -> str | None:
    """H1: recency from git log / frontmatter date / body datestamp ONLY.
    raw fs mtime is NEVER used. None => recency-unknown => NOT archivable."""
    cands: list[str] = []
    g = git_last_commit_iso(path)
    if g:
        cands.append(g[:10])
    for key in ("verified_at", "date"):
        val = fm.get(key, "")
        m = DATESTAMP.search(str(val))
        if m:
            cands.append(m.group(0))
    m = DATESTAMP.search(body)
    if m:
        cands.append(m.group(0))
    return max(cands) if cands else None


def days_since(iso_day: str | None) -> float | None:
    if not iso_day:
        return None
    try:
        d = datetime.strptime(iso_day[:10], "%Y-%m-%d").replace(
            tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - d).total_seconds() / 86400.0
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# corpus baseline / bulk-cluster fingerprint (Phase0 / H4)
# ---------------------------------------------------------------------------
def corpus_fingerprint(files: list[str]) -> tuple[str, int]:
    rows = []
    for f in sorted(files):
        try:
            rows.append(f"{os.path.basename(f)}:{int(os.stat(f).st_mtime)}")
        except OSError:
            continue
    blob = "\n".join(rows).encode("utf-8")
    return hashlib.sha256(blob).hexdigest(), len(rows)


def bulk_clusters(files: list[str], min_size: int = 20) -> dict:
    by_min: dict[int, list[str]] = {}
    for f in files:
        try:
            key = int(os.stat(f).st_mtime // 60)
        except OSError:
            continue
        by_min.setdefault(key, []).append(f)
    return {k: v for k, v in by_min.items() if len(v) > min_size}


# ---------------------------------------------------------------------------
# index parsing — A1(i) structural marker is on the INDEX line (H3)
# ---------------------------------------------------------------------------
def index_struck(index_path: str) -> set:
    """Return basenames whose INDEX line wraps the link in strikethrough
    with a 폐기/deprecated token AND a date. Body free-text is NEVER used."""
    out: set = set()
    if not os.path.isfile(index_path):
        return out
    with open(index_path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if "~~" not in line:
                continue
            if not re.search(r"(폐기|deprecated|superseded|무효)", line, re.I):
                continue
            if not DATESTAMP.search(line):
                continue
            for m in re.finditer(r"~~.*?\(([^)]+\.md)\).*?~~", line):
                out.add(os.path.basename(m.group(1)))
    return out


def index_members(index_path: str) -> tuple[set, set]:
    listed: set = set()
    starred: set = set()
    if not os.path.isfile(index_path):
        return listed, starred
    with open(index_path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            for m in re.finditer(r"\(([\w./-]+\.md)\)", line):
                b = os.path.basename(m.group(1))
                listed.add(b)
                if "⭐" in line:
                    starred.add(b)
    return listed, starred


# ---------------------------------------------------------------------------
# rubric (spec §4) — signals A1/A3/A4/A5/A6, guards K1..K6
# ---------------------------------------------------------------------------
def classify(path, fm, body, tier, struck, listed, starred, all_titles):
    """Returns (band, guards, signals, info). `info` carries human-judging
    detail (independent 2-track review: A5 duplicate reason surfaced as norm·count)."""
    base = os.path.basename(path)
    typ = (fm.get("type") or "").lower()
    signals: list[str] = []
    guards: list[str] = []
    info: dict = {}

    # ---- guards (any guard => keep; evaluated first) ----
    if base in INDEX_NAMES:                                     # K4
        return "keep", ["K4"], [], info
    if base.startswith("user_"):                                # K5
        guards.append("K5")
    rec = recency_iso(path, fm, body)                           # H1
    rec_days = days_since(rec)
    superseded_struct = base in struck
    sb = (fm.get("superseded_by") or "").strip()                # H2
    sb_valid = bool(sb) and sb.lower() not in ("null", "none") and (
        os.path.basename(sb) in all_titles or sb in all_titles)
    if typ in ("user", "feedback") and not (                    # K1 (H2/H3)
            superseded_struct or sb_valid):
        guards.append("K1")
    if fm.get("pinned", "").lower() == "true" or base in starred:  # K2
        guards.append("K2")
    if rec_days is not None and rec_days < 30:                  # K3
        guards.append("K3")
    if rec is None:                                             # H1: unknown=keep
        guards.append("K3?")
    k6 = bool(K6_PATTERNS.search(base) or K6_PATTERNS.search(
        fm.get("description", "")))
    if k6:
        guards.append("K6")

    # ---- signals ----
    if superseded_struct or sb_valid:                           # A1 (H3/H2)
        signals.append("A1")
        info["a1"] = "INDEX-strike" if superseded_struct else f"sb={sb}"
    if typ == "project" and TERMINAL_STATUS.search(body) and (
            rec_days is not None and rec_days > 45):             # A3
        signals.append("A3")
    if (not WIKILINK.search(body) and base not in listed
            and typ in ("project", "reference")
            and rec_days is not None and rec_days > 90):         # A4
        signals.append("A4")
    norm = (fm.get("description") or base).strip().lower()[:80]
    # A5 duplicate: NOT on cumulative/append log files (review keep-default)
    if norm and all_titles.get(norm, 0) > 1 and not LOG_RE.search(base):  # A5
        signals.append("A5")
        info["a5"] = f"norm={norm!r} ×{all_titles.get(norm)}"
    if re.search(r"(code-enforced|패치 적용 완료)", body):       # A6
        signals.append("A6")

    # ---- decision ----
    hard = {"K1", "K2", "K4", "K5"}
    if hard & set(guards):
        return "keep", guards, signals, info
    if "K6" in guards and signals:
        return "mid", guards, signals, info    # K6: never auto, human-surface
    if "K3" in guards or "K3?" in guards:
        return ("low" if not signals else "mid"), guards, signals, info
    if not signals:
        return "low", guards, signals, info
    if "A1" in signals or len(signals) >= 2:
        return "high", guards, signals, info
    return "mid", guards, signals, info


# ---------------------------------------------------------------------------
# tier discovery
# ---------------------------------------------------------------------------
def default_tiers() -> list[dict]:
    sb = os.path.join(HOME, "obsidian-ai-vault",
                      "AI_Second_Brain", ".claude-memory")
    proj = os.path.join(HOME, ".claude", "projects")
    tiers = []
    shared = os.path.join(sb, "shared")
    if os.path.isdir(shared):
        tiers.append({"label": "T1_shared", "dir": shared,
                      "index": os.path.join(shared, "SHARED-INDEX.md"),
                      "sub": "shared"})
    for mtag in ("machine-mac", "machine-wsl"):
        d = os.path.join(sb, mtag)
        if os.path.isdir(d):
            tiers.append({"label": "T2_" + mtag, "dir": d,
                          "index": os.path.join(d, "INDEX.md"),
                          "sub": "shared"})
    # Codex tier (source-backed Codex doc-budget surface): ~/.codex/memories
    # (may be 0 files — additive, 0-file-safe; index absent => index_*
    # return empty gracefully). Cold archive sub is env-configurable
    # (default generic; spec §6 layout).
    codex_mem = os.path.join(HOME, ".codex", "memories")
    if os.path.isdir(codex_mem):
        # shipped default = generic "codex" (no persona/bot codename in a
        # public repo — independent 2-track review). A local runtime sets
        # MEMORY_DREAMING_CODEX_SUB to its own bot subdir if desired.
        codex_sub = os.environ.get("MEMORY_DREAMING_CODEX_SUB", "codex")
        tiers.append({"label": "Codex", "dir": codex_mem,
                      "index": os.path.join(codex_mem, "INDEX.md"),
                      "sub": codex_sub})
    if os.path.isdir(proj):
        for name in sorted(os.listdir(proj)):
            md = os.path.join(proj, name, "memory")
            if os.path.isdir(md):
                tiers.append({"label": "T4:" + name, "dir": md,
                              "index": os.path.join(md, "MEMORY.md"),
                              "sub": name[:40] or "shared"})
    return tiers


def scan_tier(t: dict) -> list[dict]:
    files = [os.path.join(t["dir"], f) for f in os.listdir(t["dir"])
             if f.endswith(".md")]
    struck = index_struck(t["index"])
    listed, starred = index_members(t["index"])
    titles: dict = {}
    parsed = []
    for f in files:
        try:
            txt = open(f, "r", encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        fm, body = split_frontmatter(txt)
        titles[os.path.basename(f)] = 1
        norm = (fm.get("description") or os.path.basename(f)
                ).strip().lower()[:80]
        titles[norm] = titles.get(norm, 0) + 1
        parsed.append((f, fm, body))
    rows = []
    for f, fm, body in parsed:
        band, guards, signals, info = classify(
            f, fm, body, t, struck, listed, starred, titles)
        rows.append({"file": f, "base": os.path.basename(f), "band": band,
                     "signals": signals, "guards": guards, "info": info,
                     "tier": t["label"], "sub": t["sub"],
                     "index": t["index"]})
    return rows


# ---------------------------------------------------------------------------
# lock (H6)
# ---------------------------------------------------------------------------
class SingleFlight:
    def __init__(self, path):
        self.path = path
        self.fd = None

    def __enter__(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(self.fd)
            self.fd = None
            raise SystemExit("another memory_dreaming holds the lock; no-op")
        return self

    def __exit__(self, *exc):
        if self.fd is not None:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)


# ---------------------------------------------------------------------------
# apply (H5 tombstone-first crash-safe) + restore
# ---------------------------------------------------------------------------
def _atomic_replace_text(path: str, new_text: str) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(new_text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    _fsync_dir(os.path.dirname(path))


def _copy_verify(src: str, dst: str) -> str:
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    final = dst
    n = 1
    while True:
        try:
            fd = os.open(final, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            break
        except FileExistsError:
            root, ext = os.path.splitext(dst)
            final = f"{root}_{n}{ext}"
            n += 1
    data = open(src, "rb").read()
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    if open(final, "rb").read() != data:
        raise IOError(f"verify failed: {final}")
    _fsync_dir(os.path.dirname(final))
    return final


def _remove_index_line(index_path: str, base: str) -> None:
    if not os.path.isfile(index_path):
        return
    kept = [ln for ln in open(index_path, "r", encoding="utf-8",
            errors="replace").read().split("\n")
            if f"({base})" not in ln and f"]({base})" not in ln]
    _atomic_replace_text(index_path, "\n".join(kept))


def apply_candidate(row: dict, rubric_version: str, journal) -> None:
    src = row["file"]
    base = row["base"]
    slug = os.path.splitext(base)[0]
    sub = row["sub"]
    dst = os.path.join(ARCHIVE_ROOT, sub, base)
    # 1) copy -> fsync -> verify (source still intact)
    archived = _copy_verify(src, dst)
    # full sha256 (not truncated) — restore() verifies archive integrity
    # vs this before writing back (independent 2-track review BLOCKER1).
    sha = hashlib.sha256(open(archived, "rb").read()).hexdigest()
    # 2) tombstone FIRST (restore pointer exists before source removal).
    # `arch=` = deterministic archived abs path → restore never slug-guesses
    # across subdirs (independent 2-track review caveat: multi-tier same-slug).
    tomb = (f"- {slug} | tier={row['tier']} | reason={'+'.join(row['signals'])}"
            f" | band={row['band']} | from={src} | at={_iso()}"
            f" | rubric={rubric_version} | sha={sha} | arch={archived}"
            f" | restore: memory_dreaming.py --restore {slug}\n")
    os.makedirs(ARCHIVE_ROOT, exist_ok=True)
    with open(ARCHIVED_INDEX, "a", encoding="utf-8") as fh:
        fh.write(tomb)
        fh.flush()
        os.fsync(fh.fileno())
    _fsync_dir(ARCHIVE_ROOT)
    # 3) remove active INDEX line  4) unlink source
    _remove_index_line(row["index"], base)
    os.unlink(src)
    journal.write(json.dumps({"act": "archive", "slug": slug,
                              "archived": archived, "sha": sha,
                              "row": {k: row[k] for k in
                                      ("tier", "band", "signals", "guards")}},
                             ensure_ascii=False) + "\n")


def restore(slug: str) -> int:
    if not os.path.isfile(ARCHIVED_INDEX):
        print("no ARCHIVED-INDEX")
        return 1
    lines = open(ARCHIVED_INDEX, "r", encoding="utf-8").read().split("\n")
    hit = next((ln for ln in lines if ln.startswith(f"- {slug} |")), None)
    if not hit:
        print(f"slug not in tombstones: {slug}")
        return 1
    fields = {p.split("=", 1)[0].strip(): p.split("=", 1)[1].strip()
              for p in hit.split("|") if "=" in p}
    src_orig = fields.get("from")
    sub = fields.get("tier", "shared")
    archived = fields.get("arch")              # deterministic (no slug-guess)
    want_sha = fields.get("sha")
    if not archived or not src_orig:
        print("tombstone missing arch= or from= (pre-fix tombstone?)")
        return 1
    if not os.path.isfile(archived):
        print(f"archived body absent: {archived}")
        return 1
    # independent 2-track review BLOCKER1: verify archive integrity vs tombstone sha
    # BEFORE writing back. Mismatch => refuse (never restore corrupt).
    got_sha = hashlib.sha256(open(archived, "rb").read()).hexdigest()
    if not want_sha or got_sha != want_sha:
        print(f"CHECKSUM MISMATCH — refuse restore. "
              f"tombstone sha={str(want_sha)[:16]}… archived={got_sha[:16]}… "
              f"(archive corrupted/tampered; manual review required)")
        return 1
    _copy_verify(archived, src_orig)
    kept = [ln for ln in lines if not ln.startswith(f"- {slug} |")]
    _atomic_replace_text(ARCHIVED_INDEX, "\n".join(kept))
    # Phase3: false-positive restore => tighten event
    with open(os.path.join(ARCHIVE_ROOT, "dreaming-regressions.jsonl"),
              "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": _iso(), "slug": slug,
                             "event": "restore_false_positive",
                             "tier": sub}, ensure_ascii=False) + "\n")
    print(f"restored {slug} -> {src_orig}; logged tighten event")
    return 0


# ---------------------------------------------------------------------------
# H7 SessionStart renderer: overdue + compact hot INDEX + archived tombstones
# ---------------------------------------------------------------------------
def session_render(index_path: str, budget: int = CODEX_HOT_BUDGET) -> str:
    parts: list[str] = []
    try:
        man = read_manifest(SCHEDULE_PATH)
        nd = man.get("next_due_iso")
        overdue = bool(nd) and nd < _iso()
        gate = "잠김" if (man.get("dry_run_cycles_remaining") or 0) else "열림"
    except ManifestError:
        overdue, gate = True, "잠김"          # H6 fail-closed
    if overdue:
        parts.append(
            f"⚠ memory-dreaming OVERDUE — 주간 정리 미실행. "
            f"`memory_dreaming.py --scan` 후 mid-band 검토 (apply 게이트 {gate}).")
    if os.path.isfile(index_path):
        idx = open(index_path, "r", encoding="utf-8",
                   errors="replace").read()
        parts.append(idx[:max(0, budget // 2)])
    if os.path.isfile(ARCHIVED_INDEX):
        toks = []
        for ln in open(ARCHIVED_INDEX, "r", encoding="utf-8"):
            if ln.startswith("- "):
                f = {p.split("=")[0].strip(): p.split("=", 1)[1].strip()
                     for p in ln.split("|") if "=" in p}
                slug = ln[2:].split("|")[0].strip()
                toks.append(f"  - {slug} · {f.get('reason','?')} · "
                            f"restore: --restore {slug}")
        if toks:
            parts.append("=== archived (이동됨·복원가능) ===\n"
                         + "\n".join(toks))
    out = "\n\n".join(parts)
    if len(out.encode("utf-8")) > budget:                     # accept test 3
        out = out.encode("utf-8")[:budget - 64].decode(
            "utf-8", "ignore") + "\n…[compacted: hot-index budget]"
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def cmd_recalibrate(tiers):
    allf = []
    for t in tiers:
        allf += [os.path.join(t["dir"], f) for f in os.listdir(t["dir"])
                 if f.endswith(".md")]
    fp, n = corpus_fingerprint(allf)
    clusters = bulk_clusters(allf)
    os.makedirs(ARCHIVE_ROOT, exist_ok=True)
    json.dump({"at": _iso(), "file_count": n, "fingerprint": fp,
               "bulk_clusters": {str(k): len(v) for k, v in clusters.items()}},
              open(RECALIB_PATH, "w"), ensure_ascii=False, indent=1)
    man = {}
    try:
        man = read_manifest(SCHEDULE_PATH)
    except ManifestError:
        # independent 2-track review BLOCKER2 / spec v1.0 §4.5 RESOLVED (install-time
        # init): last_run=null, next_due = install + 7d (NOT now — else
        # fresh install is instantly OVERDUE), dry_run_cycles_remaining=N.
        man = {"cadence": "weekly", "day_of_week": "sunday", "hour_utc": 2,
               "last_run_iso": None,
               "next_due_iso": _iso(time.time() + 7 * 86400),
               "dry_run_cycles_remaining": 2, "rubric_version": "v1.0",
               "enforced": True}
    man["corpus_baseline_fingerprint"] = fp
    man["corpus_file_count"] = n
    write_manifest(SCHEDULE_PATH, man)
    print(f"recalibrated: {n} files, fp={fp[:12]}, "
          f"{len(clusters)} bulk-cluster(s)")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="reversible memory archival")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--scan", action="store_true",
                   help="(default) dry-run report; no changes")
    g.add_argument("--apply", action="store_true",
                   help="execute archival (gated; precondition + dry-run cnt)")
    g.add_argument("--restore", metavar="SLUG")
    g.add_argument("--list", action="store_true")
    g.add_argument("--recalibrate", action="store_true")
    g.add_argument("--session-render", metavar="INDEX_PATH")
    args = ap.parse_args(argv)

    if args.session_render:
        print(session_render(args.session_render))
        return 0
    if args.restore:
        with SingleFlight(LOCK_PATH):
            return restore(args.restore)
    if args.list:
        if os.path.isfile(ARCHIVED_INDEX):
            sys.stdout.write(open(ARCHIVED_INDEX).read())
        return 0

    tiers = default_tiers()
    if args.recalibrate:
        with SingleFlight(LOCK_PATH):
            return cmd_recalibrate(tiers)

    rows = []
    for t in tiers:
        rows += scan_tier(t)
    summ = {"high": 0, "mid": 0, "low": 0, "keep": 0}
    for r in rows:
        summ[r["band"]] = summ.get(r["band"], 0) + 1

    if not args.apply:                       # default = scan (dry-run)
        print(f"# memory_dreaming --scan  ({_iso()})")
        print(f"tiers={len(tiers)} files={len(rows)} {summ}")
        print("# high = (none expected; would be capped auto-archive). "
              "mid = NOT auto-archive · 사람 검토 대기 (Phase2 surface). "
              "low/keep = 미대상.")
        for r in rows:
            if r["band"] in ("high", "mid"):
                reason = "; ".join(f"{k}:{v}" for k, v
                                   in (r.get("info") or {}).items())
                tag = ("AUTO-ARCHIVE-CANDIDATE" if r["band"] == "high"
                       else "NOT-AUTO · human-review-pending")
                print(f"[{r['band']}] {tag} {r['tier']}/{r['base']} "
                      f"sig={r['signals']} grd={r['guards']}"
                      + (f" — {reason}" if reason else ""))
        print("\n(dry-run: no changes. --apply is gated. mid = surfaced "
              "for human/2-track review, never auto-moved.)")
        return 0

    # ---- --apply path: H4 precondition + H6 lock + dry-run gate ----
    with SingleFlight(LOCK_PATH):
        try:
            man = read_manifest(SCHEDULE_PATH)
        except ManifestError as e:
            print(f"FAIL-CLOSED: manifest unreadable ({e}); "
                  f"run --recalibrate first")
            return 2
        allf = []
        for t in tiers:
            allf += [os.path.join(t["dir"], f) for f in os.listdir(t["dir"])
                     if f.endswith(".md")]
        fp_now, n_now = corpus_fingerprint(allf)
        if man.get("corpus_baseline_fingerprint") != fp_now:
            print("FAIL-CLOSED: corpus drift vs baseline "
                  f"(was {str(man.get('corpus_baseline_fingerprint'))[:12]}, "
                  f"now {fp_now[:12]}). Run --recalibrate then re-review.")
            return 2
        dry_left = man.get("dry_run_cycles_remaining") or 0
        if dry_left > 0:
            man["dry_run_cycles_remaining"] = dry_left - 1
            man["last_run_iso"] = _iso()
            write_manifest(SCHEDULE_PATH, man)
            print(f"DRY-RUN cycle (remaining now {dry_left - 1}); "
                  f"no archival performed. {summ}")
            return 0
        cap = 25
        hi = [r for r in rows if r["band"] == "high"][:cap]
        os.makedirs(RUNS_DIR, exist_ok=True)
        jpath = os.path.join(RUNS_DIR, f"{_iso()}.jsonl")
        rv = man.get("rubric_version", "v1.0")
        with open(jpath, "w", encoding="utf-8") as journal:
            for r in hi:
                apply_candidate(r, rv, journal)
        man["last_run_iso"] = _iso()
        write_manifest(SCHEDULE_PATH, man)
        print(f"archived {len(hi)} high-band (cap {cap}); "
              f"mid={summ.get('mid',0)} surfaced for review; journal={jpath}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
