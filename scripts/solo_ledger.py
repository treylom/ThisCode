#!/usr/bin/env python3
"""solo_ledger.py — solo work ledger core (Track 3 / S2 + lifecycle).

Spec: obsidian-ai-vault meetings/2026-08-12-dispatch-meeting-gate/
      70-karpathy-track2-porting-spec.md v2.9 §2 (S2 · 수명주기 · S1/S3 owner)

Contract highlights (v2.9):
- Ledger namespace `solo-<bot>-<slug>-<session_id>.yaml` — deliberately NOT
  matched by meeting_watchdog's `meeting-watchdog-*` glob (no watchdog change).
- Create = O_CREAT|O_EXCL (exists = never overwrite).
- Every mutation runs under flock of a separate, never-replaced `<ledger>.lock`
  (locking the ledger itself is void across os.replace — different inodes).
- Write tx = fence prepare (2-stage durable: file fsync then parent-dir fsync,
  bound to canonical ledger path + generation) BEFORE temp write → file fsync →
  atomic replace → parent-dir fsync → fence clear (2-stage durable).
- Failure disposition is split by time-of-failure:
    pre-replace  → old ledger preserved, fail-closed log
    post-replace parent-dir fsync EIO → durability_unknown quarantine:
      fence left in place (restart-persistent marker), human alert log,
      no further claim/injection on that ledger in this process.
- SessionStart recovery = one atomic sequence under the SAME lock:
  fence strict-read → ledger reread → selector(bot+wd+state==open) →
  claim persist. Any fence present/malformed/torn/generation-mismatch =
  reject that ledger fail-closed (claim 0, injection 0, alert 1).
- Single-owner recovery (85-doc §D): plain recovery claims ONLY when
  `claim_session` is empty or already the current session. An open ledger
  claimed by another session is reported as `foreign` — no claim, no
  injection. Taking over a foreign claim is a separate explicit path
  (`takeover`) gated by a CAS under the same lock: expected current owner +
  expected generation + an approval/evidence receipt string, all must match
  or the takeover is refused. Chained-succession *policy* (leases, liveness
  signals, operator approval UX) is a P4 lifecycle-wiring decision — this
  core only provides the CAS primitive.
- Path verification before injection: ⓐ realpath ⓑ containment under
  install-fixed allowed roots ⓒ non-symlink ⓓ same-room canonical basename
  binding (ⓐ~ⓒ fail = skip that path; ⓓ fail = skip whole ledger + log).
- owner = claim_session if set else session_id.

stdlib only. Flat strict YAML (key: value lines) — same family as
scripts/meeting_watchdog.py L134~194; malformed = fail-closed.
"""

import errno
import json
import os
import re
import sys
import time

try:
    import fcntl                      # POSIX flock
    _msvcrt = None
except ImportError:                   # Windows: fcntl 부재 — msvcrt 바이트락으로
    fcntl = None                      # (CI windows-latest 실측 ModuleNotFoundError,
    import msvcrt as _msvcrt          #  2026-08-12 CI-fix 트랙)

# --- injection points (fixtures may substitute; production leaves as-is) ---
_fsync = os.fsync
_replace = os.replace


def _fsync_dir(path):
    """Durably record directory entry changes (rename/unlink visibility)."""
    fd = os.open(path, os.O_RDONLY)
    try:
        _fsync(fd)
    finally:
        os.close(fd)


ISO = "%Y-%m-%dT%H:%M:%S%z"

LEDGER_FIELDS = (
    "bot", "slug", "session_id", "wd", "started_iso",
    "room_path", "spec_path", "progress_path", "outcome_path",
    "state", "claim_session", "last_flush_iso", "generation",
    "takeover_receipt",
)

_SANE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_LINE = re.compile(r"^([a-z_]+):[ ]?(.*)$")


class LedgerError(Exception):
    pass


def state_dir():
    return os.environ.get("MEETING_WATCHDOG_STATE_DIR") or os.path.expanduser(
        "~/.claude-state")


def _now():
    return time.strftime(ISO)


def _alert_log(sdir, kind, detail):
    """Human-facing alert trail (quarantine / fence rejection / path attack)."""
    line = json.dumps({"ts": _now(), "kind": kind, **detail}, ensure_ascii=False)
    try:
        os.makedirs(sdir, exist_ok=True)
        with open(os.path.join(sdir, "solo-ledger-alerts.jsonl"), "a",
                  encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass
    print("solo-ledger ALERT %s: %s" % (kind, line), file=sys.stderr)


def owner(fields):
    return fields.get("claim_session") or fields.get("session_id") or ""


# ---------------------------------------------------------------- flat YAML
def dump_fields(fields):
    lines = []
    for key in LEDGER_FIELDS:
        val = fields.get(key, "")
        val = "" if val is None else str(val)
        if "\n" in val:
            raise LedgerError("newline in field %s" % key)
        lines.append("%s: %s" % (key, val))
    return "\n".join(lines) + "\n"


def parse_fields(text):
    """Strict flat YAML: known keys only, no duplicates. Malformed = raise."""
    fields, seen = {}, set()
    for raw in text.splitlines():
        if not raw.strip():
            continue
        m = _LINE.match(raw)
        if not m:
            raise LedgerError("malformed line: %r" % raw[:80])
        key, val = m.group(1), m.group(2).strip()
        if key not in LEDGER_FIELDS:
            raise LedgerError("unknown key: %s" % key)
        if key in seen:
            raise LedgerError("duplicate key: %s" % key)
        seen.add(key)
        fields[key] = val
    if "session_id" not in fields or "state" not in fields:
        raise LedgerError("missing required keys")
    if fields["state"] not in ("open", "closed"):
        raise LedgerError("bad state: %r" % fields["state"])
    return fields


# ---------------------------------------------------------------- fence
def _fence_path(ledger_path):
    return ledger_path + ".fence"


def _lock_path(ledger_path):
    return ledger_path + ".lock"


def _fence_prepare(ledger_path, generation, txid):
    """2-stage durable prepare. Must complete before ledger replace —
    discoverability must be durable before the swap it announces."""
    fpath = _fence_path(ledger_path)
    record = json.dumps({
        "target": os.path.realpath(ledger_path),
        "generation": generation,
        "txid": txid,
        "ts": _now(),
    }, ensure_ascii=False)
    fd = os.open(fpath, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, record.encode("utf-8"))
        _fsync(fd)                       # stage 1: file content durable
    finally:
        os.close(fd)
    _fsync_dir(os.path.dirname(fpath) or ".")   # stage 2: dir entry durable


def _fence_clear(ledger_path):
    """2-stage durable clear (unlink + parent-dir fsync)."""
    fpath = _fence_path(ledger_path)
    os.unlink(fpath)
    _fsync_dir(os.path.dirname(fpath) or ".")


def fence_status(ledger_path):
    """strict-read: ('clear', None) | ('unresolved', reason).
    Any present fence = unresolved; malformed/torn/foreign-target/
    generation-mismatch stay unresolved too (fail-closed: 모르면 잠긴 쪽)."""
    fpath = _fence_path(ledger_path)
    if not os.path.exists(fpath):
        return "clear", None
    try:
        body = open(fpath, encoding="utf-8").read()
        rec = json.loads(body)
        target = rec["target"]
        generation = int(rec["generation"])
    except Exception as exc:
        return "unresolved", "malformed/torn fence: %s" % exc
    if target != os.path.realpath(ledger_path):
        return "unresolved", "fence target mismatch: %s" % target
    return "unresolved", "unresolved fence generation=%d" % generation


# ---------------------------------------------------------------- create
def ledger_path_for(sdir, bot, slug, session_id):
    if not (_SANE.match(bot) and _SANE.match(slug)):
        raise LedgerError("bot/slug must be [a-z0-9-]: %r/%r" % (bot, slug))
    return os.path.join(sdir, "solo-%s-%s-%s.yaml" % (bot, slug, session_id))


def create_ledger(sdir, bot, slug, session_id, wd, room_path):
    os.makedirs(sdir, exist_ok=True)
    path = ledger_path_for(sdir, bot, slug, session_id)
    room = os.path.realpath(room_path)
    fields = {
        "bot": bot, "slug": slug, "session_id": session_id,
        "wd": os.path.realpath(wd), "started_iso": _now(),
        "room_path": room,
        "spec_path": os.path.join(room, "01-spec.md"),
        "progress_path": os.path.join(room, "02-progress.md"),
        "outcome_path": os.path.join(room, "03-outcome.md"),
        "state": "open", "claim_session": "", "last_flush_iso": "",
        "generation": "0", "takeover_receipt": "",
    }
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, dump_fields(fields).encode("utf-8"))
        _fsync(fd)
    finally:
        os.close(fd)
    _fsync_dir(sdir)
    return path


# ---------------------------------------------------------------- update tx
class _Lock:
    """Exclusive lock on the separate, never-replaced lock file.
    POSIX = flock(LOCK_EX, 무한 대기). Windows = msvcrt.locking(LK_LOCK,
    1바이트) — ~10초 재시도 후 OSError = 조용한 교착 대신 시끄러운 실패
    (fail-closed 유지: 예외면 tx 자체가 안 열린다)."""

    def __init__(self, ledger_path):
        self._path = _lock_path(ledger_path)

    def __enter__(self):
        self._fd = os.open(self._path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            if fcntl is not None:
                fcntl.flock(self._fd, fcntl.LOCK_EX)
            else:
                os.lseek(self._fd, 0, os.SEEK_SET)
                _msvcrt.locking(self._fd, _msvcrt.LK_LOCK, 1)
        except BaseException:
            # msvcrt 는 ~10초 재시도 후 OSError 가 설계된 정상 경로 —
            # 잠금 실패 시 fd 를 반납해야 반복 경합이 fd 고갈로 번지지
            # 않는다(코난 델타 재검 관측, 2026-08-12). fail-closed 불변:
            # 예외 재전파로 with 블록(tx) 자체가 안 열린다.
            os.close(self._fd)
            raise
        return self

    def __exit__(self, *exc):
        try:
            if fcntl is not None:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
            else:
                os.lseek(self._fd, 0, os.SEEK_SET)
                _msvcrt.locking(self._fd, _msvcrt.LK_UNLCK, 1)
        finally:
            os.close(self._fd)


_process_quarantine = set()   # ledger paths with durability_unknown this run


def update_ledger(path, expect_owner, mutations, actor_session):
    """Full S2 write tx. Returns dict {ok, reason}.
    expect_owner: required current owner() value (claim check) or None to skip
    (create-adjacent flows). Loser on mismatch = read-only + one log line."""
    sdir = os.path.dirname(path) or "."
    if path in _process_quarantine:
        return {"ok": False, "reason": "quarantined durability_unknown"}
    with _Lock(path):
        status, why = fence_status(path)
        if status != "clear":
            _alert_log(sdir, "fence_unresolved",
                       {"ledger": path, "why": why, "op": "update"})
            return {"ok": False, "reason": "fence unresolved: %s" % why}
        try:
            fields = parse_fields(open(path, encoding="utf-8").read())
        except (OSError, LedgerError) as exc:
            _alert_log(sdir, "ledger_unreadable",
                       {"ledger": path, "why": str(exc), "op": "update"})
            return {"ok": False, "reason": "ledger unreadable: %s" % exc}
        if expect_owner is not None and owner(fields) != expect_owner:
            print("solo-ledger: claim loser (owner=%s, expected=%s) — read-only"
                  % (owner(fields), expect_owner), file=sys.stderr)
            return {"ok": False, "reason": "claim mismatch"}

        generation = int(fields.get("generation") or 0) + 1
        txid = "%s-%d" % (actor_session, generation)
        new_fields = dict(fields)
        new_fields.update(mutations)
        new_fields["generation"] = str(generation)

        # fence prepare — before any replace, fully durable
        try:
            _fence_prepare(path, generation, txid)
        except OSError as exc:
            # pre-replace failure: old ledger intact; leftover fence is
            # fail-closed by design (safe quarantine, never unsafe accept)
            _alert_log(sdir, "fence_prepare_failed",
                       {"ledger": path, "why": str(exc)})
            return {"ok": False, "reason": "fence prepare failed: %s" % exc}

        tmp = "%s.tmp.%d" % (path, os.getpid())
        try:
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            try:
                os.write(fd, dump_fields(new_fields).encode("utf-8"))
                _fsync(fd)
            finally:
                os.close(fd)
            _replace(tmp, path)
        except OSError as exc:
            # still pre-replace disposition: live target is the OLD ledger
            try:
                os.unlink(tmp)
            except OSError:
                pass
            try:
                _fence_clear(path)
            except OSError:
                pass   # fence left = fail-closed, acceptable
            _alert_log(sdir, "tx_pre_replace_failed",
                       {"ledger": path, "why": str(exc)})
            return {"ok": False, "reason": "pre-replace failure: %s" % exc}

        try:
            _fsync_dir(sdir)
        except OSError as exc:
            # post-replace: live target is already NEW but not durably so.
            # durability_unknown — fence stays as restart-persistent marker.
            _process_quarantine.add(path)
            _alert_log(sdir, "durability_unknown",
                       {"ledger": path, "why": str(exc),
                        "note": "fence left in place; claim/injection halted"})
            return {"ok": False, "reason": "durability_unknown quarantine"}

        try:
            _fence_clear(path)
        except OSError as exc:
            _alert_log(sdir, "fence_clear_failed",
                       {"ledger": path, "why": str(exc)})
            # tx durable; unresolved fence only fail-closes future writers —
            # safe direction, surface it and report the tx as done.
        return {"ok": True, "reason": "generation=%d" % generation}


# ------------------------------------------------------- sessionstart recovery
def _allowed_roots():
    """Install-fixed canonical roots for meetings/solo rooms (containment).
    Config: <state>/solo-gate.json {"allowed_roots": [...]} — absent = no
    injection possible (fail-closed), recovery still claims/repairs ledgers."""
    cfg = os.path.join(state_dir(), "solo-gate.json")
    try:
        roots = json.load(open(cfg, encoding="utf-8"))["allowed_roots"]
        return [os.path.realpath(r) for r in roots]
    except Exception:
        return []


def _under(root, path):
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def _verify_paths(fields, roots, sdir, ledger):
    """v2.9 L82 검증 4종. Returns (injectable_paths, ledger_ok)."""
    room = fields.get("room_path", "")
    named = [("spec_path", "01-spec.md"), ("progress_path", "02-progress.md"),
             ("outcome_path", "03-outcome.md")]
    room_real = os.path.realpath(room) if room else ""

    # ⓓ same-room canonical basename binding — one miss poisons the ledger
    for key, basename in named:
        p = fields.get(key, "")
        expected = os.path.join(room_real, basename) if room_real else ""
        if not p or not room_real or os.path.realpath(p) != expected:
            _alert_log(sdir, "ledger_path_binding_failed",
                       {"ledger": ledger, "field": key, "value": p,
                        "expected": expected})
            return [], False

    injectable = []
    for key, _basename in named + [("room_path", "")]:
        p = fields.get(key, "")
        real = os.path.realpath(p)                        # ⓐ normalize
        if not any(_under(r, real) for r in roots):       # ⓑ containment
            continue
        if os.path.islink(p):                             # ⓒ non-symlink
            continue
        injectable.append(real)
    return injectable, True


def recover_on_sessionstart(sdir, bot, wd, session_id):
    """Scan solo ledgers; claim matching open ones; return injection payloads.
    Whole per-ledger sequence (fence check → reread → selector → claim)
    holds that ledger's lock — no lock-외부 pre-check is used for claim.
    Single-owner: an open ledger already claimed by ANOTHER session is
    reported under `foreign` and left untouched (takeover() is the only
    path that may transfer it — 85-doc §D). A blank/whitespace session_id
    is refused fail-closed before any scan: an empty claim_session must
    mean «unclaimed», so letting "" claim would re-open the ledger to any
    later session (87-doc §D input-boundary bypass)."""
    results = {"claimed": [], "rejected": [], "foreign": [], "injections": []}
    session_id = (session_id or "").strip()
    if not session_id:
        _alert_log(sdir, "recovery_blank_session", {"wd": wd})
        return results
    roots = _allowed_roots()
    wd_real = os.path.realpath(wd)
    try:
        names = sorted(os.listdir(sdir))
    except OSError:
        return results
    for name in names:
        if not (name.startswith("solo-") and name.endswith(".yaml")):
            continue
        path = os.path.join(sdir, name)
        with _Lock(path):
            status, why = fence_status(path)              # ⓐ fence first
            if status != "clear":
                _alert_log(sdir, "recovery_fence_reject",
                           {"ledger": path, "why": why})
                results["rejected"].append(path)
                continue
            try:                                          # ⓑ reread in-lock
                fields = parse_fields(open(path, encoding="utf-8").read())
            except (OSError, LedgerError) as exc:
                _alert_log(sdir, "recovery_ledger_malformed",
                           {"ledger": path, "why": str(exc)})
                results["rejected"].append(path)
                continue
            if not (fields.get("bot") == bot              # ⓒ selector 3축
                    and os.path.realpath(fields.get("wd", "")) == wd_real
                    and fields.get("state") == "open"):
                continue
            cur_claim = fields.get("claim_session", "")
            if cur_claim and cur_claim != session_id:     # single-owner 가드
                results["foreign"].append(
                    {"ledger": path, "owner": cur_claim,
                     "generation": fields.get("generation", "")})
                continue
            claim = _claim_in_lock(path, fields, session_id, sdir)
            if not claim:
                results["rejected"].append(path)
                continue
            results["claimed"].append(path)
            fields["claim_session"] = session_id
            paths, ledger_ok = _verify_paths(fields, roots, sdir, path)
            if ledger_ok:
                results["injections"].extend(paths)
    return results


def takeover(path, session_id, expect_owner, expect_generation, receipt):
    """Explicit foreign-claim transfer — CAS under the ledger lock.
    All of {current owner == expect_owner, generation == expect_generation,
    state == open, non-blank session_id, non-blank receipt} must hold or
    the takeover is refused (fail-closed). session_id/receipt are stripped
    first — whitespace-only values parse back as "" and would erase the
    owner / void the evidence (87-doc §D). The normalized receipt is
    persisted in the ledger so the transfer carries its evidence
    (85-doc §D / 83-doc orphan 승인 미결)."""
    sdir = os.path.dirname(path) or "."
    session_id = (session_id or "").strip()
    receipt = (receipt or "").strip()
    if not session_id:
        return {"ok": False, "reason": "blank session_id"}
    if not receipt:
        return {"ok": False, "reason": "empty receipt"}
    with _Lock(path):
        status, why = fence_status(path)
        if status != "clear":
            _alert_log(sdir, "takeover_fence_reject",
                       {"ledger": path, "why": why})
            return {"ok": False, "reason": "fence unresolved: %s" % why}
        try:
            fields = parse_fields(open(path, encoding="utf-8").read())
        except (OSError, LedgerError) as exc:
            return {"ok": False, "reason": "ledger unreadable: %s" % exc}
        if fields.get("state") != "open":
            return {"ok": False, "reason": "not open"}
        if owner(fields) != expect_owner:
            return {"ok": False,
                    "reason": "owner CAS mismatch (now=%s)" % owner(fields)}
        if str(fields.get("generation", "")) != str(expect_generation):
            return {"ok": False,
                    "reason": "generation CAS mismatch (now=%s)"
                              % fields.get("generation", "")}
        fields["takeover_receipt"] = receipt
        fields["claim_session"] = session_id
        ok = _claim_in_lock(path, fields, session_id, sdir)
        return {"ok": ok, "reason": "takeover" if ok else "claim tx failed"}


def _claim_in_lock(path, fields, session_id, sdir):
    """ⓓ claim persist — caller already holds the lock, so run the tx body
    inline (re-entering _Lock would deadlock; flock is per-fd)."""
    generation = int(fields.get("generation") or 0) + 1
    new_fields = dict(fields)
    new_fields["claim_session"] = session_id
    new_fields["generation"] = str(generation)
    try:
        _fence_prepare(path, generation, "%s-%d" % (session_id, generation))
    except OSError as exc:
        _alert_log(sdir, "fence_prepare_failed",
                   {"ledger": path, "why": str(exc), "op": "claim"})
        return False
    tmp = "%s.tmp.%d" % (path, os.getpid())
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, dump_fields(new_fields).encode("utf-8"))
            _fsync(fd)
        finally:
            os.close(fd)
        _replace(tmp, path)
    except OSError as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        try:
            _fence_clear(path)
        except OSError:
            pass
        _alert_log(sdir, "tx_pre_replace_failed",
                   {"ledger": path, "why": str(exc), "op": "claim"})
        return False
    try:
        _fsync_dir(sdir)
    except OSError as exc:
        _process_quarantine.add(path)
        _alert_log(sdir, "durability_unknown",
                   {"ledger": path, "why": str(exc), "op": "claim"})
        return False
    try:
        _fence_clear(path)
    except OSError as exc:
        _alert_log(sdir, "fence_clear_failed",
                   {"ledger": path, "why": str(exc), "op": "claim"})
    return True


# ---------------------------------------------------------------- CLI
def main(argv):
    if len(argv) < 2:
        print("usage: solo_ledger.py create|update|recover ...", file=sys.stderr)
        return 2
    cmd = argv[1]
    sdir = state_dir()
    if cmd == "create":
        # create <bot> <slug> <session_id> <wd> <room_path>
        path = create_ledger(sdir, argv[2], argv[3], argv[4], argv[5], argv[6])
        print(path)
        return 0
    if cmd == "update":
        # update <ledger_path> <expect_owner> <session_id> key=value...
        muts = dict(kv.split("=", 1) for kv in argv[5:])
        res = update_ledger(argv[2], argv[3] or None, muts, argv[4])
        print(json.dumps(res, ensure_ascii=False))
        return 0 if res["ok"] else 1
    if cmd == "recover":
        # recover <bot> <wd> <session_id>
        res = recover_on_sessionstart(sdir, argv[2], argv[3], argv[4])
        print(json.dumps(res, ensure_ascii=False))
        return 0
    if cmd == "takeover":
        # takeover <ledger_path> <session_id> <expect_owner> <expect_gen> <receipt>
        res = takeover(argv[2], argv[3], argv[4], argv[5], argv[6])
        print(json.dumps(res, ensure_ascii=False))
        return 0 if res["ok"] else 1
    print("unknown command: %s" % cmd, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
