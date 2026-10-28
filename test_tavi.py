import tempfile
import json
import unittest
from pathlib import Path
from unittest.mock import patch
import tavi


MODELS = [dict(id='small', description='Easy tasks', default_effort='low'),
          dict(id='large', description='Complex work', default_effort='high')]
SKILLS = [dict(id='ui', name='responsive-design', description='Fix mobile layouts and navigation', path='C:/skills/ui/SKILL.md')]


def backend(state, questions):
    return {k: (dict(choice='m0', probabilities={'m0': 0.8, 'm1': 0.1, 'unsure': 0.1})
                if q['type'] == 'choice' else dict(noul=0.85)) for k, q in questions.items()}


class RouterTests(unittest.TestCase):
    def test_mobile_retrieves_responsive_skill(self):
        skills = SKILLS + [dict(id='responsive', name='responsive-design', description='Adapt layouts across screen sizes', path='x')]
        result = tavi.shortlist('Mobile menu overflows on narrow screens', skills)
        self.assertIn('responsive', [s['id'] for s in result])

    def test_routes_and_selects_skill(self):
        result = tavi.route('Fix mobile navigation', SKILLS, MODELS, backend)
        self.assertEqual(result['model']['id'], 'small')
        self.assertEqual(result['skills'][0]['id'], 'ui')
        self.assertEqual(result['status'], 'recommended')

    def test_explicit_overrides(self):
        result = tavi.route('Hello', SKILLS, MODELS, backend, 'large', ['ui'])
        self.assertEqual(result['model']['id'], 'large')
        self.assertEqual(result['skills'][0]['selection'], 'explicit')

    def test_unknown_override_rejected(self):
        with self.assertRaises(ValueError):
            tavi.route('Hello', SKILLS, MODELS, backend, 'invented')
        with self.assertRaises(ValueError):
            tavi.route('Hello', SKILLS, MODELS, backend, requested_skills=['invented'])

    def test_abstains_on_close_choice(self):
        def close(state, questions):
            return {'model': dict(choice='m0', probabilities={'m0': .46, 'm1': .45, 'unsure': .09})}
        result = tavi.route('Hello', [], MODELS, close)
        self.assertIsNone(result['model'])
        self.assertEqual(result['status'], 'needs_review')

    def test_backend_failure_is_not_success(self):
        def broken(*args):
            raise RuntimeError('unavailable')
        self.assertEqual(tavi.route('Hi', [], MODELS, broken)['status'], 'needs_review')

    def test_invalid_probability_rejected(self):
        def invalid(*args):
            return {'model': dict(choice='m0', probabilities={'m0': float('nan')})}
        result = tavi.route('Hi', [], MODELS, invalid)
        self.assertEqual(result['status'], 'needs_review')

    def test_long_task_abstains_without_inference(self):
        def forbidden(*args):
            self.fail('Must not silently truncate and infer')
        self.assertEqual(tavi.route('a' * 1201, [], MODELS, forbidden)['status'], 'needs_review')

    def test_no_skill_is_valid(self):
        result = tavi.route('Hello', SKILLS, MODELS, backend)
        self.assertEqual(result['skills'], [])
        self.assertFalse(result['discovery']['installation_authorized'])

    def test_skill_metadata_and_deduplication(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'SKILL.md'
            path.write_text('---\nname: sample\ndescription: >\n  A useful skill\n  for tests\n---\nDo not execute me', encoding='utf-8')
            skills = tavi.scan_skills([folder, folder])
            self.assertEqual(len(skills), 1)
            self.assertEqual(skills[0]['description'], 'A useful skill for tests')

    def test_launch_plan_preserves_shell_metacharacters_as_stdin(self):
        prompt = 'Fix `x`; $(bad) & echo test'
        decision = tavi.route(prompt, [], MODELS, backend)
        with patch('tavi.codex_command', return_value=['node', 'codex.js']):
            plan = tavi.launch_plan(decision, prompt, '.')
        self.assertEqual(plan['stdin'], prompt)
        self.assertNotIn(prompt, plan['argv'])
        self.assertFalse(plan['executed'])

    def test_explicit_execution_uses_argument_array_and_stdin(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / 'config.json'
            config.write_text(json.dumps({'skill_roots': [], 'laya_runner': 'unused'}))
            args = ['tavi.py', '--config', str(config), 'route', 'hello & test', '--execute', '--backend', 'laya']
            decision = dict(decision_id='12345678-1234-1234-1234-123456789abc', status='recommended', model={'id': 'small'}, skills=[])
            with patch('sys.argv', args), patch('tavi.model_catalog', return_value=MODELS), \
                 patch('tavi.route', return_value=decision), patch('tavi.codex_command', return_value=['codex']), \
                 patch('builtins.print'), patch('tavi.subprocess.run') as run:
                run.return_value.returncode = 0
                self.assertEqual(tavi.main(), 0)
                self.assertEqual(run.call_args.kwargs['input'], 'hello & test')
                self.assertNotIn('shell', run.call_args.kwargs)
                self.assertIn('read-only', run.call_args.args[0])

    def test_uncertain_route_cannot_execute(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / 'config.json'
            config.write_text(json.dumps({'skill_roots': [], 'laya_runner': 'unused'}))
            with patch('sys.argv', ['tavi.py', '--config', str(config), 'route', 'hello', '--execute', '--backend', 'laya']), \
                 patch('tavi.model_catalog', return_value=MODELS), \
                 patch('tavi.route', return_value=dict(status='needs_review', model=None, skills=[])), \
                 patch('builtins.print'), patch('tavi.subprocess.run') as run:
                self.assertEqual(tavi.main(), 1)
                run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
