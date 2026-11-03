"""Group-heldout research-only visual escalation training regressions."""
from datetime import datetime,timezone
import hashlib
import uuid
import unittest

from tavi_field_data import FORMAT as DATA_FORMAT,validate
from tavi_escalation_train import train,score,feature_vector,FEATURES


def event(group,case,needed):
    # Synthetic fixture; cannot be confused with an actual independently
    # evaluated user site. No file is written and no live model is changed.
    e={
      'format':DATA_FORMAT,'id':str(uuid.uuid4()),
      'recorded_at':datetime.now(timezone.utc).isoformat(),
      'group_hmac':hashlib.sha256(('group'+str(group)).encode()).hexdigest(),
      'case_hmac':hashlib.sha256(('task'+str(group)+':'+str(case)).encode()).hexdigest(),
      'variant':'baseline','route':'host_control',
      'role':'button','reason':'unique_exact_control',
      'age_bucket':'0-500ms','context_present':not needed,
      'geometry_bucket':'medium','outcome':'unverified',
      'host_result_verified':False,
      'visual_label':'visual_needed' if needed else 'visual_not_needed',
      'visual_label_verified':True,'duration_ms':15.0,
      'provider_input_tokens':None,'provider_output_tokens':None,
      'provider_cached_input_tokens':None,'token_provenance':None,
      'data_source':'consented_host_attested','qualification_changed':False,
      'automatic_action_authorized':False
    }
    validate(e)
    return e


class AdvisoryTrainingTests(unittest.TestCase):
    def setUp(self):
        self.data=[event(group,i,i%2==0) for group in range(12) for i in range(10)]

    def test_group_holdout_and_no_action_or_policy_activation(self):
        model=train(self.data)
        self.assertGreaterEqual(model['training_cases'],80)
        self.assertGreaterEqual(model['holdout_cases'],20)
        self.assertGreaterEqual(model['holdout_families'],2)
        self.assertEqual(model['features'],list(FEATURES))
        self.assertLess(model['heldout_brier'],model['heldout_constant_baseline_brier'])
        self.assertFalse(model['may_click'])
        self.assertFalse(model['may_skip_ocr'])
        self.assertFalse(model['production_routing_changed'])
        self.assertFalse(model['model_adopted'])
        self.assertFalse(model['automatic_probability_qualified'])
        positive=score(model,event(40,1,True))
        negative=score(model,event(40,2,False))
        self.assertTrue(positive['suggest_additional_visual_check'])
        self.assertFalse(negative['suggest_additional_visual_check'])
        self.assertFalse(positive['action_authorized'])
        self.assertFalse(positive['may_skip_mandatory_evidence'])

    def test_underrepresented_dataset_fails_instead_of_fabricating_quality(self):
        with self.assertRaises(ValueError):
            train(self.data[:30])
        with self.assertRaises(ValueError):
            train([event(group,i,i%2==0) for group in range(4) for i in range(30)])
        with self.assertRaises(ValueError):
            train([event(group,i,True) for group in range(12) for i in range(10)])

    def test_repeated_site_cases_are_not_counted_twice(self):
        model=train(self.data+self.data[:20])
        self.assertEqual(model['training_cases']+model['holdout_cases'],len(self.data))

    def test_conflicting_label_or_feature_rejected(self):
        conflict=dict(self.data[0],id=str(uuid.uuid4()),visual_label='visual_not_needed')
        validate(conflict)
        with self.assertRaisesRegex(ValueError,'Conflicting'):
            train(self.data+[conflict])
        altered=dict(self.data[0],id=str(uuid.uuid4()),context_present=True)
        with self.assertRaisesRegex(ValueError,'Conflicting'):
            train(self.data+[altered])

    def test_only_exact_host_controls_with_operator_verified_labels_are_trainable(self):
        blocked=dict(self.data[0],id=str(uuid.uuid4()),
                     reason='ambiguous_control',route='host_review')
        validate(blocked)
        model=train(self.data+[blocked])
        self.assertEqual(model['training_cases']+model['holdout_cases'],len(self.data))
        with self.assertRaises(ValueError):
            feature_vector(blocked)
        with self.assertRaises(ValueError):
            score(model,blocked)

    def test_cannot_load_model_that_claims_automatic_action_privilege(self):
        model=train(self.data)
        for bad in (dict(model,may_click=True),
                    dict(model,may_skip_ocr=True),
                    dict(model,model_adopted=True),
                    dict(model,features=['arbitrary']),
                    dict(model,weights=[float('nan')]*len(FEATURES))):
            with self.subTest(key=str(bad)[:40]),self.assertRaises(ValueError):
                score(bad,self.data[0])


if __name__=='__main__':unittest.main()
