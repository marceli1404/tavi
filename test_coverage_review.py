import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from tavi_coverage_review import packet, validate_review, read_json


class CoverageReviewTests(unittest.TestCase):
    def request(self):
        return dict(task='Prepare and validate the report.', requirements=['Prepare data', 'Validate results'],
                    skills=[dict(id='prepare', description='Prepare data only.'), dict(id='check', description='Validate results.')])

    def answer(self, p):
        return dict(packet_id=p['packet_id'], coverage=[dict(requirement_id='r0', skill_ids=['prepare']),
                                                      dict(requirement_id='r1', skill_ids=['check'])])

    def test_modified_inventory_invalidates_old_review(self):
        p = packet(self.request())
        answer = self.answer(p)
        request = self.request()
        request['skills'][0]['description'] = 'Show a picture of data.'
        with self.assertRaisesRegex(ValueError, 'snapshot'):
            validate_review(packet(request), answer)

    def test_partial_answer_and_invented_skills_are_rejected(self):
        p = packet(self.request())
        answer = self.answer(p)
        answer['coverage'].pop()
        with self.assertRaisesRegex(ValueError, 'every requirement'):
            validate_review(p, answer)
        answer = self.answer(p)
        answer['coverage'][0]['skill_ids'] = ['invented']
        with self.assertRaisesRegex(ValueError, 'unknown'):
            validate_review(p, answer)

    def test_missing_operation_recommends_discovery_without_authority(self):
        p = packet(self.request())
        answer = self.answer(p)
        answer['coverage'][1]['skill_ids'] = []
        result = validate_review(p, answer)
        self.assertTrue(result['discovery_suggested'])
        self.assertEqual(result['missing_requirement_ids'], ['r1'])
        self.assertFalse(result['installation_authorized'])
        self.assertFalse(result['execution_capability_verified'])
        self.assertIsNone(result['probability'])

    def test_packet_is_bound_to_full_task_context(self):
        request = self.request()
        first = packet(request)
        request['task'] = 'Prepare and validate a different confidential report.'
        self.assertNotEqual(packet(request)['packet_id'], first['packet_id'])

    def test_duplicate_or_unbounded_inputs_are_rejected(self):
        for key, value in [('requirements', ['same', 'same']), ('skills', [dict(id='a', description='a')] * 2),
                           ('task', 'x' * 16001)]:
            request = self.request()
            request[key] = value
            with self.assertRaises(ValueError): packet(request)

    def test_offline_cli_needs_no_config_or_models(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            request = root / 'request.json'
            request.write_text(json.dumps(self.request()), encoding='utf-8')
            run = subprocess.run([sys.executable, str(Path(__file__).with_name('tavi.py')),
                '--config', str(root / 'absent.json'), 'coverage-review', str(request)],
                capture_output=True, text=True, encoding='utf-8', timeout=10)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout)['status'], 'needs_semantic_review')

    def test_oversized_json_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'input.json'
            path.write_bytes(b' ' * 262145)
            with self.assertRaisesRegex(ValueError, '256KiB'): read_json(path)

    def test_cli_can_read_request_without_saving_task_to_disk(self):
        run = subprocess.run([sys.executable, str(Path(__file__).with_name('tavi.py')), 'coverage-review', '-'],
            input=json.dumps(self.request()), capture_output=True, text=True, encoding='utf-8', timeout=10)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)['snapshot']['task'], self.request()['task'])


if __name__ == '__main__':
    unittest.main()
