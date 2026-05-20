"""agy Discord bridge daemon.

inbox 폴링 → 채널별 flock → 모드 라우팅 (Y-3 / Y-2 / OCR) → agy 호출 → Discord reply.

Codex code-review mitigation 모두 컴포넌트 위임:
- 항목 1·5 atomic + race → conv_map.ConvMap
- 항목 4 stdout injection → agy_worker.AgyWorker (argv + shell=False + clean)
- 항목 6 path traversal → attachment.AttachmentSandbox
- 항목 7 rotation → log_rotation.RotatingLog
- unsafe-mode 게이트 → agy_worker AGY_UNSAFE env flag
"""
import asyncio
import fcntl
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol

from conv_map import ConvMap
from attachment import AttachmentSandbox, AttachmentRejected
from log_rotation import RotatingLog
from agy_worker import AgyWorker


@dataclass
class BridgeConfig:
    inbox_dir: Path
    state_root: Path
    agy_path: str
    poll_interval: float = 1.0
    timeout: int = 300


class DiscordReplyProtocol(Protocol):
    async def reply(self, *, chat_id: str, text: str,
                    files: Optional[list] = None,
                    reply_to: Optional[str] = None) -> None: ...


class Bridge:
    CONV_ID_RE = re.compile(r"[Cc]onversation\s+([0-9a-f-]{36})")

    def __init__(self, cfg: BridgeConfig, *, agy, discord: DiscordReplyProtocol):
        self.cfg = cfg
        self.agy = agy
        self.discord = discord
        self.cfg.state_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.conv = ConvMap(cfg.state_root / "conversations" / "map.json")
        self.attachments = AttachmentSandbox(cfg.state_root / "attachments")
        self.log = RotatingLog(cfg.state_root / "logs", prefix="bridge")
        # a2 persona prepend (agy --print 가 GEMINI.md 자동 로드 미지원 — Phase 3 결정)
        persona_path = cfg.state_root.parent / "persona-essence.md"
        self.persona = persona_path.read_text(encoding="utf-8") if persona_path.exists() else ""

    def startup_cleanup(self) -> int:
        return self.log.cleanup_expired()

    async def run_forever(self) -> None:
        removed = self.startup_cleanup()
        start_msg = (
            f"[{time.strftime('%H:%M:%S')}] bridge start, "
            f"cleanup removed {removed} expired log dirs"
        )
        self.log.write(start_msg + "\n")
        print(start_msg, flush=True)
        last_heartbeat = time.time()
        try:
            while True:
                await self._poll_once()
                now = time.time()
                if now - last_heartbeat >= 30:
                    hb = f"[{time.strftime('%H:%M:%S')}] bridge alive — inbox poll ok"
                    self.log.write(hb + "\n")
                    print(hb, flush=True)
                    last_heartbeat = now
                await asyncio.sleep(self.cfg.poll_interval)
        except asyncio.CancelledError:
            self.log.write(f"[{time.strftime('%H:%M:%S')}] bridge stop\n")
            raise

    async def _poll_once(self) -> None:
        if not self.cfg.inbox_dir.exists():
            return
        for path in sorted(self.cfg.inbox_dir.glob("*.md")):
            try:
                await self.process_one(path)
            except Exception as e:
                self.log.write(
                    f"[{time.strftime('%H:%M:%S')}] ERROR {path.name}: {e}\n"
                )

    async def process_one(self, path: Path) -> None:
        data = json.loads(path.read_text())
        chat_id = data["chat_id"]
        message_id = data.get("message_id", "")

        # per-channel flock — race 차단 (Codex review item 5)
        lock_dir = self.cfg.state_root / "conversations"
        lock_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        lock_path = lock_dir / f"{_safe_channel(chat_id)}.lock"
        with open(lock_path, "w") as lock_f:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
            try:
                await self._dispatch(chat_id, message_id, data)
                path.unlink()
            finally:
                fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)

    def _tmux_inject(self, text: str) -> None:
        """Discord 메시지·응답을 agy TUI pane 으로 시각 주입 (사용자 UX — the codex-side bridge pattern mirror).

        AGY_TUI_PANE env 지정 시만 동작 (launch.sh 가 split-window 후 설정).
        prompt 누적 방지: C-u 로 prompt buffer 클리어 후 literal text 주입 (Enter 미발신 — agy 가 처리 ❌, Y-3 subprocess 가 실 응답).
        """
        target = os.environ.get("AGY_TUI_PANE", "")
        if not target:
            return
        one_line = text.replace("\n", " ").replace("\r", " ")[:300]
        try:
            import subprocess
            subprocess.run(["tmux", "send-keys", "-t", target, "C-u"], check=False, timeout=2)
            subprocess.run(["tmux", "send-keys", "-t", target, "-l", one_line], check=False, timeout=2)
        except Exception as e:
            self.log.write(f"[tmux-inject] failed: {e}\n")

    async def _dispatch(self, chat_id: str, message_id: str, data: dict) -> None:
        content = data.get("content", "")
        # 시각 print — bridge daemon pane (codex bridge bot.py `[MSG]` 패턴 mirror)
        author = data.get("author", "?")
        guild = data.get("guild", "dm")
        inbox_line = f"[{time.strftime('%H:%M:%S')}] [INBOX] ch={chat_id} msg={message_id} guild={guild} user={author} content={content[:120]!r}"
        self.log.write(inbox_line + "\n")
        print(inbox_line, flush=True)
        # agy TUI pane 시각 주입 — 사용자 UX (Discord 입력이 TUI 에 표시)
        self._tmux_inject(f"[Discord] {content[:200]}")

        # 첨부 처리
        add_dirs = []
        for att in data.get("attachments", []):
            try:
                stored = self.attachments.store(
                    guild=data.get("guild", "dm"),
                    channel=chat_id, message=message_id,
                    filename=att["filename"],
                    content=att["content_bytes"],
                )
                add_dirs.append(str(stored.parent))
            except AttachmentRejected as e:
                await self.discord.reply(
                    chat_id=chat_id, reply_to=message_id,
                    text=f"첨부 거부 — {e}",
                )
                return

        # 모드 라우팅
        if content.strip().startswith("/agy-asset"):
            await self._dispatch_y2(chat_id, message_id, content, add_dirs)
            return

        # per-channel cwd (last_conversations.json 의 path key 분리 → channel 별 conv)
        safe = _safe_channel(chat_id)
        channel_cwd = self.cfg.state_root / "channels" / safe / "cwd"
        channel_cwd.mkdir(parents=True, exist_ok=True, mode=0o700)

        # a2 persona prepend (Phase 3 결론: agy --print 가 GEMINI.md 자동 로드 미지원)
        full_prompt = f"{self.persona}\n\n---\n\n{content}" if self.persona else content

        # Y-3 단발 기본 — trace print 추가 (사용자 진단)
        conv_id = self.conv.get(chat_id)
        trace = f"[{time.strftime('%H:%M:%S')}] _dispatch chat={chat_id} msg={message_id} cwd={channel_cwd} prompt_len={len(full_prompt)} conv_id={conv_id}"
        self.log.write(trace + "\n")
        print(trace, flush=True)
        try:
            result = await self.agy.run_y3(
                prompt=full_prompt, conversation_id=conv_id, add_dirs=add_dirs,
                cwd=channel_cwd,
            )
            done = f"[{time.strftime('%H:%M:%S')}] agy.run_y3 done exit={result.exit_code} stdout_len={len(result.stdout)} stderr_len={len(result.stderr)}"
            self.log.write(done + "\n")
            print(done, flush=True)
        except Exception as e:
            err = f"[{time.strftime('%H:%M:%S')}] agy.run_y3 ERROR: {type(e).__name__}: {e}"
            self.log.write(err + "\n")
            print(err, flush=True)
            raise
        new_conv = self._extract_conv_id(result.stderr) or self._extract_conv_id(result.stdout)
        if new_conv:
            self.conv.set(chat_id, new_conv)

        reply_text = result.stdout or f"(empty agy response, exit={result.exit_code})"
        out_line = f"[{time.strftime('%H:%M:%S')}] [OUTBOX] ch={chat_id} reply_len={len(reply_text)} preview={reply_text[:120]!r}"
        self.log.write(out_line + "\n")
        print(out_line, flush=True)
        # agy TUI pane 응답 시각 주입 (실 응답은 Discord reply 가 발신)
        self._tmux_inject(f"[reply] {reply_text[:200]}")
        await self.discord.reply(
            chat_id=chat_id, reply_to=message_id, text=reply_text,
        )

    async def _dispatch_y2(self, chat_id: str, message_id: str,
                           content: str, add_dirs: list) -> None:
        prompt = content.strip()
        if prompt.startswith("/agy-asset"):
            prompt = prompt[len("/agy-asset"):].strip()
        conv_id = self.conv.get(chat_id)
        # Asset output dir — channel-scoped (not conv-scoped) so first /agy-asset
        # request also has a stable target before conv_id exists. agy receives
        # this dir via --add-dir so it knows where to write generated assets.
        safe = _safe_channel(chat_id)
        asset_dir = self.cfg.state_root / "assets" / safe
        asset_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Snapshot existing files for delta detection (avoids re-attaching old assets).
        existing_realpaths = {p.resolve() for p in asset_dir.iterdir() if p.exists()}
        session = await self.agy.start_y2(
            conversation_id=conv_id,
            add_dirs=list(add_dirs) + [str(asset_dir)],
        )
        try:
            out = await session.send(prompt)
            await self.discord.reply(
                chat_id=chat_id, reply_to=message_id, text=out,
            )
            # Delta detection — only attach NEW regular files (skip symlinks for safety).
            new_files = []
            for p in asset_dir.iterdir():
                try:
                    if not p.is_file():
                        continue
                    if p.is_symlink():
                        continue  # symlink target escape mitigation
                    if p.resolve() in existing_realpaths:
                        continue  # pre-existing
                    new_files.append(p)
                except OSError:
                    continue
            if new_files:
                await self.discord.reply(
                    chat_id=chat_id, reply_to=message_id,
                    text="(asset 생성)",
                    files=[str(p) for p in new_files],
                )
        finally:
            await session.close()

    @classmethod
    def _extract_conv_id(cls, text: str) -> Optional[str]:
        m = cls.CONV_ID_RE.search(text)
        return m.group(1) if m else None


def _safe_channel(channel_id: str) -> str:
    """flock/asset path 용 — alnum + - _ 만."""
    return "".join(c for c in channel_id if c.isalnum() or c in ("-", "_"))[:64] or "_"


class _NullDiscord:
    """gateway 모드에서 Bridge init 위해 — AgyDiscordBot 가 즉시 swap."""
    async def reply(self, **kw) -> None:
        pass


def main() -> None:
    """CLI entry — Discord gateway 모드 (default, token 있을 때) 또는 inbox polling (test).

    launch.sh 가 `python3 scripts/bridge.py` 로 호출.
    USE_DISCORD_GATEWAY=0 환경변수로 inbox polling 강제 가능 (smoke test).
    """
    import sys
    bot_name_default = os.environ.get("BOT_NAME", "mybot")
    channel_dir = Path(
        os.environ.get("DISCORD_STATE_DIR",
                       os.path.expanduser(f"~/.claude/channels/discord-{bot_name_default}"))
    )
    inbox = channel_dir / "inbox"
    state = Path(__file__).resolve().parent.parent / "state"
    agy_path = os.environ.get("AGY_PATH", os.path.expanduser("~/.local/bin/agy"))
    cfg = BridgeConfig(inbox_dir=inbox, state_root=state, agy_path=agy_path)

    sys.path.insert(0, str(Path(__file__).parent))
    worker = AgyWorker(agy_path=agy_path, state_root=state)

    token = os.environ.get("DISCORD_BOT_TOKEN", "")
    use_gateway = bool(token) and os.environ.get("USE_DISCORD_GATEWAY", "1") != "0"

    if use_gateway:
        # Discord gateway 모드 (live) — Codex bridge spec §10 Phase 2 integration
        bridge = Bridge(cfg, agy=worker, discord=_NullDiscord())
        from discord_client import AgyDiscordBot, DedupStore
        dedup = DedupStore(state / "dedup.json")
        bot_info = channel_dir / "bot-info.json"
        bot = AgyDiscordBot(bridge=bridge, dedup=dedup, bot_info_path=bot_info)
        print(f"[agy-bridge] start (Discord gateway) — channel={channel_dir.name} agy={agy_path}",
              flush=True)
        try:
            bot.run(token)
        except KeyboardInterrupt:
            print("[agy-bridge] interrupted", flush=True)
    else:
        # inbox polling 모드 (smoke test, gateway 없이 검증)
        from discord_outbox import OutboxDiscord
        outbox = channel_dir / "outbox"
        discord = OutboxDiscord(outbox)
        bridge = Bridge(cfg, agy=worker, discord=discord)
        print(f"[agy-bridge] start (inbox polling) — inbox={inbox} outbox={outbox} agy={agy_path}",
              flush=True)
        try:
            asyncio.run(bridge.run_forever())
        except KeyboardInterrupt:
            print("[agy-bridge] interrupted", flush=True)


if __name__ == "__main__":
    main()
