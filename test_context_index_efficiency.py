"""Safe context-index elision and resolution correctness on large host inventories."""
from datetime import datetime,timedelta,timezone
import unittest

from tavi_controls import ControlIndex,resolve_many
from benchmarks.context_index_efficiency import benchmark,snapshot,queries


class IndexedLookupTests(unittest.TestCase):
    def test_unscoped_results_identical_to_full_context_index(self):
        state=snapshot(128)
        cases=queries(128)
        now=datetime.now(timezone.utc)
        full=ControlIndex(state,context_index=True)
        lean=ControlIndex(state,context_index=False)
        self.assertEqual(full.snapshot_sha256,lean.snapshot_sha256)
        actual=resolve_many(state,cases,now=now)
        for query,resolved in zip(cases,actual['proposals']):
            expected=full.resolve(query['task'],query['target'],now=now)
            alternative=lean.resolve(query['task'],query['target'],now=now)
            self.assertEqual(resolved['reason'],expected['reason'])
            self.assertEqual(alternative,expected)
            self.assertFalse(resolved['authorization_granted'])
            self.assertFalse(resolved['executed_actions'])

    def test_context_scoped_batch_requires_index_and_remains_exact(self):
        state=snapshot(16)
        state['controls'][1]['label']=state['controls'][0]['label']
        query=dict(task='Inspect current button',
                   target=state['controls'][0]['label'],role='button',
                   context=state['controls'][0]['context'])
        resolved=resolve_many(state,[query])
        self.assertEqual(resolved['proposals'][0]['reason'],'unique_exact_control')
        self.assertEqual(resolved['proposals'][0]['candidate']['id'],
                         state['controls'][0]['id'])
        with self.assertRaisesRegex(ValueError,'cannot resolve context-scoped'):
            ControlIndex(state,context_index=False).resolve(
                query['task'],query['target'],context=query['context'])

    def test_ambiguous_controls_do_not_become_unique(self):
        state=snapshot(16)
        state['controls'][1]['label']=state['controls'][0]['label']
        result=resolve_many(state,[dict(task='Inspect',target=state['controls'][0]['label'])])
        self.assertEqual(result['proposals'][0]['reason'],'ambiguous_control')
        self.assertIsNone(result['proposals'][0]['candidate'])

    def test_validates_full_inventory_when_context_index_skipped(self):
        original=snapshot(16)
        invalid=[]
        dup=snapshot(16)
        dup['controls'][1]['id']=dup['controls'][0]['id']
        invalid.append(dup)
        state=snapshot(16)
        state['controls'][2]['context']=None
        invalid.append(state)
        state=snapshot(16)
        state['controls'][5]['bounds']=[0,0,-2,20]
        invalid.append(state)
        for example in invalid:
            with self.subTest(invalid=str(example['controls'][0])[:40]),self.assertRaises(ValueError):
                ControlIndex(example,context_index=False)
        for value in (1,None,'False'):
            with self.subTest(option=value),self.assertRaises(ValueError):
                ControlIndex(original,context_index=value)

    def test_identical_age_for_queries_in_same_batch(self):
        state=snapshot(32)
        result=resolve_many(state,queries(32))
        ages={entry['age_seconds'] for entry in result['proposals']}
        self.assertEqual(len(ages),1)

    def test_stale_and_future_remain_blocked(self):
        for age,reason in ((10,'stale_snapshot'),(-4,'future_snapshot')):
            state=snapshot(16)
            state['captured_at']=(datetime.now(timezone.utc)-
                                  timedelta(seconds=age)).isoformat()
            result=resolve_many(state,queries(16))
            self.assertTrue(all(x['reason']==reason for x in result['proposals']))

    def test_efficiency_benchmark_exact_proposal_parity(self):
        report=benchmark(sizes=(32,128),iterations=5)
        self.assertTrue(report['all_proposal_decisions_preserved'])
        for item in report['cases']:
            self.assertTrue(item['decisions_identical'])
            self.assertTrue(item['snapshot_digest_identical'])
            self.assertTrue(item['full_snapshot_validation_preserved'])
            self.assertFalse(item['executed_actions'])
            self.assertGreater(item['baseline_full_context_median_ms'],0)
            self.assertGreater(item['optimized_unscoped_median_ms'],0)


if __name__=='__main__':
    unittest.main()
