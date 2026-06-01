#!/usr/bin/env python3
"""ThisCodex reference bridge — Codex CLI app-server ↔ Discord (YOLO opt-in).

This is the **reference implementation** of the bridge daemon that `launch.sh`
runs as its `LAUNCH_CMD` infra process. It is what actually sends the
full-access sandbox to the Codex app-server. `launch.sh` alone is NOT enough —
without this bridge (or one that honors the same contract), a deployed user
cannot run a full-access Codex Discord bot. See docs/yolo-bridge-contract.md.

  Discord WebSocket Gateway
    ↓ inbound @mention / DM
  bot.py (discord.py + asyncio)
    ↓ format <channel source="discord" ...> text
    ↓ JSON-RPC over WebSocket → codex app-server
  codex app-server (ws://127.0.0.1:4222)
    ↓ thread/start (1x) → turn/start (per mention)
    ↓ codex auto-calls the mcp__discord__reply tool
  Discord plugin (reused as a codex MCP server)
    ↓ Discord REST API
  → Discord message sent

╔═══════════════════════════════════════════════════════════════════════════╗
║  YOLO MODE — READ BEFORE DEPLOYING                                         ║
║                                                                           ║
║  This bridge sends sandbox="danger-full-access", approvalPolicy="never"   ║
║  on BOTH thread/start AND thread/resume. That gives the model unrestricted ║
║  shell + filesystem + network on the host. It is OPT-IN, not a default:    ║
║  set THISCODEX_YOLO=1 to enable. With THISCODEX_YOLO unset the bridge runs ║
║  the SAFE default sandbox ("workspace-write"). There is no interactive     ║
║  approval UI in a headless bridge, so risky ops are DENIED by default      ║
║  (the bridge answers approval requests with "cancel"), not prompted.       ║
║                                                                           ║
║  Untrusted Discord text → a YOLO model = arbitrary code execution on your  ║
║  machine. Only enable on a host you control with a TRUSTED private Discord ║
║  server. See docs/yolo-bridge-contract.md §Security.                       ║
╚═══════════════════════════════════════════════════════════════════════════╝
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path

# unbuffered stdout — immediate tmux pane log visibility
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

try:
    import discord
    import websockets
except ImportError as e:
    print(f"[FATAL] missing dependency: {e}. Run `pip install -r requirements.txt` first")
    sys.exit(1)

# The bridge's working dir is the BOT working dir (holds .codex-thread-id,
# dedup.json, bot-info.json, and the auto-loaded SOUL.md/AGENTS.md) — NOT this
# examples/ folder. launch.sh starts the infra with cwd=$BOT_WD and exports
# BOT_WD; honor that. Never use __file__'s parent (that would scope state to
# ThisCodex/examples/ and mis-wire persona auto-load).
_bw = os.environ.get("BOT_WD")
WD = Path(_bw).resolve() if _bw else Path.cwd()

# Bot identity is NOT hardcoded — set BOT_NAME to your bot's channel-state slug.
# The Discord plugin keeps per-bot token/state at
#   ~/.claude/channels/discord-<BOT_NAME>/.env   (DISCORD_BOT_TOKEN=...)
# This mirrors the Claude Code Discord plugin layout so one plugin install
# serves both Claude Code and Codex bots.
BOT_NAME = os.environ.get("BOT_NAME", "mybot")
ENV_PATH = Path.home() / ".claude" / "channels" / f"discord-{BOT_NAME}" / ".env"
DEDUP_PATH = WD / "dedup.json"
BOT_INFO_PATH = WD / "bot-info.json"
THREAD_ID_PATH = WD / ".codex-thread-id"
_THISCODEX_ROOT = Path(__file__).resolve().parents[1]
for _scripts_dir in (
    Path(os.environ.get("THISCODEX_ROOT", _THISCODEX_ROOT)) / "scripts",
    Path.home() / "obsidian-ai-vault/.claude/scripts",
):
    if _scripts_dir.exists():
        sys.path.insert(0, str(_scripts_dir))

try:
    import memory_s5
except Exception as e:
    memory_s5 = None
    print(f"[WARN] memory_s5 import failed: {e}")

CODEX_WS = os.environ.get("CODEX_WS", "ws://127.0.0.1:4222")
TURN_TIMEOUT_SEC = int(os.environ.get("CODEX_TURN_TIMEOUT", "300"))
MAX_DEDUP_ENTRIES = 5000

# YOLO is opt-in and selectable PER BOT. Opt-in signals — all OPERATOR-
# controlled and OUTSIDE the model's writable working dir (critical: a sentinel
# inside WD would let a model, fed untrusted Discord text in safe mode, write
# the file and self-upgrade safe→YOLO on the next bridge restart):
#   - env THISCODEX_YOLO=1                    (process-scoped, one-off launch)
#   - env THISCODEX_YOLO_FILE=/abs/path       (explicit operator path), else
#   - default sentinel  ~/.claude/channels/discord-<BOT_NAME>/.thiscodex-yolo
#     (the bridge/token state dir — per-bot, and NOT the model's cwd/WD, so the
#      model cannot create it). Neither present → safe default sandbox.
_yolo_file = os.environ.get("THISCODEX_YOLO_FILE")
_yolo_sentinel = Path(_yolo_file) if _yolo_file else (ENV_PATH.parent / ".thiscodex-yolo")
YOLO = (os.environ.get("THISCODEX_YOLO", "0") == "1") or _yolo_sentinel.is_file()
SANDBOX = "danger-full-access" if YOLO else "workspace-write"
APPROVAL_POLICY = "never" if YOLO else "on-request"

# B-fix: bridge-level progress heartbeat. A long turn (model working silently)
# emits a progress message to the originating channel every
# HEARTBEAT_INTERVAL_SEC, so a long/blocked task is never a silent gap even if
# the model forgets its proactive-report rule. 0 disables.
# Default MUST be < the turn timeout, or the timeout fires first and the
# heartbeat never sends. Clamp to guarantee at least one heartbeat per turn.
HEARTBEAT_INTERVAL_SEC = int(os.environ.get("THISCODEX_HEARTBEAT_SEC", "240"))
if 0 < TURN_TIMEOUT_SEC <= HEARTBEAT_INTERVAL_SEC:
    HEARTBEAT_INTERVAL_SEC = max(30, int(TURN_TIMEOUT_SEC * 0.8))


def load_token() -> str:
    if not ENV_PATH.exists():
        raise RuntimeError(f"DISCORD_BOT_TOKEN file not found: {ENV_PATH}")
    for line in ENV_PATH.read_text().splitlines():
        if line.startswith("DISCORD_BOT_TOKEN="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError(f"no DISCORD_BOT_TOKEN= entry in {ENV_PATH}")


def load_dedup() -> dict:
    if not DEDUP_PATH.exists():
        return {}
    try:
        return json.loads(DEDUP_PATH.read_text() or "{}")
    except json.JSONDecodeError:
        return {}


def save_dedup(state: dict) -> None:
    if len(state) > MAX_DEDUP_ENTRIES:
        oldest = sorted(state.items(), key=lambda kv: kv[1].get("ts", 0))[: len(state) - MAX_DEDUP_ENTRIES]
        for k, _ in oldest:
            state.pop(k, None)
    DEDUP_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2))


class CodexRPC:
    """Minimal JSON-RPC client over WebSocket for the codex app-server v2 protocol."""

    def __init__(self, url: str):
        self.url = url
        self.ws = None
        self.next_id = 1
        self.pending: dict[int, asyncio.Future] = {}
        self.turn_done: dict[str, asyncio.Future] = {}
        self.reader_task = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        print(f"[CODEX-RPC] connecting to {self.url} ...")
        self.ws = await websockets.connect(self.url, max_size=None)
        self.reader_task = asyncio.create_task(self._reader())
        await self.call("initialize", {
            "clientInfo": {"name": "thiscodex_bridge", "version": "0.1.0"},
            "capabilities": {"experimentalApi": True},
        })
        # initialized notification (no id)
        await self.ws.send(json.dumps({"method": "initialized"}))
        print("[CODEX-RPC] initialized")

    async def _reader(self) -> None:
        try:
            async for raw in self.ws:
                # DEBUG: log every incoming frame (truncated)
                print(f"[WS-IN] {str(raw)[:400]}")
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    print(f"[CODEX-RPC] non-JSON frame: {str(raw)[:200]}")
                    continue

                if "id" in msg and ("result" in msg or "error" in msg):
                    fut = self.pending.pop(msg["id"], None)
                    if fut and not fut.done():
                        fut.set_result(msg)
                    continue

                method = msg.get("method", "")

                # Server-initiated JSON-RPC request — the client MUST respond, or
                # the codex turn hangs forever (turn/start then codex asks the
                # client for approval / elicitation / a tool call; ignoring it
                # never completes the turn).
                if "id" in msg and method:
                    print(f"[WS-SERVER-REQ] method={method} id={msg['id']}")
                    if method in ("item/commandExecution/requestApproval", "item/fileChange/requestApproval"):
                        # In YOLO the model should not be asked (approvalPolicy
                        # never); if it is, default-deny is the safe answer.
                        resp = {"id": msg["id"], "result": {"decision": "cancel"}}
                    elif method == "mcpServer/elicitation/request":
                        # MCP tool-call approval — codex asks the client right
                        # before calling e.g. mcp__discord__reply. accept +
                        # persist:"session" auto-approves for this session.
                        params = msg.get("params", {})
                        kind = (params.get("_meta") or {}).get("codex_approval_kind", "")
                        print(f"[ELICIT-ACCEPT] server={params.get('serverName')} kind={kind}")
                        resp = {"id": msg["id"], "result": {"action": "accept", "content": {}, "_meta": {"persist": "session"}}}
                    elif method == "item/tool/requestUserInput":
                        # Stateful Discord question shim — handled off the
                        # reader loop so a long human wait does not block
                        # other codex WS frames.
                        asyncio.create_task(self._handle_request_user_input(msg))
                        continue
                    elif method == "item/tool/call":
                        params = msg.get("params", {})
                        resp = {"id": msg["id"], "result": {
                            "success": False,
                            "contentItems": [{"type": "inputText", "text": f"Client-side tool not implemented: {params.get('tool', '?')}"}],
                        }}
                    elif method == "item/permissions/requestApproval":
                        resp = {"id": msg["id"], "result": {"decision": "cancel"}}
                    else:
                        resp = {"id": msg["id"], "error": {"code": -32601, "message": f"Unhandled server request: {method}"}}
                    await self.ws.send(json.dumps(resp))
                    continue

                # any "completed"-flavored turn notification resolves the future
                if method == "turn/completed" or method.endswith("/turn/completed") or "TurnCompleted" in method:
                    turn = msg.get("params", {}).get("turn") or msg.get("params", {})
                    tid = turn.get("id") if isinstance(turn, dict) else None
                    if tid:
                        fut = self.turn_done.pop(tid, None)
                        if fut and not fut.done():
                            fut.set_result(turn)
                    else:
                        # fallback: resolve oldest pending turn
                        if self.turn_done:
                            key, fut = next(iter(self.turn_done.items()))
                            self.turn_done.pop(key, None)
                            if not fut.done():
                                fut.set_result(turn)
                elif method.startswith("item/agentMessage"):
                    # stream notification — log only
                    pass
        except websockets.ConnectionClosed as e:
            print(f"[CODEX-RPC] connection closed: {e}")
        except Exception as e:
            print(f"[CODEX-RPC] reader error: {type(e).__name__}: {e}")

    async def call(self, method: str, params: dict | None = None) -> dict:
        async with self._lock:
            rid = self.next_id
            self.next_id += 1
            fut = asyncio.get_running_loop().create_future()
            self.pending[rid] = fut
            req: dict = {"id": rid, "method": method}
            if params is not None:
                req["params"] = params
            await self.ws.send(json.dumps(req))
        try:
            msg = await asyncio.wait_for(fut, timeout=60)
        except asyncio.TimeoutError:
            self.pending.pop(rid, None)
            raise RuntimeError(f"timeout: {method}")
        if "error" in msg:
            raise RuntimeError(f"{method} failed: {msg['error']}")
        return msg.get("result", {})

    async def ensure_thread(self) -> str:
        if THREAD_ID_PATH.exists():
            tid = THREAD_ID_PATH.read_text().strip()
            try:
                # CONTRACT (do NOT drop): thread/resume MUST re-send sandbox +
                # approvalPolicy. If omitted, the resumed thread silently falls
                # back to the server default (workspace-write /
                # networkAccess:false) — so YOLO would apply on the very first
                # turn and then never again after the first resume. This is the
                # single nastiest bug; see docs/yolo-bridge-contract.md.
                await self.call("thread/resume", {
                    "threadId": tid,
                    "cwd": str(WD),
                    "sandbox": SANDBOX,
                    "approvalPolicy": APPROVAL_POLICY,
                })
                print(f"[CODEX-RPC] resumed thread {tid} (sandbox={SANDBOX})")
                return tid
            except Exception as e:
                print(f"[CODEX-RPC] resume failed ({e}) — starting new thread")

        res = await self.call("thread/start", {
            "cwd": str(WD),
            "sandbox": SANDBOX,
            "approvalPolicy": APPROVAL_POLICY,
            "threadSource": "user",
        })
        # spec uncertainty — try multiple shapes
        tid = None
        if isinstance(res, dict):
            tid = res.get("threadId") or (res.get("thread") or {}).get("id")
        if not tid:
            raise RuntimeError(f"thread/start did not return id: {res}")
        await self.materialize_thread_for_tui(tid)
        THREAD_ID_PATH.write_text(tid)
        print(f"[CODEX-RPC] started new thread {tid} (sandbox={SANDBOX})")
        return tid

    async def materialize_thread_for_tui(self, thread_id: str) -> None:
        """Force local rollout creation so `codex resume --remote` can attach immediately."""
        marker = {
            "type": "message",
            "role": "assistant",
            "content": [{
                "type": "output_text",
                "text": "[bridge:init] rollout materialized for local TUI attach. No action required.",
            }],
            "phase": None,
        }
        await self.call("thread/inject_items", {
            "threadId": thread_id,
            "items": [marker],
        })
        print(f"[CODEX-RPC] materialized thread rollout for TUI attach {thread_id}")

    async def send_turn(self, thread_id: str, text: str) -> dict:
        res = await self.call("turn/start", {
            "threadId": thread_id,
            "input": [{"type": "text", "text": text}],
        })
        print(f"[CODEX-RPC] turn/start response = {json.dumps(res)[:400]}")
        turn = res if isinstance(res, dict) else {}
        turn_id = turn.get("turnId") or (turn.get("turn") or {}).get("id")
        print(f"[CODEX-RPC] extracted turn_id = {turn_id}")
        if not turn_id:
            return turn
        fut = asyncio.get_running_loop().create_future()
        self.turn_done[turn_id] = fut
        try:
            # A turn carrying a question must outlive the human wait PLUS
            # post-answer processing, else a user who answers in time still
            # gets a false `turn timed out` (independent-review BLOCKER).
            return await asyncio.wait_for(fut, timeout=EFFECTIVE_TURN_TIMEOUT_SEC)
        except asyncio.TimeoutError:
            self.turn_done.pop(turn_id, None)
            print(f"[CODEX-RPC] turn timeout: {turn_id}")
            return {"status": "timeout", "turnId": turn_id}

    # ── AskUserQuestion shim (tool-equivalence-contract.md §AskUserQuestion) ──
    async def _handle_request_user_input(self, msg: dict) -> None:
        params = msg.get("params", {}) or {}
        # Spec uncertainty: the public codex docs do not pin requestUserInput's
        # param shape. Parse defensively. KM `AskUserQuestion` sends a
        # `questions[]` batch (full/bootstrap multi-question); legacy single
        # {prompt,choices} is still accepted (→ 1-element, key "value").
        mid = msg.get("id")
        # BLOCKER: parse/send/wait may all raise; an unanswered JSON-RPC id
        # hangs the Codex request forever. Any failure → a guaranteed
        # {blocked:true, error:<type>} response (independent-review BLOCKER).
        try:
            specs = _normalize_questions(params)
            answers = await self._ask_via_discord(specs)
            if answers is not None:
                # answers is a map keyed by each question's stable key
                result = {"answers": answers}
            else:
                # condition 4: no answer + no default → blocked, never silently ok
                result = {"answers": {}, "blocked": True}
        except Exception as e:
            print(f"[QA] handler error: {type(e).__name__}: {e}")
            _audit("question_handler_error", {"id": mid, "error": type(e).__name__})
            result = {"answers": {}, "blocked": True, "error": type(e).__name__}
        # The JSON-RPC reply itself can fail (dead ws). Bounded best-effort
        # retry absorbs transient backpressure; a persistently dead ws is a
        # genuine transport failure no layer here can paper over — the
        # documented backstop is then EFFECTIVE_TURN_TIMEOUT_SEC on the Codex
        # side plus the bridge reconnect loop (independent-review BLOCKER:
        # honest limitation, not a silent hang). A request with no id is a
        # notification → nothing to answer; never emit an id:null reply.
        if mid is None:
            print("[QA] requestUserInput had no JSON-RPC id; nothing to answer")
            return
        for attempt in range(3):
            try:
                await self.ws.send(json.dumps({"id": mid, "result": result}))
                break
            except Exception as e:
                print(f"[QA] response send failed (attempt {attempt + 1}/3): "
                      f"{type(e).__name__}: {e}")
                if attempt < 2:
                    await asyncio.sleep(0.5 * (attempt + 1))
        else:
            _audit("question_response_undeliverable", {"id": mid})
            print("[QA] response undeliverable — ws transport dead; backstop = "
                  "turn timeout + bridge reconnect")

    async def _ask_via_discord(self, specs: list[dict]):
        # Snapshot the origin PER QUESTION at ask time — never read the shared
        # mutable _active_origin at reply time (worker.finally clears it; a
        # late reply would then pass the channel check with chat_id=None and
        # bypass condition 3 — independent-review BLOCKER). Each pending
        # question carries its own immutable origin.
        ch = _active_origin.get("channel")
        origin_user = _active_origin.get("user_id")
        origin_chat = _active_origin.get("chat_id")
        qid = uuid.uuid4().hex                       # condition 1: bridge UUID
        all_default = {s["key"]: s["default"] for s in specs
                       if s.get("default") is not None}
        defaults_map = (all_default
                        if len(all_default) == len(specs) and specs else None)
        if ch is None:
            _audit("question_no_origin", {"qid": qid, "n": len(specs)})
            return defaults_map
        # condition 2: bridge renders the fixed choice set; replies are matched
        # by number, free-form only where a question allows it.
        lines = [f"❓ please answer the following — question {qid[:8]}, "
                 f"one line per question (reply within {QUESTION_TIMEOUT_SEC}s):"]
        for i, s in enumerate(specs, 1):
            lines.append(f"Q{i} · {s['header']}: {s['question']}")
            for j, o in enumerate(s["options"], 1):
                lines.append(f"   {j}. {o}")
        lines.append("(one line per question in order — a number for a choice, "
                     "`1,3` for multi-select, or free text where allowed; you "
                     "may prefix `Q2: …`. defaults apply on timeout where set.)")
        fut = asyncio.get_running_loop().create_future()
        _pending_q[qid] = fut
        _q_meta[qid] = {"origin_user_id": origin_user, "origin_chat_id": origin_chat,
                        "specs": specs, "acc": {}, "defaults_map": defaults_map}
        _audit("question_asked", {"qid": qid, "origin_user_id": origin_user,
                                  "keys": [s["key"] for s in specs],
                                  "questions": [s["question"][:200] for s in specs]})
        rem = None
        try:
            try:
                await ch.send("\n".join(lines), allowed_mentions=_NO_MENTIONS)
            except Exception as e:
                # BLOCKER: the question never reached the user. Don't wait out
                # the full timeout on a dead question — fail fast so the
                # handler returns blocked+error immediately.
                print(f"[QA] question send failed: {type(e).__name__}: {e}")
                _audit("question_send_failed", {"qid": qid, "error": type(e).__name__})
                raise
            async def _remind():
                # MINOR: a long human wait should not look like a hung bot.
                await asyncio.sleep(max(30, QUESTION_TIMEOUT_SEC // 2))
                with contextlib.suppress(Exception):
                    await ch.send(f"⏳ question {qid[:8]} still open — "
                                  + ("defaults apply soon" if defaults_map is not None
                                     else "will block soon if unanswered"),
                                  allowed_mentions=_NO_MENTIONS)
            rem = asyncio.create_task(_remind())
            try:
                ans = await asyncio.wait_for(fut, timeout=QUESTION_TIMEOUT_SEC)
                _audit("question_answered", {"qid": qid, "answers": str(ans)[:500]})
                return ans
            except asyncio.TimeoutError:
                _audit("question_timeout", {"qid": qid,
                                            "had_defaults": defaults_map is not None})
                # condition 4: apply defaults only if EVERY question has one;
                # otherwise blocked, never a silent partial ok.
                if defaults_map is not None:
                    return defaults_map
                with contextlib.suppress(Exception):
                    await ch.send(f"⚠️ question {qid[:8]} timed out — not every "
                                  f"question had a default — task blocked "
                                  f"(bridge fail-safe).",
                                  allowed_mentions=_NO_MENTIONS)
                return None
        finally:
            if rem is not None:
                rem.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await rem
            _pending_q.pop(qid, None)
            _q_meta.pop(qid, None)


TOKEN = load_token()
codex = CodexRPC(CODEX_WS)
queue: asyncio.Queue = asyncio.Queue()
thread_id: str | None = None

# ── AskUserQuestion shim state (tool-equivalence-contract.md §AskUserQuestion) ──
# A skill calling the AskUserQuestion equivalent surfaces as a codex
# `item/tool/requestUserInput`. The bridge turns it into a stateful Discord
# question and returns the matched answer. The 6 security conditions are
# enforced here; an unenforced condition = a prompt-injection hole.
QUESTION_TIMEOUT_SEC = int(os.environ.get("THISCODEX_QUESTION_TIMEOUT", "300"))
# Multi-question policy (independent-review BLOCKER): KM `AskUserQuestion`
# sends `questions[]` (full Mode-R = 3, STEP-1 = 4, bootstrap = 2-call).
# The shim renders the WHOLE batch in ONE Discord message and accepts
# answers over one shared QUESTION_TIMEOUT budget (incrementally mergeable)
# — NOT N sequential per-question timeouts — so the turn-timeout invariant
# stays single-budget: turn ≥ max(turn, question + post-answer buffer).
QA_POST_ANSWER_BUFFER_SEC = int(os.environ.get("THISCODEX_QA_POST_ANSWER_BUFFER", "180"))
EFFECTIVE_TURN_TIMEOUT_SEC = max(TURN_TIMEOUT_SEC,
                                 QUESTION_TIMEOUT_SEC + QA_POST_ANSWER_BUFFER_SEC)
# Question/reminder/timeout prompts are skill-supplied text echoed to Discord.
# Treat them as data — never let an embedded @everyone/@user become a real
# ping (independent-review P1). All shim sends pass this.
_NO_MENTIONS = discord.AllowedMentions.none()
# Forensic audit must NOT live in the model's writable WD: in safe mode the
# model cwd/WD is writable, so a model fed untrusted Discord text could
# tamper with its own audit trail. Same principle as the YOLO sentinel —
# keep it in the operator-controlled bridge state dir, outside the model's
# reach (independent-review P1). Overridable via env for ops.
AUDIT_PATH = Path(os.environ.get("THISCODEX_QA_AUDIT_FILE",
                                 str(ENV_PATH.parent / ".thiscodex-qa-audit.jsonl")))
_pending_q: dict[str, asyncio.Future] = {}      # question_id → future(answers map)
_q_meta: dict[str, dict] = {}                   # question_id → {origin_*, specs[], acc{}, ...}
# origin of the turn currently being processed (worker sets this); the shim
# asks on THIS channel and only accepts a reply from THIS user (condition 3).
_active_origin: dict = {"channel": None, "chat_id": None, "user_id": None}
# condition 3: besides the original requester, only these explicitly approved
# operator user-ids may answer a question. Operator-controlled env, never
# derived from message content.
_QA_OPERATORS: set = {x for x in os.environ.get("THISCODEX_QA_OPERATORS", "").split(",") if x}


def _audit(event: str, rec: dict) -> None:
    """Condition 6: every question / response / timeout is logged. The asked
    prompt is recorded so forensic review can flag a hijacked question by a
    prompt-text ↔ answer mismatch (bridge logic itself is text-independent —
    choices/allow_free_text are params only, never driven by message text)."""
    try:
        line = json.dumps({"ts": int(time.time()), "event": event, **rec}, ensure_ascii=False)
        with open(AUDIT_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as e:
        print(f"[QA-AUDIT] write failed: {type(e).__name__}: {e}")


def _normalize_questions(params: dict) -> list[dict]:
    """KM `AskUserQuestion` sends {"questions":[{question,header,options:[{label,
    description}],multiSelect?}]}. Normalize to a stable internal spec list.
    Legacy single {prompt/question, choices/options} → a 1-element list with
    key "value" so the JSON-RPC result stays {"answers":{"value":...}}.
    Each spec key precedence: explicit id → header → q{index} (bridge-assigned,
    audited) so the answers map is stable even if the skill omits ids."""
    qs = params.get("questions")
    specs: list[dict] = []
    seen: set[str] = set()

    def _uniq(k: str, i: int) -> str:
        # independent-review P1: duplicate id/header would collapse in the
        # answers map (one reply resolving every copy). Force uniqueness
        # deterministically; the final key set is audited in question_asked.
        if k not in seen:
            seen.add(k)
            return k
        c = i
        nk = f"{k}#q{c}"
        while nk in seen:                            # loop until truly unique
            c += 1
            nk = f"{k}#q{c}"
        seen.add(nk)
        return nk

    if isinstance(qs, list) and qs:
        for i, q in enumerate(qs, 1):
            q = q if isinstance(q, dict) else {}
            header = q.get("header")
            key = _uniq(str(q.get("id") or header or f"q{i}"), i)
            raw = q.get("options") or q.get("choices") or []
            opts = [str(o.get("label") if isinstance(o, dict) else o)
                    for o in (raw if isinstance(raw, list) else [])]
            specs.append({
                "key": key,
                "header": str(header or key),
                "question": str(q.get("question") or q.get("prompt") or "(no prompt)"),
                "options": opts,
                # condition 2: free-form requires an EXPLICIT opt-in; an
                # optionless question without it is unanswerable → blocks
                # (never auto-enable free text — independent-review BLOCKER).
                "multiselect": bool(q.get("multiSelect") or q.get("multiselect")),
                "allow_free_text": bool(q.get("allow_free_text", False)),
                "default": q.get("default"),
            })
        return specs
    # legacy single-question shape
    raw = params.get("choices") or params.get("options") or []
    opts = [str(c) for c in raw] if isinstance(raw, list) else []
    specs.append({
        "key": "value",
        "header": "value",
        "question": str(params.get("prompt") or params.get("question") or "(no prompt)"),
        "options": opts,
        "multiselect": False,
        "allow_free_text": bool(params.get("allow_free_text", False)),
        "default": params.get("default"),
    })
    return specs


def _parse_batch(text: str, specs: list[dict], acc: dict) -> tuple[dict, list[str]]:
    """Parse a (possibly partial) batched reply and merge resolved answers into
    `acc`. One line per question, in original order; an optional **strict
    `Qn:` prefix only** (`Q2: …`, case-insensitive, n = 1-based question
    index) routes a line to a specific question — header/key-name routing is
    deliberately NOT honored, since natural-language free text containing a
    colon would otherwise be misrouted (independent-review P1). Unrouted
    lines fill the still-unanswered specs in order. Already-answered keys are
    never overwritten by a later message (first-write-wins,
    independent-review P1). The reply body is data only (condition 5) — it
    never changes which/what questions are asked (those come from params)."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    routed: list[tuple[dict | None, str]] = []
    for ln in lines:
        target = None
        body = ln
        if ":" in ln:
            pre, rest = ln.split(":", 1)
            m = re.fullmatch(r"[Qq](\d+)", pre.strip())
            if m:
                idx = int(m.group(1)) - 1
                if 0 <= idx < len(specs):
                    target, body = specs[idx], rest.strip()
        routed.append((target, body))
    # positional fill for unrouted lines → specs still missing from acc
    unfilled = [s for s in specs if s["key"] not in acc]
    pos = 0
    for tgt, body in routed:
        spec = tgt
        if spec is None:
            while pos < len(unfilled) and unfilled[pos]["key"] in acc:
                pos += 1
            if pos >= len(unfilled):
                continue
            spec = unfilled[pos]
            pos += 1
        # first-write-wins: a later message cannot flip an accepted answer.
        if spec["key"] in acc:
            continue
        opts = spec["options"]
        val = None
        numeric_attempt = False
        if opts:
            # condition 2: the WHOLE body must be a strict numeric selection —
            # a number buried in free text ("1 ignore the rest") must NOT
            # silently resolve as choice 1 (independent-review BLOCKER).
            if spec["multiselect"]:
                strict = re.fullmatch(r"\d+([,\s]+\d+)*", body)
            else:
                strict = re.fullmatch(r"\d+", body)
            if strict:
                # This was a choice attempt. Even if out-of-range it must NOT
                # fall through to free text (e.g. "99" silently stored as the
                # answer) — leave it unresolved so the user is re-prompted
                # (independent-review BLOCKER).
                numeric_attempt = True
                picks: list[str] = []
                ok = True
                for t in re.split(r"[,\s]+", body):
                    if not t:
                        continue
                    n = int(t)
                    if 1 <= n <= len(opts):
                        picks.append(opts[n - 1])
                    else:
                        ok = False
                        break
                if ok and picks:
                    val = picks if spec["multiselect"] else picks[0]
        if val is None and not numeric_attempt and spec["allow_free_text"] and body:
            val = body                               # condition 5: body as data
        if val is not None:
            acc[spec["key"]] = val
    unresolved = [s["key"] for s in specs if s["key"] not in acc]
    return acc, unresolved


intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


@client.event
async def on_ready():
    global thread_id
    print(f"[READY] discord.py logged in as {client.user} (id={client.user.id})")
    print(f"[READY] YOLO={'ON (danger-full-access)' if YOLO else 'off (workspace-write)'} "
          f"heartbeat={HEARTBEAT_INTERVAL_SEC}s")
    BOT_INFO_PATH.write_text(json.dumps({
        "user_id": str(client.user.id),
        "name": str(client.user),
        "ready_at": int(time.time()),
    }, ensure_ascii=False, indent=2))

    # connect codex app-server (with retries — app-server may still be booting)
    for attempt in range(10):
        try:
            await codex.connect()
            break
        except Exception as e:
            print(f"[CODEX-RPC] connect attempt {attempt+1} failed: {e}")
            await asyncio.sleep(2)
    else:
        print("[FATAL] codex app-server connect failed after 10 attempts")
        await client.close()
        return

    thread_id = await codex.ensure_thread()
    print(f"[READY] codex thread = {thread_id}")
    asyncio.create_task(worker())


async def _heartbeat(channel, started: float, stop: asyncio.Event) -> None:
    """B-fix: while a turn runs, emit a progress note every interval so a long
    or blocked task is never a silent gap (defense-in-depth alongside the
    model's proactive-report rule in SOUL.md/AGENTS.md)."""
    if HEARTBEAT_INTERVAL_SEC <= 0 or channel is None:
        return
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=HEARTBEAT_INTERVAL_SEC)
            return  # stop set → turn finished, no heartbeat needed
        except asyncio.TimeoutError:
            mins = int((time.time() - started) // 60)
            try:
                await channel.send(f"⏳ still working — {mins}m elapsed, no result yet "
                                    f"(bridge heartbeat; the bot will report when done or blocked)",
                                    allowed_mentions=_NO_MENTIONS)
            except Exception as e:
                print(f"[HEARTBEAT] send failed: {type(e).__name__}: {e}")


@client.event
async def on_message(msg: discord.Message):
    is_self = (msg.author == client.user)
    is_mentioned = (client.user in msg.mentions)
    is_dm = isinstance(msg.channel, discord.DMChannel)
    print(f"[RAW] ch={msg.channel.id} dm={is_dm} "
          f"author={msg.author} ({msg.author.id}) bot={msg.author.bot} "
          f"self={is_self} mentioned={is_mentioned} content='{msg.content[:80]}'")

    if is_self:
        return

    # ── AskUserQuestion shim: is this a reply to a pending bridge question? ──
    # Checked before the mention/dedup gates so the original requester can
    # answer without re-mentioning the bot. Enforces conditions 2,3,5.
    if _pending_q:
        for qid, fut in list(_pending_q.items()):
            meta = _q_meta.get(qid, {})
            ou = meta.get("origin_user_id")
            # condition 3: only the original requester or an approved operator
            ok_user = (str(msg.author.id) == str(ou)) or (str(msg.author.id) in _QA_OPERATORS)
            # answer must come from the SAME channel the question was asked on.
            # Use the per-question snapshot (never the shared _active_origin,
            # which worker.finally clears → would let chat_id=None match any
            # channel and bypass condition 3).
            same_ch = str(meta.get("origin_chat_id")) == str(msg.channel.id)
            if not (ok_user and same_ch):
                continue
            # strip a leading/instinctive bot mention from the answer too —
            # else "<@bot> 1" fails the digit test, falls through the mention
            # gate and enqueues a spurious NEW turn (independent-review P1).
            text = (msg.content.replace(f"<@{client.user.id}>", "")
                                .replace(f"<@!{client.user.id}>", "").strip())
            specs = meta.get("specs") or []
            acc = meta.setdefault("acc", {})
            # condition 5: the reply body is data only — parsed against the
            # fixed specs, never altering which questions are asked.
            acc, unresolved = _parse_batch(text, specs, acc)
            if unresolved:
                # From the question's origin user+channel but the batch is not
                # yet complete/valid. Consume with guidance and KEEP waiting
                # (one shared timeout) — do NOT leak a new codex turn (P1).
                _audit("question_partial_reply",
                       {"qid": qid, "resolved": list(acc.keys()),
                        "unresolved": unresolved, "raw": text[:200]})
                with contextlib.suppress(Exception):
                    todo = "; ".join(
                        f"Q{i} {s['header']}"
                        + (f" (1-{len(s['options'])})" if s["options"] else " (free text)")
                        for i, s in enumerate(specs, 1) if s["key"] in unresolved)
                    await msg.channel.send(
                        f"⚠️ question {qid[:8]}: still need — {todo}. "
                        f"One line per question, in order.",
                        allowed_mentions=_NO_MENTIONS)
                return                               # consumed, no new turn
            if not fut.done():
                fut.set_result(dict(acc))            # full answers map
            with contextlib.suppress(Exception):
                await msg.add_reaction("✅")
            return                                   # consumed; never goes to a codex turn

    # DM channel = no mention required (the bot receiving it IS the intent).
    # Guild channel/thread = mention required.
    if not is_dm and not is_mentioned:
        return

    state = load_dedup()
    if str(msg.id) in state:
        return
    state[str(msg.id)] = {"ts": int(time.time()), "ch": str(msg.channel.id)}
    save_dedup(state)

    print(f"[MSG] {msg.author} in {msg.channel} ({msg.id}): {msg.content[:120]}")
    try:
        await msg.add_reaction("🔍")
    except Exception:
        pass

    # format as a <channel> tag — codex reads it as conversation context
    clean = msg.content.replace(f"<@{client.user.id}>", "").replace(f"<@!{client.user.id}>", "").strip()
    parent_info = ""
    if hasattr(msg.channel, "parent") and msg.channel.parent is not None:
        parent_info = f' parent_chat_id="{msg.channel.parent.id}"'
    event = (
        f'<channel source="discord" chat_id="{msg.channel.id}"'
        f'{parent_info} message_id="{msg.id}"'
        f' user="{msg.author}" user_id="{msg.author.id}"'
        f' ts="{msg.created_at.isoformat()}">\n'
        f'{clean}\n'
        f'</channel>\n'
        f'→ reply to the message above.'
    )
    if memory_s5 is not None:
        try:
            reminder = memory_s5.bridge_reminder_text(clean)
            if reminder:
                print(f"[MEMORY-S5] trigger msg={msg.id} query={memory_s5.score_prompt(clean).get('query', '')[:80]}")
                event = f"{reminder}\n\n{event}"
        except Exception as e:
            print(f"[WARN] memory_s5 bridge injection failed: {type(e).__name__}: {e}")
    # Static reply rule lives in AGENTS.md (project-doc auto-loaded), NOT
    # re-injected per turn. Per-turn payload = the dynamic <channel> block +
    # one "→ reply" line only (no persona/SOUL re-announcement noise).
    await queue.put((event, msg.channel, msg.channel.id, msg.author.id))


async def worker():
    """Serialize turns — the codex app-server is single-turn-per-thread here."""
    global thread_id
    print("[WORKER-START]")
    while True:
        event, channel, o_chat, o_user = await queue.get()
        print(f"[WORKER-GET] event size = {len(event)} chars")
        # The AskUserQuestion shim asks on, and only accepts a reply from,
        # this turn's origin (condition 3). Set before the turn can call it.
        _active_origin.update({"channel": channel, "chat_id": o_chat, "user_id": o_user})
        stop = asyncio.Event()
        hb = asyncio.create_task(_heartbeat(channel, time.time(), stop))
        blocked_reason = None
        try:
            if thread_id is None:
                thread_id = await codex.ensure_thread()
            print(f"[WORKER-SEND] turn/start to thread {thread_id} ...")
            result = await codex.send_turn(thread_id, event)
            print(f"[TURN-DONE] result keys: {list(result.keys()) if isinstance(result, dict) else type(result).__name__}")
            if isinstance(result, dict) and result.get("status") == "timeout":
                blocked_reason = f"turn timed out after {EFFECTIVE_TURN_TIMEOUT_SEC}s with no result"
        except Exception as e:
            blocked_reason = f"turn dispatch error: {type(e).__name__}"
            print(f"[ERROR] turn dispatch: {type(e).__name__}: {e}")
        finally:
            stop.set()
            hb.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await hb
            # B-fix fail-safe: a timeout/exception otherwise produces NO Discord
            # message at all (the codex turn never called mcp__discord__reply).
            # Emit a generic blocked report so it is never a silent gap.
            if blocked_reason and channel is not None:
                try:
                    await channel.send(f"⚠️ blocked — {blocked_reason}; no reply was produced "
                                       f"(bridge fail-safe report; check the bot host).",
                                       allowed_mentions=_NO_MENTIONS)
                except Exception as e:
                    print(f"[BLOCKED-REPORT] send failed: {type(e).__name__}: {e}")
            # turn over → invalidate origin so a late message can't match a
            # stale question against the wrong turn.
            _active_origin.update({"channel": None, "chat_id": None, "user_id": None})
            queue.task_done()


def main():
    print(f"[INFO] WD: {WD}")
    print(f"[INFO] CODEX_WS: {CODEX_WS}")
    print(f"[INFO] ENV: {ENV_PATH}")
    print(f"[INFO] YOLO: {'ON' if YOLO else 'off'}  SANDBOX: {SANDBOX}  APPROVAL: {APPROVAL_POLICY}")
    client.run(TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
