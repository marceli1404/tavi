"""Deterministic DOM-first computer-use routing regressions."""
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image
from tavi_observe import dispatch
from tavi_observe_stream import run


def snapshot(*, age_seconds=0, controls=None, snapshot_id='host-frame-A'):
    return dict(format='tavi-control-snapshot-v1', snapshot_id=snapshot_id,
        captured_at=(datetime.now(timezone.utc)-timedelta(seconds=age_seconds)).isoformat(),
        source='supported_browser_dom', viewport=[800, 600],
        controls=list(controls if controls is not None else [
            dict(id='settings', label='Settings', role='button', context='Toolbar',
                 visible=True, enabled=True, bounds=[20,20,100,40]),
            dict(id='save', label='Save', role='button', context='Form',
                 visible=False, enabled=True, bounds=[160,20,100,40]),
            dict(id='cancel-1', label='Cancel', role='button', context='First',
                 visible=True, enabled=True, bounds=[20,90,100,40]),
            dict(id='cancel-2', label='Cancel', role='button', context='Second',
                 visible=True, enabled=True, bounds=[160,90,100,40]),
        ]))


def q(target, ident=None, **more):
    return dict(id=ident or target.lower(), task='Inspect '+target,
                target=target, role='button', **more)


class DomFirstTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.image=Path(self.tmp.name)/'frame.png'
        Image.new('RGB',(800,600),(230,232,234)).save(self.image)
        self.ocr=Mock(return_value=dict(status='available',words=[
            dict(text='Missing',x=220,y=220,width=110,height=30)]))
        self.ocr_image=lambda data:dict(path=str(self.image),snapshot_id=data['snapshot_id'])

    def test_exact_host_targets_do_not_open_screenshot_or_start_ocr(self):
        state=snapshot()
        with patch('tavi_compact.propose_batch',side_effect=AssertionError('Unexpected image preparation')):
            result=dispatch(state,[q('Settings')],image=dict(path='/does/not/exist.png',
                                                              snapshot_id=state['snapshot_id']),ocr_fn=self.ocr)
        self.ocr.assert_not_called()
        self.assertEqual(result['counts']['image_preparations'],0)
        self.assertEqual(result['counts']['ocr_passes'],0)
        self.assertEqual(result['routes'][0]['route'],'host_control')
        self.assertEqual(result['routes'][0]['control']['reason'],'unique_exact_control')
        self.assertIsNone(result['routes'][0]['visual'])
        self.assertFalse(result['authorization_granted'])
        self.assertFalse(result['executed_actions'])
        self.assertFalse(result['action_sequence_authorized'])

    def test_missing_controls_escalate_once_and_preserve_original_dom_fact(self):
        state=snapshot()
        result=dispatch(state,[q('Settings'),q('Missing'),q('Missing',ident='missing2')],
                        image=self.ocr_image(state),ocr_fn=self.ocr)
        self.assertEqual(self.ocr.call_count,1)
        self.assertEqual(result['counts']['exact_host_controls'],1)
        self.assertEqual(result['counts']['visual_review'],2)
        self.assertEqual(result['counts']['ocr_passes'],1)
        self.assertEqual(result['counts']['image_preparations'],1)
        self.assertEqual([r['route'] for r in result['routes']],
                         ['host_control','visual_review','visual_review'])
        self.assertEqual(result['routes'][1]['control']['reason'],'no_exact_control')
        self.assertIn('proposal_id',result['routes'][1]['visual'])
        self.assertNotEqual(result['routes'][1]['visual']['proposal_id'],
                            result['routes'][2]['visual']['proposal_id'])
        self.assertFalse(result['routes'][1]['visual']['authorization_granted'])
        self.assertFalse(result['routes'][1]['visual']['automatic_probability_qualified'])
        self.assertTrue(result['requires_fresh_observation_after_action'])

    def test_disabled_and_ambiguous_controls_never_get_ocr_override(self):
        state=snapshot()
        result=dispatch(state,[q('Save'),q('Cancel')],image=self.ocr_image(state),ocr_fn=self.ocr)
        self.ocr.assert_not_called()
        self.assertEqual([r['route'] for r in result['routes']],['host_review','host_review'])
        self.assertEqual([r['reason'] for r in result['routes']],
                         ['control_unavailable','ambiguous_control'])
        self.assertEqual(result['counts']['ocr_passes'],0)

    def test_stale_and_future_hosts_prevent_visual_fallback(self):
        for age,reason in ((8,'stale_snapshot'),(-3,'future_snapshot')):
            with self.subTest(age=age):
                state=snapshot(age_seconds=age)
                result=dispatch(state,[q('Missing')],image=self.ocr_image(state),ocr_fn=self.ocr)
                self.assertEqual(result['routes'][0]['route'],'reobserve')
                self.assertEqual(result['routes'][0]['reason'],reason)
                self.assertEqual(result['counts']['image_preparations'],0)
        self.ocr.assert_not_called()

    def test_missing_image_requests_screenshot_without_reusing_an_old_one(self):
        result=dispatch(snapshot(),[q('Missing')],ocr_fn=self.ocr)
        self.assertEqual(result['routes'][0]['route'],'needs_screenshot')
        self.assertEqual(result['counts']['ocr_passes'],0)
        self.ocr.assert_not_called()

    def test_image_binding_must_match_snapshot_even_when_dom_matches(self):
        with self.assertRaisesRegex(ValueError,'matching observation snapshot_id'):
            dispatch(snapshot(),[q('Settings')],
                     image=dict(path=str(self.image),snapshot_id='different'),ocr_fn=self.ocr)
        self.ocr.assert_not_called()

    def test_invalid_unsupported_and_oversized_queries_rejected(self):
        invalid=[
            [],[q('Missing',ident=str(i)) for i in range(17)],
            [dict(q('Settings'),execute=True)],
            [dict(q('Settings'),role='unsupported')],
            [q('Settings'),q('Save',ident='settings')]
        ]
        for sample in invalid:
            with self.subTest(sample=str(sample)[:100]),self.assertRaises(ValueError):
                dispatch(snapshot(),sample,ocr_fn=self.ocr)
        self.ocr.assert_not_called()
        for detail in (True,'auto',None):
            with self.assertRaises(ValueError):
                dispatch(snapshot(),[q('Settings')],detail=detail)

    def test_full_ocr_evidence_is_opt_in(self):
        state=snapshot()
        result=dispatch(state,[q('Missing')],image=self.ocr_image(state),
                        detail='full',ocr_fn=self.ocr)
        self.assertIn('review_packet',result['routes'][0]['visual'])
        self.assertEqual(result['routes'][0]['visual']['hosted_calls'],0)
        self.assertFalse(result['routes'][0]['visual']['executed_actions'])


class StreamTests(unittest.TestCase):
    def test_stream_starts_ocr_only_on_missing_control_and_reuses_worker(self):
        class FakeSession:
            created=0
            def __init__(self):
                FakeSession.created+=1
                self.requests=0
                self.closed=False
            def __call__(self,path):
                self.requests+=1
                return dict(status='available',words=[])
            def close(self):
                self.closed=True
        FakeSession.created=0
        state=snapshot()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'screen.png'
            Image.new('RGB',(800,600),'white').save(path)
            second=snapshot(snapshot_id='host-frame-B')
            third=snapshot(snapshot_id='host-frame-C')
            lines=[
                dict(id='dom',snapshot=state,queries=[q('Settings')]),
                dict(id='ocr',snapshot=second,queries=[q('Missing')],
                     image=dict(path=str(path),snapshot_id=second['snapshot_id'])),
                dict(id='next',snapshot=third,queries=[q('Missing')],
                     image=dict(path=str(path),snapshot_id=third['snapshot_id'])),
                dict(id='replay',snapshot=second,queries=[q('Settings')]),
                dict(id='invalid',snapshot=state,queries=[q('Settings')],execute=True)
            ]
            output=io.StringIO()
            status=run(io.StringIO(''.join(json.dumps(line)+'\n' for line in lines)),
                       output,session_factory=FakeSession)
        events=[json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(status,0)
        self.assertEqual([e['status'] for e in events],
                         ['ready','routed','routed','routed','error','error'])
        self.assertFalse(events[1]['ocr_session_started'])
        self.assertEqual(events[1]['session_ocr_requests'],0)
        self.assertTrue(events[2]['ocr_session_started'])
        self.assertEqual(events[3]['session_ocr_requests'],2)
        self.assertIn('already processed',events[4]['error'])
        self.assertEqual(FakeSession.created,1)
        self.assertFalse(events[2]['executed_actions'])

    def test_duplicate_fields_and_json_constants_do_not_trigger_ocr(self):
        state=snapshot()
        data=['{"snapshot":{},"snapshot":{},"queries":[]}',
              '{"snapshot":{},"queries":[],"max_edge":NaN}',
              json.dumps(dict(snapshot=state,queries=[q('Settings')]))]
        output=io.StringIO()
        with patch('tavi_observe_stream.OcrSession',side_effect=AssertionError('No OCR')):
            self.assertEqual(run(io.StringIO('\n'.join(data)+'\n'),output),0)
        events=[json.loads(s) for s in output.getvalue().splitlines()]
        self.assertEqual([v['status'] for v in events[1:]],['error','error','routed'])


if __name__=='__main__':
    unittest.main()
