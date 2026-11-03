"""Planner-only observation wire: safety, parity, and token-size regressions."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

from PIL import Image
from tavi_metrics import UsageMetrics
from tavi_observe import dispatch
from tavi_observe_stream import run
from tavi_observe_wire import planner_packet, FORMAT, COLUMNS


def snapshot(*, id='test-frame', age=0, controls=None):
    return dict(
        format='tavi-control-snapshot-v1',source='supported_browser_dom',
        snapshot_id=id,
        captured_at=(datetime.now(timezone.utc)-timedelta(seconds=age)).isoformat(),
        viewport=[960,720],
        controls=controls if controls is not None else [
            dict(id=f'control-{i}',label=f'Action {i}',role='button',
                 context='Panel',visible=True,enabled=True,
                 bounds=[20,30+i*38,140,32])
            for i in range(12)])


def queries(n=12):
    return [dict(id=f'query-{i}',task=f'Inspect Action {i}',
                 target=f'Action {i}',role='button') for i in range(n)]


class PlannerWireTests(unittest.TestCase):
    def test_exact_candidate_projections_preserve_identity_and_policy(self):
        full=dispatch(snapshot(),queries())
        concise=planner_packet(full)
        self.assertEqual(concise['format'],FORMAT)
        self.assertEqual(concise['snapshot_sha256'],full['snapshot_sha256'])
        self.assertEqual(concise['columns'],list(COLUMNS))
        self.assertEqual(len(concise['rows']),len(full['routes']))
        for row,original in zip(concise['rows'],full['routes']):
            self.assertEqual(row[0],original['query_id'])
            self.assertEqual(row[1],'host_control')
            self.assertEqual(row[2],'unique_exact_control')
            self.assertEqual(row[3],[original['control']['candidate'][k]
                                     for k in ('id','label','role','context','bounds')])
            self.assertIsNone(row[4])
        self.assertTrue(concise['planner_only'])
        self.assertTrue(concise['requires_live_host_check'])
        self.assertTrue(concise['requires_fresh_observation_after_action'])
        for flag in ('authorization_granted','executed_actions','action_sequence_authorized'):
            self.assertFalse(concise[flag])
        self.assertNotIn('routes',concise)
        self.assertNotIn('task_sha256',json.dumps(concise))
        self.assertLess(len(json.dumps(concise)),len(json.dumps(full)))

    def test_blocked_routes_remain_blocked_and_have_no_candidate(self):
        controls=snapshot()['controls']
        controls[0]['enabled']=False
        controls.append(dict(controls[1],id='duplicate-control'))
        state=snapshot(controls=controls)
        full=dispatch(state,queries(3))
        concise=planner_packet(full)
        self.assertEqual([r[1] for r in concise['rows']],
                         ['host_review','host_review','host_control'])
        self.assertEqual([r[2] for r in concise['rows'][:2]],
                         ['control_unavailable','ambiguous_control'])
        self.assertIsNone(concise['rows'][0][3])
        self.assertIsNone(concise['rows'][1][3])
        self.assertEqual(planner_packet(dispatch(snapshot(age=9),queries(1)))['rows'][0][1],
                         'reobserve')

    def test_missing_controls_request_screenshot_but_not_action(self):
        state=snapshot()
        full=dispatch(state,[dict(task='Inspect absent',target='Absent')])
        view=planner_packet(full)
        self.assertEqual(view['rows'][0][1:3],['needs_screenshot','no_exact_control'])
        self.assertEqual(view['rows'][0][3:], [None,None])
        self.assertFalse(view['authorization_granted'])

    def test_visual_review_brief_and_full_keep_review_only(self):
        with TemporaryDirectory() as folder:
            path=Path(folder)/'image.png'
            Image.new('RGB',(960,720),'white').save(path)
            state=snapshot()
            query=[dict(task='Find Absent',target='Absent',role='button')]
            binding=dict(path=str(path),snapshot_id=state['snapshot_id'])
            ocr=Mock(return_value=dict(status='available',words=[
                dict(text='Absent',x=240,y=160,width=90,height=32)]))
            for detail in ('brief','full'):
                full=dispatch(state,query,image=binding,ocr_fn=ocr,detail=detail)
                projected=planner_packet(full)
                row=projected['rows'][0]
                self.assertEqual(row[1],'visual_review')
                self.assertIsNone(row[3])
                self.assertIsInstance(row[4]['proposal_id'],str)
                self.assertEqual(len(row[4]['image_sha256']),64)
                self.assertFalse(row[4]['automatic_probability_qualified'])
                self.assertFalse(projected['action_sequence_authorized'])
            self.assertEqual(ocr.call_count,2)

    def test_rejects_any_attempt_to_upgrade_action_policy(self):
        packet=dispatch(snapshot(),queries(2))
        mutations=[]
        for flag in ('authorization_granted','executed_actions','action_sequence_authorized'):
            item=deepcopy(packet);item[flag]=True;mutations.append(item)
        item=deepcopy(packet);item['routes'][0]['control']['authorization_granted']=True;mutations.append(item)
        item=deepcopy(packet);item['routes'][0]['route']='visual_review';mutations.append(item)
        item=deepcopy(packet);item['routes'][0]['control']['candidate']['bounds']=[1,2,0,4];mutations.append(item)
        item=deepcopy(packet);item['routes'][0]['control']['offline']=True;mutations.append(item)
        item=deepcopy(packet);item['snapshot_sha256']='not-a-digest';mutations.append(item)
        for mutated in mutations:
            with self.subTest(mutation=mutated['routes'][0].get('route')),self.assertRaises(ValueError):
                planner_packet(mutated)

    def test_compact_stream_is_opt_in_and_accounts_for_wire_bytes(self):
        messages=[]
        for ident,wire in [('full','full'),('planner','planner'),('invalid','action')]:
            state=snapshot(id=ident)
            messages.append(dict(id=ident,snapshot=state,queries=queries(8),wire=wire))
        out=io.StringIO()
        meter=UsageMetrics()
        code=run(io.StringIO(''.join(json.dumps(m)+'\n' for m in messages)),out,
                 metrics=meter,session_factory=lambda: None)
        events=[json.loads(s) for s in out.getvalue().splitlines()]
        self.assertEqual(code,0)
        self.assertEqual(events[1]['format'],'tavi-observe-route-v1')
        self.assertEqual(events[2]['format'],FORMAT)
        self.assertEqual(events[2]['status'],'routed')
        self.assertEqual(events[2]['request_id'],'planner')
        self.assertFalse(events[2]['authorization_granted'])
        self.assertEqual(events[3]['status'],'error')
        self.assertIn('wire must be',events[3]['error'])
        self.assertEqual(meter.summary()['counters']['observations'],2)
        self.assertGreater(events[1]['telemetry']['counters']['response_bytes_total'],
                           events[2]['telemetry']['counters']['response_bytes_total']-
                           events[1]['telemetry']['counters']['response_bytes_total'])
        self.assertLess(
            len(json.dumps(events[2],separators=(',',':'))),
            len(json.dumps(events[1],separators=(',',':'))))

    def test_default_stream_keeps_old_full_schema(self):
        state=snapshot()
        message=dict(snapshot=state,queries=queries(2))
        out=io.StringIO()
        self.assertEqual(run(io.StringIO(json.dumps(message)+'\n'),out),0)
        result=json.loads(out.getvalue().splitlines()[1])
        self.assertEqual(result['format'],'tavi-observe-route-v1')
        self.assertIn('control',result['routes'][0])
        self.assertNotIn('planner_only',result)


if __name__=='__main__':
    unittest.main()
