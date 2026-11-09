"""MCP integration core contract; no installed SDK/Codex/UI access required."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock
import tavi_codex_tools as tools


class CodexToolsTests(unittest.TestCase):
    def test_status_does_not_request_capture_or_actions(self):
        response = tools.status()
        self.assertFalse(response['can_capture_screen'])
        self.assertFalse(response['can_draw_overlay'])
        self.assertFalse(response['can_click_or_type'])
        self.assertFalse(response['can_switch_current_codex_model'])

    def test_rejects_route_invalid_input_without_launching_subprocess(self):
        with patch.object(tools.subprocess, 'run') as run:
            for task, pref in (('', 'auto'), ('x' * 16001, 'auto'), ('x', 'unlimited')):
                with self.assertRaises(ValueError):
                    tools.route_task(task, pref)
            run.assert_not_called()

    def test_route_is_advisory_only_and_does_not_execute_or_record(self):
        good = {'status': 'recommended', 'model': {'id': 'checked-model'},
                'skills': [{'name': 'design', 'path': '/skill', 'selection': 'learned'}],
                'warnings': [], 'decision_id': 'test'}
        with patch.object(Path, 'is_file', return_value=True), \
             patch.object(tools.subprocess, 'run', return_value=MagicMock(
                 returncode=0, stdout=json.dumps(good))) as run:
            outcome = tools.route_task('Fix nav', 'speed')
            argv = run.call_args.args[0]
            self.assertEqual(argv[2:4], ['route', 'Fix nav'])
            self.assertIn('--preference', argv)
            self.assertNotIn('--execute', argv)
            self.assertNotIn('--record', argv)
            self.assertNotIn('--plan', argv)
            self.assertEqual(outcome['model']['id'], 'checked-model')
            self.assertFalse(outcome['hosted_task_started'])
            self.assertFalse(outcome['model_switched'])
            self.assertTrue(outcome['advisory_only'])

    def test_route_without_config_fails_closed(self):
        with patch.object(Path, 'is_file', return_value=False), \
             patch.object(tools.subprocess, 'run') as run:
            self.assertEqual(tools.route_task('Fix nav')['status'], 'configuration_required')
            run.assert_not_called()

    def test_route_failure_does_not_leak_stderr(self):
        with patch.object(Path, 'is_file', return_value=True), \
             patch.object(tools.subprocess, 'run', return_value=MagicMock(
                 returncode=1, stderr='SECRET-IN-ERROR')):
            result = tools.route_task('Fix nav')
            self.assertEqual(result['status'], 'unavailable')
            self.assertNotIn('SECRET-IN-ERROR', str(result))

    def test_oversize_and_nonfinite_snapshot_fails_before_dispatch(self):
        with self.assertRaises(ValueError):
            tools.match_controls({'too_large': 'a'*300000}, [{'target': 'Settings'}])
        with self.assertRaises(ValueError):
            tools.match_controls({'a': float('nan')}, [{'target': 'Settings'}])
        with self.assertRaises(ValueError):
            tools.match_controls({}, [])

    def test_control_tool_reuses_existing_read_only_dispatch(self):
        import sys
        fake_observe = MagicMock()
        fake_observe.dispatch.return_value = {'sample': 'full'}
        fake_wire = MagicMock()
        fake_wire.planner_packet.return_value = {'planner_only': True,
                                                  'authorization_granted': False}
        with patch.dict(sys.modules, {'tavi_observe': fake_observe,
                                      'tavi_observe_wire': fake_wire}):
            value = tools.match_controls({'format':'tavi-control-snapshot-v1'},
                                         [{'task':'Locate', 'target':'Settings'}])
        self.assertTrue(value['planner_only'])
        self.assertFalse(value['authorization_granted'])
        self.assertEqual(fake_observe.dispatch.call_args.kwargs['image'], None)
        self.assertEqual(fake_observe.dispatch.call_args.kwargs['detail'], 'brief')
        fake_wire.planner_packet.assert_called_once()


if __name__ == '__main__':
    unittest.main()
