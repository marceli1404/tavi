import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from benchmarks.judge import judge,validate
from benchmarks.outcomes import summarise,ensure_run_manifest
from benchmarks.compare_routers import common_coverage
from tavi_appserver import switch_loaded_thread,desktop_status,RpcError

BASE=Path(__file__).resolve().parent


class OutcomeTests(unittest.TestCase):
    def test_upstream_reference_solutions_pass_the_judge(self):
        cases=json.loads((BASE/'benchmarks/humaneval/cases.json').read_text(encoding='utf-8'))
        for case in cases:
            with self.subTest(task=case['task_id']):
                self.assertTrue(judge(case['prompt']+case['canonical_solution'],case['test'],case['entry_point'])['passed'])

    def test_wrong_solution_fails_real_assertions(self):
        with self.assertRaises(AssertionError):
            judge('def solution(n): return 0','def check(candidate): assert candidate(3)==7','solution')

    def test_file_access_and_dynamic_execution_are_rejected(self):
        for source in ['open("secret")','import os','eval("1")','x.__class__','x.gi_frame']:
            with self.subTest(source=source),self.assertRaises(ValueError):
                validate(source)

    def test_token_summary_does_not_invent_dollar_prices(self):
        rows=[dict(role='fast',elapsed_seconds=2.,usage=dict(input_tokens=100,output_tokens=20,cached_input_tokens=5),verdict={'passed':True,'result':'passed'})]
        result=summarise(rows)['fast']
        self.assertEqual(result['input_tokens'],100)
        self.assertEqual(result['passed'],1)
        self.assertIsNone(result['usd_cost'])

    def test_outcome_cases_are_not_in_tavi_training_data(self):
        cases=json.loads((BASE/'benchmarks/humaneval/cases.json').read_text(encoding='utf-8'))
        rows=json.loads((BASE/'models/tavi-v2/dataset.json').read_text(encoding='utf-8'))
        training={' '.join(r['prompt'].split()) for r in rows}
        self.assertFalse(training & {' '.join(c['prompt'].split()) for c in cases})

    def test_changed_benchmark_spec_cannot_reuse_cached_outcomes(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            ensure_run_manifest(root,'dataset-a')
            ensure_run_manifest(root,'dataset-a')
            with self.assertRaises(ValueError):ensure_run_manifest(root,'dataset-b')

    def test_common_coverage_excludes_abstentions_from_both_sides(self):
        outcome=dict(verdict={'passed':True},elapsed_seconds=2.,usage=dict(input_tokens=10,output_tokens=3))
        results=[dict(task_id='shared',tavi=dict(observed_outcome=outcome,inference_ms=1),laya=dict(observed_outcome=outcome,inference_ms=5)),
                 dict(task_id='abstained',tavi=dict(observed_outcome=None,inference_ms=1),laya=dict(observed_outcome=outcome,inference_ms=5))]
        report=common_coverage(results)
        self.assertEqual(report['tasks'],1)
        self.assertEqual(report['tavi']['input_tokens'],report['laya']['input_tokens'])
        self.assertEqual(report['task_ids'],['shared'])


class FakeClient:
    def __init__(self,loaded=True,status='idle',verify=True):
        self.loaded,self.status,self.verify=loaded,status,verify
        self.notifications=[]
        self.calls=[]
    def call(self,method,params):
        self.calls.append((method,params))
        if method=='thread/loaded/list':return {'data':['known'] if self.loaded else []}
        if method=='model/list':return {'data':[dict(id='model-b',supportedReasoningEfforts=[{'reasoningEffort':'medium'}])]}
        if method=='thread/read':return {'thread':dict(id='known',model='model-a',reasoningEffort='low',status={'type':self.status})}
        if method=='thread/settings/update':return {}
        raise AssertionError(method)
    def wait_notification(self,method,thread_id):
        if not self.verify:raise RpcError('Missing confirmation')
        return {'threadSettings':dict(model='model-b',effort='medium')}


class DesktopTests(unittest.TestCase):
    def test_idle_switch_only_changes_model_and_effort(self):
        client=FakeClient()
        result=switch_loaded_thread(client,'known','model-b','medium')
        self.assertEqual(result['status'],'verified')
        sent=[p for m,p in client.calls if m=='thread/settings/update']
        self.assertEqual(sent,[dict(threadId='known',model='model-b',effort='medium')])
        self.assertFalse(result['started_generation'])
        self.assertFalse(any(m in ('turn/start','thread/resume') for m,_ in client.calls))

    def test_unloaded_or_busy_thread_is_not_modified(self):
        for client in [FakeClient(loaded=False),FakeClient(status='active')]:
            with self.assertRaises(RpcError):switch_loaded_thread(client,'known','model-b','medium')
            self.assertFalse(any(m=='thread/settings/update' for m,_ in client.calls))

    def test_unavailable_model_or_effort_is_not_modified(self):
        for model,effort in [('unknown','medium'),('model-b','ultra')]:
            client=FakeClient()
            with self.assertRaises(RpcError):switch_loaded_thread(client,'known',model,effort)
            self.assertFalse(any(m=='thread/settings/update' for m,_ in client.calls))

    def test_missing_confirmation_is_not_success_or_retried(self):
        client=FakeClient(verify=False)
        result=switch_loaded_thread(client,'known','model-b','medium')
        self.assertEqual(result['status'],'verification_unavailable')
        self.assertEqual(sum(m=='thread/settings/update' for m,_ in client.calls),1)

    def test_unreachable_desktop_is_explicit_and_unchanged(self):
        with patch('tavi_appserver.AppServer',side_effect=RpcError('No control socket')):
            result=desktop_status()
        self.assertEqual(result['status'],'unavailable')
        self.assertFalse(result['changed_desktop'])


if __name__=='__main__':unittest.main()
