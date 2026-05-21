"""Discord reply 어댑터 — outbox 폴더에 reply 페이로드 적재.

분리 정신: bridge 가 직접 HTTP 안 침. Discord plugin (또는 별도 sender) 가
outbox 폴링해 발신. 토큰 격리 + 단일 책임.

Codex code-review 항목 7 (rotation·DoS) mitigation 일부 — outbox 도 별도 cleanup
필요 (Discord plugin 이 발신 후 unlink 가 표준).
"""
import json
import time
from pathlib import Path
from typing import Optional


class OutboxDiscord:
    def __init__(self, outbox_dir: Path):
        self.outbox = Path(outbox_dir)
        self.outbox.mkdir(parents=True, exist_ok=True, mode=0o700)

    async def reply(self, *, chat_id: str, text: str,
                    files: Optional[list] = None,
                    reply_to: Optional[str] = None) -> None:
        payload = {
            "chat_id": chat_id, "text": text,
            "reply_to": reply_to, "files": files or [],
        }
        name = f"{int(time.time() * 1000)}-{_safe(chat_id)}.json"
        out = self.outbox / name
        out.write_text(json.dumps(payload, ensure_ascii=False))
        out.chmod(0o600)


def _safe(s: str) -> str:
    return "".join(c for c in s if c.isalnum() or c in ("-", "_"))[:64] or "_"
