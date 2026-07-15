import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


class BenchmarkJudgeGoldNotesTest(unittest.TestCase):
    def test_load_gold_notes_reads_all_queries_from_runner(self):
        import benchmark_judge

        gold = benchmark_judge.load_gold_notes(SCRIPTS_DIR / 'benchmark_runner.py')

        self.assertEqual(len(gold), 24)
        self.assertEqual(gold['Q01'], ['GraphRAG-Theory-MOC', 'Obsidian-GraphRAG-Journey-MOC'])
        self.assertEqual(gold['Q18'], ['얼룩소-아카이브-MOC', 'AI-기술-MOC', '정치-민주주의-MOC'])
        self.assertEqual(gold['Q23'], ['Agent-Teams-아키텍처', 'Building-Effective-Agents-Orchestrator-Workers', 'Claude-46-Subagent-Orchestration'])
        self.assertEqual(gold['Q24'], ['임베딩과-벡터공간-기하학'])


class BenchmarkJudgeCliTest(unittest.TestCase):
    def test_cli_writes_judges_json_shape(self):
        sample = {
            'queries': [
                {
                    'id': 'Q01',
                    'query': 'GraphRAG',
                    'top_5_results': [
                        {'rank': 1, 'name': 'GraphRAG-Theory-MOC', 'score': 0.99, 'confidence': 'high'},
                        {'rank': 2, 'name': 'Obsidian-GraphRAG-Journey-MOC', 'score': 0.97, 'confidence': 'high'},
                        {'rank': 3, 'name': 'GraphRAG-Overview', 'score': 0.72, 'confidence': 'medium'},
                        {'rank': 4, 'name': 'Obsidian-Automation', 'score': 0.51, 'confidence': 'medium'},
                        {'rank': 5, 'name': 'Random-Note', 'score': 0.10, 'confidence': 'low'},
                    ],
                    'total_results': 5,
                }
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / 'benchmark.json'
            output_path = Path(tmpdir) / 'judges.json'
            input_path.write_text(json.dumps(sample, ensure_ascii=False), encoding='utf-8')

            proc = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / 'benchmark_judge.py'), str(input_path), '--output', str(output_path)],
                capture_output=True,
                text=True,
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            judges = json.loads(output_path.read_text(encoding='utf-8'))

        self.assertIn('queries', judges)
        self.assertIn('Q01', judges['queries'])
        q1 = judges['queries']['Q01']
        self.assertEqual(q1['result_count'], 5)
        self.assertIn('opus', q1)
        self.assertIn('gpt54', q1)
        self.assertGreaterEqual(q1['opus']['ranking'], 8.5)
        self.assertGreaterEqual(q1['gpt54']['ranking'], 8.5)
        self.assertGreater(q1['opus']['relevance_avg'], 0)
        self.assertGreaterEqual(q1['opus']['confidence_matches'], 3)


if __name__ == '__main__':
    unittest.main()
