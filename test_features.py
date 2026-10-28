import contextlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import tavi
from tavi_model import DecisionModel
from tavi_router import route_custom
from tavi_health import inventory_health, activate_candidate, rollback, model_location
from tavi_batch import route_batch, read_tasks

BASE = Path(__file__).resolve().parent
MODELS = [dict(id=m, default_effort='low', efforts=['low','medium','high']) for m in ['gpt-6-luna','gpt-6.1-sol','gpt-6-astra']]
SKILLS = [dict(id='responsive', name='responsive-design', description='Responsive layout', path='x')]


class FeatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = DecisionModel.load(BASE/'models/tavi-v1')

    def test_preferences_change_model_and_effort_without_changing_prediction(self):
        fast = route_custom('Fix a mobile layout', SKILLS, MODELS, self.model, preference='speed')
        quality = route_custom('Fix a mobile layout', SKILLS, MODELS, self.model, preference='quality')
        self.assertEqual(fast['model']['id'], 'gpt-6-luna')
        self.assertEqual(quality['model']['id'], 'gpt-6-astra')
        self.assertEqual(fast['model']['reasoning'], 'low')
        self.assertEqual(quality['model']['reasoning'], 'high')
        self.assertEqual(fast['prediction'], quality['prediction'])

    def test_explicit_model_wins_over_preference(self):
        result = route_custom('Say hello', [], MODELS, self.model, 'gpt-6.1-sol', preference='quality')
        self.assertEqual(result['model']['id'], 'gpt-6.1-sol')
        self.assertEqual(result['model']['selection'], 'explicit')

    def test_preference_does_not_force_ambiguous_task(self):
        self.assertEqual(route_custom('Do it', [], MODELS, self.model, preference='quality')['status'], 'needs_review')

    def test_model_exclusion_falls_back_and_all_excluded_abstains(self):
        result = route_custom('Say hello', [], MODELS, self.model, excluded_models=['gpt-6-luna'])
        self.assertEqual(result['model']['id'], 'gpt-6.1-sol')
        result = route_custom('Say hello', [], MODELS, self.model, excluded_models=[m['id'] for m in MODELS])
        self.assertEqual(result['status'], 'needs_review')
        with self.assertRaises(ValueError):
            route_custom('Hello', [], MODELS, self.model, 'gpt-6-luna', excluded_models=['gpt-6-luna'])

    def test_skill_exclusion_and_required_policy_conflict(self):
        result = route_custom('Fix a mobile responsive layout', SKILLS, MODELS, self.model, excluded_skills=['responsive-design'])
        self.assertFalse(result['skills'])
        with self.assertRaises(ValueError):
            route_custom('Fix a mobile layout', SKILLS, MODELS, self.model,
                         policy={'always_skills':['responsive-design']}, excluded_skills=['responsive'])
        with self.assertRaises(ValueError):
            route_custom('Fix a mobile layout', SKILLS, MODELS, self.model, excluded_skills=['typo'])

    def test_batch_preserves_good_items_and_reports_invalid_ones(self):
        tasks = ['Say hello', {'id':'deep', 'prompt':'Prove a complex concurrent algorithm correct'},
                 {'id':'bad','prompt':4}, {'id':'deep','prompt':'Duplicate'}, {'prompt':'hello','execute':True}]
        with patch('subprocess.run', side_effect=AssertionError('No batch execution')):
            result = route_batch(tasks, SKILLS, MODELS, self.model)
        self.assertEqual(result['tasks'], 5)
        self.assertEqual(result['errors'], 3)
        self.assertIn('decision', result['results'][0])
        self.assertFalse(result['executed'])

    def test_batch_input_bounds(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'tasks.json'
            path.write_text('[]')
            with self.assertRaises(ValueError):
                read_tasks(path)
            path.write_text('["Say hello"]')
            self.assertEqual(read_tasks(path), ['Say hello'])

    def test_doctor_detects_changed_new_and_removed_metadata(self):
        rows = json.loads((BASE/'models/tavi-v1/dataset.json').read_text(encoding='utf-8'))
        skills = [dict(id=r['id'], name=r['skills'][0], description=r['prompt'][len(r['skills'][0].replace('-',' '))+1:])
                  for r in rows if r.get('origin') == 'weak-skill-metadata']
        initial = inventory_health(self.model, skills, BASE/'models/tavi-v1')
        self.assertEqual(initial['status'], 'current')
        removed = skills.pop()
        skills[0]['description'] += ' changed'
        skills.append(dict(id='new', name='new-skill', description='Novel capability'))
        report = inventory_health(self.model, skills, BASE/'models/tavi-v1')
        self.assertIn('new-skill', report['new_skills'])
        self.assertIn(removed['name'], report['removed_skills'])
        self.assertIn(skills[0]['name'], report['changed_skills'])

    def test_activation_rejects_stale_config_and_failed_report(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            candidate = root/'candidate'
            candidate.mkdir()
            for name in ['weights.npz','model.json']:
                shutil.copyfile(BASE/'models/tavi-v1'/name, candidate/name)
            config = root/'config.json'
            original = b'{"model_path":"old"}'
            config.write_bytes(b'{"model_path":"concurrent-change"}')
            accepted = dict(passed=True, weights_sha256=self.model.metadata['weights_sha256'])
            with self.assertRaises(RuntimeError):
                activate_candidate(config, original, candidate, accepted)
            with self.assertRaises(ValueError):
                activate_candidate(config, config.read_bytes(), candidate, dict(passed=False))
            self.assertIn('concurrent-change', config.read_text())

    def test_activation_and_rollback_preserve_other_preferences(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            candidate = root/'candidate'
            candidate.mkdir()
            for name in ['weights.npz','model.json']:
                shutil.copyfile(BASE/'models/tavi-v1'/name, candidate/name)
            config = root/'config.json'
            original = json.dumps(dict(model_path=str(BASE/'models/tavi-v1'), policy={'example':1})).encode()
            config.write_bytes(original)
            activate_candidate(config, original, candidate, dict(passed=True, weights_sha256=self.model.metadata['weights_sha256']))
            updated = json.loads(config.read_text())
            updated['policy']['example'] = 2
            config.write_text(json.dumps(updated))
            rollback(config, root)
            result = json.loads(config.read_text())
            self.assertEqual(Path(result['model_path']), BASE/'models/tavi-v1')
            self.assertEqual(result['policy']['example'], 2)
            self.assertEqual((candidate/'previous-config.json').read_bytes(), original)

    def test_relative_model_path_is_relative_to_config(self):
        path = model_location({'model_path':'models/accepted'}, BASE/'config.json', BASE)
        self.assertEqual(path, BASE/'models/accepted')

    def test_batch_cli_loads_inventory_once_and_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config = root/'config.json'
            config.write_text(json.dumps(dict(skill_roots=[], model_path=str(BASE/'models/tavi-v1'))))
            tasks = root/'tasks.json'
            tasks.write_text('["Say hello", "Fix a mobile layout"]')
            output = root/'results.json'
            args = ['tavi.py','--config',str(config),'batch',str(tasks),'--output',str(output)]
            with patch('sys.argv',args), patch('tavi.model_catalog',return_value=MODELS) as inventory, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(tavi.main(), 0)
                inventory.assert_called_once()
            before = output.read_bytes()
            with patch('sys.argv',args), patch('tavi.model_catalog',return_value=MODELS), \
                 contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(tavi.main(), 1)
            self.assertEqual(before, output.read_bytes())


if __name__ == '__main__':
    unittest.main()
