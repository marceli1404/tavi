"""Regression checks for the opt-in token-efficient control wire format."""
import copy
import io
import json
import unittest
from datetime import datetime, timezone, timedelta

from tavi_control_compact import compact_batch
from tavi_control_matrix import matrix_batch, expand_matrix
from tavi_control_stream import run
from tavi_controls import resolve_many


class ControlMatrixTests(unittest.TestCase):
    def fixture(self, *, count=24, age=0, duplicate=False, offline=False):
        control = dict(id='run', label='Run', role='button', context='Toolbar',
                       visible=True, enabled=True, bounds=[10, 20, 80, 30])
        snapshot = dict(format='tavi-control-snapshot-v1', snapshot_id='frame-4',
                        captured_at=(datetime.now(timezone.utc)-timedelta(seconds=age)).isoformat(),
                        source='supported_browser_dom', viewport=[1280, 720],
                        controls=[control])
        if duplicate:
            snapshot['controls'].append(dict(control, id='run-other'))
        queries = [dict(task=f'Run task {i}', target='Run' if i % 3 else 'Missing',
                        role='button', context='Toolbar', id=f'q{i}') for i in range(count)]
        return snapshot, queries, resolve_many(snapshot, queries, offline=offline)

    def test_round_trip_match_missing_duplicate_stale_and_offline(self):
        cases = ({}, {'duplicate': True}, {'age': 7}, {'age': -10}, {'offline': True})
        for options in cases:
            with self.subTest(options=options):
                _, _, batch = self.fixture(**options)
                before = copy.deepcopy(batch)
                matrix = matrix_batch(batch)
                self.assertEqual(expand_matrix(matrix), batch)
                self.assertEqual(batch, before)
                self.assertTrue(matrix['requires_live_host_check'])
                self.assertFalse(matrix['authorization_granted'])
                self.assertFalse(matrix['executed_actions'])

    def test_optional_query_id_and_independent_candidates(self):
        _, _, batch = self.fixture(count=4)
        batch['proposals'][1].pop('query_id')
        matrix = matrix_batch(batch)
        self.assertEqual(expand_matrix(matrix), batch)
        matrix['rows'][1][5]['bounds'][0] = 999  # candidate is not shared
        self.assertEqual(batch['proposals'][0]['candidate'], None)
        self.assertEqual(batch['proposals'][1]['candidate']['bounds'][0], 10)

    def test_authority_flags_never_promoted(self):
        _, _, batch = self.fixture()
        for location in ('batch', 'proposal'):
            changed = copy.deepcopy(batch)
            (changed if location == 'batch' else changed['proposals'][0])['authorization_granted'] = True
            with self.assertRaises(ValueError):
                matrix_batch(changed)
        matrix = matrix_batch(batch)
        matrix['authorization_granted'] = True
        with self.assertRaises(ValueError):
            expand_matrix(matrix)

    def test_wire_bytes_smaller_than_lossless_compact_for_many_queries(self):
        _, _, batch = self.fixture(count=64)
        encode = lambda x: json.dumps(x, ensure_ascii=False, separators=(',', ':'))
        full = len(encode(batch).encode('utf-8'))
        compact = len(encode(compact_batch(batch)).encode('utf-8'))
        matrix = len(encode(matrix_batch(batch)).encode('utf-8'))
        self.assertLess(matrix, compact)
        self.assertLess(compact, full)

    def test_stream_opt_in_and_backward_compatibility(self):
        snapshot, queries, batch = self.fixture(count=5)
        payload = [dict(id='matrix-1', snapshot=snapshot, queries=queries, compact='matrix'),
                   dict(id='compact-1', snapshot=snapshot, queries=queries, compact=True),
                   dict(id='default-1', snapshot=snapshot, queries=queries),
                   dict(snapshot=snapshot, queries=queries, compact='unsupported')]
        output = io.StringIO()
        self.assertEqual(run(io.StringIO(''.join(json.dumps(x)+'\n' for x in payload)), output), 0)
        events = [json.loads(line) for line in output.getvalue().splitlines()]
        matrix = events[1]
        self.assertEqual(matrix['format'], 'tavi-control-matrix-v1')
        self.assertEqual(matrix['request_id'], 'matrix-1')
        self.assertIs(matrix['observation_reused'], False)
        matrix.pop('request_id')
        matrix.pop('observation_reused')
        restored = expand_matrix(matrix)
        for p in restored['proposals']:
            p.pop('age_seconds')
        for p in batch['proposals']:
            p.pop('age_seconds')
        self.assertEqual(restored, batch)
        self.assertEqual(events[2]['format'], 'tavi-control-batch-compact-v1')
        self.assertEqual(events[3]['format'], 'tavi-control-batch-v1')
        self.assertEqual(events[4]['status'], 'error')


if __name__ == '__main__':
    unittest.main()
