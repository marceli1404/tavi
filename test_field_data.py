"""Local consented evidence and matched comparison safety regressions."""
from datetime import datetime,timezone
import json
from pathlib import Path
import tempfile
import unittest
from tavi_field_data import record,load,compare,validate
from tavi_observe import dispatch


class FieldEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.root=tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.directory=Path(self.root.name)/'evidence'
        self.secret=b'secret-32-bytes-to-hmac-case-keys!!'
        self.family='https://my-private-site.example'
        self.case='private form workflow #1'
        state=dict(format='tavi-control-snapshot-v1',source='supported_browser_dom',
                   snapshot_id='private-session-id',
                   captured_at=datetime.now(timezone.utc).isoformat(),
                   viewport=[1200,800],controls=[dict(id='secret-user-control',
                    label='Search private account',role='button',context='secret-plan-987',
                    visible=True,enabled=True,bounds=[50,60,120,50])])
        self.packet=dispatch(state,[dict(task='Search private account',target='Search private account')])

    def save(self,variant='baseline',case=None,**kwargs):
        defaults=dict(consent=True,sensitivity_reviewed=True,sensitive=False,
                      secret=self.secret,site_family=self.family,case_key=case or self.case,
                      variant=variant,outcome='success',host_result_verified=True,
                      duration_ms=205,visual_label='visual_not_needed',
                      visual_label_verified=True)
        defaults.update(kwargs)
        return record(self.directory,self.packet,**defaults)

    def test_requires_explicit_consent_and_non_sensitive_review(self):
        for kw in (dict(consent=False),dict(sensitivity_reviewed=False),dict(sensitive=True)):
            with self.subTest(**kw),self.assertRaises(PermissionError):
                self.save(**kw)
        self.assertFalse(self.directory.exists())

    def test_never_writes_raw_site_task_labels_or_dom_context(self):
        event=self.save(input_tokens=110,output_tokens=22,cached_input_tokens=70,
                        token_provenance='provider_reported')
        data=json.dumps(event)
        saved=''.join(path.read_text() for path in self.directory.glob('*.json'))
        for forbidden in (self.family,self.case,'secret-plan-987','secret-user-control',
                          'Search private account','private-session-id'):
            self.assertNotIn(forbidden,data)
            self.assertNotIn(forbidden,saved)
        self.assertEqual(event['token_provenance'],'provider_reported')
        self.assertFalse(event['automatic_action_authorized'])
        self.assertEqual(load(self.directory),[event])

    def test_paired_success_latency_and_token_comparison(self):
        self.save('baseline',duration_ms=210,input_tokens=100,output_tokens=30,
                  token_provenance='provider_reported')
        self.save('optimized',duration_ms=90,input_tokens=55,output_tokens=15,
                  token_provenance='provider_reported')
        report=compare(load(self.directory))
        self.assertEqual(report['matched_pairs'],1)
        self.assertEqual(report['matched_verified_pairs'],1)
        self.assertEqual(report['baseline']['success_rate'],1)
        self.assertEqual(report['optimized']['median_ms'],90)
        self.assertEqual(report['paired_input_token_delta'],-45)
        self.assertEqual(report['paired_output_token_delta'],-15)
        self.assertEqual(report['paired_token_measured'],1)
        self.assertFalse(report['automatic_action_qualified'])

    def test_missing_tokens_are_not_interpreted_as_zero(self):
        self.save('baseline')
        self.save('optimized')
        report=compare(load(self.directory))
        self.assertEqual(report['paired_token_measured'],0)
        self.assertIsNone(report['paired_input_token_delta'])
        self.assertIsNone(report['baseline']['input_tokens_total'])

    def test_duplicate_variant_fails_closed(self):
        self.save('baseline')
        self.save('baseline')
        with self.assertRaisesRegex(ValueError,'Duplicate variant'):
            compare(load(self.directory))

    def test_outcomes_and_labels_require_host_or_operator_verification(self):
        for kw in (
                dict(outcome='success',host_result_verified=False),
                dict(visual_label='visual_needed',visual_label_verified=False),
                dict(input_tokens=10,output_tokens=5,token_provenance=None),
                dict(input_tokens=10,output_tokens=None,token_provenance='provider_reported'),
                dict(duration_ms=float('nan')),
                dict(variant='untrusted')):
            with self.subTest(kw=kw),self.assertRaises(ValueError):
                self.save(**kw)
        self.assertFalse(self.directory.exists())

    def test_different_secrets_change_pseudonyms_and_group_keys(self):
        first=self.save('baseline')
        second=self.save('optimized',secret=b'z'*32)
        self.assertNotEqual(first['group_hmac'],second['group_hmac'])
        self.assertNotEqual(first['case_hmac'],second['case_hmac'])
        self.assertEqual(compare(load(self.directory))['matched_pairs'],0)

    def test_incomplete_or_extra_record_fields_rejected(self):
        event=self.save()
        for edit in (dict(event,raw_url=self.family),
                     dict(event,qualification_changed=True),
                     dict(event,visual_label='visual_needed',visual_label_verified=False),
                     dict(event,data_source='unverified'),
                     dict(event,provider_input_tokens=1)):
            with self.subTest(edit=str(edit)[:70]),self.assertRaises(ValueError):
                validate(edit)

    def test_only_nonexecuting_routes_can_be_recorded(self):
        for modified in (dict(self.packet,executed_actions=True),
                         dict(self.packet,authorization_granted=True),
                         dict(self.packet,format='forged')):
            with self.assertRaises(ValueError):
                record(self.directory,modified,consent=True,sensitivity_reviewed=True,
                       sensitive=False,secret=self.secret,site_family=self.family,
                       case_key=self.case,variant='baseline',duration_ms=12)
        self.assertFalse(self.directory.exists())


if __name__=='__main__':unittest.main()
