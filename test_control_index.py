import copy
from datetime import datetime,timedelta
import unittest
from unittest.mock import patch
from tavi_controls import ControlIndex,resolve_many,resolve
from test_controls import fixture,NOW

class IndexedControlTests(unittest.TestCase):
    def test_one_shot_result_geometry_cannot_modify_original_observation(self):
        snapshot=fixture()
        result=resolve(snapshot,'Press Go','Go',now=NOW)
        result['candidate']['bounds'][0]=999
        self.assertEqual(snapshot['controls'][0]['bounds'],[10,20,80,30])

    def test_queries_recheck_freshness_and_do_not_reset_capture_time(self):
        index=ControlIndex(fixture())
        self.assertIsNotNone(index.resolve('Press Go','Go',now=NOW)['candidate'])
        self.assertEqual(index.resolve('Press Go','Go',now=NOW+timedelta(seconds=6))['reason'],'stale_snapshot')
        self.assertEqual(index.resolve('Press Go','Go',now=NOW+timedelta(seconds=6),offline=True)['status'],'offline_match')

    def test_input_and_returned_geometry_cannot_mutate_index(self):
        snapshot=fixture();index=ControlIndex(snapshot);digest=index.snapshot_sha256
        snapshot['controls'][0]['bounds'][0]=400;snapshot['controls'][0]['label']='Stop'
        snapshot['snapshot_id']='different';snapshot['captured_at']=(NOW+timedelta(seconds=50)).isoformat()
        result=index.resolve('Press Go','Go',now=NOW)
        self.assertEqual(result['candidate']['bounds'],[10,20,80,30])
        result['candidate']['bounds'][0]=999
        self.assertEqual(index.resolve('Press Go','Go',now=NOW)['candidate']['bounds'],[10,20,80,30])
        self.assertEqual(index.snapshot_sha256,digest)
        with self.assertRaises(AttributeError):index.snapshot_sha256='fake'

    def test_context_index_retains_unicode_normalization_role_and_ambiguity(self):
        snapshot=fixture();other=copy.deepcopy(snapshot['controls'][0]);other.update(id='second',context='Cafe\u0301')
        snapshot['controls'].append(other);index=ControlIndex(snapshot)
        self.assertEqual(index.resolve('Press Go','Go',now=NOW)['reason'],'ambiguous_control')
        self.assertEqual(index.resolve('Press Go','  gO ',context='CAFÉ',now=NOW)['candidate']['id'],'second')
        self.assertEqual(index.resolve('Press Go','Go',role='link',now=NOW)['reason'],'no_exact_control')

    def test_batch_checks_age_for_each_query(self):
        queries=[dict(task='Press Go',target='Go',id=str(i)) for i in range(2)]
        with patch('tavi_controls.datetime',wraps=datetime) as clock:
            clock.now.side_effect=[NOW,NOW+timedelta(seconds=6)]
            result=resolve_many(fixture(),queries)
        self.assertEqual(result['proposals'][0]['status'],'host_verification_required')
        self.assertEqual(result['proposals'][1]['reason'],'stale_snapshot')
        self.assertFalse(result['authorization_granted']);self.assertFalse(result['executed_actions'])
        self.assertTrue(all(p['probability'] is None for p in result['proposals']))

    def test_bad_nonmatching_controls_cannot_skip_validation(self):
        snapshot=fixture();bad=copy.deepcopy(snapshot['controls'][0]);bad.update(id='bad',label='Unrelated',enabled='yes')
        snapshot['controls'].append(bad)
        with self.assertRaises(ValueError):ControlIndex(snapshot)

    def test_batch_rejects_duplicate_ids_unknown_action_flags_and_bad_counts(self):
        q=dict(task='Press Go',target='Go',id='same')
        for queries in ([q,q],[dict(q,execute=True)],[],[q]*1001):
            with self.assertRaises(ValueError):resolve_many(fixture(),queries,now=NOW)

    def test_future_index_never_becomes_actionable_through_offline_option(self):
        snapshot=fixture();snapshot['captured_at']=(NOW+timedelta(seconds=2)).isoformat()
        result=ControlIndex(snapshot).resolve('Press Go','Go',offline=True,now=NOW)
        self.assertEqual(result['reason'],'future_snapshot');self.assertIsNone(result['candidate'])

if __name__=='__main__':unittest.main()
