"""Per-channel conversation_id map with flock + atomic write.

Bridge 가 agy 전역 last_conversations.json 대신 자체 SoT 로 사용.
Codex code-review 항목 1 (atomic write) + 항목 5 (race) mitigation.
"""
import fcntl
import json
import os
import tempfile
from pathlib import Path
from typing import Optional


class ConvMap:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not self.path.exists():
            self._atomic_write({})

    def _read(self) -> dict:
        try:
            with open(self.path, "r") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    return json.load(f)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _atomic_write(self, data: dict) -> None:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", dir=self.path.parent, delete=False,
            prefix=".conv_map_", suffix=".tmp",
        )
        try:
            json.dump(data, tmp)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp.close()
            os.chmod(tmp.name, 0o600)
            os.replace(tmp.name, self.path)
        except Exception:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
            raise

    def get(self, channel_id: str) -> Optional[str]:
        return self._read().get(channel_id)

    def set(self, channel_id: str, conv_id: str) -> None:
        # exclusive write lock via sibling lockfile
        lock_path = self.path.with_suffix(".lock")
        with open(lock_path, "w") as lock_f:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
            try:
                data = self._read()
                data[channel_id] = conv_id
                self._atomic_write(data)
            finally:
                fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)
