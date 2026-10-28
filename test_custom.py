import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import tavi
from tavi_model import DecisionModel
from tavi_router import route_custom
from tavi_discovery import review, validate_path
from tavi_feedback import save_feedback

BASE = Path(__file__).resolve().parent
MODELS = [dict(id='gpt-6-luna', efforts=['low', 'medium', 'high'], default_effort='medium'),
          dict(id='gpt-6.1-sol', efforts=['low', 'medium', 'high'], default_effort='low'),
          dict(id='gpt-6-astra', efforts=['low', 'medium', 'high'], default_effort='low')]
SKILLS = [dict(id='ui', name='responsive-design', description='Responsive layout', path='x'),
          dict(id='copy', name='website-copy-humanizer', description='Review changed website copy', path='y')]


class CustomModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = DecisionModel.load(BASE/'models/tavi-v1')

    def test_model_artifact_is_real_and_finite(self):
        self.assertGreater(self.model.metadata['parameters'], 400_000)
        self.assertTrue(all(np.isfinite(a).all() for a in self.model.arrays.values()))

    def test_learned_routing_without_laya_or_network(self):
        with patch('subprocess.run', side_effect=AssertionError('No backend process allowed')), \
             patch('urllib.request.urlopen', side_effect=AssertionError('No network allowed')):
            result = route_custom('Fix the mobile navigation overflowing a phone screen', SKILLS, MODELS, self.model)
        self.assertEqual(result['model']['id'], 'gpt-6.1-sol')
        self.assertEqual(result['model']['reasoning'], 'medium')
        self.assertIn('responsive-design', [s['name'] for s in result['skills']])

    def test_fast_deep_and_ambiguous_tasks(self):
        fast = route_custom('Say hello', [], MODELS, self.model)
        deep = route_custom('Prove correctness of a concurrent distributed consensus algorithm', [], MODELS, self.model)
        unclear = route_custom('Do it', [], MODELS, self.model)
        unknown = route_custom('zxqvv plkrrr xxzzww', [], MODELS, self.model)
        self.assertEqual(fast['model']['id'], 'gpt-6-luna')
        self.assertEqual(deep['model']['id'], 'gpt-6-astra')
        self.assertIsNone(unclear['model'])
        self.assertEqual(unknown['status'], 'needs_review')

    def test_external_search_is_a_learned_decision(self):
        result = route_custom('Find a new skill online for missing robotics integration', [], MODELS, self.model)
        self.assertEqual(result['discovery']['status'], 'search_recommended')
        self.assertFalse(result['discovery']['installation_authorized'])
        self.assertEqual(result['discovery']['provider'], 'awesomeskill')
        self.assertIn('sort=stars', result['discovery']['search_url'])

    def test_explicit_choice_and_unavailable_models(self):
        result = route_custom('Say hello', [], MODELS, self.model, 'gpt-6-astra')
        self.assertEqual(result['model']['id'], 'gpt-6-astra')
        self.assertEqual(route_custom('Say hello', [], [], self.model)['status'], 'needs_review')
        with self.assertRaises(ValueError):
            route_custom('Say hello', [], MODELS, self.model, 'imaginary-model')

    def test_visible_policy_requirements(self):
        policy = {'rules': [{'pattern': 'website', 'skills': ['website-copy-humanizer']}]}
        result = route_custom('Build a website interface', SKILLS, MODELS, self.model, policy=policy)
        self.assertIn('website-copy-humanizer', result['policy_skills'])
        result = route_custom('Build a website interface', [], MODELS, self.model, policy=policy)
        self.assertEqual(result['status'], 'needs_review')

    def test_weight_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'model.json').write_bytes((BASE/'models/tavi-v1/model.json').read_bytes())
            (root/'weights.npz').write_bytes(b'invalid')
            with self.assertRaises(ValueError):
                DecisionModel.load(root)

    def test_cli_default_needs_no_laya_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder)/'config.json'
            config.write_text(json.dumps(dict(skill_roots=[], model_path=str(BASE/'models/tavi-v1'))))
            output = io.StringIO()
            with patch('sys.argv', ['tavi.py', '--config', str(config), 'route', 'Say hello']), \
                 patch('tavi.model_catalog', return_value=MODELS), \
                 patch('subprocess.run', side_effect=AssertionError('No Laya subprocess')), \
                 contextlib.redirect_stdout(output):
                code = tavi.main()
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output.getvalue())['backend'], 'tavi-neural-cpu')

    def test_train_validation_test_exact_disjointness(self):
        from training.heldout import CASES
        rows = json.loads((BASE/'models/tavi-v1/dataset.json').read_text())
        train = {r['prompt'].strip().lower() for r in rows if r['split'] == 'train'}
        val = {r['prompt'].strip().lower() for r in rows if r['split'] == 'validation'}
        test = {c[0].strip().lower() for c in CASES}
        self.assertFalse(train & val or train & test or val & test)

    def test_saved_model_meets_predeclared_synthetic_gates(self):
        report = json.loads((BASE/'models/tavi-v1/evaluation.json').read_text())
        self.assertEqual(report['weights_sha256'], self.model.metadata['weights_sha256'])
        self.assertTrue(all(report['metrics'][k] >= v for k,v in report['gates'].items()))


class SourceReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = DecisionModel.load(BASE/'models/tavi-v1')

    def fake_api(self, script=b'print("hello")', mode='100644', truncated=False):
        import base64
        content = {'SKILL.md': b'---\nname: sample-skill\ndescription: Help with robotics\n---\nRobotics integration workflow',
                   'scripts/tool.py': script, 'LICENSE.txt': b'Example licence text'}
        hashes = {p: hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest() for p,b in content.items()}
        tree = [dict(path='skill/'+p, type='blob', mode=mode if p.endswith('.py') else '100644', size=len(b), sha=hashes[p]) for p,b in content.items()]
        def api(endpoint):
            if endpoint == '/repos/example/repo':
                return dict(default_branch='main', license={'spdx_id':'MIT'})
            if '/commits/' in endpoint:
                return {'sha':'a'*40}
            if '/git/trees/' in endpoint:
                return dict(tree=tree, truncated=truncated)
            if '/git/blobs/' in endpoint:
                sha = endpoint.split('/')[-1]
                payload = next(b for p,b in content.items() if hashes[p] == sha)
                return dict(encoding='base64', size=len(payload), content=base64.b64encode(payload).decode())
            raise AssertionError(endpoint)
        return api

    def test_reviews_stages_and_pins_without_execution(self):
        model = self.model
        with tempfile.TemporaryDirectory() as folder, patch('tavi_discovery.api', side_effect=self.fake_api()), \
             patch('subprocess.run', side_effect=AssertionError('No source execution')):
            root = Path(folder)/'source'
            report = review('example/repo', 'skill/SKILL.md', 'robotics integration', model, stage=root)
            self.assertEqual(report['commit'], 'a'*40)
            self.assertEqual(report['recommendation'], 'download_for_review')
            self.assertTrue((root/'scripts/tool.py').is_file())
            self.assertTrue((root/'tavi-review.json').is_file())

    def test_flags_dynamic_execution_and_detects_dependencies(self):
        with patch('tavi_discovery.api', side_effect=self.fake_api(b'import requests\neval("hello")')):
            report = review('example/repo', 'skill/SKILL.md', 'robotics', self.model)
        self.assertEqual(report['recommendation'], 'review_required')
        self.assertIn('requests', report['dependency_hints'])

    def test_duplicate_candidate_skipped(self):
        with patch('tavi_discovery.api', side_effect=self.fake_api(b'import requests\nprint("hello")')):
            report = review('example/repo', 'skill/SKILL.md', 'robotics', self.model, ['sample-skill'])
        self.assertEqual(report['recommendation'], 'skip_duplicate')
        self.assertEqual(report['name'], 'sample-skill')

    def test_incomplete_and_symlink_sources_rejected(self):
        for options in [dict(truncated=True), dict(mode='120000')]:
            with patch('tavi_discovery.api', side_effect=self.fake_api(**options)), self.assertRaises(ValueError):
                review('example/repo', 'skill/SKILL.md', 'robotics', self.model)

    def test_staging_cannot_overwrite_existing_folder(self):
        with tempfile.TemporaryDirectory() as folder, patch('tavi_discovery.api', side_effect=self.fake_api()), self.assertRaises(ValueError):
            review('example/repo', 'skill/SKILL.md', 'robotics', self.model, stage=folder)

    def test_unsafe_paths_rejected(self):
        for path in ['../secret', '/absolute', 'C:/secret', 'folder\\file', 'CON.txt', 'a/nul', 'trailing.']:
            with self.subTest(path=path), self.assertRaises(ValueError):
                validate_path(path)

    def test_feedback_events_append_and_original_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            records = root/'data/decisions'
            records.mkdir(parents=True)
            ident = '12345678-1234-1234-1234-123456789abc'
            original = json.dumps(dict(prompt='Hello', decision={}, outcome=None))
            (records/(ident+'.json')).write_text(original)
            for _ in range(2):
                save_feedback(root, ident, 'fast', [], False, 'unverified', 'Operator observation')
            self.assertEqual(len(list((root/'data/feedback').glob('*.json'))), 2)
            self.assertEqual((records/(ident+'.json')).read_text(), original)


if __name__ == '__main__':
    unittest.main()
