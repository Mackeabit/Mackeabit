from datetime import date
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


claude = load('claude_activity')
ai = load('ai_activity')
TODAY = date(2026, 11, 28)


def line(msg_id, req, stamp, output=10, cache_read=100, kind='assistant'):
    return json.dumps({'type': kind, 'requestId': req, 'timestamp': stamp, 'cwd': '/home/secret-project',
                       'message': {'id': msg_id, 'model': 'claude-opus-5-5', 'content': [{'text': 'private'}],
                                   'usage': {'input_tokens': 1, 'output_tokens': output,
                                             'cache_creation_input_tokens': 5, 'cache_read_input_tokens': cache_read}}})


class CollectTests(unittest.TestCase):
    def collect(self, files):
        with tempfile.TemporaryDirectory() as tmp:
            for i, lines in enumerate(files):
                path = Path(tmp) / 'projects' / f'p{i}' / 'session.jsonl'
                path.parent.mkdir(parents=True)
                path.write_text('\n'.join(lines) + '\nnot json\n', encoding='utf-8')
            return claude.collect([Path(tmp)], TODAY)

    def test_repeated_responses_count_once_across_files(self):
        first = [line('m1', 'r1', '2026-11-26T10:00:00Z', output=3), line('m1', 'r1', '2026-11-26T10:00:01Z', output=10)]
        resumed = [line('m1', 'r1', '2026-11-26T10:00:00Z', output=10), line('m2', 'r2', '2026-11-27T23:59:59Z')]
        self.assertEqual(self.collect([first, resumed]), {'2026-11-26': 116, '2026-11-27': 116})

    def test_today_and_user_lines_are_excluded_and_days_use_utc(self):
        lines = [line('m1', 'r1', '2026-11-28T00:00:00Z'), line('m2', 'r2', '2026-11-27T15:30:00Z', kind='user'),
                 line('m3', 'r3', '2026-11-28T08:00:00+09:00')]
        self.assertEqual(self.collect([lines]), {'2026-11-27': 116})


class PublishShapeTests(unittest.TestCase):
    def test_merge_never_shrinks_published_days(self):
        data = claude.build('0a1b2c3d', {'2026-11-26': 50, '2026-11-27': 300}, {'2026-11-01': 7, '2026-11-26': 90})
        self.assertEqual(data['days'], [{'date': '2026-11-01', 'tokens': 7}, {'date': '2026-11-26', 'tokens': 90},
                                        {'date': '2026-11-27', 'tokens': 300}])
        self.assertEqual(data['dataThrough'], '2026-11-27')

    def test_empty_usage_is_refused(self):
        with self.assertRaises(ValueError): claude.build('0a1b2c3d', {}, {})

    def test_only_dates_totals_and_random_host_are_exported(self):
        text = claude.render(claude.build('0a1b2c3d', {'2026-11-27': 116}, {}))
        self.assertEqual(set(json.loads(text)), {'schema', 'source', 'host', 'dataThrough', 'days'})
        for private in ('secret-project', 'claude-opus', 'private', 'm1'): self.assertNotIn(private, text)

    def test_published_copy_is_validated(self):
        good = claude.build('0a1b2c3d', {'2026-11-27': 1}, {})
        self.assertEqual(claude.validate(good, '0a1b2c3d', TODAY), {'2026-11-27': 1})
        for bad in ({**good, 'host': 'ffffffff'}, {**good, 'days': [{'date': '2026-11-28', 'tokens': 1}]},
                    {**good, 'days': [{'date': '2026-11-27', 'tokens': -1}]}):
            with self.assertRaises(ValueError): claude.validate(bad, '0a1b2c3d', TODAY)


class CombineTests(unittest.TestCase):
    codex = {'schema': 1, 'dataThrough': '2026-11-26', 'days': [{'date': '2026-11-25', 'tokens': 10}, {'date': '2026-11-26', 'tokens': 20}]}

    def host(self, host, days):
        return {f'{host}.json': {'schema': 1, 'host': host, 'days': [{'date': d, 'tokens': n} for d, n in days]}}

    def test_sums_codex_and_every_host_per_day(self):
        hosts = {**self.host('0a1b2c3d', [('2026-11-26', 5), ('2026-11-27', 7)]), **self.host('ffff0000', [('2026-11-26', 1)])}
        result = ai.combine(self.codex, hosts, TODAY)
        self.assertEqual(result['days'], [{'date': '2026-11-25', 'tokens': 10}, {'date': '2026-11-26', 'tokens': 26},
                                          {'date': '2026-11-27', 'tokens': 7}])
        self.assertEqual((result['dataThrough'], result['sources']), ('2026-11-27', 3))

    def test_works_with_either_source_missing(self):
        self.assertEqual(ai.combine(None, self.host('0a1b2c3d', [('2026-11-27', 7)]), TODAY)['dataThrough'], '2026-11-27')
        self.assertEqual(ai.combine(self.codex, {}, TODAY)['dataThrough'], '2026-11-26')

    def test_rejects_mislabelled_future_or_duplicate_host_data(self):
        for files in ({'0a1b2c3d.json': self.host('ffff0000', [('2026-11-26', 1)])['ffff0000.json']},
                      self.host('0a1b2c3d', [('2026-11-29', 1)]),
                      self.host('0a1b2c3d', [('2026-11-26', 1), ('2026-11-26', 2)]),
                      {'laptop.json': {'schema': 1, 'host': 'laptop', 'days': []}}):
            with self.assertRaises(ValueError): ai.combine(self.codex, files, TODAY)


if __name__ == '__main__': unittest.main()
