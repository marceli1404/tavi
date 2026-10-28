import copy
import json
import re
from pathlib import Path
import unittest
import numpy as np
from tavi_model import DecisionModel,is_coding_spec
from tavi_probability import validate_calibration
from benchmarks.outcomes import judge
from benchmarks.judge import validate

BASE=Path(__file__).parent


class CodingConfidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before=DecisionModel.load(BASE/'models/tavi-v3')
        cls.after=DecisionModel.load(BASE/'models/tavi-v4-clean')

    def test_old_parameters_and_plain_text_tiers_frozen(self):
        for key,value in self.before.arrays.items():np.testing.assert_array_equal(value,self.after.arrays[key])
        rows=json.loads((BASE/'models/tavi-v3/tier-dataset.json').read_text())
        texts=[r['prompt'] for r in rows if not is_coding_spec(r['prompt'])]
        a,b=self.before.predict(texts),self.after.predict(texts)
        for first,second in zip(a,b):np.testing.assert_array_equal(first,second)

    def test_frozen_coverage_gates_pass_and_no_old_routes_lost(self):
        report=json.loads((BASE/'models/tavi-v4-clean/coding-evaluation.json').read_text())
        self.assertTrue(report['passed'])
        self.assertEqual(report['public']['prior_audit']['after'],6)
        self.assertEqual(report['public']['historical']['after'],8)
        self.assertTrue(all(not r['lost'] for r in report['public'].values()))

    def test_no_benchmark_prompts_fitted(self):
        fitted=json.loads((BASE/'models/tavi-v4-clean/coding-dataset.json').read_text())
        seen={' '.join(r['prompt'].lower().split()) for r in fitted}
        for name in ['humaneval/cases.json','coverage-v0.8/cases.json','coverage-v0.8/audit-cases.json','coverage-v0.9/cases.json']:
            rows=json.loads((BASE/'benchmarks'/name).read_text());rows=rows['cases'] if isinstance(rows,dict) else rows
            self.assertFalse(seen & {' '.join(r['prompt'].lower().split()) for r in rows})

    def test_partial_calibration_labels_actual_context(self):
        text=self.after.infer('Write a short farewell')['probabilities']
        self.assertEqual(text['status'],'partially_synthetic_policy_calibrated')
        self.assertEqual(text['tier']['status'],'uncalibrated')
        self.assertEqual(text['external_search']['status'],'synthetic_policy_calibrated')
        code=self.after.infer('def measure(values):\n    """Return the total of all positive measurements."""')['probabilities']
        self.assertEqual(code['tier']['status'],'synthetic_policy_calibrated')
        self.assertEqual(code['external_search']['status'],'uncalibrated')
        self.assertIn('limited_context_validation_accuracy',code['review_reasons'])

    def test_rejected_head_keeps_raw_value(self):
        prompt='def sample(values):\n    """Return the largest reading or None for empty input."""'
        result=self.after.infer(prompt)
        self.assertAlmostEqual(result['external_score'],result['probabilities']['external_search']['yes'],places=12)
        text=self.after.infer('Fix a small Python parser')
        np.testing.assert_allclose(list(text['tier_scores'].values()),list(text['probabilities']['tier']['distribution'].values()),atol=1e-8)

    def test_inconsistent_context_metadata_rejected(self):
        artifact=copy.deepcopy(self.after.calibration)
        artifact['context_acceptance']['plain_text']['tier']=True
        artifact['head_acceptance']['tier']=False
        with self.assertRaises(ValueError):validate_calibration(artifact,self.after.metadata)
        artifact=copy.deepcopy(self.after.calibration);artifact['context_acceptance']['unexpected']={'tier':True,'external':True}
        with self.assertRaises(ValueError):validate_calibration(artifact,self.after.metadata)

    def test_applied_calibrations_pass_each_context_gate(self):
        report=self.after.calibration
        self.assertEqual(report['fit_cases'],132);self.assertEqual(report['check_cases'],132)
        for context,heads in report['context_acceptance'].items():
            for head,accepted in heads.items():
                if accepted:
                    metrics=report['context_metrics'][context][head]
                    for key in ('nll','brier'):self.assertLessEqual(metrics['after'][key],metrics['before'][key]+1e-6)

    def test_new_answers_reproduce_with_upstream_helper_context(self):
        cases={r['task_id']:r for r in json.loads((BASE/'benchmarks/coverage-v0.9/cases.json').read_text())}
        answers=json.loads((BASE/'benchmarks/coverage-v0.9/outcome-answers.json').read_text())
        self.assertEqual(len(answers),2)
        for answer in answers:self.assertTrue(judge(answer['code'],cases[answer['task_id']])['passed'])

    def test_candidate_random_import_still_rejected(self):
        with self.assertRaises(ValueError):validate('import random\ndef example(): return 1')

    def test_authored_function_names_do_not_expose_tier(self):
        rows=json.loads((BASE/'models/tavi-v4-clean/coding-dataset.json').read_text())
        rows+=json.loads((BASE/'training/probability_cases_v4_clean.json').read_text())
        for row in rows:
            for name in re.findall(r'(?m)^\s*def\s+(\w+)\(',row['prompt']):
                self.assertNotIn(row['tier'],name.split('_'))


if __name__=='__main__':unittest.main()
