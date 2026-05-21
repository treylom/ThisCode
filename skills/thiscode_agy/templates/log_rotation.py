"""Per-day + size-capped + TTL log rotation.

Codex code-review 항목 7 (rotation·DoS) mitigation.
Codex app-server log 가 258MB 까지 누적된 회귀 case 기반.
"""
import os
import shutil
import time
from datetime import datetime
from pathlib import Path


class RotatingLog:
    def __init__(self, root: Path, *, prefix: str,
                 max_size: int = 50 * 1024 * 1024,
                 ttl_days: int = 7):
        self.root = Path(root)
        self.prefix = prefix
        self.max_size = max_size
        self.ttl_days = ttl_days
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def _today_dir(self) -> Path:
        d = self.root / datetime.now().strftime("%Y-%m-%d")
        d.mkdir(parents=True, exist_ok=True, mode=0o700)
        return d

    def _current_file(self) -> Path:
        d = self._today_dir()
        base = d / f"{self.prefix}.log"
        if not base.exists():
            base.touch(mode=0o600)
            os.chmod(base, 0o600)
        return base

    def write(self, msg: str) -> None:
        p = self._current_file()
        with open(p, "a") as f:
            f.write(msg)
        # post-write rotate — cap 넘으면 즉시 회전
        if p.stat().st_size >= self.max_size:
            ts = int(time.time() * 1000)
            p.rename(p.parent / f"{self.prefix}.{ts}.log")

    def cleanup_expired(self) -> int:
        cutoff = time.time() - self.ttl_days * 86400
        removed = 0
        for child in self.root.iterdir():
            if not child.is_dir():
                continue
            if child.stat().st_mtime < cutoff:
                shutil.rmtree(child)
                removed += 1
        return removed
