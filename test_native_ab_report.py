"""No simulated Windows computer-use result can be reported as field evidence."""
from copy import deepcopy
import unittest
from tavi_native_ab_report import summarize,validate


def record(task,variant,**changes):
    result=dict(
        task_id=task,variant=variant,
        model_id='same-model-and-reasoning-settings',
        host_backend='computer',
        environment_id='same-windows-test-host',
        consented=True,verified_success=True,
        duration_ms=1300.0 if variant=='computer_only' else 1100.0,
        screenshots=2 if variant=='computer_only' else 1,
        input_tokens=500 if variant=='computer_only' else 380,
        output_tokens=100 if variant=='computer_only' else 90,
        provider_usage_source='provider_reported',
        permission_incidents=0,
    )
    result.update(changes)
    return result


class FieldComparisonTests(unittest.TestCase):
    def setUp(self):
        self.task_a='a'*32
        self.task_b='b'*32
        self.records=[
            record(self.task_a,'computer_only'),
            record(self.task_a,'computer_tavi'),
            record(self.task_b,'computer_only',duration_ms=2000,verified_success=False),
            record(self.task_b,'computer_tavi',duration_ms=3000,verified_success=False),
        ]

    def test_paired_includes_failures_and_does_not_claim_speed_from_them(self):
        report=summarize(self.records)
        summary=report['trials']
        self.assertEqual(summary['computer_only']['verified_successes'],1)
        self.assertEqual(summary['computer_tavi']['verified_successes'],1)
        self.assertEqual(summary['matched']['pairs'],2)
        self.assertEqual(summary['matched']['both_succeeded'],1)
        self.assertEqual(summary['matched']['median_paired_wall_time_delta_ms'],-400)
        self.assertEqual(summary['matched']['screenshot_pairs_measured'],2)
        self.assertEqual(summary['matched']['provider_token_pairs_measured'],2)
        self.assertEqual(summary['matched']['provider_token_totals']['input'],
                         {'computer_only':1000,'computer_tavi':760})
        self.assertIsNone(summary['matched']['model_cost'])

    def test_missing_usage_does_not_become_zero(self):
        records=deepcopy(self.records)
        records[1].update(input_tokens=None,output_tokens=None,
                          provider_usage_source='unavailable')
        result=summarize(records)['trials']['matched']
        self.assertEqual(result['provider_token_pairs_measured'],1)
        self.assertEqual(result['provider_token_totals']['input'],
                         {'computer_only':500,'computer_tavi':380})

    def test_both_missing_usage_must_be_null(self):
        records=deepcopy(self.records)
        for item in records:
            item.update(input_tokens=None,output_tokens=None,
                        provider_usage_source='unavailable')
        report=summarize(records)['trials']['matched']
        self.assertEqual(report['provider_token_pairs_measured'],0)
        self.assertIsNone(report['provider_token_totals'])

    def test_invalid_privacy_fields_and_unpaired_records_rejected(self):
        for addition in (
            {'prompt':'Read my messages'}, {'window_title':'Secret path'},
            {'screenshot':'base64'}, {'raw_controls':['Private']},
        ):
            rows=deepcopy(self.records)
            rows[0].update(addition)
            with self.subTest(addition=addition),self.assertRaises(ValueError):
                validate(rows)
        with self.assertRaises(ValueError):
            validate(self.records[:-1])

    def test_model_or_environment_mismatch_must_fail(self):
        for key in ('model_id','host_backend','environment_id'):
            rows=deepcopy(self.records)
            rows[1][key]='different'
            with self.subTest(key=key),self.assertRaises(ValueError):
                validate(rows)

    def test_duplicate_and_unverified_consent_rejected(self):
        with self.assertRaises(ValueError):
            validate(self.records+[deepcopy(self.records[0])])
        rows=deepcopy(self.records)
        rows[0]['consented']=False
        with self.assertRaises(ValueError):
            validate(rows)

    def test_not_claimed_provider_usage_is_not_accepted(self):
        rows=deepcopy(self.records)
        rows[0]['provider_usage_source']='provider_reported'
        rows[0]['input_tokens']=None
        with self.assertRaises(ValueError):
            validate(rows)
        rows=deepcopy(self.records)
        rows[0]['provider_usage_source']='unavailable'
        with self.assertRaises(ValueError):
            validate(rows)

    def test_no_fabricated_actions_or_negative_values(self):
        rows=deepcopy(self.records)
        rows[0]['screenshots']=-1
        with self.assertRaises(ValueError):
            validate(rows)
        rows=deepcopy(self.records)
        rows[0]['duration_ms']=0
        with self.assertRaises(ValueError):
            validate(rows)
        rows=deepcopy(self.records)
        rows[0]['task_id']='file-explorer-favorites'
        with self.assertRaises(ValueError):
            validate(rows)


if __name__=='__main__':
    unittest.main()
