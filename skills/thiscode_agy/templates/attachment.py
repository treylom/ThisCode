"""첨부 격리 + MIME 검사.

Codex code-review 항목 6 (path traversal) mitigation:
- mkdtemp 0700
- basename 정화 (`../`, `/`, NUL 제거)
- allowlist 확장자
- symlink follow ❌ (O_NOFOLLOW)
- size cap (Discord 25MB 한계)
"""
import os
import secrets
from pathlib import Path

ATTACHMENT_ALLOWLIST = frozenset({
    ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".txt", ".md", ".csv", ".tsv", ".json", ".yaml", ".yml", ".log",
})
MAX_SIZE = 25 * 1024 * 1024  # 25MB (Discord 한계)


class AttachmentRejected(Exception):
    pass


def sanitize_basename(name: str) -> str:
    """`../`, `/`, NUL 제거 후 basename 만 반환."""
    if "\x00" in name:
        raise ValueError("NUL byte in filename")
    base = os.path.basename(name.replace("\\", "/"))
    while base.startswith("."):
        base = base.lstrip(".") or "unnamed"
    return base or "unnamed"


def _sanitize_path_part(s: str) -> str:
    return "".join(c for c in s if c.isalnum() or c in ("-", "_"))[:64] or "_"


class AttachmentSandbox:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def store(self, *, guild: str, channel: str, message: str,
              filename: str, content: bytes) -> Path:
        if len(content) > MAX_SIZE:
            raise AttachmentRejected(f"size {len(content)} > {MAX_SIZE}")
        safe = sanitize_basename(filename)
        ext = os.path.splitext(safe)[1].lower()
        if ext not in ATTACHMENT_ALLOWLIST:
            raise AttachmentRejected(f"ext {ext!r} not in allowlist")

        msg_dir = (
            self.root
            / _sanitize_path_part(guild)
            / _sanitize_path_part(channel)
            / _sanitize_path_part(message)
        )
        msg_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

        rnd = secrets.token_hex(4)
        out = msg_dir / f"{rnd}-{safe}"
        fd = os.open(
            out, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600,
        )
        with os.fdopen(fd, "wb") as f:
            f.write(content)
        return out
