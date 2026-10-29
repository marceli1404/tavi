import copy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from tavi_actions import AutoClickSession,configured,plan

NOW=datetime(2026,10,28,20,0,tzinfo=timezone.utc)

def proposal(probability=.95):
    return dict(status='pending_current_codex_review',eligible_compact_review=True,review_reasons=[],
        confidence=dict(probability=probability,percent=round(probability*100,1),automatic_probability_qualified=True),
        proposal_id='proposal-one',image_sha256='a'*64,created_at=NOW.isoformat(),
        image=dict(original_size=[1200,700]),executed_actions=False,review=None,
        review_packet=dict(proposal_id='proposal-one',task='Press Go',requested_label='Go',
                           proposed=dict(id='candidate-0',label='Go',x=200.,y=250.)))

class ActionTests(unittest.TestCase):
    def setUp(self):
        self.data=proposal()
        self.context=dict(authorized=True,routine=True,visible=True,enabled=True,is_button=True,
            requires_confirmation=False,image_sha256='a'*64,candidate_id='candidate-0',task='Press Go',
            label='Go',coordinates_verified=True)
        self.inspect=Mock(side_effect=lambda data:self.context.copy())
        self.click=Mock(); self.verify=Mock(return_value=True)
        self.session=AutoClickSession(enabled=True,clock=lambda:NOW)

    def perform(self,session=None):
        return (session or self.session).perform(self.data,task='Press Go',inspect=self.inspect,click=self.click,verify=self.verify)

    def test_exactly_95_qualifies_and_clicks_once(self):
        self.assertEqual(self.perform()['status'],'clicked_verified')
        self.click.assert_called_once(); self.verify.assert_called_once()

    def test_higher_confidence_qualifies(self):
        self.assertTrue(plan(proposal(.999),True)['candidate_eligible'])

    def test_unqualified_probability_cannot_click_even_above_95(self):
        for value in (False,None,1,'true'):
            self.data['confidence']['automatic_probability_qualified']=value
            self.assertEqual(self.perform()['status'],'withheld')
        self.data['confidence'].pop('automatic_probability_qualified')
        self.assertEqual(self.perform()['status'],'withheld')
        self.click.assert_not_called()

    def test_rounded_95_but_raw_below_threshold_never_clicks(self):
        self.data=proposal(.9496)
        self.assertEqual(self.data['confidence']['percent'],95.0)
        self.assertEqual(self.perform()['status'],'withheld'); self.click.assert_not_called()

    def test_disabled_policy_never_clicks(self):
        self.perform(AutoClickSession(clock=lambda:NOW)); self.click.assert_not_called()

    def test_invalid_probability_is_not_authorization(self):
        for value in (None,True,float('nan'),float('inf'),1.1,-.1):
            data=proposal(); data['confidence']['probability']=value
            self.assertFalse(plan(data,True)['candidate_eligible'])

    def test_missing_hash_or_invalid_coordinates_withholds(self):
        for change in ('hash','coordinates'):
            data=proposal()
            if change=='hash': data['image_sha256']=None
            else: data['review_packet']['proposed']['x']=9000
            self.assertFalse(plan(data,True)['candidate_eligible'])

    def test_ambiguity_noninteractive_and_disabled_context_remain_blocks(self):
        for reason in ('ambiguous_targets','noninteractive_context','negative_context'):
            data=proposal(.999); data['review_reasons']=[reason]
            self.assertFalse(plan(data,True)['candidate_eligible'])

    def test_reviewer_rejection_cannot_be_overridden_by_score(self):
        self.data['review']=dict(decision='need_image',candidate_id='candidate-0',proposal_id='proposal-one')
        self.perform(); self.click.assert_not_called()

    def test_each_live_host_requirement_is_mandatory(self):
        for key in ('authorized','routine','visible','enabled','is_button','coordinates_verified'):
            with self.subTest(key=key):
                context=self.context.copy(); context[key]=False
                inspect=Mock(return_value=context); click=Mock()
                result=AutoClickSession(True,clock=lambda:NOW).perform(self.data,task='Press Go',inspect=inspect,click=click,verify=self.verify)
                self.assertEqual(result['status'],'withheld'); click.assert_not_called()

    def test_host_confirmation_cannot_be_bypassed(self):
        self.context['requires_confirmation']=True
        self.perform(); self.click.assert_not_called()

    def test_changed_live_bindings_never_click(self):
        for key,value in [('image_sha256','b'*64),('candidate_id','other'),('task','other'),('label','Cancel')]:
            context=self.context.copy(); context[key]=value; click=Mock()
            AutoClickSession(True,clock=lambda:NOW).perform(self.data,task='Press Go',inspect=lambda _:context,click=click,verify=self.verify)
            click.assert_not_called()

    def test_task_must_match(self):
        result=self.session.perform(self.data,task='Press Cancel',inspect=self.inspect,click=self.click,verify=self.verify)
        self.assertEqual(result['status'],'withheld'); self.click.assert_not_called()

    def test_expired_or_future_proposal_is_withheld(self):
        for delta in (-6,1):
            self.data['created_at']=(NOW+timedelta(seconds=delta)).isoformat()
            self.perform(); self.click.assert_not_called()

    def test_expiry_during_inspection_prevents_click(self):
        times=iter([NOW,NOW+timedelta(seconds=6)])
        self.perform(AutoClickSession(True,clock=lambda:next(times))); self.click.assert_not_called()

    def test_successful_proposal_cannot_be_replayed(self):
        self.perform(); result=self.perform()
        self.assertEqual(result['reason'],'proposal_already_consumed'); self.assertEqual(self.click.call_count,1)

    def test_concurrent_duplicate_attempts_click_only_once(self):
        with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(lambda _:self.perform(),range(2)))
        self.assertEqual(self.click.call_count,1)
        self.assertEqual(sum(r['status']=='clicked_verified' for r in results),1)

    def test_failed_click_is_consumed_and_never_retried(self):
        self.click.side_effect=OSError('Driver failure')
        result=self.perform(); self.assertIsNone(result['executed_actions'])
        self.assertFalse(result['retry_allowed']); self.perform(); self.assertEqual(self.click.call_count,1)

    def test_failed_verification_is_not_retried(self):
        self.verify.return_value=False
        self.assertEqual(self.perform()['status'],'verification_failed')
        self.perform(); self.assertEqual(self.click.call_count,1)

    def test_driver_false_result_is_uncertain_not_success(self):
        self.click.return_value=False
        self.assertEqual(self.perform()['status'],'click_outcome_unknown'); self.verify.assert_not_called()

    def test_configuration_is_explicit_and_preserves_threshold(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'config.json'; self.assertFalse(configured(path))
            path.write_text(json.dumps({'auto_click':{'enabled':True,'threshold_percent':95,'routine_buttons_only':True}}))
            self.assertTrue(configured(path))
            path.write_text(json.dumps({'auto_click':{'enabled':True,'threshold_percent':90}}))
            with self.assertRaises(ValueError): configured(path)
