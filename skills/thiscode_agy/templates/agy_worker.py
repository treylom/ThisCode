"""agy CLI subprocess wrapper.

Y-3 = 단발 --print + --conversation
Y-2 = PTY 세션 유지 (이미지 반복 수정 / 메모리 누적)

Codex code-review mitigation:
- 항목 4 stdout injection: argv array, shell=False, control char strip
- 항목 5 race: per-channel WD (caller cwd 지정)
- unsafe-mode 게이트: AGY_UNSAFE=1 env flag → --dangerously-skip-permissions
- 기본 --sandbox
"""
import asyncio
import fcntl
import os
import pty
import signal
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


class AgyTimeout(Exception):
    pass


@dataclass
class AgyResult:
    stdout: str
    stderr: str
    exit_code: int


class AgyWorker:
    def __init__(self, *, agy_path: str, state_root: Path, timeout: int = 300):
        if "/" not in agy_path:
            raise ValueError(f"agy_path must be absolute, got {agy_path!r}")
        self.agy_path = agy_path
        self.state_root = Path(state_root)
        self.timeout = timeout
        self.unsafe = os.environ.get("AGY_UNSAFE") == "1"

    def _build_argv(self, *, prompt: str, conversation_id: Optional[str],
                    add_dirs: List[str]) -> List[str]:
        argv = [self.agy_path, "--print", prompt]
        if conversation_id:
            argv += ["--conversation", conversation_id]
        for d in add_dirs:
            argv += ["--add-dir", d]
        if self.unsafe:
            argv.append("--dangerously-skip-permissions")
        else:
            argv.append("--sandbox")
        return argv

    @staticmethod
    def _clean_output(b: bytes) -> str:
        """bytes → UTF-8 (errors=replace) + control char strip.

        Codex code-review 항목 4 mitigation — ANSI / control char 제거.
        """
        text = b.decode("utf-8", errors="replace")
        return "".join(c for c in text if c.isprintable() or c in "\n\t ")

    async def run_y3(self, *, prompt: str, conversation_id: Optional[str],
                     add_dirs: List[str], cwd: Optional[Path] = None) -> AgyResult:
        argv = self._build_argv(
            prompt=prompt, conversation_id=conversation_id, add_dirs=add_dirs,
        )
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd) if cwd else None,
            start_new_session=True,  # killpg 위한 process group
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(), timeout=self.timeout,
            )
        except asyncio.TimeoutError:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                await asyncio.sleep(2)
                if proc.returncode is None:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
            raise AgyTimeout(f"agy timeout after {self.timeout}s")

        return AgyResult(
            stdout=self._clean_output(stdout_b),
            stderr=self._clean_output(stderr_b),
            exit_code=proc.returncode or 0,
        )

    async def start_y2(self, *, conversation_id: Optional[str],
                       add_dirs: List[str]) -> "AgyPTYSession":
        """Y-2 PTY 세션 — 이미지 반복 수정·메모리 누적용.

        bridge 가 한 conversation 동안 여러 prompt 보낼 수 있게 stdin 열어둠.
        """
        argv = [self.agy_path, "--prompt-interactive", ""]
        if conversation_id:
            argv += ["--conversation", conversation_id]
        for d in add_dirs:
            argv += ["--add-dir", d]
        argv.append(
            "--dangerously-skip-permissions" if self.unsafe else "--sandbox"
        )

        master_fd, slave_fd = pty.openpty()
        flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
            start_new_session=True,
        )
        os.close(slave_fd)
        return AgyPTYSession(master_fd, proc)


class AgyPTYSession:
    """PTY 세션 wrapper — send 후 read_timeout 동안 buffer drain."""

    def __init__(self, master_fd: int, proc: asyncio.subprocess.Process):
        self.master_fd = master_fd
        self.proc = proc

    async def send(self, prompt: str, *, read_timeout: float = 3.0) -> str:
        os.write(self.master_fd, (prompt + "\n").encode())
        await asyncio.sleep(0.2)  # initial wait — child read + echo
        buf = bytearray()
        loop = asyncio.get_event_loop()
        deadline = loop.time() + read_timeout
        last_chunk_at = loop.time()
        while loop.time() < deadline:
            try:
                chunk = os.read(self.master_fd, 4096)
                if not chunk:
                    break
                buf.extend(chunk)
                last_chunk_at = loop.time()
            except BlockingIOError:
                # 마지막 chunk 후 0.5s idle = response 종료 휴리스틱
                if loop.time() - last_chunk_at > 0.5 and buf:
                    break
                await asyncio.sleep(0.05)
        return AgyWorker._clean_output(bytes(buf))

    async def close(self) -> None:
        try:
            os.close(self.master_fd)
        except OSError:
            pass
        try:
            self.proc.terminate()
            await asyncio.wait_for(self.proc.wait(), timeout=5)
        except (asyncio.TimeoutError, ProcessLookupError):
            try:
                self.proc.kill()
            except ProcessLookupError:
                pass
