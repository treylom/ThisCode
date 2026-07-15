"""External note-embedding worker with coalescing and atomic generation promotion.

Phase A only: this module provides the worker, verifier, queue and activation
contract. Launchd wiring and migration of the live index to ``current`` are a
separate cutover gate.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Callable

import numpy as np

import embedding_index

PROJECT_DIR = Path(__file__).resolve().parents[3]
DEFAULT_ROOT = Path(os.environ.get(
    "GRAPHRAG_GENERATION_ROOT",
    str(PROJECT_DIR / ".team-os/graphrag/index-generations"),
))
DEFAULT_VAULT_PATH = Path(os.environ.get(
    "GRAPHRAG_VAULT_PATH",
    "<vault>",
))
DEFAULT_DB_PATH = Path(os.environ.get(
    "GRAPHRAG_DB_PATH",
    str(PROJECT_DIR / ".team-os/graphrag/index/vault_graph.db"),
))
DEFAULT_ACTIVATE_URL = os.environ.get(
    "GRAPHRAG_ACTIVATE_URL",
    "http://127.0.0.1:8400/api/index/activate",
)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    os.replace(temp, path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_pair(
    directory: Path,
    *,
    vectors_name: str,
    meta_name: str,
    entries_key: str,
    expected_model: str,
    required: bool,
) -> dict[str, Any] | None:
    vectors_path = directory / vectors_name
    meta_path = directory / meta_name
    present = (vectors_path.exists(), meta_path.exists())
    if not any(present):
        if required:
            raise ValueError(f"required index pair missing: {vectors_name}, {meta_name}")
        return None
    if not all(present):
        raise ValueError(f"partial index pair: {vectors_name}, {meta_name}")

    raw_meta = _read_json(meta_path)
    if not isinstance(raw_meta, dict):
        raise ValueError(f"{meta_name} must be an object")
    if raw_meta.get("model") != expected_model:
        raise ValueError(
            f"model mismatch in {meta_name}: {raw_meta.get('model')!r} != {expected_model!r}"
        )
    entries = raw_meta.get(entries_key)
    if not isinstance(entries, list):
        raise ValueError(f"{meta_name}.{entries_key} must be a list")

    vectors = np.load(vectors_path, allow_pickle=False)
    if vectors.ndim != 2:
        raise ValueError(f"{vectors_name} must be a 2D matrix")
    if vectors.shape[0] != len(entries):
        raise ValueError(
            f"row count mismatch for {vectors_name}: {vectors.shape[0]} vectors != {len(entries)} metadata rows"
        )
    if vectors.size and not np.isfinite(vectors).all():
        raise ValueError(f"{vectors_name} contains non-finite values")

    return {
        "vectors": vectors.shape[0],
        "dimensions": vectors.shape[1] if vectors.ndim == 2 else 0,
        "vectors_sha256": _sha256(vectors_path),
        "meta_sha256": _sha256(meta_path),
    }


def verify_generation(directory: Path | str, *, expected_model: str) -> dict[str, Any]:
    """Reject partial, model-mismatched, shape-mismatched or non-finite generations."""
    generation = Path(directory)
    if not generation.is_dir():
        raise ValueError(f"generation directory missing: {generation}")
    note = _validate_pair(
        generation,
        vectors_name="embeddings.npy",
        meta_name="embedding_meta.json",
        entries_key="notes",
        expected_model=expected_model,
        required=True,
    )
    entity = _validate_pair(
        generation,
        vectors_name=embedding_index.ENTITY_EMBEDDINGS_FILE,
        meta_name=embedding_index.ENTITY_META_FILE,
        entries_key="entities",
        expected_model=expected_model,
        required=False,
    )
    return {"model": expected_model, "note": note, "entity": entity}


def prepare_staging_generation(root: Path | str, generation_name: str) -> Path:
    """Clone the current generation into a private staging directory."""
    root_path = Path(root)
    generations = root_path / "generations"
    generations.mkdir(parents=True, exist_ok=True)
    staging = generations / f".{generation_name}.staging"
    if staging.exists():
        raise FileExistsError(f"staging generation already exists: {staging}")
    current = root_path / "current"
    if current.exists():
        shutil.copytree(current.resolve(), staging, copy_function=shutil.copy2)
    else:
        staging.mkdir()
    return staging


def promote_generation(
    generation: Path | str,
    *,
    current_link: Path | str,
    expected_model: str,
) -> dict[str, Any]:
    """Verify first, then atomically replace the ``current`` symlink."""
    generation_path = Path(generation).resolve()
    current = Path(current_link)
    verification = verify_generation(generation_path, expected_model=expected_model)
    current.parent.mkdir(parents=True, exist_ok=True)
    # macOS maps /var -> /private/var. Resolve both sides before computing the
    # relative target or the symlink can accidentally point at /private/private.
    relative_target = os.path.relpath(generation_path, current.parent.resolve())
    temporary_link = current.with_name(f".{current.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    temporary_link.symlink_to(relative_target, target_is_directory=True)
    try:
        os.replace(temporary_link, current)
    finally:
        temporary_link.unlink(missing_ok=True)
    return verification


class PendingQueue:
    """One-file queue: N requests collapse to one pending follow-up."""

    def __init__(self, state_dir: Path | str):
        self.state_dir = Path(state_dir)
        self.pending_path = self.state_dir / "pending.json"
        self.lock_path = self.state_dir / "worker.lock"

    def request(self, payload: dict[str, Any] | None = None) -> None:
        already_pending = self.pending_path.exists()
        request_payload = dict(payload or {})
        requested_at = time.time()
        request_payload["requested_at_epoch"] = requested_at
        _atomic_write_json(self.pending_path, request_payload)
        try:
            status = _read_json(self.state_dir / "status.json")
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            status = {}
        if not isinstance(status, dict):
            status = {}
        coalesced = int(status.get("pending_coalesced", 0))
        _write_worker_status(
            self.state_dir,
            phase="queued" if not already_pending else status.get("phase", "queued"),
            queued_at_epoch=requested_at,
            pending_coalesced=coalesced + int(already_pending),
        )

    def _consume(self) -> dict[str, Any] | None:
        try:
            payload = _read_json(self.pending_path)
        except FileNotFoundError:
            return None
        self.pending_path.unlink(missing_ok=True)
        return payload if isinstance(payload, dict) else {}

    def drain(
        self,
        run_once: Callable[[dict[str, Any]], None],
        *,
        max_jobs: int = 2,
    ) -> int:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+") as lock_handle:
            try:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return 0
            completed = 0
            while completed < max_jobs:
                payload = self._consume()
                if payload is None:
                    break
                run_once(payload)
                completed += 1
            return completed


def _write_worker_status(root: Path, **changes: Any) -> None:
    status_path = root / "status.json"
    try:
        current = _read_json(status_path)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        current = {}
    if not isinstance(current, dict):
        current = {}
    current.update(changes)
    _atomic_write_json(status_path, current)


def _note_mtimes(directory: Path) -> dict[str, float]:
    try:
        payload = _read_json(directory / "embedding_meta.json")
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    notes = payload.get("notes", []) if isinstance(payload, dict) else []
    return {
        str(note.get("note_path", "")): float(note.get("mtime", 0.0))
        for note in notes
        if isinstance(note, dict) and note.get("note_path")
    }


def _changed_note_count(before: dict[str, float], after: dict[str, float]) -> int:
    paths = set(before) | set(after)
    return sum(before.get(path) != after.get(path) for path in paths)


def notify_activation(url: str = DEFAULT_ACTIVATE_URL, *, timeout: float = 15.0) -> dict[str, Any]:
    request = urllib.request.Request(url, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def build_and_promote(
    *,
    root: Path,
    vault_path: Path,
    db_path: Path,
    activate_url: str | None,
) -> dict[str, Any]:
    generation_name = time.strftime("gen-%Y%m%dT%H%M%S") + f"-{uuid.uuid4().hex[:8]}"
    started_at = time.time()
    _write_worker_status(
        root,
        phase="cloning",
        job_id=generation_name,
        generation=generation_name,
        pid=os.getpid(),
        started_at_epoch=started_at,
        heartbeat_at_epoch=started_at,
        changed_notes=None,
        last_error=None,
    )
    try:
        staging = prepare_staging_generation(root, generation_name)
        final = root / "generations" / generation_name
        before_mtimes = _note_mtimes(staging)
        _write_worker_status(
            root,
            phase="encoding",
            heartbeat_at_epoch=time.time(),
        )
        os.environ["GRAPHRAG_EMBED_DEVICE"] = "cpu"
        os.environ.setdefault("GRAPHRAG_EMBED_BATCH", "8")
        embedding_index.build_index(
            vault_path=str(vault_path),
            db_path=str(db_path),
            output_dir=str(staging),
        )
        after_mtimes = _note_mtimes(staging)
        changed_notes = _changed_note_count(before_mtimes, after_mtimes)
        _write_worker_status(
            root,
            phase="verifying",
            heartbeat_at_epoch=time.time(),
            changed_notes=changed_notes,
        )
        verification = verify_generation(staging, expected_model=embedding_index.MODEL_NAME)
        os.replace(staging, final)
        _write_worker_status(root, phase="promoting", heartbeat_at_epoch=time.time())
        promote_generation(
            final,
            current_link=root / "current",
            expected_model=embedding_index.MODEL_NAME,
        )
        activation = None
        if activate_url:
            _write_worker_status(root, phase="activating", heartbeat_at_epoch=time.time())
            activation = notify_activation(activate_url)
        result = {
            "generation": generation_name,
            "verification": verification,
            "activation": activation,
        }
        _write_worker_status(
            root,
            phase="idle",
            finished_at_epoch=time.time(),
            heartbeat_at_epoch=time.time(),
            last_result=result,
            last_error=None,
        )
        return result
    except BaseException as exc:
        _write_worker_status(
            root,
            phase="error",
            finished_at_epoch=time.time(),
            heartbeat_at_epoch=time.time(),
            last_error=f"{type(exc).__name__}: {exc}",
        )
        raise


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("request", "run", "verify"))
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT_PATH)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--activate-url", default=DEFAULT_ACTIVATE_URL)
    parser.add_argument("--generation", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.command == "verify":
        if args.generation is None:
            raise SystemExit("--generation is required for verify")
        print(json.dumps(
            verify_generation(args.generation, expected_model=embedding_index.MODEL_NAME),
            ensure_ascii=False,
            indent=2,
        ))
        return 0

    queue = PendingQueue(args.root)
    if args.command == "request":
        queue.request({"reason": "cli"})
        return 0

    completed = queue.drain(
        lambda _payload: build_and_promote(
            root=args.root,
            vault_path=args.vault,
            db_path=args.db,
            activate_url=args.activate_url or None,
        ),
        max_jobs=2,
    )
    print(json.dumps({"completed_jobs": completed}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
