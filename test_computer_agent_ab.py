"""Checks matched Computer field evidence without running a host or model."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from benchmarks.computer_agent_ab import evaluate, load_jsonl, validate


def row(mode='computer', *, pair='pair001', **changes):
    item=dict(
        trial_id=('trial_'+mode+'_'+pair),
        pair_id=pair,
        mode=mode,
        task_family='file_explorer',
        task_source='controlled_fixture',
        planner_id='shared_planner_v1',
        executor_id='shared_executor_v1',
        environment_id='same_windows_vm',
        success=True, outcome_verified=True,
        duration_ms=1200 if mode=='computer' else 700,
        screenshots=3 if mode=='computer' else 1,
        native_observations=1 if mode=='computer' else 4,
        actions_attempted=3, unexpected_actions=0,
        provider_tokens={'input':1000 if mode=='computer' else 650,
                         'output':250 if mode=='computer' else 240,
                         'source':'provider_reported'},
        provider_cost_usd=None,
    )
    item.update(changes)
    return item


class ComputerAgentABTests(unittest.TestCase):
    def test_valid_matched_tasks_and_real_usage_totals(self):
        output=evaluate([row('computer'),row('computer_tavi')])
        self.assertEqual(output['data_scope']['pairs'],1)
        self.assertEqual(output['matched']['both_succeeded'],1)
        self.assertEqual(output['matched']['median_paired_wall_time_ratio'],
                         round(1200/700,3))
        self.assertEqual(output['matched']['provider_tokens']['baseline_tokens'],1250)
        self.assertEqual(output['matched']['provider_tokens']['tavi_tokens'],890)
        self.assertEqual(output['matched']['provider_tokens']['reduction_pct'],28.8)
        self.assertEqual(output['matched']['screenshot_reduction_pct'],66.67)
        self.assertTrue(output['matched']['no_unexpected_actions_observed'])
        self.assertTrue(output['limits']['does_not_execute_computer'])

    def test_failures_are_included_never_filtered(self):
        output=evaluate([row('computer',success=False),
                         row('computer_tavi',success=True)])
        self.assertEqual(output['matched']['tavi_only_succeeded'],1)
        self.assertEqual(output['modes']['computer']['success_rate'],0)
        self.assertEqual(output['modes']['computer_tavi']['success_rate'],1)

    def test_missing_tokens_not_zero_or_estimated(self):
        output=evaluate([row('computer',provider_tokens=None),
                         row('computer_tavi')])
        self.assertIsNone(output['matched']['provider_tokens'])
        self.assertIsNone(output['matched']['provider_invoiced_cost'])

    def test_subset_usage_only_on_complete_pairs(self):
        a=row('computer')
        b=row('computer_tavi')
        c=row('computer',pair='pair002',provider_tokens=None)
        d=row('computer_tavi',pair='pair002')
        output=evaluate([a,b,c,d])
        self.assertEqual(output['data_scope']['pairs'],2)
        self.assertEqual(output['matched']['provider_tokens']['pairs'],1)
        self.assertTrue(output['matched']['provider_tokens'][
            'excludes_pairs_without_both_provider_reports'])

    def test_rejects_unmatched_or_incompatible_experiments(self):
        with self.assertRaisesRegex(ValueError,'Unmatched'):
            evaluate([row('computer'),row('computer',pair='pair002')])
        for changed in ('planner_id','executor_id','environment_id',
                        'task_family','task_source'):
            altered=row('computer_tavi')
            altered[changed]='different_identifier' if changed not in ('task_family','task_source') else (
                'settings' if changed=='task_family' else 'consented_real_task')
            with self.subTest(changed=changed),self.assertRaisesRegex(ValueError,'changes'):
                evaluate([row('computer'),altered])
        with self.assertRaisesRegex(ValueError,'Duplicate mode'):
            evaluate([row('computer'),row('computer_tavi'),row('computer',trial_id='other999')])

    def test_rejects_untrusted_or_non_numeric_data(self):
        invalid=[
            row('computer',success='yes'),
            row('computer',outcome_verified=False),
            row('computer',provider_tokens={'input':200,'output':50,'source':'estimated'}),
            row('computer',duration_ms=0),
            row('computer',unexpected_actions=4),
            row('computer',screenshots=-1),
            row('computer',provider_cost_usd='0.05'),
            row('computer',task_source='unapproved_private'),
            row('computer',task_prompt='Read a private folder'),
            row('computer',pair_id='../external'),
        ]
        for item in invalid:
            with self.subTest(item=str(item)[-70:]),self.assertRaises(ValueError):
                validate(item)

    def test_unexpected_action_marks_safety_failure(self):
        result=evaluate([row('computer'),row('computer_tavi',unexpected_actions=1)])
        self.assertFalse(result['matched']['no_unexpected_actions_observed'])
        self.assertEqual(result['modes']['computer_tavi']['unexpected_actions_total'],1)

    def test_file_loader_rejects_empty_duplicate_and_bad_constants(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'trials.jsonl'
            for content in ('', '{"trial_id":"x","trial_id":"y"}\n',
                            '{"duration_ms":NaN}\n'):
                path.write_text(content,encoding='utf-8')
                with self.subTest(content=content),self.assertRaises(ValueError):
                    load_jsonl(path)
            path.write_text('\n'.join(json.dumps(x) for x in [
                row('computer'),row('computer_tavi')])+'\n',encoding='utf-8')
            self.assertEqual(len(load_jsonl(path)),2)


if __name__=='__main__':
    unittest.main()
