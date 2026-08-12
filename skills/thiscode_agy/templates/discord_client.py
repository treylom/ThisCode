"""Discord gateway client — AgyDiscordBot + DiscordReplyAdapter.

Codex bridge spec 06-codex-bridge-pattern.md §1.1, §3, §5 mirror.
Codex bridge bot.py pattern: bridge.py 가 inbox 폴링하는 대신
discord.py 가 on_message → queue → bridge._dispatch.
"""
import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any

import discord


@dataclass
class BridgeMessage:
    chat_id: str
    message_id: str
    guild_id: Optional[str]
    channel_id: str
    author_id: str
    content: str
    attachments: list = field(default_factory=list)
    discord_message: Optional[Any] = None


class DiscordReplyAdapter:
    """spec §5 — message.reply() 우선, id-only fallback 은 fetch_channel/fetch_message."""

    def __init__(self, client: discord.Client):
        self.client = client

    async def reply(self, *, chat_id: str, text: str,
                    files: Optional[list] = None,
                    reply_to: Optional[str] = None,
                    discord_message: Optional[discord.Message] = None) -> None:
        discord_files = [discord.File(p) for p in (files or [])]
        if discord_message is not None:
            await discord_message.reply(text, files=discord_files, mention_author=False)
            return
        channel = await self.client.fetch_channel(int(chat_id))
        if reply_to:
            target = await channel.fetch_message(int(reply_to))
            await target.reply(text, files=discord_files, mention_author=False)
        else:
            await channel.send(text, files=discord_files)


class DedupStore:
    """spec §3 — message_id dedup, 0600 atomic locked."""

    def __init__(self, path: Path, max_entries: int = 5000, ttl: int = 86400):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.max_entries = max_entries
        self.ttl = ttl
        self._lock = asyncio.Lock()

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _atomic_write(self, state: dict) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.path)

    def _gc(self, state: dict) -> dict:
        now = int(time.time())
        kept = {k: v for k, v in state.items() if (now - v.get("ts", 0)) < self.ttl}
        if len(kept) > self.max_entries:
            items = sorted(kept.items(), key=lambda kv: kv[1].get("ts", 0))
            kept = dict(items[-self.max_entries:])
        return kept

    async def seen_or_add(self, message_id: str, channel_id: str) -> bool:
        async with self._lock:
            state = self._load()
            if message_id in state:
                return True
            state[message_id] = {"ts": int(time.time()), "ch": channel_id}
            state = self._gc(state)
            self._atomic_write(state)
            return False


class AgyDiscordBot:
    """discord.py gateway client — on_message → BridgeMessage → queue → bridge worker."""

    def __init__(self, *, bridge, reply_adapter: Optional[DiscordReplyAdapter] = None,
                 dedup: Optional[DedupStore] = None,
                 bot_info_path: Optional[Path] = None):
        self.bridge = bridge
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True  # requires "Server Members Intent" ON in the Developer Portal (else PrivilegedIntentsRequired at startup)
        self.client = discord.Client(intents=intents)
        self.reply_adapter = reply_adapter or DiscordReplyAdapter(self.client)
        self.queue: asyncio.Queue[BridgeMessage] = asyncio.Queue()
        self.dedup = dedup
        self.bot_info_path = bot_info_path
        # Codex review hardening: class var → instance (multi-instance 공유 차단 + reconnect 중복 worker guard)
        self._msg_lookup: dict = {}
        self._worker_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._channel_locks: dict = {}  # gateway 경로 per-channel asyncio.Lock
        self._register_events()
        # bridge 가 outbox 가 아닌 DiscordReplyAdapter 통해 reply 하도록 swap
        self.bridge.discord = self._BridgeAdapter(self.reply_adapter,
                                                  self._discord_message_map)

    def _discord_message_map(self):
        return self._msg_lookup

    class _BridgeAdapter:
        """bridge.Bridge.discord 가 reply 호출하면 → DiscordReplyAdapter 위임.

        spec §5 — message.reply() 우선. id-only fallback.
        """
        def __init__(self, adapter: DiscordReplyAdapter, msg_map_fn):
            self.adapter = adapter
            self._msg_map_fn = msg_map_fn

        async def reply(self, *, chat_id: str, text: str,
                        files=None, reply_to: Optional[str] = None) -> None:
            msg_map = self._msg_map_fn()
            dmsg = msg_map.get(reply_to) if reply_to else None
            await self.adapter.reply(
                chat_id=chat_id, text=text, files=files,
                reply_to=reply_to, discord_message=dmsg,
            )

    def _register_events(self) -> None:
        @self.client.event
        async def on_ready():
            user = self.client.user
            if self.bot_info_path is not None:
                info = {
                    "user_id": str(user.id) if user else None,
                    "name": str(user) if user else None,
                    "ready_at": int(time.time()),
                }
                self.bot_info_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                self.bot_info_path.write_text(
                    json.dumps(info, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                os.chmod(self.bot_info_path, 0o600)
            ready_msg = f"[{time.strftime('%H:%M:%S')}] gateway READY — {user} (user_id={user.id if user else '?'})"
            self.bridge.log.write(ready_msg + "\n")
            print(ready_msg, flush=True)
            # Codex review hardening: reconnect 중복 worker guard
            if self._worker_task is None or self._worker_task.done():
                self._worker_task = asyncio.create_task(self._worker())
            if self._heartbeat_task is None or self._heartbeat_task.done():
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        @self.client.event
        async def on_message(msg: discord.Message):
            await self._handle_message(msg)

    async def _heartbeat_loop(self) -> None:
        """gateway 모드 heartbeat — tmux pane 의 사용자가 daemon alive 확인 (silent loop 차단)."""
        while True:
            await asyncio.sleep(30)
            try:
                bot_name = os.environ.get("BOT_NAME", "mybot")
                hb = (
                    f"[{time.strftime('%H:%M:%S')}] {bot_name} alive — "
                    f"queue={self.queue.qsize()} channels={len(self._channel_locks)}"
                )
                self.bridge.log.write(hb + "\n")
                print(hb, flush=True)
            except Exception:
                pass

    async def _handle_message(self, msg: discord.Message) -> None:
        # raw debug print — 사용자가 daemon pane 에서 모든 inbound 메시지 가시 (the codex-side bridge pattern mirror)
        is_self = (self.client.user is not None and msg.author.id == self.client.user.id)
        is_dm = isinstance(msg.channel, discord.DMChannel)
        is_mentioned = (self.client.user is not None and self.client.user in msg.mentions)
        raw_line = (
            f"[{time.strftime('%H:%M:%S')}] [RAW] ch={msg.channel.id} dm={is_dm} "
            f"author={msg.author} ({msg.author.id}) bot={msg.author.bot} "
            f"self={is_self} mentioned={is_mentioned} "
            f"mentions={[u.id for u in msg.mentions]} "
            f"content={msg.content[:80]!r}"
        )
        try:
            self.bridge.log.write(raw_line + "\n")
        except Exception:
            pass
        print(raw_line, flush=True)
        # spec §3 — self / mention / dedup filter
        if is_self:
            return
        if not is_dm and not is_mentioned:
            return
        if self.dedup is not None:
            seen = await self.dedup.seen_or_add(str(msg.id), str(msg.channel.id))
            if seen:
                return

        attachments = []
        for att in msg.attachments:
            try:
                raw = await att.read()
                attachments.append({
                    "filename": att.filename,
                    "content_type": att.content_type,
                    "content_bytes": raw,
                })
            except Exception:
                continue

        bridge_msg = BridgeMessage(
            chat_id=str(msg.channel.id),
            message_id=str(msg.id),
            guild_id=str(msg.guild.id) if msg.guild else None,
            channel_id=str(msg.channel.id),
            author_id=str(msg.author.id),
            content=msg.content or "",
            attachments=attachments,
            discord_message=msg,
        )
        self._msg_lookup[bridge_msg.message_id] = msg
        await self.queue.put(bridge_msg)

    async def _worker(self) -> None:
        while True:
            bridge_msg: BridgeMessage = await self.queue.get()
            try:
                # Codex review hardening: gateway 경로 per-channel lock
                # (process_one 의 fcntl.flock 은 inbox 경로 전용, gateway 는 별도 보호)
                lock = self._channel_locks.setdefault(
                    bridge_msg.chat_id, asyncio.Lock()
                )
                async with lock:
                    data = {
                        "chat_id": bridge_msg.chat_id,
                        "message_id": bridge_msg.message_id,
                        "guild": bridge_msg.guild_id or "dm",
                        "content": bridge_msg.content,
                        "attachments": bridge_msg.attachments,
                    }
                    # bridge._dispatch 가 처리 (per-channel cwd + persona prepend + agy)
                    await self.bridge._dispatch(
                        bridge_msg.chat_id, bridge_msg.message_id, data,
                    )
            except Exception as e:
                self.bridge.log.write(
                    f"[discord-worker] ERROR msg={bridge_msg.message_id}: {e}\n"
                )
                try:
                    await self.reply_adapter.reply(
                        chat_id=bridge_msg.chat_id, text=f"오류: {e}",
                        reply_to=bridge_msg.message_id,
                        discord_message=bridge_msg.discord_message,
                    )
                except Exception:
                    pass
            finally:
                self.queue.task_done()
                # 메모리 누수 차단 — 처리 끝나면 lookup 제거
                self._msg_lookup.pop(bridge_msg.message_id, None)

    def run(self, token: str) -> None:
        self.client.run(token, log_handler=None)
