import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from tavi_model import DecisionModel
from tavi_probability import signature
from tavi_health import activate_candidate,refresh
from tavi_quantize import export_int8

BASE=Path(__file__).parent


class CoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=DecisionModel.load(BASE/'models/tavi-v2')
        cls.model=DecisionModel.load(BASE/'models/tavi-v3')

    def test_accepted_candidate_and_fresh_audit_bound_to_model(self):
        report=json.loads((BASE/'models/tavi-v3/acceptance.json').read_text())
        self.assertTrue(report['passed'])
        self.assertEqual(report['model_signature'],signature(self.model.metadata))
        audit=json.loads((BASE/'models/tavi-v3/fresh-audit.json').read_text())
        self.assertGreater(audit['metrics']['after']['policy_accuracy'],audit['metrics']['before']['policy_accuracy'])

    def test_all_original_arrays_skills_and_external_outputs_frozen(self):
        for name,array in self.base.arrays.items():np.testing.assert_array_equal(array,self.model.arrays[name])
        prompts=['Say hello','Find a missing agent skill for Blender','Do something unspecified','Fix this mobile layout','Prove consensus safety']
        a,b=self.base.predict(prompts),self.model.predict(prompts)
        np.testing.assert_array_equal(a[1],b[1]);np.testing.assert_array_equal(a[2],b[2])

    def test_no_fit_check_overlap_and_no_public_tasks_fitted(self):
        rows=json.loads((BASE/'models/tavi-v3/tier-dataset.json').read_text())
        seen={' '.join(r['prompt'].lower().split()) for r in rows}
        checks=json.loads((BASE/'training/coverage_heldout.json').read_text())
        checks+=json.loads((BASE/'training/coverage_audit.json').read_text())['cases']
        checks+=json.loads((BASE/'benchmarks/coverage-v0.8/cases.json').read_text())
        checks+=json.loads((BASE/'benchmarks/coverage-v0.8/audit-cases.json').read_text())['cases']
        self.assertFalse(seen & {' '.join(r['prompt'].lower().split()) for r in checks})

    def test_stale_calibration_not_silently_reused(self):
        self.assertIsNone(self.model.calibration)
        self.assertEqual(self.model.infer('Say hello')['probabilities']['status'],'uncalibrated')
        self.assertFalse(json.loads((BASE/'models/tavi-v3/probability-evaluation.json').read_text())['accepted'])

    def test_activation_refuses_wrong_metadata_with_same_weights(self):
        report=json.loads((BASE/'models/tavi-v3/acceptance.json').read_text())
        report['model_signature']='incorrect-policy'
        with tempfile.TemporaryDirectory() as folder:
            config=Path(folder)/'config.json';config.write_text('{}')
            with self.assertRaises(ValueError):activate_candidate(config,b'{}',BASE/'models/tavi-v3',report)

    def test_full_refresh_refuses_to_drop_tier_adapter(self):
        with tempfile.TemporaryDirectory() as folder:
            config=Path(folder)/'config.json'
            config.write_text(json.dumps(dict(model_path=str(BASE/'models/tavi-v3'),skill_roots=[])))
            with patch('subprocess.run',side_effect=AssertionError('Must not train')):
                with self.assertRaises(ValueError):refresh(BASE,config,strategy='full')

    def test_unvalidated_int8_export_cannot_silently_drop_adapter(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'candidate'
            with self.assertRaises(ValueError):export_int8(self.model,target)
            self.assertFalse(target.exists())

    def test_raw_predictions_need_no_host_or_network(self):
        with patch('subprocess.run',side_effect=AssertionError('No host')),patch('urllib.request.urlopen',side_effect=AssertionError('No network')):
            result=self.model.infer('Write a short farewell')
        self.assertEqual(result['tier'],'fast')

    def test_saved_new_coding_answers_reproduce(self):
        from benchmarks.outcomes import judge
        cases={r['task_id']:r for r in json.loads((BASE/'benchmarks/coverage-v0.8/cases.json').read_text())}
        answers=json.loads((BASE/'benchmarks/coverage-v0.8/outcome-answers.json').read_text())
        self.assertEqual(len(answers),6)
        for row in answers:self.assertTrue(judge(row['code'],cases[row['task_id']])['passed'])


if __name__=='__main__':unittest.main()
