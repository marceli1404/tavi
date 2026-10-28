import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from tavi_model import DecisionModel
from tavi_probability import (binary_temperature, fit_calibration, metrics, signature,
                              summarize, temperature_probabilities, validate_calibration)
from tavi_quantize import export_int8, QuantizedDecisionModel

BASE = Path(__file__).parent


class ProbabilityTests(unittest.TestCase):
    def test_extreme_scores_are_finite_normalized(self):
        p = temperature_probabilities([[0,0,0,1],[0,0,0,0]],2)
        self.assertTrue(np.isfinite(p).all())
        np.testing.assert_allclose(p.sum(1),1)
        self.assertTrue(np.isfinite(binary_temperature([0,1],2)).all())

    def test_metrics_distinguish_overconfident_error(self):
        certain = metrics([[.99,.01]],[1])
        uncertain = metrics([[.5,.5]],[1])
        self.assertGreater(certain['nll'],uncertain['nll'])
        self.assertGreater(certain['brier'],uncertain['brier'])

    def test_coverage_can_request_review_despite_high_score(self):
        p = dict(tier='fast',tier_scores=dict(fast=.999,balanced=.0004,deep=.0004,review=.0002),
                 external_score=.9,vocabulary_coverage=0)
        report = summarize(p)
        self.assertTrue(report['review_recommended'])
        self.assertIn('low_vocabulary_coverage',report['review_reasons'])
        self.assertEqual(report['skills']['status'],'uncalibrated_selection_scores')
        self.assertFalse(report['affects_routing'])

    def test_ambiguous_distribution_reports_margin_entropy(self):
        p = dict(tier='fast',tier_scores=dict(fast=.26,balanced=.25,deep=.25,review=.24),
                 external_score=.5,vocabulary_coverage=1)
        report = summarize(p)
        self.assertIn('close_tier_alternatives',report['review_reasons'])
        self.assertIn('high_tier_entropy',report['review_reasons'])

    def test_wrong_model_or_invalid_temperature_rejected(self):
        model = DecisionModel.load(BASE/'models/tavi-v2')
        calibration = json.loads((BASE/'models/tavi-v2/probability.json').read_text())
        validate_calibration(calibration,model.metadata)
        invalid = copy.deepcopy(calibration)
        invalid['model_signature'] = 'different'
        with self.assertRaises(ValueError):validate_calibration(invalid,model.metadata)
        for temperature in (0,-1,float('nan'),float('inf')):
            invalid = copy.deepcopy(calibration)
            invalid['tier_temperature'] = temperature
            with self.assertRaises(ValueError):validate_calibration(invalid,model.metadata)

    def test_calibration_does_not_change_raw_predictions(self):
        model = DecisionModel.load(BASE/'models/tavi-v2')
        calibrated = model.infer('Inspect this Python parser')
        model.calibration = None
        raw = model.infer('Inspect this Python parser')
        for key in ('tier','tier_scores','skills','external_score','skill_threshold','external_threshold'):
            self.assertEqual(calibrated[key],raw[key])
        self.assertEqual(calibrated['probabilities']['status'],'synthetic_policy_calibrated')

    def test_fit_rejects_seen_prompts_and_inadequate_support(self):
        model = DecisionModel.load(BASE/'models/tavi-v2')
        rows = json.loads((BASE/'training/probability_cases.json').read_text())
        with self.assertRaises(ValueError):fit_calibration(model,rows,[rows[0]['prompt']])
        with self.assertRaises(ValueError):fit_calibration(model,rows[:4])

    def test_check_labels_never_fit_temperatures(self):
        model = DecisionModel.load(BASE/'models/tavi-v2')
        rows = json.loads((BASE/'training/probability_cases.json').read_text())
        first = fit_calibration(model,rows)
        changed = copy.deepcopy(rows)
        tiers = ['fast','balanced','deep','review']
        for row in changed:
            if row['split']=='check':row['tier']=tiers[(tiers.index(row['tier'])+1)%4]
        second = fit_calibration(model,changed)
        self.assertEqual(first['tier_temperature'],second['tier_temperature'])
        self.assertEqual(first['external_temperature'],second['external_temperature'])


class QuantizationTests(unittest.TestCase):
    def test_export_load_and_reject_existing_folder(self):
        model = DecisionModel.load(BASE/'models/tavi-v2')
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/'candidate'
            candidate = export_int8(model,target)
            self.assertEqual(candidate.arrays['W'].dtype,np.int8)
            self.assertIsNone(candidate.calibration)
            self.assertLess((target/'weights.npz').stat().st_size,(BASE/'models/tavi-v2/weights.npz').stat().st_size)
            result = candidate.infer('Say hello')
            self.assertEqual(result['tier'],'fast')
            self.assertEqual(result['probabilities']['status'],'uncalibrated')
            with self.assertRaises(ValueError):export_int8(model,target)

    def test_accumulation_avoids_int8_overflow_and_zero_input(self):
        fake = object.__new__(QuantizedDecisionModel)
        fake.arrays = dict(W=np.full((1000,1),127,dtype=np.int8),W_scale=np.ones(1,dtype=np.float32))
        output = fake.matmul(np.ones((1,1000),dtype=np.float32),'W')
        np.testing.assert_allclose(output,[[127000]],rtol=1e-5)
        np.testing.assert_allclose(fake.matmul(np.zeros((1,1000),dtype=np.float32),'W'),0)

    def test_corrupt_scale_rejected(self):
        model = DecisionModel.load(BASE/'models/tavi-v2')
        with tempfile.TemporaryDirectory() as folder:
            candidate = export_int8(model,Path(folder)/'candidate')
            candidate.arrays['W_scale'][0]=0
            with self.assertRaises(ValueError):QuantizedDecisionModel(candidate.metadata,candidate.arrays)


if __name__ == '__main__':
    unittest.main()
