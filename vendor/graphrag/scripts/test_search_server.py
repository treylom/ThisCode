import asyncio
import inspect
import json
import sqlite3
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


class SearchServerHealthTest(unittest.TestCase):
    def test_health_endpoint_returns_ok(self):
        import search_server

        client = TestClient(search_server.app)
        response = client.get('/health')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'ok')
        self.assertIn('models_ready', data)
        self.assertIn('index_update', data)
        self.assertIn('update_in_progress', data['index_update'])
        self.assertIn('phase', data['index_update'])

    def test_index_status_endpoint_exposes_update_lifecycle(self):
        import search_server

        search_server._reset_index_update_status()
        search_server._set_index_update_status(update_in_progress=True, phase='note_embeddings')
        client = TestClient(search_server.app)
        response = client.get('/api/index/status')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['update_in_progress'])
        self.assertEqual(response.json()['phase'], 'note_embeddings')
        search_server._reset_index_update_status()

    def test_index_status_includes_external_worker_status(self):
        import search_server

        with patch.object(search_server, '_get_embedding_worker_status', return_value={
            'phase': 'building',
            'generation': 'gen-123',
        }):
            data = asyncio.run(search_server.index_update_status())

        self.assertEqual(data['embedding_worker']['phase'], 'building')
        self.assertEqual(data['embedding_worker']['generation'], 'gen-123')


class SearchModeTest(unittest.TestCase):
    def test_valid_modes_accepted(self):
        import search_server

        client = TestClient(search_server.app)

        for mode in ['hybrid', 'quick', 'deep']:
            with self.subTest(mode=mode), \
                 patch.object(search_server, '_enqueue_query_log', create=True), \
                 patch.object(search_server._models_ready, 'wait', return_value=True), \
                 patch.object(search_server.app.state, 'conn', 'CONN', create=True), \
                 patch.object(search_server.app.state, 'index_dir', 'INDEX', create=True), \
                 patch.object(search_server.graph_search, 'hybrid_search', return_value=[]):
                response = client.get('/api/search', params={'q': 'test', 'mode': mode})

            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data['source'], 'hybrid')
            self.assertEqual(data['results'], [])

    def test_invalid_mode_rejected(self):
        import search_server

        client = TestClient(search_server.app)
        with patch.object(search_server, '_enqueue_query_log', create=True):
            response = client.get('/api/search', params={'q': 'test', 'mode': 'dense'})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()['detail'],
            "Invalid mode: dense. Valid: ['deep', 'hybrid', 'quick']",
        )


class TypedRelationRescoreGateTest(unittest.TestCase):
    def test_typed_relation_rescore_is_off_by_default(self):
        import search_server

        client = TestClient(search_server.app)
        with patch.dict('os.environ', {}, clear=False), \
             patch.object(search_server, '_enqueue_query_log', create=True), \
             patch.object(search_server._models_ready, 'wait', return_value=True), \
             patch.object(search_server.app.state, 'conn', 'CONN', create=True), \
             patch.object(search_server.app.state, 'index_dir', 'INDEX', create=True), \
             patch.object(search_server.graph_search, 'hybrid_search', return_value=[{'entity': 'A'}, {'entity': 'B'}]), \
             patch.object(search_server.graph_search, 'rerank', return_value=[{'entity': 'A'}, {'entity': 'B'}]), \
             patch.object(search_server.graph_search, 'classify_query_complexity', return_value=search_server.graph_search.QueryLevel.L1), \
             patch.object(search_server.graph_search, 'community_rescore', return_value=[{'entity': 'A'}, {'entity': 'B'}]), \
             patch.object(search_server.graph_search, 'typed_relation_rescore') as typed_rescore:
            response = client.get('/api/search', params={'q': 'typed off', 'mode': 'hybrid'})

        self.assertEqual(response.status_code, 200)
        typed_rescore.assert_not_called()

    def test_typed_relation_rescore_runs_when_env_enabled(self):
        import search_server

        client = TestClient(search_server.app)
        typed_results = [{'entity': 'B'}, {'entity': 'A'}]
        with patch.dict('os.environ', {'GRAPHRAG_TYPED_RESCORE': '1'}, clear=False), \
             patch.object(search_server, '_enqueue_query_log', create=True), \
             patch.object(search_server._models_ready, 'wait', return_value=True), \
             patch.object(search_server.app.state, 'conn', 'CONN', create=True), \
             patch.object(search_server.app.state, 'index_dir', 'INDEX', create=True), \
             patch.object(search_server.graph_search, 'hybrid_search', return_value=[{'entity': 'A'}, {'entity': 'B'}]), \
             patch.object(search_server.graph_search, 'rerank', return_value=[{'entity': 'A'}, {'entity': 'B'}]), \
             patch.object(search_server.graph_search, 'classify_query_complexity', return_value=search_server.graph_search.QueryLevel.L1), \
             patch.object(search_server.graph_search, 'community_rescore', return_value=[{'entity': 'A'}, {'entity': 'B'}]), \
             patch.object(search_server.graph_search, 'typed_relation_rescore', return_value=typed_results) as typed_rescore:
            response = client.get('/api/search', params={'q': 'typed on', 'mode': 'hybrid'})

        self.assertEqual(response.status_code, 200)
        typed_rescore.assert_called_once_with(
            [{'entity': 'A'}, {'entity': 'B'}],
            'CONN',
            search_server.graph_search.QueryLevel.L1,
        )
        self.assertEqual(response.json()['results'], typed_results)


class SearchServerQueryLoggingTest(unittest.TestCase):
    def test_search_endpoint_enqueues_structured_query_log(self):
        import search_server

        captured = []
        client = TestClient(search_server.app)

        with patch.object(search_server, '_enqueue_query_log', side_effect=captured.append, create=True), \
             patch.object(search_server._models_ready, 'wait', return_value=True), \
             patch.object(search_server.app.state, 'conn', 'CONN', create=True), \
             patch.object(search_server.app.state, 'index_dir', 'INDEX', create=True), \
             patch.object(search_server.graph_search, 'hybrid_search', return_value=[{'path': 'hit.md'}]), \
             patch.object(search_server.graph_search, 'rerank', return_value=[{'path': 'hit.md'}]):
            response = client.get(
                '/api/search',
                params={'q': 'structured log', 'mode': 'hybrid', 'top_k': 5},
                headers={'User-Agent': 'sonseokhee-test', 'X-Caller': 'unit-test'},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(captured), 1)
        record = captured[0]
        self.assertEqual(record['query'], 'structured log')
        self.assertIn('timestamp_kst', record)
        self.assertEqual(record['mode'], 'hybrid')
        self.assertEqual(record['top_k'], 5)
        self.assertEqual(record['status_code'], 200)
        self.assertEqual(record['result_count'], 1)
        self.assertIsNone(record.get('failure_type'))
        self.assertGreaterEqual(record['elapsed_ms'], 0)
        self.assertEqual(
            set(record['phase_timings_ms']),
            {'cache_hit', 'qe', 'dense', 'hybrid_total', 'rerank', 'rescore'},
        )
        self.assertEqual(record['caller']['user_agent'], 'sonseokhee-test')
        self.assertEqual(record['caller']['x_caller'], 'unit-test')

    def test_search_endpoint_marks_zero_result_as_failed_query(self):
        import search_server

        captured = []
        client = TestClient(search_server.app)

        with patch.object(search_server, '_enqueue_query_log', side_effect=captured.append, create=True), \
             patch.object(search_server._models_ready, 'wait', return_value=True), \
             patch.object(search_server.app.state, 'conn', 'CONN', create=True), \
             patch.object(search_server.app.state, 'index_dir', 'INDEX', create=True), \
             patch.object(search_server.graph_search, 'hybrid_search', return_value=[]):
            response = client.get('/api/search', params={'q': 'no hits expected', 'mode': 'hybrid'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0]['result_count'], 0)
        self.assertEqual(captured[0]['failure_type'], 'zero_results')

    def test_search_endpoint_logs_http_5xx_failures(self):
        import search_server

        captured = []
        client = TestClient(search_server.app)

        with patch.object(search_server, '_enqueue_query_log', side_effect=captured.append, create=True), \
             patch.object(search_server.app.state, 'conn', None, create=True):
            response = client.get('/api/search', params={'q': 'missing db', 'mode': 'hybrid'})

        self.assertEqual(response.status_code, 503)
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0]['query'], 'missing db')
        self.assertEqual(captured[0]['status_code'], 503)
        self.assertEqual(captured[0]['failure_type'], 'http_5xx')

    def test_search_endpoint_logs_model_warmup_timeout(self):
        import search_server

        captured = []
        client = TestClient(search_server.app)

        with patch.object(search_server, '_enqueue_query_log', side_effect=captured.append, create=True), \
             patch.object(search_server._models_ready, 'wait', return_value=False), \
             patch.object(search_server.app.state, 'conn', 'CONN', create=True), \
             patch.object(search_server.app.state, 'index_dir', 'INDEX', create=True), \
             patch.object(search_server.graph_search, 'hybrid_search') as hybrid:
            response = client.get('/api/search', params={'q': 'warmup wait', 'mode': 'hybrid'})

        self.assertEqual(response.status_code, 503)
        hybrid.assert_not_called()
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0]['status_code'], 503)
        self.assertEqual(captured[0]['failure_type'], 'timeout')

    def test_write_query_log_record_appends_jsonl_and_failed_tsv(self):
        import search_server

        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            record = {
                'timestamp_kst': '2026-06-11T15:40:00+09:00',
                'query': 'no hits expected',
                'mode': 'hybrid',
                'top_k': 20,
                'rerank': True,
                'caller': {'user_agent': 'test-agent', 'x_caller': '', 'remote_addr': 'testclient'},
                'elapsed_ms': 1.5,
                'result_count': 0,
                'status_code': 200,
                'failure_type': 'zero_results',
            }

            search_server._write_query_log_record(record, log_dir=log_dir)

            json_lines = (log_dir / 'query-log.jsonl').read_text(encoding='utf-8').splitlines()
            self.assertEqual(json.loads(json_lines[0])['failure_type'], 'zero_results')

            failed_lines = (log_dir / 'failed-queries.tsv').read_text(encoding='utf-8').splitlines()
            self.assertEqual(failed_lines[0], 'timestamp_kst\tfailure_type\tstatus_code\tresult_count\telapsed_ms\tquery')
            self.assertEqual(
                failed_lines[1],
                '2026-06-11T15:40:00+09:00\tzero_results\t200\t0\t1.5\tno hits expected',
            )


class SearchServerLazyGraphTest(unittest.TestCase):
    def test_load_runtime_state_defers_graph_build(self):
        # v2.3.3 drift fix: search_server 안 `get_connection` symbol 없음 — 실제 `_open_readonly_connection`.
        # Path.exists mock 으로 v2.3.1 graceful fix 의 db_p.exists() branch 도 cover.
        import search_server

        with patch.object(search_server, '_open_readonly_connection', return_value='CONN') as open_conn, \
             patch('pathlib.Path.exists', return_value=True), \
             patch.object(search_server.embedding_index, 'load_index', return_value='NOTE_INDEX', create=True), \
             patch.object(search_server.embedding_index, 'load_entity_index', return_value='ENTITY_INDEX', create=True), \
             patch.object(search_server, 'build_networkx_graph') as build_graph:
            state = search_server._load_runtime_state()

        open_conn.assert_called_once()
        # _warm_models is now called in background thread (lifespan), not in _load_runtime_state
        build_graph.assert_not_called()
        self.assertEqual(state['conn'], 'CONN')
        self.assertIsNone(state['graph'])

    def test_load_runtime_state_loads_vector_indexes_once(self):
        import search_server

        with patch.object(search_server, '_open_readonly_connection', return_value='CONN'), \
             patch('pathlib.Path.exists', return_value=True), \
             patch.object(search_server.embedding_index, 'load_index', return_value='NOTE_INDEX', create=True) as load_note, \
             patch.object(search_server.embedding_index, 'load_entity_index', return_value='ENTITY_INDEX', create=True) as load_entity:
            state = search_server._load_runtime_state()

        load_note.assert_called_once_with(str(search_server.DEFAULT_INDEX_DIR))
        load_entity.assert_called_once_with(str(search_server.DEFAULT_INDEX_DIR))
        self.assertEqual(state['note_index'], 'NOTE_INDEX')
        self.assertEqual(state['entity_index'], 'ENTITY_INDEX')


class SearchServerV231ConnNoneRegressionTest(unittest.TestCase):
    """v2.3.1 + v2.3.2 conn=None regression tests (Phase 2 finding 안 backfill)."""

    def test_load_runtime_state_graceful_when_db_missing(self):
        # v2.3.1: db_path.exists() False 시 conn = None
        import search_server

        with patch('pathlib.Path.exists', return_value=False):
            state = search_server._load_runtime_state()

        self.assertIsNone(state['conn'])
        self.assertIsNone(state['graph'])

    def test_api_search_returns_503_when_conn_none(self):
        # v2.3.2: /api/search conn=None → HTTPException 503
        import search_server

        client = TestClient(search_server.app)
        with patch.object(search_server.app.state, 'conn', None, create=True), \
             patch.object(search_server, '_enqueue_query_log', create=True), \
             patch.object(search_server._models_ready, 'wait', return_value=True):
            response = client.get('/api/search', params={'q': 'test', 'mode': 'hybrid'})

        self.assertEqual(response.status_code, 503)
        self.assertIn('error', response.json()['detail'])

    def test_get_graph_returns_503_when_conn_none(self):
        # v2.3.2: _get_graph() conn=None → HTTPException 503
        import search_server
        from fastapi import HTTPException

        app = SimpleNamespace(state=SimpleNamespace(conn=None, graph=None))
        with self.assertRaises(HTTPException) as ctx:
            search_server._get_graph(app)
        self.assertEqual(ctx.exception.status_code, 503)

    def test_ready_endpoint_returns_503_when_db_not_ready(self):
        # v2.3.2: /ready endpoint 별도 — conn=None 시 503
        import search_server

        client = TestClient(search_server.app)
        with patch.object(search_server.app.state, 'conn', None, create=True):
            response = client.get('/ready')

        self.assertEqual(response.status_code, 503)
        detail = response.json()['detail']
        self.assertFalse(detail['ready'])
        self.assertEqual(detail['reason'], 'db_not_ready')

    def test_get_graph_builds_once_and_reuses_cached_graph(self):
        import search_server

        app = SimpleNamespace(state=SimpleNamespace(conn='CONN', graph=None))

        with patch.object(search_server, 'build_networkx_graph', side_effect=['GRAPH']) as build_graph:
            first = search_server._get_graph(app)
            second = search_server._get_graph(app)

        self.assertEqual(first, 'GRAPH')
        self.assertEqual(second, 'GRAPH')
        self.assertEqual(app.state.graph, 'GRAPH')
        build_graph.assert_called_once_with('CONN')

    def test_reload_clears_hybrid_cache(self):
        import search_server

        app = search_server.app
        original_state = {
            'db_path': getattr(app.state, 'db_path', None),
            'index_dir': getattr(app.state, 'index_dir', None),
            'conn': getattr(app.state, 'conn', None),
            'graph': getattr(app.state, 'graph', None),
        }

        app.state.db_path = 'dummy.db'
        app.state.index_dir = 'dummy-index'
        app.state.conn = 'OLD_CONN'
        app.state.graph = 'OLD_GRAPH'

        try:
            async def run_test():
                with patch.object(search_server.graph_search, 'clear_hybrid_cache') as clear_hybrid, \
                     patch.object(search_server, '_load_runtime_state', return_value={
                         'db_path': 'new.db',
                         'index_dir': 'new-index',
                         'conn': 'NEW_CONN',
                         'graph': None,
                     }) as load_state, \
                     patch.object(search_server, '_replace_runtime_state') as replace_state, \
                     patch.object(search_server.threading, 'Thread'):
                    response = await search_server.reload_models()

                clear_hybrid.assert_called_once_with()
                load_state.assert_called_once()
                replace_state.assert_called_once_with(app, {
                    'db_path': 'new.db',
                    'index_dir': 'new-index',
                    'conn': 'NEW_CONN',
                    'graph': None,
                })
                self.assertEqual(response['status'], 'reloaded')
                self.assertEqual(response['db_path'], 'dummy.db')
                self.assertEqual(response['index_dir'], 'dummy-index')

            asyncio.run(run_test())
        finally:
            for key, value in original_state.items():
                setattr(app.state, key, value)


class SearchServerIndexUpdateTest(unittest.TestCase):
    def test_search_remains_available_while_external_worker_is_building(self):
        import search_server

        client = TestClient(search_server.app)
        app = search_server.app
        original_conn = getattr(app.state, 'conn', None)
        original_index_dir = getattr(app.state, 'index_dir', None)
        app.state.conn = 'OLD_CONN'
        app.state.index_dir = '/tmp/current'
        try:
            with patch.object(search_server, '_get_embedding_worker_status', return_value={'phase': 'building'}), \
                 patch.object(search_server._models_ready, 'wait', return_value=True), \
                 patch.object(search_server, '_enqueue_query_log', create=True), \
                 patch.object(search_server.graph_search, 'hybrid_search', return_value=[{'path': 'old.md'}]), \
                 patch.object(search_server.graph_search, 'rerank', return_value=[{'path': 'old.md'}]), \
                 patch.object(search_server.graph_search, 'classify_query_complexity', return_value='L0'), \
                 patch.object(search_server.graph_search, 'community_rescore', return_value=[{'path': 'old.md'}]):
                response = client.get('/api/search', params={'q': 'worker building', 'mode': 'hybrid'})
                status = client.get('/api/index/status')
        finally:
            app.state.conn = original_conn
            app.state.index_dir = original_index_dir

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['results'], [{'path': 'old.md'}])
        self.assertEqual(status.json()['embedding_worker']['phase'], 'building')

    def test_activate_index_is_local_only_and_preserves_model_caches(self):
        import search_server

        app = search_server.app
        original = {
            key: getattr(app.state, key, None)
            for key in ('db_path', 'index_dir', 'conn', 'graph', 'note_index', 'entity_index')
        }
        app.state.db_path = '/tmp/vault_graph.db'
        app.state.index_dir = '/tmp/current'
        app.state.conn = 'OLD_CONN'
        app.state.graph = 'OLD_GRAPH'
        request = SimpleNamespace(client=SimpleNamespace(host='127.0.0.1'))
        new_state = {
            'db_path': '/tmp/vault_graph.db',
            'index_dir': '/tmp/current',
            'conn': 'NEW_CONN',
            'graph': None,
            'note_index': 'NEW_NOTE_INDEX',
            'entity_index': 'NEW_ENTITY_INDEX',
        }
        try:
            with patch.object(search_server, '_load_runtime_state', return_value=new_state) as load_state, \
                 patch.object(search_server, '_replace_runtime_state') as replace_state, \
                 patch.object(search_server, '_clear_model_caches') as clear_models, \
                 patch.object(search_server.graph_search, 'clear_hybrid_cache') as clear_hybrid:
                response = asyncio.run(search_server.activate_index(request))

            load_state.assert_called_once_with(Path('/tmp/vault_graph.db'), Path('/tmp/current'))
            replace_state.assert_called_once_with(app, new_state)
            clear_models.assert_not_called()
            clear_hybrid.assert_called_once_with()
            self.assertEqual(response['status'], 'activated')
        finally:
            for key, value in original.items():
                setattr(app.state, key, value)

    def test_activate_index_rejects_non_local_request(self):
        import search_server
        from fastapi import HTTPException

        request = SimpleNamespace(client=SimpleNamespace(host='10.0.0.8'))
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(search_server.activate_index(request))
        self.assertEqual(ctx.exception.status_code, 403)

    def test_index_update_status_tracks_phase_and_last_result(self):
        import search_server

        search_server._reset_index_update_status()
        search_server._set_index_update_status(
            update_in_progress=True,
            phase='entity_embeddings',
            started_at='2026-07-14T20:00:00+09:00',
        )
        active = search_server._get_index_update_status()
        self.assertTrue(active['update_in_progress'])
        self.assertEqual(active['phase'], 'entity_embeddings')

        search_server._set_index_update_status(
            update_in_progress=False,
            phase='completed',
            finished_at='2026-07-14T20:01:00+09:00',
            last_result={'status': 'updated', 'total_changes': 1},
            last_error=None,
        )
        completed = search_server._get_index_update_status()
        self.assertFalse(completed['update_in_progress'])
        self.assertEqual(completed['last_result']['status'], 'updated')
        self.assertIsNone(completed['last_error'])

    def test_run_incremental_update_skips_embeddings_when_no_files_changed(self):
        import search_server

        with patch.object(search_server, 'get_connection', return_value='WRITE_CONN'), \
             patch.object(search_server, 'detect_changes', return_value={'added': [], 'modified': [], 'deleted': []}), \
             patch.object(search_server, 'sync_frontmatter_to_graph', create=True) as sync_aliases, \
             patch.object(search_server, 'create_fts5_tables'), \
             patch.object(search_server, 'populate_fts5'), \
             patch.object(search_server, 'incremental_update') as incremental_update, \
             patch.object(search_server, 'run_community_detection') as communities, \
             patch.object(search_server.embedding_index, 'build_index') as build_index, \
             patch.object(search_server.embedding_index, 'build_entity_index') as build_entity_index, \
             patch.object(search_server, 'close_connection'):
            result = search_server._run_incremental_index_update(
                db_path='/tmp/vault_graph.db',
                vault_path='/tmp/vault',
                index_dir='/tmp/index',
                rebuild_embeddings=True,
                rebuild_entities=True,
            )

        self.assertEqual(result['status'], 'up_to_date')
        self.assertEqual(result['total_changes'], 0)
        self.assertFalse(result['embedding_rebuilt'])
        self.assertFalse(result['entity_embedding_rebuilt'])
        incremental_update.assert_not_called()
        communities.assert_not_called()
        sync_aliases.assert_not_called()
        build_index.assert_not_called()
        build_entity_index.assert_not_called()

    def test_run_incremental_update_syncs_frontmatter_aliases_when_files_changed(self):
        import search_server

        with patch.object(search_server, 'get_connection', return_value='WRITE_CONN'), \
             patch.object(search_server, 'detect_changes', return_value={'added': [], 'modified': ['note.md'], 'deleted': []}), \
             patch.object(search_server, 'incremental_update', return_value={'added': 0, 'modified': 1, 'deleted': 0, 'errors': 0}), \
             patch.object(search_server, 'run_community_detection', return_value={'updated': True}), \
             patch.object(search_server, 'sync_frontmatter_to_graph', create=True, return_value={'processed': 1, 'errors': 0}) as sync_aliases, \
             patch.object(search_server, 'create_fts5_tables'), \
             patch.object(search_server, 'populate_fts5'), \
             patch.object(search_server.embedding_index, 'build_index'), \
             patch.object(search_server.embedding_index, 'build_entity_index'), \
             patch.object(search_server, 'close_connection'):
            result = search_server._run_incremental_index_update(
                db_path='/tmp/vault_graph.db',
                vault_path='/tmp/vault',
                index_dir='/tmp/index',
                rebuild_embeddings=True,
                rebuild_entities=True,
            )

        sync_aliases.assert_called_once_with('WRITE_CONN', Path('/tmp/vault'))
        self.assertEqual(result['frontmatter_alias_sync'], {'processed': 1, 'errors': 0})
        self.assertTrue(result['embedding_rebuilt'])
        self.assertTrue(result['entity_embedding_rebuilt'])

    def test_index_update_endpoint_schedules_background_update_without_reloading_inline(self):
        import search_server

        class FakeBackgroundTasks:
            def __init__(self):
                self.tasks = []

            def add_task(self, func, **kwargs):
                self.tasks.append((func, kwargs))

        app = search_server.app
        original_state = {
            'db_path': getattr(app.state, 'db_path', None),
            'index_dir': getattr(app.state, 'index_dir', None),
            'conn': getattr(app.state, 'conn', None),
            'graph': getattr(app.state, 'graph', None),
            'note_index': getattr(app.state, 'note_index', None),
            'entity_index': getattr(app.state, 'entity_index', None),
        }
        app.state.db_path = '/tmp/vault_graph.db'
        app.state.index_dir = '/tmp/index'
        app.state.conn = 'OLD_CONN'
        app.state.graph = 'OLD_GRAPH'

        try:
            self.assertIn('background_tasks', inspect.signature(search_server.update_index).parameters)

            background_tasks = FakeBackgroundTasks()
            update_result = {
                'status': 'updated',
                'vault_path': '/tmp/vault',
                'changes': {'added': ['a.md'], 'modified': [], 'deleted': []},
                'stats': {'added': 1, 'modified': 0, 'deleted': 0, 'errors': 0},
                'total_changes': 1,
                'embedding_rebuilt': True,
                'entity_embedding_rebuilt': True,
            }
            with patch.object(search_server, '_run_incremental_index_update', return_value=update_result) as run_update, \
                 patch.object(search_server, '_load_runtime_state', return_value={
                     'db_path': '/tmp/vault_graph.db',
                     'index_dir': '/tmp/index',
                     'conn': 'NEW_CONN',
                     'graph': None,
                     'note_index': 'NOTE_INDEX',
                     'entity_index': 'ENTITY_INDEX',
                 }) as load_state, \
                 patch.object(search_server, '_replace_runtime_state') as replace_state, \
                 patch.object(search_server.graph_search, 'clear_hybrid_cache') as clear_hybrid:
                data = asyncio.run(search_server.update_index(background_tasks, vault_path='/tmp/vault'))

                self.assertEqual(data['status'], 'accepted')
                self.assertTrue(data['update_in_progress'])
                run_update.assert_not_called()
                load_state.assert_not_called()
                replace_state.assert_not_called()
                clear_hybrid.assert_not_called()
                self.assertEqual(len(background_tasks.tasks), 1)

                func, kwargs = background_tasks.tasks[0]
                func(**kwargs)

                run_update.assert_called_once()
                kwargs = run_update.call_args.kwargs
                self.assertEqual(str(kwargs['db_path']), '/tmp/vault_graph.db')
                self.assertEqual(str(kwargs['vault_path']), '/tmp/vault')
                self.assertEqual(str(kwargs['index_dir']), '/tmp/index')
                self.assertTrue(kwargs['rebuild_embeddings'])
                self.assertTrue(kwargs['rebuild_entities'])
                load_state.assert_called_once_with(Path('/tmp/vault_graph.db'))
                replace_state.assert_called_once()
                clear_hybrid.assert_called_once_with()
                status = search_server._get_index_update_status()
                self.assertFalse(status['update_in_progress'])
                self.assertEqual(status['phase'], 'completed')
                self.assertEqual(status['last_result']['total_changes'], 1)
                self.assertFalse(search_server._index_update_lock.locked())
        finally:
            if search_server._index_update_lock.locked():
                search_server._index_update_lock.release()
            for key, value in original_state.items():
                setattr(app.state, key, value)

    def test_ready_endpoint_responds_while_index_update_is_in_progress(self):
        import search_server

        app = search_server.app
        original_conn = getattr(app.state, 'conn', None)
        original_db_path = getattr(app.state, 'db_path', None)

        app.state.conn = 'OLD_CONN'
        app.state.db_path = '/tmp/vault_graph.db'
        search_server._models_ready.set()
        acquired = search_server._index_update_lock.acquire(blocking=False)
        self.assertTrue(acquired)
        try:
            response = asyncio.run(search_server.ready())
        finally:
            search_server._index_update_lock.release()
            app.state.conn = original_conn
            app.state.db_path = original_db_path

        self.assertTrue(response['ready'])
        self.assertEqual(response['db_path'], '/tmp/vault_graph.db')

    def test_search_endpoint_uses_current_runtime_while_index_update_is_in_progress(self):
        import search_server

        client = TestClient(search_server.app)
        app = search_server.app
        original_conn = getattr(app.state, 'conn', None)
        original_index_dir = getattr(app.state, 'index_dir', None)

        app.state.conn = 'OLD_CONN'
        app.state.index_dir = '/tmp/index'
        acquired = search_server._index_update_lock.acquire(blocking=False)
        self.assertTrue(acquired)
        try:
            with patch.object(search_server._models_ready, 'wait', return_value=True), \
                 patch.object(search_server, '_enqueue_query_log', create=True), \
                 patch.object(search_server.graph_search, 'hybrid_search', return_value=[{'path': 'old.md'}]) as hybrid, \
                 patch.object(search_server.graph_search, 'rerank', return_value=[{'path': 'old.md'}]), \
                 patch.object(search_server.graph_search, 'classify_query_complexity', return_value='L0'), \
                 patch.object(search_server.graph_search, 'community_rescore', return_value=[{'path': 'old.md'}]):
                response = client.get('/api/search', params={'q': 'during update', 'mode': 'hybrid'})
        finally:
            search_server._index_update_lock.release()
            app.state.conn = original_conn
            app.state.index_dir = original_index_dir

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['results'], [{'path': 'old.md'}])
        hybrid.assert_called_once()

    def test_background_update_skips_runtime_reload_when_no_files_changed(self):
        import search_server

        if search_server._index_update_lock.locked():
            search_server._index_update_lock.release()
        acquired = search_server._index_update_lock.acquire(blocking=False)
        self.assertTrue(acquired)
        update_result = {
            'status': 'up_to_date',
            'total_changes': 0,
            'embedding_rebuilt': False,
            'entity_embedding_rebuilt': False,
        }

        with patch.object(search_server, '_run_incremental_index_update', return_value=update_result), \
             patch.object(search_server.graph_search, 'clear_hybrid_cache') as clear_hybrid, \
             patch.object(search_server, '_load_runtime_state') as load_state, \
             patch.object(search_server, '_replace_runtime_state') as replace_state:
            search_server._execute_index_update_background(
                db_path=Path('/tmp/vault_graph.db'),
                vault_path=Path('/tmp/vault'),
                index_dir=Path('/tmp/index'),
                use_llm=False,
                rebuild_embeddings=True,
                rebuild_entities=True,
                reload_runtime=True,
            )

        clear_hybrid.assert_not_called()
        load_state.assert_not_called()
        replace_state.assert_not_called()
        self.assertFalse(search_server.app.state.last_index_update['runtime_reloaded'])
        self.assertFalse(search_server._index_update_lock.locked())

    def test_runtime_reload_connection_can_be_used_from_request_thread(self):
        import search_server

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / 'vault_graph.db'
            setup_conn = sqlite3.connect(db_path)
            setup_conn.execute('CREATE TABLE smoke (id INTEGER PRIMARY KEY, value TEXT)')
            setup_conn.execute('INSERT INTO smoke (value) VALUES (?)', ('ok',))
            setup_conn.commit()
            setup_conn.close()

            fake_app = SimpleNamespace(state=SimpleNamespace(conn=None))
            errors: list[BaseException] = []

            def update_thread():
                try:
                    with patch.object(search_server.embedding_index, 'load_index', return_value=None), \
                         patch.object(search_server.embedding_index, 'load_entity_index', return_value=None):
                        state = search_server._load_runtime_state(db_path)
                    search_server._replace_runtime_state(fake_app, state)
                except BaseException as exc:
                    errors.append(exc)

            worker = threading.Thread(target=update_thread)
            worker.start()
            worker.join()
            self.assertFalse(errors)
            self.assertIsNotNone(fake_app.state.conn)

            request_errors: list[BaseException] = []
            request_values: list[str] = []

            def request_thread():
                try:
                    row = fake_app.state.conn.execute('SELECT value FROM smoke WHERE id = 1').fetchone()
                    request_values.append(row['value'])
                except BaseException as exc:
                    request_errors.append(exc)

            requester = threading.Thread(target=request_thread)
            requester.start()
            requester.join()

            try:
                self.assertFalse(request_errors)
                self.assertEqual(request_values, ['ok'])
            finally:
                search_server.close_connection(fake_app.state.conn)




if __name__ == '__main__':
    unittest.main()
