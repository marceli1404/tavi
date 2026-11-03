"""Native Computer bridge regressions; Linux tests inject trusted fake UIA data."""
from copy import deepcopy
import io
import json
import sys
import unittest

from tavi_computer_native import (
    NativeComputerAdapter, WindowsUiaWorker, _binding, _candidate,
    _decode, _query, serve,
)


class FakeWindowsProvider:
    def __init__(self, *, controls=None):
        self.calls=0
        self.binding={'hwnd':260123,'process_id':5924,'rect':[120,80,800,600]}
        self.controls = (
            controls if controls is not None else [
                dict(id='uia-123-4',label='Favorites',role='tab',
                     context='Navigation',visible=True,enabled=True,
                     bounds=[40.0,30.0,140.0,44.0]),
                dict(id='uia-123-5',label='Save',role='button',
                     context='Toolbar',visible=True,enabled=False,
                     bounds=[210.0,30.0,100.0,44.0]),
            ])
    def capture(self):
        self.calls+=1
        return dict(status='captured',window_binding=deepcopy(self.binding),
                    viewport=self.binding['rect'][2:],
                    controls=deepcopy(self.controls),visited_nodes=len(self.controls)+1)


def request(**kwargs):
    return dict(op='suggest',target='Favorites',role='tab',**kwargs)


class WindowsNativeTests(unittest.TestCase):
    def test_scoped_candidate_preserves_denial_and_provenance(self):
        backend=FakeWindowsProvider()
        result=NativeComputerAdapter(backend).handle(request(id='step-1'))
        self.assertEqual(backend.calls,1)
        self.assertEqual(result['format'],'tavi-observe-planner-v1')
        self.assertEqual(result['rows'][0][1],'host_control')
        self.assertEqual(result['rows'][0][2],'unique_exact_control')
        self.assertEqual(result['rows'][0][3][:3],
                         ['uia-123-4','Favorites','tab'])
        self.assertEqual(result['window_binding'],backend.binding)
        self.assertTrue(result['planner_only'])
        self.assertTrue(result['requires_live_host_check'])
        self.assertTrue(result['requires_host_recheck_before_action'])
        self.assertFalse(result['authorization_granted'])
        self.assertFalse(result['executed_actions'])
        self.assertFalse(result['action_sequence_authorized'])
        self.assertEqual(result['hosted_model_calls'],0)
        self.assertNotIn('controls',result)

    def test_recheck_requires_new_capture_and_stable_binding(self):
        backend=FakeWindowsProvider()
        adapter=NativeComputerAdapter(backend)
        first=adapter.handle(request())
        expected=dict(window_binding=first['window_binding'],
                      candidate=first['rows'][0][3])
        check=dict(op='recheck',target='Favorites',role='tab',expected=expected)
        latest=adapter.handle(check)
        self.assertEqual(backend.calls,2)
        self.assertTrue(latest['exact_candidate_unchanged'])
        self.assertFalse(latest['authorization_granted'])
        self.assertFalse(latest['executed_actions'])
        self.assertTrue(latest['requires_live_host_check'])
        backend.binding['hwnd']+=1
        changed=adapter.handle(check)
        self.assertFalse(changed['exact_candidate_unchanged'])
        backend.binding['hwnd']-=1
        backend.controls[0]['label']='Favorites updated'
        changed=adapter.handle(check)
        self.assertFalse(changed['exact_candidate_unchanged'])
        self.assertEqual(changed['route'],'needs_screenshot')

    def test_duplicate_and_disabled_controls_require_review(self):
        backend=FakeWindowsProvider()
        adapter=NativeComputerAdapter(backend)
        missing=adapter.handle(dict(op='suggest',target='Unknown',role='button'))
        self.assertEqual(missing['rows'][0][1],'needs_screenshot')
        self.assertEqual(missing['fallback'],'computer_screenshot')
        disabled=adapter.handle(dict(op='suggest',target='Save',role='button'))
        self.assertEqual(disabled['rows'][0][1],'host_review')
        self.assertIsNone(disabled['rows'][0][3])
        backend.controls.append(dict(backend.controls[0],id='uia-123-6'))
        ambiguous=adapter.handle(request())
        self.assertEqual(ambiguous['rows'][0][1],'host_review')
        self.assertEqual(ambiguous['rows'][0][2],'ambiguous_control')
        self.assertIsNone(ambiguous['rows'][0][3])

    def test_full_inventory_validation_including_unrelated_control(self):
        backend=FakeWindowsProvider()
        backend.controls.append(dict(backend.controls[1],id='uia-123-7',enabled='yes'))
        with self.assertRaises(ValueError):
            NativeComputerAdapter(backend).handle(request())

    def test_bad_provenance_and_bounds_fail_closed(self):
        examples=[
            dict(hwnd=0,process_id=100,rect=[0,0,800,600]),
            dict(hwnd=10,process_id=0,rect=[0,0,800,600]),
            dict(hwnd=10,process_id=100,rect=[0,0,-1,600]),
            dict(hwnd=10,process_id=100,rect=[0,0,float('nan'),600]),
            dict(hwnd=10,process_id=100,rect=[0,0,20000,600]),
        ]
        for value in examples:
            with self.subTest(binding=value),self.assertRaises(ValueError):
                _binding(value)
        backend=FakeWindowsProvider()
        backend.binding['rect'][2]=801
        backend.capture=lambda:dict(status='captured',
             window_binding=backend.binding,viewport=[800,600],
             controls=backend.controls,visited_nodes=3)
        with self.assertRaises(ValueError):
            NativeComputerAdapter(backend).handle(request())

    def test_request_rejects_actions_and_unclear_rechecks(self):
        invalid=[
            dict(request(),click=True),
            dict(request(),action='click'),
            dict(request(),execute=True),
            dict(request(),target=''),
            dict(request(),role='window'),
            dict(request(),context=' '),
            dict(op='recheck',target='Favorites',role='tab'),
            dict(op='recheck',target='Favorites',role='tab',
                 expected={'candidate':['uia-1','Favorites','tab','', [0,0,1,1]]}),
            dict(request(),id='a'*81),
            dict(op='capture',target='Favorites'),
        ]
        for value in invalid:
            with self.subTest(request=value),self.assertRaises(ValueError):
                _query(value)

    def test_stream_stays_warm_and_keeps_errors_generic(self):
        backend=FakeWindowsProvider()
        requests=[
            request(id='good-1'),
            dict(request(),click=True),
            request(id='good-2'),
        ]
        output=io.StringIO()
        code=serve(io.StringIO(''.join(json.dumps(r)+'\n' for r in requests)),
                   output,provider=backend)
        lines=[json.loads(row) for row in output.getvalue().splitlines()]
        self.assertEqual(code,0)
        self.assertEqual(lines[0]['status'],'ready')
        self.assertEqual([e['status'] for e in lines[1:]],
                         ['observed','error','observed'])
        self.assertEqual(backend.calls,2)
        self.assertEqual(lines[2]['reason'],'invalid_request')
        self.assertFalse(lines[2]['authorization_granted'])
        self.assertNotIn('process_id',lines[2])

    def test_json_does_not_allow_duplicate_or_nonfinite_fields(self):
        for payload in ('{"op":"suggest","op":"suggest"}',
                        '{"target":NaN}', '[]', 'not-json'):
            with self.assertRaises(ValueError):
                _decode(payload)

    @unittest.skipIf(sys.platform=='win32', 'Worker platform rejection only on non-Windows')
    def test_non_windows_worker_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, 'Windows'):
            WindowsUiaWorker()


if __name__=='__main__':
    unittest.main()
