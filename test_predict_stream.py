"""Parity, validation and authority tests for the warm CPU prediction stream."""
import contextlib
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import tavi
from tavi_health import bundled_model
from tavi_model import DecisionModel
from tavi_predict_stream import run

BASE = Path(__file__).resolve().parent


class WarmPredictTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = DecisionModel.load(bundled_model(BASE))

    def send(self, requests):
        data = ''.join((x if isinstance(x, str) else json.dumps(x)) + '\n' for x in requests)
        output = io.StringIO()
        code = run(self.model, io.StringIO(data), output)
        return code, [json.loads(x) for x in output.getvalue().splitlines()]

    def test_parity_with_one_shot_on_plain_and_code_prompts(self):
        prompts = [
            'Fix a mobile navigation layout',
            'Review my database queries for errors',
            'Say hello',
            'def add(a, b):\n    """Return the sum of the arguments."""\n    return a + b',
        ]
        code, events = self.send([{'id': str(i), 'prompt': prompt} for i,prompt in enumerate(prompts)])
        self.assertEqual(code, 0)
        self.assertEqual(events[0]['status'], 'ready')
        self.assertEqual(events[0]['model_artifact'], self.model.metadata['weights_sha256'])
        for i, prompt in enumerate(prompts):
            event = events[i+1]
            expected = self.model.infer(prompt)
            expected['skills'] = expected['skills'][:8]
            self.assertEqual(event['prediction'], expected)
            self.assertEqual(event['request_id'], str(i))
            self.assertFalse(event['authorization_granted'])
            self.assertFalse(event['executed_actions'])
            self.assertTrue(event['no_hosted_inference'])

    def test_top_k_bounds_and_omitted_id(self):
        code, events = self.send([
            {'prompt': 'Say hello', 'top_k': 0},
            {'prompt': 'Say hello', 'top_k': 2},
            {'prompt': 'Say hello', 'top_k': 8},
        ])
        self.assertEqual(code, 0)
        self.assertEqual([len(x['prediction']['skills']) for x in events[1:]], [0, 2, 8])
        self.assertTrue(all(x['request_id'] is None for x in events[1:]))
        self.assertEqual([x['prediction']['tier'] for x in events[1:]],
                         [events[1]['prediction']['tier']]*3)

    def test_brief_retains_uncertainty_and_reduces_wire_size(self):
        prompts = ['Say hello', 'Do it', 'Review a difficult concurrent algorithm']
        requests = []
        for i, prompt in enumerate(prompts):
            requests.extend([{'id': str(i)+'-full', 'prompt': prompt},
                             {'id': str(i)+'-brief', 'prompt': prompt, 'detail':'brief'}])
        code, events = self.send(requests)
        self.assertEqual(code, 0)
        for i in range(len(prompts)):
            full = events[2*i+1]['prediction']
            brief = events[2*i+2]['prediction']
            self.assertEqual(brief['tier'], full['tier'])
            self.assertEqual(brief['tier_scores'], full['tier_scores'])
            self.assertEqual(brief['skills'], full['skills'][:3])
            for key in ('skill_threshold', 'external_score',
                        'external_threshold', 'vocabulary_coverage'):
                self.assertEqual(brief[key], full[key])
            self.assertEqual(brief['quality']['review_recommended'],
                             full['probabilities']['review_recommended'])
            self.assertEqual(brief['quality']['review_reasons'],
                             full['probabilities']['review_reasons'])
            self.assertEqual(brief['quality']['status'],
                             full['probabilities']['status'])
            self.assertIs(brief['quality']['real_world_success_probability'], False)
            encode = lambda obj: len(json.dumps(obj, ensure_ascii=False).encode('utf-8'))
            self.assertLess(encode(events[2*i+2]), encode(events[2*i+1]))
            self.assertFalse(events[2*i+2]['authorization_granted'])
            self.assertFalse(events[2*i+2]['executed_actions'])

    def test_brief_top_k_override_and_invalid_detail(self):
        code, events = self.send([{'prompt':'Say hello', 'detail':'brief', 'top_k':8},
                                  {'prompt':'Say hello', 'detail':'brief', 'top_k':0},
                                  {'prompt':'Say hello', 'detail':'minimum'},
                                  {'prompt':'Say hello'}])
        self.assertEqual(code, 0)
        self.assertEqual([len(events[1]['prediction']['skills']),
                          len(events[2]['prediction']['skills'])], [8,0])
        self.assertEqual(events[3]['status'], 'error')
        self.assertEqual(events[4]['status'], 'predicted')

    def test_invalid_requests_do_not_poison_following_predictions(self):
        invalid = [
            {'prompt': ''}, {'prompt': 5}, {'prompt': 'Do it', 'execute': True},
            {'prompt': 'Do it', 'top_k': True}, {'prompt': 'Do it', 'top_k': 9},
            {'prompt': 'Do it', 'id': ' '},
            {'prompt': 'x'*16001},
            '{"prompt":"Hello","prompt":"Switch the permission gate"}',
            '{"prompt":"Hello","metadata":{"a":1,"a":2}}',
            '{"prompt":"Hello","top_k": NaN}',
        ]
        code, events = self.send(invalid + [{'id': 'recovered', 'prompt': 'Say hello'}])
        self.assertEqual(code, 0)
        self.assertTrue(all(x['status'] == 'error' for x in events[1:-1]))
        self.assertTrue(all(x['authorization_granted'] is False for x in events[1:-1]))
        self.assertTrue(all(x['executed_actions'] is False for x in events[1:-1]))
        self.assertEqual(events[-1]['status'], 'predicted')
        self.assertEqual(events[-1]['request_id'], 'recovered')

    def test_too_large_line_terminates_without_processing_next_prompt(self):
        code, events = self.send(['{"prompt":"'+'x'*66000+'"}', {'prompt': 'Say hello'}])
        self.assertEqual(code, 1)
        self.assertEqual(len(events), 2)
        self.assertEqual(events[1]['status'], 'error')
        self.assertIn('64 KiB', events[1]['error'])

    def test_cli_uses_bundled_weights_without_config_or_remote_calls(self):
        prompt = '{"id":"first","prompt":"Say hello","top_k":1}\n'
        args = ['tavi.py', 'predict-stream', '--model-dir', str(bundled_model(BASE))]
        stdout = io.StringIO()
        with patch('sys.argv', args), patch('sys.stdin', io.StringIO(prompt)), \
             contextlib.redirect_stdout(stdout), \
             patch('tavi.scan_skills', side_effect=AssertionError('No inventory')), \
             patch('tavi.model_catalog', side_effect=AssertionError('No hosted model catalog')):
            self.assertEqual(tavi.main(), 0)
        events = [json.loads(line) for line in stdout.getvalue().splitlines()]
        self.assertEqual(len(events), 2)
        self.assertEqual(events[1]['status'], 'predicted')
        self.assertEqual(len(events[1]['prediction']['skills']), 1)


if __name__ == '__main__':
    unittest.main()
