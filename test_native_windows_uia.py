"""Cross-platform fake-provider tests for the read-only Windows UIA adapter."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
import io
import json
import unittest
from unittest.mock import patch

from tavi_windows_uia import (
    capture_scoped_window,observe_window,planner_view,revalidate_window,
    NativeUIAUnavailable,
)
from tavi_native_stream import run


class Rect:
    def __init__(self,left,top,right,bottom):
        self.left=left;self.top=top;self.right=right;self.bottom=bottom


class FakeControl:
    def __init__(self,name='',kind='PaneControl',rect=(100,100,600,500),
                 *,enabled=True,offscreen=False,handle=0,children=None):
        self.Name=name;self.ControlTypeName=kind
        self.BoundingRectangle=Rect(*rect)
        self.IsEnabled=enabled;self.IsOffscreen=offscreen
        self.NativeWindowHandle=handle
        self.children=list(children or [])
    def GetChildren(self):
        return list(self.children)
    def Click(self):
        raise AssertionError('Tavi must never click')
    def Invoke(self):
        raise AssertionError('Tavi must never invoke')
    def SetFocus(self):
        raise AssertionError('Tavi must never focus')


class FakeProvider:
    def __init__(self,root):
        self.root=root;self.calls=0
    def get_root(self,hwnd):
        self.calls+=1
        return self.root


def fixture():
    favorite=FakeControl('Favorites','TabItemControl',(120,140,240,180))
    settings=FakeControl('Settings','ButtonControl',(130,210,260,250))
    secret=FakeControl('SECRET-TEXT-MUST-NOT-LEAK','EditControl',(130,270,350,295))
    toolbar=FakeControl('Toolbar','ToolBarControl',
                        children=[favorite,settings,secret])
    root=FakeControl('Explorer','WindowControl',
                     handle=1212,children=[toolbar])
    return FakeProvider(root),favorite,settings,secret


def q(label='Favorites',role='tab'):
    return [dict(id='goal-1',task='Find tab',target=label,role=role)]


class WindowsUIATests(unittest.TestCase):
    def test_scoped_exact_and_no_unrelated_information_in_planner(self):
        backend,_,_,_=fixture()
        observed=observe_window(1212,q(),provider=backend)
        view=planner_view(observed)
        self.assertEqual(observed.snapshot['source'],'supported_native')
        self.assertEqual(len(observed.snapshot['controls']),1)
        self.assertEqual(view['rows'][0][1],'host_control')
        self.assertEqual(view['rows'][0][3][1],'Favorites')
        self.assertEqual(view['rows'][0][3][3],'Toolbar')
        self.assertEqual(view['rows'][0][3][4],[20.,40.,120.,40.])
        self.assertNotIn('SECRET-TEXT-MUST-NOT-LEAK',json.dumps(view))
        self.assertNotIn('SECRET-TEXT-MUST-NOT-LEAK',json.dumps(observed.snapshot))
        self.assertFalse(view['authorization_granted'])
        self.assertTrue(view['planner_only'])
        self.assertEqual(backend.calls,1)

    def test_fresh_recheck_revalidates_but_never_authorizes_click(self):
        backend,target,_,_=fixture()
        observed=observe_window(1212,q(),provider=backend)
        good,why=revalidate_window(observed,provider=backend)
        self.assertTrue(good)
        self.assertIn('requires_computer_authorization',why)
        self.assertEqual(backend.calls,2)

    def test_renamed_disabled_removed_and_moved_controls_fail_closed(self):
        for change in ('rename','disable','move','delete','window_move'):
            with self.subTest(change=change):
                backend,target,_,_=fixture()
                observed=observe_window(1212,q(),provider=backend)
                if change=='rename':target.Name='Not Favorites'
                if change=='disable':target.IsEnabled=False
                if change=='move':target.BoundingRectangle=Rect(120,140,250,180)
                if change=='delete':backend.root.children[0].children.remove(target)
                if change=='window_move':
                    backend.root.BoundingRectangle=Rect(110,100,610,500)
                good,_=revalidate_window(observed,provider=backend)
                self.assertFalse(good)

    def test_ambiguous_duplicate_never_returns_candidate(self):
        backend,target,_,_=fixture()
        backend.root.children[0].children.append(
            FakeControl('Favorites','TabItemControl',(280,140,390,180)))
        obs=observe_window(1212,q(),provider=backend)
        self.assertEqual(planner_view(obs)['rows'][0][1],'host_review')
        self.assertIsNone(planner_view(obs)['rows'][0][3])
        self.assertEqual(revalidate_window(obs,provider=backend)[0],False)

    def test_no_match_returns_screenshot_request_not_action(self):
        backend,_,_,_=fixture()
        view=planner_view(observe_window(1212,q('Missing'),provider=backend))
        self.assertEqual(view['rows'][0][1],'needs_screenshot')
        self.assertEqual(view['rows'][0][3],None)
        self.assertFalse(view['action_sequence_authorized'])

    def test_handle_mismatch_and_excessive_depth_or_nodes_fail(self):
        backend,_,_,_=fixture()
        with self.assertRaises(NativeUIAUnavailable):
            capture_scoped_window(1213,q(),provider=backend)
        with self.assertRaises(NativeUIAUnavailable):
            capture_scoped_window(1212,q(),provider=backend,max_nodes=2)
        with self.assertRaises(NativeUIAUnavailable):
            capture_scoped_window(1212,q(),provider=backend,max_depth=1)
        with self.assertRaises(ValueError):
            capture_scoped_window(0,q(),provider=backend)
        with self.assertRaises(ValueError):
            capture_scoped_window(1212,[],provider=backend)

    def test_stale_original_recheck_does_not_reuse_it(self):
        backend,_,_,_=fixture()
        seen=observe_window(1212,q(),provider=backend)
        old=dict(seen.snapshot,captured_at=(
            datetime.now(timezone.utc)-timedelta(seconds=20)).isoformat())
        # Tampering with a host snapshot invalidates binding.
        self.assertFalse(revalidate_window(
            replace(seen,snapshot=old),provider=backend)[0])

    def test_stream_one_window_recheck_and_replay_block(self):
        backend,_,_,_=fixture()
        output=io.StringIO()
        class DynamicInput:
            index=0
            token=None
            def readline(self,max_chars):
                self.index+=1
                if self.index==1:
                    return json.dumps(dict(op='observe',id='first',queries=q()))+'\n'
                if self.index==2:
                    self.token=json.loads(output.getvalue().splitlines()[-1])['observation_id']
                    return json.dumps(dict(op='recheck',id='second',
                                           observation_id=self.token))+'\n'
                if self.index==3:
                    return json.dumps(dict(op='recheck',id='third',
                                           observation_id=self.token))+'\n'
                return ''
        result=run(allowed_hwnd=1212,input_stream=DynamicInput(),
                   output_stream=output,provider=backend)
        self.assertEqual(result,0)
        ready,observed,checked,replayed=map(json.loads,output.getvalue().splitlines())
        self.assertEqual(ready['status'],'ready')
        self.assertEqual(observed['status'],'observed')
        self.assertEqual(observed['result']['rows'][0][1],'host_control')
        self.assertFalse(observed['authorization_granted'])
        self.assertTrue(checked['matched'])
        self.assertFalse(checked['authorization_granted'])
        self.assertFalse(replayed['matched'])
        self.assertEqual(backend.calls,2)

    def test_stream_rejects_extra_execution_fields_without_reading_window(self):
        backend,_,_,_=fixture()
        bad=dict(op='observe',queries=q(),execute=True)
        output=io.StringIO()
        self.assertEqual(run(allowed_hwnd=1212,
            input_stream=io.StringIO(json.dumps(bad)+'\n'),
            output_stream=output,provider=backend),0)
        self.assertEqual(json.loads(output.getvalue().splitlines()[-1])['status'],'error')
        self.assertEqual(backend.calls,0)

    def test_stream_only_errors_never_leak_accessibility_data(self):
        backend,target,_,_=fixture()
        target.Name=None
        output=io.StringIO()
        run(allowed_hwnd=1212,input_stream=io.StringIO(json.dumps(
            dict(op='observe',queries=q()))+'\n'),output_stream=output,provider=backend)
        result=json.loads(output.getvalue().splitlines()[-1])
        self.assertEqual(result['status'],'error')
        self.assertNotIn('Favorites',json.dumps(result))


if __name__=='__main__':
    unittest.main()
