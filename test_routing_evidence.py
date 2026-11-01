"""Abstention reasons must describe model evidence without inventing task facts."""
from copy import deepcopy
import unittest
from tavi_router import route_custom

MODELS=[dict(id='gpt-6-luna',efforts=['low','medium'],default_effort='medium')]


class Model:
    metadata={'weights_sha256':'fixture'}
    def __init__(self,tier='fast',score=.8,coverage=.8):
        self.prediction=dict(tier=tier,tier_scores={t:score if t==tier else (1-score)/3
            for t in ['fast','balanced','deep','review']},vocabulary_coverage=coverage,
            skills=[],skill_threshold=.2,external_score=0,external_threshold=.7,
            probabilities={'review_recommended':True})
    def infer(self,prompt):return deepcopy(self.prediction)


class RoutingEvidenceTests(unittest.TestCase):
    def route(self,model,**kwargs):return route_custom('A complete fixture task.',[],MODELS,model,**kwargs)

    def test_review_prediction_is_not_a_task_ambiguity_finding(self):
        result=self.route(Model('review'))
        self.assertEqual(result['status'],'needs_review')
        self.assertEqual(result['routing_evidence']['withheld_reasons'],['classifier_predicted_review'])
        self.assertFalse(result['routing_evidence']['classifier_review_establishes_task_ambiguity'])
        self.assertFalse(result['routing_evidence']['role_lookup_performed'])

    def test_low_score_and_low_vocabulary_are_separate(self):
        self.assertEqual(self.route(Model(score=.4))['routing_evidence']['withheld_reasons'],['low_workload_score'])
        self.assertEqual(self.route(Model(coverage=.1))['routing_evidence']['withheld_reasons'],['limited_vocabulary_coverage'])

    def test_inventory_reason_only_after_eligible_role_lookup(self):
        result=self.route(Model(),excluded_models=['gpt-6-luna'])
        self.assertEqual(result['routing_evidence']['withheld_reasons'],['configured_role_model_unavailable'])
        self.assertTrue(result['routing_evidence']['role_lookup_performed'])

    def test_explicit_model_still_preserves_existing_override(self):
        result=self.route(Model('review',coverage=.1),requested_model='gpt-6-luna')
        self.assertEqual(result['status'],'recommended')
        self.assertEqual(result['routing_evidence']['withheld_reasons'],[])
        self.assertTrue(result['routing_evidence']['explicit_model_requested'])

    def test_required_policy_missing_still_withholds(self):
        result=self.route(Model(),policy={'always_skills':['missing-fixture']})
        self.assertEqual(result['status'],'needs_review')
        self.assertEqual(result['routing_evidence']['withheld_reasons'],['required_policy_skill_unavailable'])

    def test_review_advice_does_not_silently_change_route(self):
        result=self.route(Model(score=.5,coverage=.15))
        self.assertEqual(result['status'],'recommended')
        self.assertTrue(result['routing_evidence']['quality_review_recommended'])
        self.assertFalse(result['routing_evidence']['changes_routing'])


if __name__=='__main__':unittest.main()
