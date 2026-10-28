import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from tavi_model import DecisionModel
from tavi_expand import train_expansion
from tavi_health import inventory_health, refresh, bundled_model
from evaluate_expansion import evaluate
from training.extension_heldout import CASES

BASE = Path(__file__).resolve().parent


def dataset_skills(directory):
    rows = json.loads((Path(directory)/'dataset.json').read_text(encoding='utf-8'))
    return [dict(id=r['id'], name=r['skills'][0], description=r['prompt'][len(r['skills'][0].replace('-',' '))+1:])
            for r in rows if r.get('origin') == 'weak-skill-metadata']


class ExpansionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = DecisionModel.load(BASE/'models/tavi-v1')
        cls.expanded = DecisionModel.load(BASE/'models/tavi-v2')

    def test_every_base_array_is_unchanged(self):
        for key,value in self.base.arrays.items():
            self.assertTrue(np.array_equal(value,self.expanded.arrays[key]),key)

    def test_new_skill_is_selected_without_external_inference(self):
        with patch('subprocess.run', side_effect=AssertionError('No Laya process')), \
             patch('urllib.request.urlopen', side_effect=AssertionError('No network')):
            prediction = self.expanded.infer('Use Tavi to choose a model and skills for this task')
        self.assertEqual(prediction['skills'][0]['name'],'tavi-decision')
        self.assertGreaterEqual(prediction['skills'][0]['score'],prediction['skill_threshold'])

    def test_base_outputs_unchanged_on_acceptance_inputs(self):
        from training.heldout import CASES as ORIGINAL
        prompts = [c[0] for c in ORIGINAL]+[p for p,_ in CASES]
        before,after = self.base.predict(prompts),self.expanded.predict(prompts)
        self.assertTrue(np.array_equal(before[0],after[0]))
        self.assertTrue(np.array_equal(before[1],after[1][:,:len(self.base.metadata['skills'])]))
        self.assertTrue(np.array_equal(before[2],after[2]))

    def test_both_acceptance_reports_match_the_accepted_weights(self):
        for name in ('evaluation.json','extension-evaluation.json'):
            report = json.loads((BASE/'models/tavi-v2'/name).read_text(encoding='utf-8'))
            self.assertEqual(report['weights_sha256'],self.expanded.metadata['weights_sha256'])
            self.assertTrue(report['passed'])

    def test_doctor_reports_all_current_skills_trained(self):
        report = inventory_health(self.expanded,dataset_skills(BASE/'models/tavi-v2'),BASE/'models/tavi-v2')
        self.assertEqual(report['status'],'current')
        self.assertEqual(report['installed_skill_names'],148)
        self.assertFalse(report['new_skills'] or report['unvalidated_skills'])

    def test_no_drift_refresh_does_not_start_training(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder)/'config.json'
            config.write_text(json.dumps(dict(model_path=str(BASE/'models/tavi-v2'),skill_roots=[])))
            with patch('tavi.scan_skills',return_value=dataset_skills(BASE/'models/tavi-v2')), \
                 patch('subprocess.run',side_effect=AssertionError('No redundant training')):
                result = refresh(BASE,config,True)
            self.assertEqual(result['status'],'current')
            self.assertFalse(result['activated'])

    def test_second_unvalidated_skill_is_not_silently_approved(self):
        skills = dataset_skills(BASE/'models/tavi-v2')
        skills.append(dict(id='novel',name='novel-integration',description='Manage a newly installed unfamiliar device integration'))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)/'candidate'
            train_expansion(BASE/'models/tavi-v2',skills,root)
            candidate = DecisionModel.load(root)
            for key,value in self.expanded.arrays.items():
                self.assertTrue(np.array_equal(value,candidate.arrays[key]),key)
            report = inventory_health(candidate,skills,root)
            self.assertEqual(report['status'],'needs_validation')
            self.assertIn('novel-integration',report['unvalidated_skills'])
            score = next(s['score'] for s in candidate.infer(skills[-1]['description'])['skills'] if s['name']=='novel-integration')
            self.assertEqual(score,0.)
            acceptance = evaluate(BASE/'models/tavi-v2',root)
            self.assertFalse(acceptance['passed'])
            self.assertIn('novel-integration',acceptance['uncovered_new_skills'])

    def test_preservation_gate_detects_mutated_base_even_with_valid_checksum(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            shutil.copyfile(BASE/'models/tavi-v2/dataset.json',root/'dataset.json')
            arrays = {k:v.copy() for k,v in self.expanded.arrays.items()}
            arrays['bt'][0] += .05
            np.savez_compressed(root/'weights.npz',**arrays)
            metadata = dict(self.expanded.metadata)
            metadata['weights_sha256'] = hashlib.sha256((root/'weights.npz').read_bytes()).hexdigest()
            (root/'model.json').write_text(json.dumps(metadata))
            report = evaluate(BASE/'models/tavi-v1',root)
            self.assertFalse(report['arrays_preserved'])
            self.assertFalse(report['passed'])

    def test_portable_default_uses_expanded_model_and_cannot_escape(self):
        self.assertEqual(bundled_model(BASE),BASE/'models/tavi-v2')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'models').mkdir()
            (root/'models/default-model.json').write_text('{"path":"../../outside"}')
            with self.assertRaises(ValueError):
                bundled_model(root)

    def test_full_retrain_must_not_forget_an_accepted_added_skill(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ('model.json','weights.npz','dataset.json'):
                shutil.copyfile(BASE/'models/tavi-v1'/name,root/name)
            report = evaluate(BASE/'models/tavi-v2',root,require_preservation=False)
            self.assertFalse(report['passed'])
            self.assertEqual(report['metrics']['recall'],0.)


if __name__ == '__main__':
    unittest.main()
