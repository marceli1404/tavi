"""Computer host evaluation must never manufacture model tokens or actions."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tavi_computer_compare import attest, compare, read, save, validate

SECRET=b'Native computer-use test-only HMAC secret (never production)'


def event(mode, *, case_key='task-1', planner='same-model',
          environment='win-11-lab', tokens=False, success=True):
    return attest(secret=SECRET,case_key=case_key,family='native-tabs',
                  mode=mode,planner=planner,environment=environment,
                  outcome='success' if success else 'failure',
                  host_verified=True,elapsed_ms=1200 if mode=='computer_only' else 800,
                  screenshots=3 if mode=='computer_only' else 1,
                  input_tokens=950 if mode=='computer_only' else 490 if tokens else None,
                  output_tokens=120 if tokens else None,
                  provider_usage='provider_reported' if tokens else 'unavailable',
                  consent=True,sensitivity_reviewed=True,sensitive=False)


class ComputerHostComparisonTests(unittest.TestCase):
    def test_empty_evidence_reports_unknown_not_zero(self):
        summary=compare([])
        self.assertEqual(summary['host_verified_pairs'],0)
        self.assertIsNone(summary['median_paired_ms_saved'])
        self.assertIsNone(summary['paired_input_tokens_saved'])
        self.assertFalse(summary['independently_verified'])

    def test_paired_host_measured_time_success_and_screenshots(self):
        summary=compare([event('computer_only'),event('computer_tavi')])
        self.assertEqual(summary['matched_pairs'],1)
        self.assertEqual(summary['host_verified_pairs'],1)
        self.assertEqual(summary['computer_only']['successes'],1)
        self.assertEqual(summary['computer_tavi']['successes'],1)
        self.assertEqual(summary['median_paired_ms_saved'],400)
        self.assertEqual(summary['median_paired_speed_ratio'],1.5)
        self.assertEqual(summary['computer_only']['total_screenshots'],3)
        self.assertEqual(summary['computer_tavi']['total_screenshots'],1)
        self.assertIsNone(summary['paired_input_tokens_saved'])

    def test_real_token_pairs_only_and_fabricated_usage_rejected(self):
        a=event('computer_only',tokens=True)
        b=event('computer_tavi',tokens=True)
        a['provider_input_tokens']=950
        b['provider_input_tokens']=490
        results=compare([a,b])
        self.assertEqual(results['paired_input_tokens_saved'],460)
        self.assertEqual(results['provider_token_pairs'],1)
        b['provider_usage']='unavailable'
        with self.assertRaises(ValueError):
            compare([a,b])

    def test_rejects_unmatched_planner_and_environment(self):
        a=event('computer_only')
        b=event('computer_tavi',planner='different-model')
        r=compare([a,b])
        self.assertEqual(r['rejected_different_planner_or_environment'],1)
        self.assertEqual(r['host_verified_pairs'],0)
        self.assertIsNone(r['median_paired_speed_ratio'])
        b=event('computer_tavi',environment='different-window')
        self.assertEqual(compare([a,b])['host_verified_pairs'],0)

    def test_duplicate_variant_rejected_and_failed_tasks_stay_in(self):
        a=event('computer_only')
        with self.assertRaisesRegex(ValueError,'Duplicate mode'):
            compare([a,deepcopy(a)])
        b=event('computer_tavi',success=False)
        data=compare([a,b])
        self.assertEqual(data['computer_tavi']['successes'],0)
        self.assertEqual(data['computer_tavi']['verified_tasks'],1)

    def test_no_consent_no_sensitive_or_unverified_outcome(self):
        args=dict(secret=SECRET,case_key='x',family='test',
                  mode='computer_only',environment='env',planner='model',
                  outcome='success',host_verified=True,elapsed_ms=42,
                  screenshots=0)
        for flags in (
            dict(consent=False,sensitivity_reviewed=True,sensitive=False),
            dict(consent=True,sensitivity_reviewed=False,sensitive=False),
            dict(consent=True,sensitivity_reviewed=True,sensitive=True),
        ):
            with self.subTest(flags=flags),self.assertRaises(PermissionError):
                attest(**args,**flags)
        with self.assertRaises(ValueError):
            attest(**dict(args,host_verified=False),
                   consent=True,sensitivity_reviewed=True,sensitive=False)

    def test_pseudonymization_and_exclusive_local_storage(self):
        with TemporaryDirectory() as folder:
            a=event('computer_only')
            b=event('computer_tavi')
            p1=save(folder,a)
            p2=save(folder,b)
            self.assertNotEqual(p1,p2)
            self.assertEqual(len(read(folder)),2)
            txt=p1.read_text(encoding='utf-8')
            for forbidden in ('task-1','win-11-lab','same-model','native-tabs'):
                self.assertNotIn(forbidden,txt)
            self.assertTrue(all(len(e['case_hmac'])==64 for e in read(folder)))

    def test_invalid_metrics_or_unknown_fields_rejected(self):
        original=event('computer_only')
        mutations=[]
        for field,value in (
            ('elapsed_ms',float('nan')),
            ('screenshots',-1),
            ('screenshots',True),
            ('automatic_action_authorized',True),
            ('case_hmac','not-a-digest'),
            ('provider_usage','estimated'),
        ):
            item=deepcopy(original);item[field]=value;mutations.append(item)
        added=deepcopy(original);added['raw_url']='https://private.example'
        mutations.append(added)
        for item in mutations:
            with self.subTest(fields=list(item)),self.assertRaises(ValueError):
                validate(item)


if __name__=='__main__':
    unittest.main()
