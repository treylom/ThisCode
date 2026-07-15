import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _write_generation(path: Path, *, model: str = 'test-model', rows: int = 2) -> None:
    path.mkdir(parents=True, exist_ok=True)
    vectors = np.arange(rows * 3, dtype=np.float32).reshape(rows, 3)
    np.save(path / 'embeddings.npy', vectors)
    notes = [{'note_path': f'note-{index}.md'} for index in range(rows)]
    (path / 'embedding_meta.json').write_text(
        json.dumps({'model': model, 'notes': notes}),
        encoding='utf-8',
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class EmbeddingDeviceTest(unittest.TestCase):
    def test_model_loader_honors_explicit_cpu_device(self):
        import embedding_index

        captured = []

        class FakeSentenceTransformer:
            def __init__(self, model_name, **kwargs):
                captured.append((model_name, kwargs))

        fake_module = type(sys)('sentence_transformers')
        fake_module.SentenceTransformer = FakeSentenceTransformer
        previous = embedding_index._model
        embedding_index._model = None
        try:
            with patch.dict(os.environ, {'GRAPHRAG_EMBED_DEVICE': 'cpu'}), \
                 patch.dict(sys.modules, {'sentence_transformers': fake_module}):
                embedding_index._get_model()
        finally:
            embedding_index._model = previous

        self.assertEqual(captured, [(embedding_index.MODEL_NAME, {'device': 'cpu'})])

    def test_worker_overrides_inherited_mps_device_and_finishes_idle(self):
        import embedding_worker

        captured_devices = []

        def fake_build(*, vault_path, db_path, output_dir):
            captured_devices.append(os.environ.get('GRAPHRAG_EMBED_DEVICE'))
            _write_generation(
                Path(output_dir),
                model=embedding_worker.embedding_index.MODEL_NAME,
                rows=2,
            )

        with tempfile.TemporaryDirectory() as tmp, \
             patch.dict(os.environ, {'GRAPHRAG_EMBED_DEVICE': 'mps'}, clear=False), \
             patch.object(embedding_worker.embedding_index, 'build_index', side_effect=fake_build):
            root = Path(tmp)
            result = embedding_worker.build_and_promote(
                root=root,
                vault_path=root / 'vault',
                db_path=root / 'vault_graph.db',
                activate_url=None,
            )
            status = json.loads((root / 'status.json').read_text(encoding='utf-8'))

            self.assertEqual(captured_devices, ['cpu'])
            self.assertEqual(status['phase'], 'idle')
            self.assertEqual(status['changed_notes'], 2)
            self.assertEqual(Path(os.path.realpath(root / 'current')).name, result['generation'])


class GenerationVerifierTest(unittest.TestCase):
    def test_verified_generation_promotes_and_survives_fresh_resolution(self):
        import embedding_worker

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = root / 'generations' / 'gen-old'
            new = root / 'generations' / 'gen-new'
            _write_generation(old, rows=1)
            _write_generation(new, rows=3)
            current = root / 'current'
            current.symlink_to(Path('generations') / old.name, target_is_directory=True)

            result = embedding_worker.promote_generation(
                new,
                current_link=current,
                expected_model='test-model',
            )

            self.assertEqual(result['note']['vectors'], 3)
            self.assertEqual(Path(os.path.realpath(current)), new.resolve())
            reopened = embedding_worker.verify_generation(
                Path(os.path.realpath(current)),
                expected_model='test-model',
            )
            self.assertEqual(reopened['note']['vectors'], 3)

    def test_verifier_rejects_meta_vector_row_mismatch(self):
        import embedding_worker

        with tempfile.TemporaryDirectory() as tmp:
            generation = Path(tmp) / 'generation'
            _write_generation(generation, rows=2)
            meta = json.loads((generation / 'embedding_meta.json').read_text())
            meta['notes'].append({'note_path': 'extra.md'})
            (generation / 'embedding_meta.json').write_text(json.dumps(meta))

            with self.assertRaisesRegex(ValueError, 'row count'):
                embedding_worker.verify_generation(generation, expected_model='test-model')

    def test_verifier_rejects_non_finite_vectors(self):
        import embedding_worker

        with tempfile.TemporaryDirectory() as tmp:
            generation = Path(tmp) / 'generation'
            _write_generation(generation, rows=2)
            vectors = np.load(generation / 'embeddings.npy')
            vectors[0, 0] = np.nan
            np.save(generation / 'embeddings.npy', vectors)

            with self.assertRaisesRegex(ValueError, 'finite'):
                embedding_worker.verify_generation(generation, expected_model='test-model')

    def test_verifier_rejects_wrong_model(self):
        import embedding_worker

        with tempfile.TemporaryDirectory() as tmp:
            generation = Path(tmp) / 'generation'
            _write_generation(generation, model='wrong-model', rows=2)

            with self.assertRaisesRegex(ValueError, 'model mismatch'):
                embedding_worker.verify_generation(generation, expected_model='test-model')

    def test_failed_generation_keeps_current_pointer_and_bytes(self):
        import embedding_worker

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            generations = root / 'generations'
            old = generations / 'gen-old'
            bad = generations / 'gen-bad'
            _write_generation(old, rows=2)
            _write_generation(bad, rows=2)
            meta = json.loads((bad / 'embedding_meta.json').read_text())
            meta['notes'].append({'note_path': 'mismatch.md'})
            (bad / 'embedding_meta.json').write_text(json.dumps(meta))
            current = root / 'current'
            current.symlink_to(Path('generations') / old.name, target_is_directory=True)
            old_sha = _sha256(old / 'embeddings.npy')

            with self.assertRaises(ValueError):
                embedding_worker.promote_generation(
                    bad,
                    current_link=current,
                    expected_model='test-model',
                )

            self.assertEqual(current.resolve(), old.resolve())
            self.assertEqual(_sha256(old / 'embeddings.npy'), old_sha)

    def test_sigkill_before_promotion_keeps_current_pointer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = root / 'generations' / 'gen-old'
            _write_generation(old, rows=1)
            current = root / 'current'
            current.symlink_to(Path('generations') / old.name, target_is_directory=True)
            code = (
                'import pathlib,time,embedding_worker; '
                f"embedding_worker.prepare_staging_generation(pathlib.Path({str(root)!r}), 'gen-new'); "
                'time.sleep(60)'
            )
            process = subprocess.Popen(
                [sys.executable, '-c', code],
                env={**os.environ, 'PYTHONPATH': str(SCRIPTS_DIR)},
            )
            try:
                staging = root / 'generations' / '.gen-new.staging'
                for _ in range(100):
                    if staging.exists():
                        break
                    process.poll()
                    if process.returncode is not None:
                        self.fail(f'worker fixture exited early: {process.returncode}')
                    import time
                    time.sleep(0.01)
                self.assertTrue(staging.exists())
                process.kill()
                process.wait(timeout=5)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)

            self.assertEqual(current.resolve(), old.resolve())


class PendingQueueTest(unittest.TestCase):
    def test_request_exposes_queued_and_coalesced_status(self):
        import embedding_worker

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue = embedding_worker.PendingQueue(root)
            queue.request({'reason': 'first'})
            queue.request({'reason': 'second'})

            status = json.loads((root / 'status.json').read_text(encoding='utf-8'))
            self.assertEqual(status['phase'], 'queued')
            self.assertEqual(status['pending_coalesced'], 1)
            self.assertIn('queued_at_epoch', status)

    def test_three_triggers_coalesce_to_one_active_and_one_followup(self):
        import embedding_worker

        with tempfile.TemporaryDirectory() as tmp:
            queue = embedding_worker.PendingQueue(Path(tmp))
            queue.request({'reason': 'first'})
            calls = []

            def run_once(payload):
                calls.append(payload)
                if len(calls) == 1:
                    queue.request({'reason': 'second'})
                    queue.request({'reason': 'third'})

            completed = queue.drain(run_once, max_jobs=2)

            self.assertEqual(completed, 2)
            self.assertEqual([call['reason'] for call in calls], ['first', 'third'])
            self.assertFalse(queue.pending_path.exists())


if __name__ == '__main__':
    unittest.main()
