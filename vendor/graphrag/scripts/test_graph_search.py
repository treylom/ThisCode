import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import graph_search


def _candidate(name, **overrides):
    candidate = {
        'entity': name,
        'name': name,
        'type': 'note',
        'source_note': f'{name.lower()}.md',
        'description': f'{name} description',
        'centrality_score': 0.0,
        'source': 'dense',
        'alias_matched': False,
        'matched_alias': '',
    }
    candidate.update(overrides)
    return candidate


class HybridSearchCacheTest(unittest.TestCase):
    def setUp(self):
        if hasattr(graph_search, 'clear_hybrid_cache'):
            graph_search.clear_hybrid_cache()

    def tearDown(self):
        if hasattr(graph_search, 'clear_hybrid_cache'):
            graph_search.clear_hybrid_cache()

    def test_hybrid_search_caches_repeated_queries(self):
        call_count = 0

        def fake_fts5_search(conn, query, limit):
            nonlocal call_count
            call_count += 1
            return [
                {'name': 'Alpha', 'type': 'note', 'description': 'A', 'source_note': 'alpha.md', 'centrality_score': 1.0},
                {'name': 'Beta', 'type': 'note', 'description': 'B', 'source_note': 'beta.md', 'centrality_score': 0.8},
                {'name': 'Gamma', 'type': 'note', 'description': 'C', 'source_note': 'gamma.md', 'centrality_score': 0.6},
            ]

        with patch.object(graph_search, '_EMBEDDING_AVAILABLE', False), \
             patch.object(graph_search, 'fts5_search', side_effect=fake_fts5_search), \
             patch.object(graph_search, '_decompose_query', return_value=[]):
            first = graph_search.hybrid_search(
                MagicMock(),
                'cached query',
                top_k=3,
                sparse_weight=1.0,
                decomposed_weight=0.0,
                entity_weight=0.0,
            )
            second = graph_search.hybrid_search(
                MagicMock(),
                'cached query',
                top_k=3,
                sparse_weight=1.0,
                decomposed_weight=0.0,
                entity_weight=0.0,
            )

        self.assertEqual(call_count, 1)
        self.assertEqual(first, second)
        self.assertIsNot(first, second)
        self.assertIsNot(first[0], second[0])

    def test_hybrid_search_cache_key_normalizes_case_and_outer_whitespace(self):
        call_count = 0

        def fake_fts5_search(conn, query, limit):
            nonlocal call_count
            call_count += 1
            return [
                {'name': 'GraphRAG', 'type': 'note', 'description': 'A', 'source_note': 'graphrag.md', 'centrality_score': 1.0},
            ]

        with patch.object(graph_search, '_EMBEDDING_AVAILABLE', False), \
             patch.object(graph_search, 'fts5_search', side_effect=fake_fts5_search), \
             patch.object(graph_search, '_decompose_query', return_value=[]):
            first = graph_search.hybrid_search(
                MagicMock(),
                '  GraphRAG  ',
                top_k=1,
                sparse_weight=1.0,
                decomposed_weight=0.0,
                entity_weight=0.0,
            )
            second = graph_search.hybrid_search(
                MagicMock(),
                'graphrag',
                top_k=1,
                sparse_weight=1.0,
                decomposed_weight=0.0,
                entity_weight=0.0,
            )

        self.assertEqual(call_count, 1)
        self.assertEqual(first, second)

    def test_hybrid_search_reports_qe_and_dense_phase_timings(self):
        timings = {}
        with patch.object(graph_search, '_EMBEDDING_AVAILABLE', False), \
             patch.object(graph_search, 'fts5_search', return_value=[]), \
             patch.object(graph_search, '_decompose_query', return_value=[]), \
             patch.object(graph_search, 'expand_query_llm', return_value=graph_search._QE_DEFAULT):
            graph_search.hybrid_search(
                MagicMock(),
                'timed query',
                top_k=1,
                decomposed_weight=0.0,
                entity_weight=0.0,
                timings=timings,
            )

        self.assertGreaterEqual(timings['qe'], 0)
        self.assertGreaterEqual(timings['dense'], 0)

    def test_query_expansion_cache_key_normalizes_case_and_outer_whitespace(self):
        expected = {'expanded_terms': ['graph'], 'english_query': 'GraphRAG', 'intent': 'lookup'}
        graph_search._QE_CACHE.clear()
        graph_search._QE_CACHE['graphrag'] = expected
        try:
            self.assertIs(graph_search.expand_query_llm('  GraphRAG  '), expected)
        finally:
            graph_search._QE_CACHE.clear()

    def test_hybrid_search_uses_loaded_indexes_without_disk_search(self):
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        conn.execute(
            'CREATE TABLE entities (id INTEGER PRIMARY KEY, name TEXT, type TEXT, description TEXT, source_note TEXT, centrality_score REAL)'
        )
        conn.execute(
            'INSERT INTO entities (id, name, type, description, source_note, centrality_score) VALUES (1, ?, ?, ?, ?, ?)',
            ('Alpha', 'note', 'Alpha description', 'alpha.md', 0.0)
        )
        conn.commit()

        with patch.object(graph_search, '_EMBEDDING_AVAILABLE', True), \
             patch.object(graph_search._embedding_index, 'search', side_effect=AssertionError('disk note search called')), \
             patch.object(graph_search._embedding_index, 'search_entities', side_effect=AssertionError('disk entity search called')), \
             patch.object(graph_search._embedding_index, 'search_loaded', return_value=[
                 {'note_path': 'alpha.md', 'title': 'Alpha', 'score': 0.9},
             ], create=True) as search_loaded, \
             patch.object(graph_search._embedding_index, 'search_entities_loaded', return_value=[
                 {'name': 'Alpha', 'type': 'note', 'source_note': 'alpha.md', 'score': 0.8},
             ], create=True) as search_entities_loaded, \
             patch.object(graph_search, 'fts5_search', return_value=[]), \
             patch.object(graph_search, '_decompose_query', return_value=[]), \
             patch.object(graph_search, 'get_bulk_rel_strengths', return_value={}):
            results = graph_search.hybrid_search(
                conn,
                'fresh query',
                top_k=3,
                decomposed_weight=0.0,
                note_index='NOTE_INDEX',
                entity_index='ENTITY_INDEX',
            )

        search_loaded.assert_called_once()
        search_entities_loaded.assert_called_once()
        self.assertTrue(results)
        self.assertIn('dense', results[0]['source'])
        conn.close()


class HybridSearchCommunitySummaryTest(unittest.TestCase):
    def setUp(self):
        if hasattr(graph_search, 'clear_hybrid_cache'):
            graph_search.clear_hybrid_cache()

    def tearDown(self):
        if hasattr(graph_search, 'clear_hybrid_cache'):
            graph_search.clear_hybrid_cache()

    def test_hybrid_search_includes_summary_matched_community_entities(self):
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        conn.execute(
            'CREATE TABLE communities (id INTEGER PRIMARY KEY, level INTEGER, name TEXT, summary TEXT)'
        )
        conn.execute(
            'CREATE TABLE entities (id INTEGER PRIMARY KEY, name TEXT, type TEXT, description TEXT, source_note TEXT, centrality_score REAL, community_id INTEGER)'
        )
        conn.execute(
            'INSERT INTO communities (id, level, name, summary) VALUES (1, 1, ?, ?)',
            ('정치와 사회', '정치 사회 글쓰기와 민주주의 연구를 연결하는 허브')
        )
        conn.execute(
            'INSERT INTO entities (id, name, type, description, source_note, centrality_score, community_id) VALUES (1, ?, ?, ?, ?, ?, ?)',
            ('Hub-001', 'note', '커뮤니티 허브 노트', 'hub-001.md', 0.9, 1)
        )
        conn.commit()

        with patch.object(graph_search, '_EMBEDDING_AVAILABLE', False), \
             patch.object(graph_search, 'fts5_search', return_value=[]), \
             patch.object(graph_search, '_decompose_query', return_value=[]):
            results = graph_search.hybrid_search(
                conn,
                '정치 사회 연결',
                top_k=5,
                sparse_weight=1.0,
                decomposed_weight=0.0,
                entity_weight=0.0,
            )

        self.assertTrue(results)
        self.assertEqual(results[0]['entity'], 'Hub-001')
        self.assertIn('community', results[0]['source'])
        conn.close()


class RerankFilterTest(unittest.TestCase):
    def test_negative_scores_filtered(self):
        candidates = [
            _candidate('Alpha', description='Alpha candidate'),
            _candidate('Beta', description='Beta candidate'),
            _candidate('Gamma', description='Gamma candidate'),
            _candidate('Delta', description='Delta candidate'),
        ]
        ce = MagicMock()
        ce.predict.return_value = [0.8, -0.1, 0.2, -0.7]

        with patch.object(graph_search, '_get_cross_encoder', return_value=ce):
            results = graph_search.rerank('alpha query', candidates, top_k=4)

        self.assertEqual([result['entity'] for result in results], ['Alpha', 'Gamma', 'Beta'])
        self.assertNotIn('Delta', [result['entity'] for result in results])
        self.assertEqual(results[2]['rerank_score'], -0.1)

    def test_min_3_safeguard(self):
        candidates = [
            _candidate('Alpha'),
            _candidate('Beta'),
            _candidate('Gamma'),
            _candidate('Delta'),
        ]
        ce = MagicMock()
        ce.predict.return_value = [-0.8, -0.2, -1.1, -0.5]

        with patch.object(graph_search, '_get_cross_encoder', return_value=ce):
            results = graph_search.rerank('negative query', candidates, top_k=4)

        self.assertEqual(len(results), 3)
        self.assertEqual([result['entity'] for result in results], ['Beta', 'Delta', 'Alpha'])
        self.assertEqual([result['rerank_score'] for result in results], [-0.2, -0.5, -0.8])


class AliasRerankerTest(unittest.TestCase):
    def test_alias_prefix_injected(self):
        candidates = [
            _candidate(
                'Alpha',
                alias_matched=True,
                matched_alias='Some Alias',
                source='like',
                source_note='alpha.md',
                description='Alias candidate',
            )
        ]
        captured_pairs = []
        ce = MagicMock()

        def capture_pairs(pairs):
            captured_pairs.extend(pairs)
            return [0.9]

        ce.predict.side_effect = capture_pairs

        with patch.object(graph_search, '_get_cross_encoder', return_value=ce):
            graph_search.rerank('alias query', candidates, top_k=1)

        self.assertEqual(len(captured_pairs), 1)
        self.assertEqual(
            captured_pairs[0],
            ('alias query', '[alias: Some Alias] Alpha alpha.md Alias candidate'),
        )

    def test_no_alias_prefix_for_non_alias(self):
        candidates = [
            _candidate(
                'Alpha',
                alias_matched=False,
                matched_alias='',
                source='dense',
                source_note='alpha.md',
                description='Plain candidate',
            )
        ]
        captured_pairs = []
        ce = MagicMock()

        def capture_pairs(pairs):
            captured_pairs.extend(pairs)
            return [0.4]

        ce.predict.side_effect = capture_pairs

        with patch.object(graph_search, '_get_cross_encoder', return_value=ce):
            graph_search.rerank('plain query', candidates, top_k=1)

        self.assertEqual(len(captured_pairs), 1)
        self.assertEqual(
            captured_pairs[0],
            ('plain query', 'Alpha alpha.md Plain candidate'),
        )
        self.assertNotIn('[alias:', captured_pairs[0][1])

    def test_phrase_prefix_injected(self):
        candidates = [
            _candidate(
                'Phrase Gold',
                phrase_matched=True,
                matched_phrase='semantic search',
                source='phrase',
                source_note='phrase.md',
                description='Phrase candidate',
            )
        ]
        captured_pairs = []
        ce = MagicMock()

        def capture_pairs(pairs):
            captured_pairs.extend(pairs)
            return [0.9]

        ce.predict.side_effect = capture_pairs

        with patch.object(graph_search, '_get_cross_encoder', return_value=ce):
            graph_search.rerank('의미 검색', candidates, top_k=1)

        self.assertEqual(len(captured_pairs), 1)
        self.assertEqual(
            captured_pairs[0],
            ('의미 검색', '[phrase: semantic search] Phrase Gold phrase.md Phrase candidate'),
        )

    def test_alias_matched_candidate_gets_rerank_boost(self):
        candidates = [
            _candidate(
                'Plain',
                alias_matched=False,
                matched_alias='',
                source='dense+like',
            ),
            _candidate(
                'Alias Gold',
                alias_matched=True,
                matched_alias='Exact Alias',
                source='dense+like',
            ),
        ]
        ce = MagicMock()
        ce.predict.return_value = [0.5, 0.5]

        with patch.object(graph_search, '_get_cross_encoder', return_value=ce):
            results = graph_search.rerank('Exact Alias', candidates, top_k=2)

        self.assertEqual([result['entity'] for result in results], ['Alias Gold', 'Plain'])
        self.assertGreater(results[0]['alias_boost'], 0.0)

    def test_partial_alias_match_does_not_get_rerank_boost(self):
        candidates = [
            _candidate(
                'Alias Gold',
                alias_matched=True,
                matched_alias='Exact Alias',
                source='dense+like',
            ),
        ]
        ce = MagicMock()
        ce.predict.return_value = [0.5]

        with patch.object(graph_search, '_get_cross_encoder', return_value=ce):
            results = graph_search.rerank('Exact Alias related notes', candidates, top_k=1)

        self.assertEqual(results[0]['alias_boost'], 0.0)

    def test_alias_backed_phrase_matched_candidate_gets_rerank_boost(self):
        candidates = [
            _candidate(
                'Plain',
                phrase_matched=False,
                matched_phrase='',
                source='dense',
            ),
            _candidate(
                'Phrase Gold',
                alias_matched=True,
                matched_alias='Vector Embedding Semantic Search',
                phrase_matched=True,
                matched_phrase='semantic search',
                source='phrase',
            ),
        ]
        ce = MagicMock()
        ce.predict.return_value = [0.5, 0.5]

        with patch.object(graph_search, '_get_cross_encoder', return_value=ce):
            results = graph_search.rerank('의미 검색', candidates, top_k=2)

        self.assertEqual([result['entity'] for result in results], ['Phrase Gold', 'Plain'])
        self.assertGreater(results[0]['phrase_boost'], 0.0)

    def test_entity_phrase_match_does_not_get_rerank_boost(self):
        candidates = [
            _candidate(
                'Plain',
                phrase_matched=False,
                matched_phrase='',
                source='dense',
            ),
            _candidate(
                'Entity Phrase',
                phrase_matched=True,
                matched_phrase='generic phrase',
                source='phrase',
            ),
        ]
        ce = MagicMock()
        ce.predict.return_value = [0.5, 0.5]

        with patch.object(graph_search, '_get_cross_encoder', return_value=ce):
            results = graph_search.rerank('generic phrase', candidates, top_k=2)

        phrase_result = next(result for result in results if result['entity'] == 'Entity Phrase')
        self.assertEqual(phrase_result['phrase_boost'], 0.0)

    def test_alias_matched_candidate_gets_hybrid_score_boost(self):
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE entities (
                id TEXT PRIMARY KEY,
                name TEXT,
                type TEXT,
                description TEXT,
                source_note TEXT,
                centrality_score REAL
            );
            CREATE TABLE entity_aliases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_id TEXT NOT NULL,
                alias_name TEXT NOT NULL,
                alias_type TEXT DEFAULT 'manual',
                UNIQUE(entity_id, alias_name)
            );
            """
        )
        conn.execute(
            "INSERT INTO entities (id, name, type, description, source_note, centrality_score) VALUES ('gold', 'Alias Gold', 'concept', '', 'gold.md', 0.0)"
        )
        conn.execute(
            "INSERT INTO entity_aliases (entity_id, alias_name, alias_type) VALUES ('gold', 'Exact Alias', 'frontmatter')"
        )
        conn.commit()

        with patch.object(graph_search, '_EMBEDDING_AVAILABLE', False), \
             patch.object(graph_search, 'fts5_search', return_value=[]), \
             patch.object(graph_search, '_decompose_query', return_value=[]), \
             patch.object(graph_search, 'get_bulk_rel_strengths', return_value={}):
            results = graph_search.hybrid_search(
                conn,
                'Exact Alias',
                top_k=5,
                dense_weight=0.0,
                sparse_weight=0.0,
                decomposed_weight=0.0,
                entity_weight=0.0,
            )

        conn.close()
        self.assertEqual(results[0]['entity'], 'Alias Gold')
        self.assertTrue(results[0]['alias_matched'])
        self.assertGreater(results[0]['alias_boost'], 0.0)
        self.assertGreater(results[0]['score'], results[0]['rrf_raw'])


class ExactPhraseCandidateTest(unittest.TestCase):
    def setUp(self):
        if hasattr(graph_search, 'clear_hybrid_cache'):
            graph_search.clear_hybrid_cache()

    def tearDown(self):
        if hasattr(graph_search, 'clear_hybrid_cache'):
            graph_search.clear_hybrid_cache()

    def _conn(self):
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE entities (
                id TEXT PRIMARY KEY,
                name TEXT,
                type TEXT,
                description TEXT,
                source_note TEXT,
                centrality_score REAL
            );
            CREATE TABLE entity_aliases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_id TEXT NOT NULL,
                alias_name TEXT NOT NULL,
                alias_type TEXT DEFAULT 'manual',
                UNIQUE(entity_id, alias_name)
            );
            """
        )
        return conn

    def test_multi_token_cross_lingual_phrase_in_alias_enters_candidates(self):
        conn = self._conn()
        conn.execute(
            "INSERT INTO entities (id, name, type, description, source_note, centrality_score) VALUES ('gold', 'Vector Gold', 'concept', '', 'gold.md', 0.0)"
        )
        conn.execute(
            "INSERT INTO entity_aliases (entity_id, alias_name, alias_type) VALUES ('gold', 'Vector Embedding Semantic Search', 'frontmatter')"
        )
        conn.commit()

        with patch.object(graph_search, '_EMBEDDING_AVAILABLE', False), \
             patch.object(graph_search, 'fts5_search', return_value=[]), \
             patch.object(graph_search, '_decompose_query', return_value=[]), \
             patch.object(graph_search, 'get_bulk_rel_strengths', return_value={}):
            results = graph_search.hybrid_search(
                conn,
                '벡터 임베딩 의미 검색',
                top_k=5,
                dense_weight=0.0,
                sparse_weight=0.0,
                decomposed_weight=0.0,
                entity_weight=0.0,
            )

        conn.close()
        self.assertEqual(results[0]['entity'], 'Vector Gold')
        self.assertIn('phrase', results[0]['source'])
        self.assertEqual(results[0]['phrase_rank'], 1)
        self.assertEqual(results[0]['matched_phrase'], 'vector embedding')

    def test_single_token_alias_does_not_enter_phrase_channel(self):
        conn = self._conn()
        conn.execute(
            "INSERT INTO entities (id, name, type, description, source_note, centrality_score) VALUES ('noise', 'Vector Noise', 'concept', '', 'noise.md', 0.0)"
        )
        conn.execute(
            "INSERT INTO entity_aliases (entity_id, alias_name, alias_type) VALUES ('noise', 'vector', 'frontmatter')"
        )
        conn.commit()

        with patch.object(graph_search, '_EMBEDDING_AVAILABLE', False), \
             patch.object(graph_search, 'fts5_search', return_value=[]), \
             patch.object(graph_search, '_decompose_query', return_value=[]), \
             patch.object(graph_search, 'get_bulk_rel_strengths', return_value={}):
            results = graph_search.hybrid_search(
                conn,
                '벡터',
                top_k=5,
                dense_weight=0.0,
                sparse_weight=0.0,
                decomposed_weight=0.0,
                entity_weight=0.0,
            )

        conn.close()
        self.assertTrue(results)
        self.assertNotIn('phrase', results[0]['source'])
        self.assertIsNone(results[0]['phrase_rank'])

    def test_unmapped_broad_phrase_does_not_enter_phrase_channel(self):
        phrases = graph_search._exact_phrase_queries('Anthropic AI Safety 관련 연구')

        self.assertNotIn('anthropic ai', phrases)
        self.assertNotIn('ai safety', phrases)

    def test_cross_lingual_phrase_normalizes_separators(self):
        conn = self._conn()
        conn.execute(
            "INSERT INTO entities (id, name, type, description, source_note, centrality_score) VALUES ('gold', 'Agent Gold', 'concept', '', 'gold.md', 0.0)"
        )
        conn.execute(
            "INSERT INTO entity_aliases (entity_id, alias_name, alias_type) VALUES ('gold', 'Orchestrator-Workers Pattern', 'frontmatter')"
        )
        conn.commit()

        with patch.object(graph_search, '_EMBEDDING_AVAILABLE', False), \
             patch.object(graph_search, 'fts5_search', return_value=[]), \
             patch.object(graph_search, '_decompose_query', return_value=[]), \
             patch.object(graph_search, 'get_bulk_rel_strengths', return_value={}):
            results = graph_search.hybrid_search(
                conn,
                'agent orchestration patterns',
                top_k=5,
                dense_weight=0.0,
                sparse_weight=0.0,
                decomposed_weight=0.0,
                entity_weight=0.0,
            )

        conn.close()
        self.assertEqual(results[0]['entity'], 'Agent Gold')
        self.assertIn('phrase', results[0]['source'])
        self.assertEqual(results[0]['matched_phrase'], 'orchestrator workers pattern')

    def test_more_specific_mapped_phrase_not_starved_by_broad_earlier_phrase(self):
        conn = self._conn()
        for idx in range(3):
            conn.execute(
                "INSERT INTO entities (id, name, type, description, source_note, centrality_score) VALUES (?, ?, 'concept', ?, ?, ?)",
                (
                    f'broad-{idx}',
                    f'Broad Agent Orchestration {idx}',
                    'agent orchestration overview',
                    f'broad-{idx}.md',
                    1.0 - idx * 0.1,
                ),
            )
        conn.execute(
            "INSERT INTO entities (id, name, type, description, source_note, centrality_score) VALUES ('gold', 'Agent Gold', 'concept', '', 'gold.md', 0.0)"
        )
        conn.execute(
            "INSERT INTO entity_aliases (entity_id, alias_name, alias_type) VALUES ('gold', 'Orchestrator-Workers Pattern', 'frontmatter')"
        )
        conn.commit()

        results = graph_search._exact_phrase_search(conn, 'agent orchestration patterns', limit=2)

        conn.close()
        self.assertIn('Agent Gold', [result['name'] for result in results])
        gold = next(result for result in results if result['name'] == 'Agent Gold')
        self.assertEqual(gold['matched_phrase'], 'orchestrator workers pattern')


class LlmSynthesisTest(unittest.TestCase):
    def test_llm_completion_returns_none_when_disabled(self):
        with patch.dict("os.environ", {"GRAPHRAG_LLM_ENABLED": "0"}), \
             patch("httpx.post", side_effect=AssertionError("provider should not be called")):
            self.assertIsNone(graph_search._llm_completion("prompt", max_tokens=123))

    def test_llm_completion_returns_none_when_httpx_missing(self):
        with patch.dict("os.environ", {"GRAPHRAG_LLM_ENABLED": "1"}), \
             patch.dict("sys.modules", {"httpx": None}):
            self.assertIsNone(graph_search._llm_completion("prompt", max_tokens=123))

    def test_llm_completion_uses_anthropic_compatible_proxy_when_enabled(self):
        response = MagicMock()
        response.json.return_value = {"content": [{"type": "text", "text": "synthesized answer"}]}
        captured = {}

        def fake_post(url, headers, json, timeout):
            captured.update({"url": url, "headers": headers, "json": json, "timeout": timeout})
            return response

        with patch.dict(
            "os.environ",
            {
                "GRAPHRAG_LLM_ENABLED": "1",
                "GRAPHRAG_LLM_API_BASE": "http://llm.test",
                "GRAPHRAG_LLM_API_KEY": "test-key",
                "GRAPHRAG_LLM_MODEL": "cheap-model",
                "GRAPHRAG_LLM_TIMEOUT": "3",
            },
        ), patch("httpx.post", side_effect=fake_post):
            text = graph_search._llm_completion("prompt", max_tokens=123)

        self.assertEqual(text, "synthesized answer")
        self.assertEqual(captured["url"], "http://llm.test/v1/messages")
        self.assertEqual(captured["headers"]["x-api-key"], "test-key")
        self.assertEqual(captured["json"]["model"], "cheap-model")
        self.assertEqual(captured["json"]["max_tokens"], 123)
        self.assertEqual(captured["timeout"], 3.0)
        response.raise_for_status.assert_called_once()

    def test_llm_completion_uses_default_timeout_when_env_invalid(self):
        response = MagicMock()
        response.json.return_value = {"content": [{"type": "text", "text": "fallback timeout answer"}]}
        captured = {}

        def fake_post(url, headers, json, timeout):
            captured["timeout"] = timeout
            return response

        with patch.dict(
            "os.environ",
            {
                "GRAPHRAG_LLM_ENABLED": "1",
                "GRAPHRAG_LLM_API_BASE": "http://llm.test",
                "GRAPHRAG_LLM_TIMEOUT": "bad",
            },
        ), patch("httpx.post", side_effect=fake_post):
            text = graph_search._llm_completion("prompt", max_tokens=123)

        self.assertEqual(text, "fallback timeout answer")
        self.assertEqual(captured["timeout"], 10.0)

    def test_llm_completion_uses_codex_cli_provider_when_enabled(self):
        completed = MagicMock()
        completed.returncode = 0
        completed.stdout = "progress log ignored"
        completed.stderr = ''
        captured = {}

        def fake_run(cmd, **kwargs):
            captured.update({"cmd": cmd, **kwargs})
            output_path = cmd[cmd.index("-o") + 1]
            Path(output_path).write_text("codex synthesis\n", encoding="utf-8")
            return completed

        with patch.dict(
            "os.environ",
            {
                "GRAPHRAG_LLM_ENABLED": "1",
                "GRAPHRAG_LLM_PROVIDER": "codex_cli",
                "GRAPHRAG_LLM_MODEL": "gpt-5.5",
                "GRAPHRAG_LLM_TIMEOUT": "13",
                "OPENAI_API_KEY": "must-not-leak",
                "ANTHROPIC_API_KEY": "must-not-leak",
            },
        ), patch("subprocess.run", side_effect=fake_run), \
             patch("httpx.post", side_effect=AssertionError("http provider should not be called")):
            text = graph_search._llm_completion("prompt text", max_tokens=123)

        self.assertEqual(text, "codex synthesis")
        self.assertEqual(captured["cmd"][0:2], ["codex", "exec"])
        self.assertIn("--ephemeral", captured["cmd"])
        self.assertIn("--skip-git-repo-check", captured["cmd"])
        self.assertIn("--ignore-user-config", captured["cmd"])
        self.assertIn("--ignore-rules", captured["cmd"])
        self.assertEqual(captured["cmd"][captured["cmd"].index("--sandbox") + 1], "read-only")
        self.assertEqual(captured["cmd"][captured["cmd"].index("-C") + 1], "/tmp")
        self.assertEqual(captured["cmd"][captured["cmd"].index("-m") + 1], "gpt-5.5")
        self.assertEqual(captured["cmd"][-1], "-")
        self.assertEqual(captured["input"], "prompt text")
        self.assertEqual(captured["timeout"], 13.0)
        self.assertEqual(captured["cwd"], "/tmp")
        self.assertNotIn("OPENAI_API_KEY", captured["env"])
        self.assertNotIn("ANTHROPIC_API_KEY", captured["env"])
        self.assertTrue(captured["capture_output"])
        self.assertTrue(captured["text"])
        self.assertFalse(Path(captured["cmd"][captured["cmd"].index("-o") + 1]).exists())

    def test_llm_completion_codex_cli_returns_none_on_empty_output(self):
        completed = MagicMock()
        completed.returncode = 0
        completed.stdout = ""
        completed.stderr = ''

        def fake_run(cmd, **kwargs):
            Path(cmd[cmd.index("-o") + 1]).write_text("", encoding="utf-8")
            return completed

        with patch.dict(
            "os.environ",
            {"GRAPHRAG_LLM_ENABLED": "1", "GRAPHRAG_LLM_PROVIDER": "codex_cli"},
        ), patch("subprocess.run", side_effect=fake_run):
            self.assertIsNone(graph_search._llm_completion("prompt", max_tokens=123))

    def test_llm_completion_codex_cli_returns_none_on_nonzero_exit(self):
        completed = MagicMock()
        completed.returncode = 1
        completed.stdout = ""
        completed.stderr = "error"

        def fake_run(cmd, **kwargs):
            Path(cmd[cmd.index("-o") + 1]).write_text("should not be used", encoding="utf-8")
            return completed

        with patch.dict(
            "os.environ",
            {"GRAPHRAG_LLM_ENABLED": "1", "GRAPHRAG_LLM_PROVIDER": "codex_cli"},
        ), patch("subprocess.run", side_effect=fake_run):
            self.assertIsNone(graph_search._llm_completion("prompt", max_tokens=123))

    def test_llm_completion_codex_cli_returns_none_on_oversize_output(self):
        completed = MagicMock()
        completed.returncode = 0
        completed.stdout = ""
        completed.stderr = ''

        def fake_run(cmd, **kwargs):
            Path(cmd[cmd.index("-o") + 1]).write_text("too long", encoding="utf-8")
            return completed

        with patch.dict(
            "os.environ",
            {
                "GRAPHRAG_LLM_ENABLED": "1",
                "GRAPHRAG_LLM_PROVIDER": "codex_cli",
                "GRAPHRAG_LLM_CODEX_MAX_OUTPUT_CHARS": "3",
            },
        ), patch("subprocess.run", side_effect=fake_run):
            self.assertIsNone(graph_search._llm_completion("prompt", max_tokens=123))

    def test_llm_completion_codex_cli_returns_none_on_timeout(self):
        import subprocess

        with patch.dict(
            "os.environ",
            {"GRAPHRAG_LLM_ENABLED": "1", "GRAPHRAG_LLM_PROVIDER": "codex_cli"},
        ), patch("subprocess.run", side_effect=subprocess.TimeoutExpired(["codex"], 1)):
            self.assertIsNone(graph_search._llm_completion("prompt", max_tokens=123))

    def test_llm_completion_codex_cli_uses_concurrency_bound(self):
        class FakeSemaphore:
            entered = False
            exited = False

            def __enter__(self):
                self.entered = True
                return self

            def __exit__(self, exc_type, exc, tb):
                self.exited = True

        completed = MagicMock()
        completed.returncode = 0
        completed.stdout = ""
        completed.stderr = ''
        semaphore = FakeSemaphore()

        def fake_run(cmd, **kwargs):
            Path(cmd[cmd.index("-o") + 1]).write_text("bounded codex", encoding="utf-8")
            return completed

        with patch.dict(
            "os.environ",
            {"GRAPHRAG_LLM_ENABLED": "1", "GRAPHRAG_LLM_PROVIDER": "codex_cli"},
        ), patch.object(graph_search, "_get_codex_cli_semaphore", return_value=semaphore, create=True), \
             patch("subprocess.run", side_effect=fake_run):
            text = graph_search._llm_completion("prompt", max_tokens=123)

        self.assertEqual(text, "bounded codex")
        self.assertTrue(semaphore.entered)
        self.assertTrue(semaphore.exited)

    def test_llm_completion_returns_none_on_http_error(self):
        response = MagicMock()
        response.raise_for_status.side_effect = RuntimeError("http error")

        with patch.dict("os.environ", {"GRAPHRAG_LLM_ENABLED": "1"}), \
             patch("httpx.post", return_value=response):
            self.assertIsNone(graph_search._llm_completion("prompt", max_tokens=123))

    def test_llm_completion_returns_none_on_invalid_provider_json(self):
        response = MagicMock()
        response.json.side_effect = ValueError("bad json")

        with patch.dict("os.environ", {"GRAPHRAG_LLM_ENABLED": "1"}), \
             patch("httpx.post", return_value=response):
            self.assertIsNone(graph_search._llm_completion("prompt", max_tokens=123))

    def test_llm_completion_returns_none_on_empty_provider_content(self):
        response = MagicMock()
        response.json.return_value = {"content": []}

        with patch.dict("os.environ", {"GRAPHRAG_LLM_ENABLED": "1"}), \
             patch("httpx.post", return_value=response):
            self.assertIsNone(graph_search._llm_completion("prompt", max_tokens=123))

    def test_llm_synthesize_returns_model_text_when_enabled(self):
        with patch.object(graph_search, "_llm_completion", return_value="actual synthesis"):
            self.assertEqual(graph_search._llm_synthesize("prompt"), "actual synthesis")

    def test_llm_map_answer_parses_json_response(self):
        payload = '{"answer": "community answer", "relevance_score": 0.7, "key_entities": ["Alpha"]}'

        with patch.object(graph_search, "_llm_completion", return_value=payload):
            result = graph_search._llm_map_answer("prompt")

        self.assertEqual(result["answer"], "community answer")
        self.assertEqual(result["relevance_score"], 0.7)
        self.assertEqual(result["key_entities"], ["Alpha"])

    def test_llm_map_answer_returns_fallback_for_invalid_json(self):
        with patch.object(graph_search, "_llm_completion", return_value="not json"):
            result = graph_search._llm_map_answer("prompt")

        self.assertEqual(result, graph_search._LLM_MAP_FALLBACK)


class GlobalSearchCostCapTest(unittest.TestCase):
    def test_global_search_caps_selected_level_communities(self):
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        conn.execute(
            'CREATE TABLE communities (id INTEGER PRIMARY KEY, name TEXT, summary TEXT, member_entity_ids TEXT, level INTEGER)'
        )
        conn.execute(
            'CREATE TABLE entities (id TEXT PRIMARY KEY, name TEXT, type TEXT, description TEXT)'
        )
        for idx in range(5):
            entity_id = f'e{idx}'
            conn.execute(
                'INSERT INTO entities (id, name, type, description) VALUES (?, ?, ?, ?)',
                (entity_id, f'Entity {idx}', 'note', f'Entity {idx} description'),
            )
            conn.execute(
                'INSERT INTO communities (id, name, summary, member_entity_ids, level) VALUES (?, ?, ?, ?, ?)',
                (idx, f'Community {idx}', 'summary', f'["{entity_id}"]', 1),
            )
        conn.commit()

        with patch.dict("os.environ", {"GRAPHRAG_GLOBAL_MAX_COMMUNITIES": "3"}), \
             patch.object(
                 graph_search,
                 "_llm_map_answer",
                 return_value={"answer": "mapped", "relevance_score": 0.5, "key_entities": []},
             ) as map_answer, \
             patch.object(graph_search, "_llm_synthesize", return_value="synthesized"):
            result = graph_search.global_search(conn, MagicMock(), "broad question", community_level=1)

        self.assertEqual(map_answer.call_count, 3)
        self.assertEqual(result["communities_analyzed"], 3)
        conn.close()


class TypedRelationRescoreTest(unittest.TestCase):
    def test_typed_relation_rescore_boosts_connected_results_deterministically(self):
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        conn.execute('CREATE TABLE entities (id TEXT PRIMARY KEY, name TEXT)')
        conn.execute(
            'CREATE TABLE relationships (source_id TEXT, target_id TEXT, type TEXT, strength REAL)'
        )
        conn.executemany(
            'INSERT INTO entities (id, name) VALUES (?, ?)',
            [('a', 'Alpha'), ('b', 'Beta'), ('c', 'Gamma')],
        )
        conn.executemany(
            'INSERT INTO relationships (source_id, target_id, type, strength) VALUES (?, ?, ?, ?)',
            [('a', 'b', 'parent', 1.0), ('a', 'c', 'sourced_from', 1.0)],
        )
        results = [
            {'entity': 'Beta', 'rerank_score': 0.3},
            {'entity': 'Gamma', 'rerank_score': 0.2},
            {'entity': 'Alpha', 'rerank_score': 0.1},
        ]

        rescored = graph_search.typed_relation_rescore(results, conn, graph_search.QueryLevel.L1)

        # v2: 큰 rerank 격차(0.1+)는 뒤집지 않는다 — Alpha는 2 edge여도 cap 0.04까지만.
        self.assertEqual([r['entity'] for r in rescored], ['Beta', 'Gamma', 'Alpha'])
        alpha = next(r for r in rescored if r['entity'] == 'Alpha')
        self.assertAlmostEqual(alpha['typed_relation_boost'], graph_search._TYPED_RESCORE_CAP)
        self.assertEqual(alpha['typed_relation_types'], ['parent', 'sourced_from'])

        # v2: 근소 격차(δ 미만)는 high-class edge가 뒤집을 수 있다 (결정적).
        near = [
            {'entity': 'Beta', 'rerank_score': 0.21},
            {'entity': 'Alpha', 'rerank_score': 0.2},
            {'entity': 'Gamma', 'rerank_score': 0.1},
        ]
        rescored2 = graph_search.typed_relation_rescore(near, conn, graph_search.QueryLevel.L1)
        self.assertEqual([r['entity'] for r in rescored2][0], 'Alpha')
        conn.close()

    def test_typed_relation_rescore_skips_l0(self):
        conn = sqlite3.connect(':memory:')
        results = [{'entity': 'Alpha', 'rerank_score': 0.1}, {'entity': 'Beta', 'rerank_score': 0.9}]

        rescored = graph_search.typed_relation_rescore(results, conn, graph_search.QueryLevel.L0)

        self.assertEqual([r['entity'] for r in rescored], ['Alpha', 'Beta'])
        self.assertNotIn('typed_relation_boost', rescored[0])
        conn.close()


if __name__ == '__main__':
    unittest.main()
